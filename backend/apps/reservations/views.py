"""预约申请、审批与冲突控制、使用进度、图文沟通、完工评价视图。"""
import datetime

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsApplicant, IsLabAdminOrSystemAdmin
from apps.auditlog.services import build_change_detail, log_operation
from apps.labs.models import Device

from .models import ChatMessage, ChatThread, Evaluation, Reservation, ReservationStatusLog
from .serializers import (
    ApproveSerializer,
    CancelSerializer,
    ChatMessageSerializer,
    ChatThreadSerializer,
    CompleteSerializer,
    EvaluationCreateSerializer,
    EvaluationReplySerializer,
    EvaluationSerializer,
    RejectSerializer,
    ReservationCreateSerializer,
    ReservationDetailSerializer,
    ReservationListSerializer,
    ReservationStatusLogSerializer,
    ReservationUpdateSerializer,
    SignInSerializer,
    SignOutSerializer,
    TransferSerializer,
    WithdrawSerializer,
)
from .services import (
    ReservationError,
    change_status,
    close_chat_thread,
    create_reservation,
    ensure_chat_thread,
    notify_approve_result,
    notify_chat_reply,
    notify_completed,
    notify_pending_approval,
    notify_sign_out_to_admin,
    notify_transfer,
    parse_datetime,
    validate_full_reservation,
)


# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------
def scope_queryset(queryset, user):
    """按角色限制数据访问范围。"""
    if user.is_sys_admin:
        return queryset
    if user.is_lab_admin:
        return queryset.filter(laboratory_id__in=user.managed_lab_ids)
    return queryset.filter(applicant=user)


def check_lab_manage_permission(user, reservation):
    """判断用户是否有权管理（审批/完工）某个实验室的预约。"""
    if user.is_sys_admin:
        return True
    if user.is_lab_admin and reservation.laboratory_id in user.managed_lab_ids:
        return True
    if reservation.approver_id == user.id:
        return True
    return False


def apply_filters(queryset, params):
    """多条件检索。"""
    keyword = params.get("keyword")
    if keyword:
        queryset = queryset.filter(
            Q(no__icontains=keyword)
            | Q(applicant_name__icontains=keyword)
            | Q(device__name__icontains=keyword)
            | Q(device__code__icontains=keyword)
            | Q(purpose__icontains=keyword)
        )
    if params.get("status"):
        queryset = queryset.filter(status__in=params["status"].split(","))
    if params.get("laboratory"):
        queryset = queryset.filter(laboratory_id=params["laboratory"])
    if params.get("device"):
        queryset = queryset.filter(device_id=params["device"])
    if params.get("category"):
        queryset = queryset.filter(device__category_id=params["category"])
    if params.get("applicant"):
        queryset = queryset.filter(applicant_id=params["applicant"])
    if params.get("urgency"):
        queryset = queryset.filter(urgency=params["urgency"])
    if params.get("approver"):
        queryset = queryset.filter(approver_id=params["approver"])
    if params.get("is_evaluated") not in (None, ""):
        queryset = queryset.filter(is_evaluated=str(params["is_evaluated"]).lower() in ("1", "true"))
    if params.get("lab_ids"):
        queryset = queryset.filter(laboratory_id__in=params["lab_ids"].split(","))

    start_date = params.get("start_date")
    end_date = params.get("end_date")
    if start_date:
        queryset = queryset.filter(end_time__date__gte=_to_date(start_date))
    if end_date:
        queryset = queryset.filter(start_time__date__lte=_to_date(end_date))

    # 是否只看当前生效中的预约
    if params.get("only_active") == "1":
        queryset = queryset.filter(status__in=Reservation.ACTIVE_STATUSES)
    if params.get("only_overdue") == "1":
        queryset = queryset.filter(
            status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                        Reservation.Status.IN_USE],
            end_time__lt=timezone.now(),
        )
    if params.get("only_todo") == "1":
        user_id = params.get("_user_id")
        queryset = queryset.filter(
            Q(status=Reservation.Status.PENDING)
            | Q(status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                            Reservation.Status.IN_USE], end_time__lt=timezone.now())
            | Q(status=Reservation.Status.COMPLETED, is_evaluated=False, applicant_id=user_id)
            | Q(status__in=[Reservation.Status.WAITING_USE, Reservation.Status.IN_USE],
                applicant_id=user_id)
        )
    return queryset


def _to_date(value):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


class ReservationViewSet(viewsets.ModelViewSet):
    """预约单管理。"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    ordering_fields = ["id", "created_at", "start_time", "end_time", "status"]
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        queryset = (
            Reservation.objects.select_related(
                "applicant", "laboratory", "device", "device__category", "approver",
                "completion_operator",
            )
            .prefetch_related("status_logs", "laboratory__managers")
            .all()
        )
        queryset = scope_queryset(queryset, self.request.user)
        # 管理员可通过 scope=mine 只看自己提交的
        if self.request.query_params.get("scope") == "mine":
            queryset = queryset.filter(applicant=self.request.user)
        params = self.request.query_params.copy()
        params["_user_id"] = self.request.user.id
        return apply_filters(queryset, params)

    def get_serializer_class(self):
        if self.action == "list":
            return ReservationListSerializer
        if self.action == "create":
            return ReservationCreateSerializer
        if self.action in ("update", "partial_update"):
            return ReservationUpdateSerializer
        return ReservationDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ReservationDetailSerializer(instance, context={"request": request})
        return Response({"code": 0, "message": "success", "data": serializer.data})

    # ---------------------- 新增 / 修改 / 删除 ----------------------
    def create(self, request, *args, **kwargs):
        user = request.user
        if not user.is_applicant:
            raise PermissionDenied("仅学生和教师可以提交预约申请")
        if not user.phone:
            user.phone = user.phone or ""
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        submit = data.get("submit", True)
        try:
            reservation = create_reservation(user, data, submit=submit)
        except ReservationError as exc:
            return Response({"code": 400, "message": exc.message, "data": None},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "code": 0,
                "message": "预约已提交，等待管理员审批" if submit else "预约已暂存，可稍后提交",
                "data": ReservationDetailSerializer(reservation, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        if instance.applicant_id != user.id and not user.is_sys_admin:
            raise PermissionDenied("只能修改自己提交的预约")
        if instance.status not in (Reservation.Status.DRAFT, Reservation.Status.REJECTED):
            raise ValidationError({"detail": "只有暂存或被驳回的预约可以修改"})

        serializer = ReservationUpdateSerializer(
            data=request.data, context={"reservation": instance}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            validate_full_reservation(
                user, data["laboratory"], data["device"], data["start_time"], data["end_time"],
                exclude_reservation_id=instance.id, check_advance=False,
            )
        except ReservationError as exc:
            return Response({"code": 400, "message": exc.message, "data": None},
                            status=status.HTTP_400_BAD_REQUEST)

        old = Reservation.objects.select_related("device", "laboratory").get(pk=instance.pk)
        for field in ("laboratory", "device", "start_time", "end_time", "purpose", "urgency"):
            if field in data:
                setattr(instance, field, data[field])
        instance.save()
        detail = build_change_detail(old, data)
        if detail:
            log_operation(
                operator=user, action="update", target_type="reservation",
                target_id=instance.id, target_repr=instance.no, lab=instance.laboratory,
                detail=detail, remark="修改预约申请", request=request,
            )
        return Response({"code": 0, "message": "预约信息已更新",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.applicant_id != request.user.id and not request.user.is_sys_admin:
            raise PermissionDenied("只能删除自己提交的预约")
        if instance.status not in (Reservation.Status.DRAFT, Reservation.Status.CANCELLED):
            raise ValidationError({"detail": "只能删除暂存或已取消的预约"})
        log_operation(
            operator=request.user, action="delete", target_type="reservation",
            target_id=instance.id, target_repr=instance.no, lab=instance.laboratory,
            remark="删除预约单", request=request,
        )
        instance.delete()
        return Response({"code": 0, "message": "预约已删除", "data": None})

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        serializer = ReservationListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # ---------------------- 冲突预校验 ----------------------
    @action(detail=False, methods=["post"], url_path="check-conflict")
    def check_conflict(self, request):
        """提交前预校验：时长上限、开放时段、设备冲突。"""
        user = request.user
        from apps.labs.models import Laboratory

        laboratory = Laboratory.objects.filter(pk=request.data.get("laboratory")).first()
        device = Device.objects.filter(pk=request.data.get("device")).first()
        start = parse_datetime(request.data.get("start_time"))
        end = parse_datetime(request.data.get("end_time"))
        exclude = request.data.get("exclude_id")
        try:
            validate_full_reservation(
                user, laboratory, device, start, end,
                exclude_reservation_id=exclude, check_advance=False,
            )
        except ReservationError as exc:
            return Response({"code": 0, "message": exc.message,
                             "data": {"available": False, "reason": exc.message}})
        return Response({
            "code": 0, "message": "该时段可以预约",
            "data": {"available": True, "reason": "", "duration_hours":
                     round((end - start).total_seconds() / 3600, 2)},
        })

    # ---------------------- 暂存 / 提交 / 撤回 ----------------------
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        """提交暂存的预约。"""
        instance = self.get_object()
        self._ensure_owner(request.user, instance)
        if instance.status not in (Reservation.Status.DRAFT, Reservation.Status.REJECTED):
            raise ValidationError({"detail": "只有暂存或已驳回的预约可以提交"})
        try:
            validate_full_reservation(
                request.user, instance.laboratory, instance.device,
                instance.start_time, instance.end_time,
                exclude_reservation_id=instance.id,
            )
        except ReservationError as exc:
            return Response({"code": 400, "message": exc.message, "data": None},
                            status=status.HTTP_400_BAD_REQUEST)
        instance.submit_time = timezone.now()
        instance.reject_reason = ""
        instance.save(update_fields=["submit_time", "reject_reason", "updated_at"])
        change_status(instance, Reservation.Status.PENDING, request.user, "submit", "提交预约申请")
        notify_pending_approval(instance)
        return Response({"code": 0, "message": "预约已提交，等待审批",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    @action(detail=True, methods=["post"], url_path="withdraw")
    def withdraw(self, request, pk=None):
        """撤回未审批的预约。"""
        instance = self.get_object()
        self._ensure_owner(request.user, instance)
        if instance.status != Reservation.Status.PENDING:
            raise ValidationError({"detail": "只有待审批的预约可以撤回"})
        serializer = WithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "") or "预约人主动撤回"
        instance.withdraw_time = timezone.now()
        instance.cancel_reason = reason
        instance.save(update_fields=["withdraw_time", "cancel_reason", "updated_at"])
        change_status(instance, Reservation.Status.CANCELLED, request.user, "withdraw", f"撤回预约：{reason}")
        close_chat_thread(instance)
        from apps.notifications.services import create_notification

        for manager in instance.laboratory.managers.all():
            create_notification(
                user=manager, notify_type="system", title="预约已被撤回",
                content=f"{instance.applicant_name} 撤回了预约 {instance.no}。",
                reservation=instance,
                dedupe_key=f"withdraw:{instance.id}:{manager.id}",
            )
        return Response({"code": 0, "message": "预约已撤回",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """取消已通过的预约（预约人或管理员）。"""
        instance = self.get_object()
        if instance.applicant_id != request.user.id and not check_lab_manage_permission(request.user, instance):
            raise PermissionDenied("无权取消该预约")
        if instance.status not in (Reservation.Status.APPROVED, Reservation.Status.WAITING_USE):
            raise ValidationError({"detail": "当前状态不允许取消"})
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("cancel_reason", "") or "主动取消"
        instance.cancel_reason = reason
        instance.save(update_fields=["cancel_reason", "updated_at"])
        change_status(instance, Reservation.Status.CANCELLED, request.user, "cancel", f"取消预约：{reason}")
        close_chat_thread(instance)
        return Response({"code": 0, "message": "预约已取消",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    # ---------------------- 审批与冲突控制 ----------------------
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """审批通过。"""
        instance = self.get_object()
        if not check_lab_manage_permission(request.user, instance):
            raise PermissionDenied("您不是该实验室的负责管理员，无权审批")
        if instance.status != Reservation.Status.PENDING:
            raise ValidationError({"detail": "只有待审批的预约可以审批"})
        serializer = ApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .services import validate_device_conflict

        conflict = validate_device_conflict(
            instance.device, instance.start_time, instance.end_time, instance.id
        )
        if conflict:
            return Response({"code": 400, "message": conflict, "data": None},
                            status=status.HTTP_400_BAD_REQUEST)

        instance.approver = request.user
        instance.approver_name = request.user.real_name or request.user.username
        instance.approve_time = timezone.now()
        instance.approve_remark = serializer.validated_data.get("approve_remark", "")
        instance.save(update_fields=["approver", "approver_name", "approve_time",
                                     "approve_remark", "updated_at"])
        change_status(instance, Reservation.Status.APPROVED, request.user, "approve",
                      instance.approve_remark or "审批通过")
        notify_approve_result(instance, True, instance.approve_remark)
        ensure_chat_thread(instance)
        return Response({"code": 0, "message": "审批通过",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """驳回并填写原因。"""
        instance = self.get_object()
        if not check_lab_manage_permission(request.user, instance):
            raise PermissionDenied("您不是该实验室的负责管理员，无权审批")
        if instance.status != Reservation.Status.PENDING:
            raise ValidationError({"detail": "只有待审批的预约可以驳回"})
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reject_reason"]
        instance.approver = request.user
        instance.approver_name = request.user.real_name or request.user.username
        instance.approve_time = timezone.now()
        instance.reject_reason = reason
        instance.save(update_fields=["approver", "approver_name", "approve_time",
                                     "reject_reason", "updated_at"])
        change_status(instance, Reservation.Status.REJECTED, request.user, "reject", f"驳回：{reason}")
        notify_approve_result(instance, False, reason)
        return Response({"code": 0, "message": "已驳回该预约",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    @action(detail=True, methods=["post"], url_path="transfer")
    def transfer(self, request, pk=None):
        """转派给其他管理员审批。"""
        instance = self.get_object()
        if not check_lab_manage_permission(request.user, instance):
            raise PermissionDenied("无权转派该预约")
        if instance.status != Reservation.Status.PENDING:
            raise ValidationError({"detail": "只有待审批的预约可以转派"})
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.accounts.models import User

        new_approver = User.objects.get(pk=serializer.validated_data["approver"])
        old_approver_name = instance.approver_name or "未指派"
        instance.approver = new_approver
        instance.approver_name = new_approver.real_name or new_approver.username
        instance.transferred_from = instance.transferred_from
        instance.save(update_fields=["approver", "approver_name", "updated_at"])

        remark = serializer.validated_data.get("remark", "")
        ReservationStatusLog.objects.create(
            reservation=instance, from_status=instance.status, to_status=instance.status,
            action="transfer",
            operator=request.user, operator_name=request.user.real_name or request.user.username,
            remark=f"转派给 {instance.approver_name}；{remark}".strip("；"),
        )
        log_operation(
            operator=request.user, action="transfer", target_type="reservation",
            target_id=instance.id, target_repr=instance.no, lab=instance.laboratory,
            detail={"审批人": [old_approver_name, instance.approver_name]},
            remark="转派预约审批", request=request,
        )
        notify_transfer(instance, new_approver, request.user)
        return Response({"code": 0, "message": f"已转派给 {instance.approver_name}",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    # ---------------------- 使用进度 ----------------------
    @action(detail=True, methods=["post"], url_path="sign-in")
    def sign_in(self, request, pk=None):
        """签到开始使用。"""
        instance = self.get_object()
        self._ensure_owner(request.user, instance)
        if instance.status not in (Reservation.Status.APPROVED, Reservation.Status.WAITING_USE):
            raise ValidationError({"detail": "当前状态不允许签到"})
        now = timezone.now()
        earliest = instance.start_time - datetime.timedelta(minutes=30)
        if now < earliest:
            raise ValidationError({"detail": f"未到签到时间，最早可于 "
                                             f"{earliest.strftime('%Y-%m-%d %H:%M')} 签到"})
        if now > instance.end_time:
            raise ValidationError({"detail": "预约已超过结束时间，无法签到，请重新预约"})
        serializer = SignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.sign_in_time = now
        instance.save(update_fields=["sign_in_time", "updated_at"])
        change_status(instance, Reservation.Status.IN_USE, request.user, "sign_in",
                      f"签到开始使用（{now.strftime('%Y-%m-%d %H:%M')}）")
        return Response({"code": 0, "message": "签到成功，开始计时",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    @action(detail=True, methods=["post"], url_path="sign-out")
    def sign_out(self, request, pk=None):
        """签退并登记设备状态与异常情况。"""
        instance = self.get_object()
        self._ensure_owner(request.user, instance)
        if instance.status != Reservation.Status.IN_USE:
            raise ValidationError({"detail": "只有使用中的预约可以签退"})
        serializer = SignOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        old_device_status = instance.device.get_status_display()

        instance.sign_out_time = now
        instance.device_status_after = data["device_status_after"]
        instance.abnormal_note = data.get("abnormal_note", "")
        instance.save(update_fields=["sign_out_time", "device_status_after",
                                     "abnormal_note", "updated_at"])

        # 登记设备状态
        if data["device_status_after"] != instance.device.status:
            instance.device.set_status(
                data["device_status_after"], operator=request.user,
                reason=f"预约 {instance.no} 签退登记",
            )

        ReservationStatusLog.objects.create(
            reservation=instance, from_status=instance.status, to_status=instance.status,
            action="sign_out",
            operator=request.user, operator_name=request.user.real_name or request.user.username,
            remark=(f"签退：设备状态 {old_device_status} → {instance.get_device_status_after_display()}"
                    + (f"；异常：{data.get('abnormal_note')}" if data.get("abnormal_note") else "")),
        )
        log_operation(
            operator=request.user, action="sign_out", target_type="reservation",
            target_id=instance.id, target_repr=instance.no, lab=instance.laboratory,
            detail={
                "设备状态": [old_device_status, instance.get_device_status_after_display()],
                "异常情况": ["", data.get("abnormal_note", "")],
            },
            remark="签退归还，等待管理员核验", request=request,
        )
        notify_sign_out_to_admin(instance)
        return Response({"code": 0, "message": "签退成功，等待管理员核验完工",
                         "data": ReservationDetailSerializer(instance, context={"request": request}).data})

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """管理员确认设备归还与状态核验，完成闭环。"""
        instance = self.get_object()
        if not check_lab_manage_permission(request.user, instance):
            raise PermissionDenied("您不是该实验室的负责管理员，无权确认完工")
        if instance.status != Reservation.Status.IN_USE:
            raise ValidationError({"detail": "只有使用中的预约可以确认完工"})
        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data.get("return_confirmed", True):
            raise ValidationError({"detail": "请先确认设备已归还后再完成预约"})

        old_device_status = instance.device.get_status_display()
        instance.return_confirmed = True
        instance.completion_time = timezone.now()
        instance.completion_operator = request.user
        instance.completion_remark = data.get("completion_remark", "")
        if data.get("device_status_after"):
            instance.device_status_after = data["device_status_after"]
        instance.save(update_fields=["return_confirmed", "completion_time", "completion_operator",
                                     "completion_remark", "device_status_after", "updated_at"])

        if data.get("device_status_after") and data["device_status_after"] != instance.device.status:
            instance.device.set_status(
                data["device_status_after"], operator=request.user,
                reason=f"预约 {instance.no} 完工核验",
            )

        change_status(instance, Reservation.Status.COMPLETED, request.user, "complete",
                      data.get("completion_remark") or "设备已归还并核验完成")
        close_chat_thread(instance)
        notify_completed(instance)
        return Response({
            "code": 0, "message": "已确认完工，预约完成",
            "data": ReservationDetailSerializer(instance, context={"request": request}).data,
        })

    @action(detail=True, methods=["post"], url_path="evaluate")
    def evaluate(self, request, pk=None):
        """学生对已完成预约进行评价。"""
        instance = self.get_object()
        self._ensure_owner(request.user, instance)
        if instance.status != Reservation.Status.COMPLETED:
            raise ValidationError({"detail": "只有已完成的预约可以评价"})
        if instance.is_evaluated:
            raise ValidationError({"detail": "该预约已评价，不能重复评价"})
        serializer = EvaluationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        evaluation = Evaluation.objects.create(
            reservation=instance,
            device_score=data["device_score"],
            speed_score=data["speed_score"],
            service_score=data["service_score"],
            content=data.get("content", ""),
            images=data.get("images", []) or [],
            evaluator=request.user,
            evaluator_name=request.user.real_name or request.user.username,
        )
        evaluation.average_score = evaluation.compute_average()
        evaluation.save(update_fields=["average_score"])
        instance.is_evaluated = True
        instance.save(update_fields=["is_evaluated", "updated_at"])

        log_operation(
            operator=request.user, action="evaluate", target_type="reservation",
            target_id=instance.id, target_repr=instance.no, lab=instance.laboratory,
            detail={"综合评分": ["", evaluation.average_score],
                    "评价内容": ["", data.get("content", "")[:60]]},
            remark="提交完工评价", request=request,
        )
        return Response({"code": 0, "message": "评价提交成功，感谢您的反馈",
                         "data": EvaluationSerializer(evaluation).data})

    # ---------------------- 查询辅助 ----------------------
    @action(detail=False, methods=["get"], url_path="my-progress")
    def my_progress(self, request):
        """学生/教师查看当前进度和预计可用时间。"""
        user = request.user
        queryset = Reservation.objects.select_related("device", "laboratory").filter(applicant=user)
        current = queryset.filter(status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                                              Reservation.Status.IN_USE]).order_by("start_time")
        now = timezone.now()
        data = [
            {
                "id": item.id,
                "no": item.no,
                "device_name": item.device.name,
                "laboratory_name": item.laboratory.name,
                "status": item.status,
                "status_display": item.get_status_display(),
                "start_time": item.start_time,
                "end_time": item.end_time,
                "sign_in_time": item.sign_in_time,
                "sign_out_time": item.sign_out_time,
                "progress_percent": item.progress_percent,
                "is_overdue": item.is_overdue,
                "overdue_minutes": item.overdue_minutes,
                "can_sign_in": item.can_sign_in and item.start_time - datetime.timedelta(minutes=30) <= now <= item.end_time,
                "can_sign_out": item.status == Reservation.Status.IN_USE,
                "remaining_minutes": max(0, int((item.end_time - now).total_seconds() // 60)),
            }
            for item in current
        ]
        stats = {
            "total": queryset.count(),
            "pending": queryset.filter(status=Reservation.Status.PENDING).count(),
            "using": queryset.filter(status=Reservation.Status.IN_USE).count(),
            "completed": queryset.filter(status=Reservation.Status.COMPLETED).count(),
            "overdue": queryset.filter(
                status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                            Reservation.Status.IN_USE],
                end_time__lt=now).count(),
            "to_evaluate": queryset.filter(status=Reservation.Status.COMPLETED, is_evaluated=False).count(),
        }
        return Response({"code": 0, "message": "success",
                         "data": {"current": data, "statistics": stats}})

    @action(detail=False, methods=["get"], url_path="device-usage")
    def device_usage(self, request):
        """查看某设备未来占用情况（预计可用时间）。"""
        device_id = request.query_params.get("device")
        if not device_id:
            raise ValidationError({"detail": "请提供 device 参数"})
        now = timezone.now()
        queryset = (
            Reservation.objects.filter(device_id=device_id, status__in=Reservation.ACTIVE_STATUSES,
                                       end_time__gt=now)
            .select_related("applicant").order_by("start_time")
        )
        device = Device.objects.filter(pk=device_id).first()
        if device is None:
            raise ValidationError({"detail": "设备不存在"})
        occupied_until = device.next_available_time(now)
        return Response({
            "code": 0, "message": "success",
            "data": {
                "device": {"id": device.id, "name": device.name, "code": device.code,
                           "status": device.status, "status_display": device.get_status_display()},
                "occupied_until": occupied_until,
                "is_busy_now": bool(device.is_busy_at(now, now + datetime.timedelta(minutes=1))),
                "future": [
                    {
                        "no": item.no,
                        "start_time": item.start_time,
                        "end_time": item.end_time,
                        "status": item.status,
                        "status_display": item.get_status_display(),
                        "applicant_name": item.applicant_name,
                    }
                    for item in queryset
                ],
            },
        })

    @action(detail=False, methods=["get"], url_path="todo")
    def todo(self, request):
        """我的待办：待审批（管理员）/待签到/待归还/待评价。"""
        user = request.user
        now = timezone.now()
        data = {"pending_approval": 0, "pending_sign_in": 0, "pending_return": 0,
                "pending_evaluate": 0, "overdue": 0}

        if user.is_lab_admin or user.is_sys_admin:
            base = Reservation.objects.filter(status=Reservation.Status.PENDING)
            if not user.is_sys_admin:
                base = base.filter(laboratory_id__in=user.managed_lab_ids)
            data["pending_approval"] = base.count()
            overdue = Reservation.objects.filter(
                laboratory_id__in=user.managed_lab_ids,
                status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                            Reservation.Status.IN_USE],
                end_time__lt=now,
            ) if not user.is_sys_admin else Reservation.objects.filter(
                status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                            Reservation.Status.IN_USE], end_time__lt=now)
            data["overdue"] = overdue.count()
            pending_return = Reservation.objects.filter(status=Reservation.Status.IN_USE, sign_out_time__isnull=False)
            if not user.is_sys_admin:
                pending_return = pending_return.filter(laboratory_id__in=user.managed_lab_ids)
            data["pending_return"] = pending_return.count()
        else:
            mine = Reservation.objects.filter(applicant=user)
            data["pending_sign_in"] = mine.filter(
                status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE],
                start_time__lte=now + datetime.timedelta(minutes=30),
                end_time__gte=now,
            ).count()
            data["pending_return"] = mine.filter(status=Reservation.Status.IN_USE).count()
            data["pending_evaluate"] = mine.filter(
                status=Reservation.Status.COMPLETED, is_evaluated=False
            ).count()
            data["overdue"] = mine.filter(
                status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                            Reservation.Status.IN_USE],
                end_time__lt=now,
            ).count()
        return Response({"code": 0, "message": "success", "data": data})

    @action(detail=False, methods=["get"], url_path="status-logs")
    def status_logs(self, request):
        """查看某预约的状态流转记录。"""
        reservation_id = request.query_params.get("reservation")
        if not reservation_id:
            raise ValidationError({"detail": "请提供 reservation 参数"})
        instance = Reservation.objects.filter(pk=reservation_id).first()
        if instance is None:
            raise ValidationError({"detail": "预约不存在"})
        if not (instance.applicant_id == request.user.id
                or check_lab_manage_permission(request.user, instance)):
            raise PermissionDenied("无权查看该预约的流转记录")
        logs = instance.status_logs.all()
        return Response({"code": 0, "message": "success",
                         "data": ReservationStatusLogSerializer(logs, many=True).data})

    @staticmethod
    def _ensure_owner(user, reservation):
        if reservation.applicant_id != user.id:
            raise PermissionDenied("只能操作自己提交的预约")


class ChatViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """图文沟通：按预约单保留历史沟通记录。"""

    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_value_regex = r"\d+"

    def get_serializer_class(self):
        if self.action in ("list", "retrieve", "by_reservation"):
            return ChatThreadSerializer
        return ChatMessageSerializer

    def get_queryset(self):
        queryset = ChatThread.objects.select_related(
            "reservation", "reservation__applicant", "reservation__device",
            "reservation__laboratory", "last_sender",
        ).prefetch_related("messages")
        user = self.request.user
        if user.is_sys_admin:
            pass
        elif user.is_lab_admin:
            queryset = queryset.filter(
                Q(reservation__laboratory_id__in=user.managed_lab_ids)
                | Q(reservation__applicant=user)
            )
        else:
            queryset = queryset.filter(reservation__applicant=user)

        params = self.request.query_params
        if params.get("status"):
            queryset = queryset.filter(status__in=params["status"].split(","))
        if params.get("keyword"):
            keyword = params["keyword"]
            queryset = queryset.filter(
                Q(reservation__no__icontains=keyword)
                | Q(reservation__applicant_name__icontains=keyword)
                | Q(reservation__device__name__icontains=keyword)
            )
        return queryset.distinct()

    @action(detail=False, methods=["get"], url_path="unanswered-count")
    def unanswered_count(self, request):
        """待回复会话数量（管理员角标）。"""
        queryset = self.get_queryset().filter(status=ChatThread.Status.PENDING_REPLY)
        return Response({"code": 0, "message": "success", "data": {"count": queryset.count()}})

    @action(detail=False, methods=["get"], url_path="by-reservation")
    def by_reservation(self, request):
        """按预约单查看沟通记录（不存在则自动创建会话）。"""
        reservation_id = request.query_params.get("reservation")
        if not reservation_id:
            raise ValidationError({"detail": "请提供 reservation 参数"})
        reservation = Reservation.objects.filter(pk=reservation_id).first()
        if reservation is None:
            raise ValidationError({"detail": "预约不存在"})
        if not (reservation.applicant_id == request.user.id
                or check_lab_manage_permission(request.user, reservation)):
            raise PermissionDenied("无权查看该预约的沟通记录")
        thread = ensure_chat_thread(reservation)
        # 阅读即标记已读
        thread.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
        serializer = ChatThreadSerializer(thread, context={"request": request})
        return Response({"code": 0, "message": "success", "data": serializer.data})

    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, pk=None):
        """查看会话消息。"""
        thread = self.get_object()
        self._check_permission(request.user, thread)
        thread.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
        serializer = ChatMessageSerializer(
            thread.messages.select_related("sender"), many=True, context={"request": request}
        )
        return Response({"code": 0, "message": "success", "data": serializer.data})

    @action(detail=False, methods=["post"], url_path="send")
    def send(self, request):
        """发送沟通消息（文字 + 图片）。"""
        reservation_id = request.data.get("reservation")
        if not reservation_id:
            raise ValidationError({"detail": "请提供 reservation 参数"})
        reservation = Reservation.objects.select_related("laboratory").filter(pk=reservation_id).first()
        if reservation is None:
            raise ValidationError({"detail": "预约不存在"})
        if not (reservation.applicant_id == request.user.id
                or check_lab_manage_permission(request.user, reservation)):
            raise PermissionDenied("无权参与该预约的沟通")

        content = (request.data.get("content") or "").strip()
        image = request.FILES.get("image")
        if not content and not image:
            raise ValidationError({"detail": "请输入内容或上传图片"})

        thread = ensure_chat_thread(reservation)
        if thread.status == ChatThread.Status.CLOSED and reservation.status not in (
            Reservation.Status.COMPLETED, Reservation.Status.CANCELLED,
        ):
            thread.status = ChatThread.Status.PENDING_REPLY
            thread.save(update_fields=["status"])

        is_admin_side = check_lab_manage_permission(request.user, reservation)
        message = ChatMessage.objects.create(
            thread=thread,
            sender=request.user,
            sender_name=request.user.real_name or request.user.username,
            sender_role=request.user.role,
            is_admin_side=is_admin_side,
            content=content,
            image=image,
            reply_to_id=request.data.get("reply_to") or None,
        )

        thread.last_message_time = timezone.now()
        thread.last_sender = request.user
        thread.message_count = thread.messages.count()
        thread.status = (
            ChatThread.Status.REPLIED if is_admin_side else ChatThread.Status.PENDING_REPLY
        )
        thread.save(update_fields=["last_message_time", "last_sender", "message_count",
                                   "status", "updated_at"])

        log_operation(
            operator=request.user, action="message", target_type="reservation",
            target_id=reservation.id, target_repr=reservation.no, lab=reservation.laboratory,
            detail={"沟通内容": ["", (content or "[图片]")[:60]]},
            remark="预约图文沟通", request=request,
        )

        # 通知对方
        if is_admin_side:
            notify_chat_reply(reservation, reservation.applicant, request.user, content)
        else:
            for manager in reservation.laboratory.managers.all():
                notify_chat_reply(reservation, manager, request.user, content)

        return Response({
            "code": 0, "message": "消息已发送",
            "data": ChatMessageSerializer(message, context={"request": request}).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        """结束本次沟通。"""
        thread = self.get_object()
        self._check_permission(request.user, thread)
        thread.status = ChatThread.Status.CLOSED
        thread.save(update_fields=["status", "updated_at"])
        return Response({"code": 0, "message": "本次沟通已结束", "data": None})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        """标记会话消息为已读。"""
        thread = self.get_object()
        self._check_permission(request.user, thread)
        count = thread.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
        return Response({"code": 0, "message": f"已标记 {count} 条消息为已读", "data": {"count": count}})

    @staticmethod
    def _check_permission(user, thread):
        reservation = thread.reservation
        if reservation.applicant_id == user.id:
            return
        if check_lab_manage_permission(user, reservation):
            return
        raise PermissionDenied("无权访问该沟通会话")


class EvaluationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """评价管理：管理员查看评价详情并可回复。"""

    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticated]
    lookup_value_regex = r"\d+"
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Evaluation.objects.select_related(
            "reservation", "reservation__laboratory", "reservation__device", "evaluator"
        )
        user = self.request.user
        if user.is_sys_admin:
            pass
        elif user.is_lab_admin:
            queryset = queryset.filter(reservation__laboratory_id__in=user.managed_lab_ids)
        else:
            queryset = queryset.filter(evaluator=user)

        params = self.request.query_params
        if params.get("laboratory"):
            queryset = queryset.filter(reservation__laboratory_id=params["laboratory"])
        if params.get("category"):
            queryset = queryset.filter(reservation__device__category_id=params["category"])
        if params.get("score"):
            queryset = queryset.filter(average_score__gte=params["score"])
        if params.get("keyword"):
            keyword = params["keyword"]
            queryset = queryset.filter(
                Q(reservation__no__icontains=keyword)
                | Q(reservation__applicant_name__icontains=keyword)
                | Q(content__icontains=keyword)
            )
        return queryset

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request):
        """评价统计：平均分与各维度平均分。"""
        from django.db.models import Avg

        queryset = self.get_queryset()
        data = queryset.aggregate(
            count=Count("id"),
            device_avg=Avg("device_score"),
            speed_avg=Avg("speed_score"),
            service_avg=Avg("service_score"),
            overall_avg=Avg("average_score"),
        )
        by_lab = list(
            queryset.values("reservation__laboratory__name")
            .annotate(count=Count("id"), avg=Avg("average_score"))
            .order_by("-avg")
        )
        return Response({
            "code": 0, "message": "success",
            "data": {
                "count": data["count"] or 0,
                "device_avg": round(data["device_avg"] or 0, 2),
                "speed_avg": round(data["speed_avg"] or 0, 2),
                "service_avg": round(data["service_avg"] or 0, 2),
                "overall_avg": round(data["overall_avg"] or 0, 2),
                "by_laboratory": [
                    {"laboratory": item["reservation__laboratory__name"],
                     "count": item["count"], "avg": round(item["avg"] or 0, 2)}
                    for item in by_lab
                ],
            },
        })

    @action(detail=True, methods=["post"], url_path="reply")
    def reply(self, request, pk=None):
        """管理员回复评价。"""
        evaluation = self.get_object()
        user = request.user
        if not (user.is_sys_admin
                or (user.is_lab_admin
                    and evaluation.reservation.laboratory_id in user.managed_lab_ids)):
            raise PermissionDenied("仅该实验室管理员可以回复评价")
        serializer = EvaluationReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        evaluation.reply_content = serializer.validated_data["reply_content"]
        evaluation.reply_time = timezone.now()
        evaluation.save(update_fields=["reply_content", "reply_time"])
        return Response({"code": 0, "message": "回复成功",
                         "data": EvaluationSerializer(evaluation).data})
