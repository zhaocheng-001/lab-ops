"""运维模块视图。"""
from datetime import date, datetime, timedelta

from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import scope_queryset_by_user
from apps.labs.models import Device

from .models import (
    FaultReport,
    InspectRecord,
    MaintenanceOrder,
    MaintenancePlan,
)
from .permissions import IsMaintenanceAdmin, scope_inspect_records, scope_orders
from .serializers import (
    FaultReportCreateSerializer,
    FaultReportSerializer,
    InspectRecordSerializer,
    MaintenanceOrderSerializer,
    MaintenancePlanSerializer,
)


def _ok(message="success", data=None, http_status=status.HTTP_200_OK):
    return Response({"code": 0, "message": message, "data": data}, status=http_status)


def _err(message, http_status=status.HTTP_400_BAD_REQUEST, code=1):
    return Response({"code": code, "message": message, "data": None}, status=http_status)


class FaultReportViewSet(viewsets.ModelViewSet):
    """故障报修：任何人可发起，管理员处理。"""

    permission_classes = [IsAuthenticated]
    serializer_class = FaultReportSerializer
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = FaultReport.objects.select_related("device", "laboratory", "reporter", "order")
        if user.is_sys_admin:
            return qs
        if user.is_lab_admin:
            return qs.filter(laboratory_id__in=user.managed_lab_ids)
        return qs.filter(reporter=user)

    def get_serializer_class(self):
        if self.action == "create":
            return FaultReportCreateSerializer
        return FaultReportSerializer

    def create(self, request, *args, **kwargs):
        """学生 / 教师发起报修，触发设备进入维修状态。"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        # 把设备状态切到维修中（如未报废）
        device = report.device
        if device.status != Device.Status.SCRAPPED:
            device.set_status(
                Device.Status.REPAIRING, operator=request.user,
                reason=f"故障报修 {report.no}",
            )
        return _ok(
            "报修提交成功",
            FaultReportSerializer(report).data,
            http_status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="my")
    def my_reports(self, request):
        """我的报修记录。"""
        qs = self.get_queryset().filter(reporter=request.user)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(FaultReportSerializer(page, many=True).data)
        return _ok(data=FaultReportSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_order(self, request, pk=None):
        """管理员将报修转为工单。"""
        if not (request.user.is_sys_admin or request.user.is_lab_admin):
            return _err("仅管理员可派单", http_status=status.HTTP_403_FORBIDDEN)
        report = self.get_object()
        if report.status not in (FaultReport.Status.PENDING, FaultReport.Status.DISPATCHED):
            return _err(f"当前状态 {report.get_status_display()} 不允许派单")

        handler_id = request.data.get("handler_id") or request.data.get("handler")
        priority = request.data.get("priority") or MaintenanceOrder.Priority.P2
        # 兼容前端 early 版本传的 normal/high/urgent
        priority = {"normal": "P2", "high": "P1", "urgent": "P0"}.get(priority, priority)
        if priority not in MaintenanceOrder.Priority.values:
            priority = MaintenanceOrder.Priority.P2
        title = request.data.get("title") or f"维修-{report.device.name}"
        if not handler_id:
            return _err("请选择处理人")
        from apps.accounts.models import User
        try:
            handler = User.objects.get(pk=handler_id)
        except User.DoesNotExist:
            return _err("处理人不存在")

        order = MaintenanceOrder.objects.create(
            title=title,
            source=MaintenanceOrder.Source.FAULT,
            device=report.device,
            laboratory=report.laboratory,
            fault=report,
            priority=priority,
            status=MaintenanceOrder.Status.PENDING,
            handler=handler,
            handler_name=handler.real_name or handler.username,
            dispatcher=request.user,
            dispatcher_name=request.user.real_name or request.user.username,
            fault_desc=report.description,
            scheduled_time=request.data.get("scheduled_time") or None,
        )
        report.status = FaultReport.Status.DISPATCHED
        report.order = order
        report.save(update_fields=["status", "order", "updated_at"])
        # 写审计日志
        from apps.auditlog.services import log_operation
        log_operation(
            operator=request.user,
            action="create",
            target_type="maintenance_order",
            target_id=order.id,
            target_repr=str(order),
            lab=order.laboratory,
            detail={"来源": [report.no]},
            remark="故障派单",
        )
        # 站内通知：处理人收到派单、报修人收到"已派单"
        from apps.notifications.services import create_notification
        if handler.id != request.user.id:
            create_notification(
                user=handler,
                notify_type="system",
                title="收到新的维修工单",
                content=(
                    f"工单 {order.no}（{order.title}）已派给你，"
                    f"来源：{report.no}，设备：{order.device.name}。"
                ),
                dedupe_key=f"order_dispatch:{order.id}",
                level="warning",
            )
        if report.reporter_id and report.reporter_id != request.user.id:
            create_notification(
                user=report.reporter,
                notify_type="system",
                title="您的故障报修已派单",
                content=(
                    f"您提交的报修 {report.no}（{report.device.name}）"
                    f"已生成工单 {order.no}，处理人：{handler.real_name or handler.username}。"
                ),
                dedupe_key=f"fault_dispatched:{report.id}",
                level="info",
            )
        return _ok(
            "派单成功",
            MaintenanceOrderSerializer(order).data,
            http_status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """管理员驳回报修（如重复/误报）。"""
        if not (request.user.is_sys_admin or request.user.is_lab_admin):
            return _err("仅管理员可驳回", http_status=status.HTTP_403_FORBIDDEN)
        report = self.get_object()
        if report.status in (FaultReport.Status.CLOSED, FaultReport.Status.RESOLVED):
            return _err("已完成/已关闭的报修不可驳回")
        reason = request.data.get("reason") or "经核实无需处理"
        report.status = FaultReport.Status.REJECTED
        report.reject_reason = reason
        report.save(update_fields=["status", "reject_reason", "updated_at"])
        # 设备回到可用
        if report.device.status == Device.Status.REPAIRING:
            report.device.set_status(
                Device.Status.AVAILABLE, operator=request.user, reason="报修驳回，恢复可用",
            )
        return _ok("已驳回", FaultReportSerializer(report).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        """关闭已修复的报修。"""
        report = self.get_object()
        if report.status not in (FaultReport.Status.RESOLVED, FaultReport.Status.DISPATCHED):
            return _err("当前状态不允许关闭")
        report.status = FaultReport.Status.CLOSED
        report.save(update_fields=["status", "updated_at"])
        return _ok("已关闭", FaultReportSerializer(report).data)

    @action(detail=False, methods=["get"], url_path="device-summary")
    def device_summary(self, request):
        """按设备聚合运维历史：故障数 / 工单数 / 最近巡检 / 故障率。"""
        device_id = request.query_params.get("device_id")
        if not device_id:
            return _err("缺少 device_id 参数")
        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            return _err("设备不存在", http_status=status.HTTP_404_NOT_FOUND)
        fault_count = FaultReport.objects.filter(device=device).count()
        order_count = MaintenanceOrder.objects.filter(device=device).count()
        resolved_count = MaintenanceOrder.objects.filter(
            device=device, status=MaintenanceOrder.Status.VERIFIED,
        ).count()
        last_inspection = InspectRecord.objects.filter(device=device).order_by("-inspected_at").first()
        last_fault = FaultReport.objects.filter(device=device).order_by("-created_at").first()
        last_order = MaintenanceOrder.objects.filter(device=device).order_by("-created_at").first()
        recent_faults = list(
            FaultReport.objects.filter(device=device).order_by("-created_at")
            .values("id", "no", "status", "severity", "created_at")[:5]
        )
        recent_orders = list(
            MaintenanceOrder.objects.filter(device=device).order_by("-created_at")
            .values("id", "no", "title", "status", "priority", "created_at")[:5]
        )
        recent_records = list(
            InspectRecord.objects.filter(device=device).order_by("-inspected_at")
            .values("id", "result", "inspected_at", "inspector_name")[:5]
        )
        return _ok(data={
            "device_id": device.id,
            "device_name": device.name,
            "fault_count": fault_count,
            "order_count": order_count,
            "resolved_count": resolved_count,
            "last_inspection_at": last_inspection.inspected_at if last_inspection else None,
            "last_fault_at": last_fault.created_at if last_fault else None,
            "last_order_at": last_order.created_at if last_order else None,
            "recent_faults": recent_faults,
            "recent_orders": recent_orders,
            "recent_inspections": recent_records,
        })


class MaintenanceOrderViewSet(viewsets.ModelViewSet):
    """维修工单：管理员全权处理。"""

    permission_classes = [IsAuthenticated, IsMaintenanceAdmin]
    serializer_class = MaintenanceOrderSerializer
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = MaintenanceOrder.objects.select_related(
            "device", "laboratory", "handler", "dispatcher", "fault", "plan",
        )
        return scope_orders(qs, self.request.user)

    def perform_create(self, serializer):
        """管理员手动开单（计划性维护 / 巡检发现 / 主动维护）。"""
        serializer.save(
            dispatcher=self.request.user,
            dispatcher_name=self.request.user.real_name or self.request.user.username,
            source=serializer.validated_data.get(
                "source", MaintenanceOrder.Source.ROUTINE,
            ),
        )

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, pk=None):
        """指派处理人 / 改派。"""
        order = self.get_object()
        if order.status in (MaintenanceOrder.Status.RESOLVED,
                            MaintenanceOrder.Status.VERIFIED,
                            MaintenanceOrder.Status.CANCELLED):
            return _err("已完成/已取消工单不可改派")
        handler_id = request.data.get("handler_id")
        if not handler_id:
            return _err("请选择处理人")
        from apps.accounts.models import User
        try:
            handler = User.objects.get(pk=handler_id)
        except User.DoesNotExist:
            return _err("处理人不存在")
        order.handler = handler
        order.handler_name = handler.real_name or handler.username
        if order.status == MaintenanceOrder.Status.PENDING:
            order.status = MaintenanceOrder.Status.PROCESSING
        order.save(update_fields=["handler", "handler_name", "status", "updated_at"])
        # 站内通知：新处理人收到指派
        from apps.notifications.services import create_notification
        if handler.id != request.user.id:
            create_notification(
                user=handler,
                notify_type="system",
                title="工单指派给你",
                content=(
                    f"工单 {order.no}（{order.title}，设备 {order.device.name}）"
                    f"已指派给你，请尽快处理。"
                ),
                dedupe_key=f"order_assign:{order.id}",
                level="warning",
            )
        return _ok("指派成功", MaintenanceOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        """开始处理：记录实际开始时间。"""
        order = self.get_object()
        if order.status not in (MaintenanceOrder.Status.PENDING, MaintenanceOrder.Status.PROCESSING):
            return _err("当前状态不允许开始")
        if not order.handler_id:
            return _err("请先指派处理人")
        order.status = MaintenanceOrder.Status.PROCESSING
        order.started_time = order.started_time or timezone.now()
        order.save(update_fields=["status", "started_time", "updated_at"])
        return _ok("已开始处理", MaintenanceOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """修复完成：提交处理方案。"""
        order = self.get_object()
        if order.status not in (MaintenanceOrder.Status.PENDING, MaintenanceOrder.Status.PROCESSING):
            return _err("当前状态不允许完成")
        solution = request.data.get("solution") or ""
        parts_replaced = request.data.get("parts_replaced") or ""
        cost = request.data.get("cost") or 0
        images = request.data.get("images") or []
        if not solution.strip():
            return _err("请填写处理方案")
        order.solution = solution
        order.parts_replaced = parts_replaced
        order.cost = cost
        order.images = images
        order.status = MaintenanceOrder.Status.RESOLVED
        order.completed_time = timezone.now()
        if not order.started_time:
            order.started_time = order.completed_time
        order.save()
        # 关联报修变为已修复
        if order.fault_id and order.fault.status != FaultReport.Status.CLOSED:
            order.fault.status = FaultReport.Status.RESOLVED
            order.fault.resolved_at = order.completed_time
            order.fault.save(update_fields=["status", "resolved_at", "updated_at"])
        # 设备回到可用状态
        if order.device.status == Device.Status.REPAIRING:
            order.device.set_status(
                Device.Status.AVAILABLE, operator=request.user,
                reason=f"维修完成 {order.no}",
            )
        # 审计日志
        from apps.auditlog.services import log_operation
        log_operation(
            operator=request.user,
            action="update",
            target_type="maintenance_order",
            target_id=order.id,
            target_repr=str(order),
            lab=order.laboratory,
            detail={
                "处理方案": [order.solution[:30] + ("..." if len(order.solution) > 30 else "")],
                "费用": [order.cost],
            },
            remark="维修完成",
        )
        # 站内通知：报修人收到"已修复"、派单人收到"已完成待验收"
        from apps.notifications.services import create_notification
        if order.fault_id and order.fault.reporter_id:
            create_notification(
                user=order.fault.reporter,
                notify_type="system",
                title="您的故障已修复",
                content=(
                    f"报修 {order.fault.no}（{order.device.name}）已处理完成："
                    f"{order.solution[:40]}{'...' if len(order.solution) > 40 else ''}。"
                    "请到设备现场确认，或点击「关闭」结束报修。"
                ),
                dedupe_key=f"fault_resolved:{order.fault.id}",
                level="info",
            )
        if order.dispatcher_id and order.dispatcher_id != request.user.id:
            create_notification(
                user=order.dispatcher,
                notify_type="system",
                title="工单已完成待验收",
                content=(
                    f"您派出的工单 {order.no}（{order.device.name}）已完成，请尽快验收。"
                ),
                dedupe_key=f"order_resolved:{order.id}",
                level="warning",
            )
        return _ok("已标记完成", MaintenanceOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        """管理员验收工单。"""
        order = self.get_object()
        if order.status != MaintenanceOrder.Status.RESOLVED:
            return _err("仅已修复工单可验收")
        order.status = MaintenanceOrder.Status.VERIFIED
        order.verified_time = timezone.now()
        order.verifier = request.user
        order.save(update_fields=["status", "verified_time", "verifier", "updated_at"])
        return _ok("已验收", MaintenanceOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """取消工单。"""
        order = self.get_object()
        if order.status in (MaintenanceOrder.Status.VERIFIED, MaintenanceOrder.Status.CANCELLED):
            return _err("已验收/已取消工单不可再取消")
        reason = request.data.get("reason") or "管理员取消"
        order.status = MaintenanceOrder.Status.CANCELLED
        order.cancel_reason = reason
        order.save(update_fields=["status", "cancel_reason", "updated_at"])
        # 关联设备回到可用
        if order.device.status == Device.Status.REPAIRING:
            order.device.set_status(
                Device.Status.AVAILABLE, operator=request.user, reason=f"工单取消 {order.no}",
            )
        # 关联报修关闭
        if order.fault_id and order.fault.status not in (
            FaultReport.Status.CLOSED, FaultReport.Status.RESOLVED,
        ):
            order.fault.status = FaultReport.Status.CLOSED
            order.fault.save(update_fields=["status", "updated_at"])
        return _ok("已取消", MaintenanceOrderSerializer(order).data)

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        """运维仪表盘：工单状态、严重度、SLA。"""
        qs = self.get_queryset()
        today = date.today()
        month_start = today.replace(day=1)
        by_status = list(
            qs.values("status").annotate(count=Count("id"))
        )
        by_priority = list(qs.filter(status__in=["pending", "processing"]).values("priority")
                          .annotate(count=Count("id")))
        avg_response = qs.filter(started_time__isnull=False).aggregate(
            avg_min=Avg(F("started_time") - F("created_at")),
        )
        avg_minutes = 0
        if avg_response.get("avg_min") is not None:
            avg_minutes = int(avg_response["avg_min"].total_seconds() // 60)
        overdue = qs.filter(
            status__in=["pending", "processing"],
            created_at__lt=timezone.now() - timedelta(hours=24),
        ).count()
        recent = list(
            qs.filter(created_at__gte=month_start)
            .values("id", "no", "title", "status", "priority", "created_at")
            .order_by("-created_at")[:10]
        )
        # 故障报修与维保计划统计（同样按用户权限裁剪）
        fault_qs = FaultReport.objects.select_related("device", "laboratory")
        if request.user.is_lab_admin and not request.user.is_sys_admin:
            fault_qs = fault_qs.filter(laboratory_id__in=request.user.managed_lab_ids)
        fault_summary = {
            "pending": fault_qs.filter(status=FaultReport.Status.PENDING).count(),
            "dispatched": fault_qs.filter(status=FaultReport.Status.DISPATCHED).count(),
            "repairing": fault_qs.filter(status=FaultReport.Status.REPAIRING).count(),
            "resolved": fault_qs.filter(status=FaultReport.Status.RESOLVED).count(),
            "month_total": fault_qs.filter(created_at__gte=month_start).count(),
        }
        plan_qs = MaintenancePlan.objects.filter(is_active=True)
        if request.user.is_lab_admin and not request.user.is_sys_admin:
            plan_qs = plan_qs.filter(laboratory_id__in=request.user.managed_lab_ids)
        overdue_plans = plan_qs.filter(next_due_date__lt=today).count()
        plan_summary = {
            "active": plan_qs.count(),
            "overdue": overdue_plans,
            "due_soon": plan_qs.filter(
                next_due_date__gte=today, next_due_date__lte=today + timedelta(days=7),
            ).count(),
        }
        return _ok(data={
            "by_status": [
                {"status": item["status"], "status_display": MaintenanceOrder.Status(item["status"]).label,
                 "count": item["count"]}
                for item in by_status
            ],
            "by_priority": [
                {"priority": item["priority"],
                 "priority_display": MaintenanceOrder.Priority(item["priority"]).label,
                 "count": item["count"]}
                for item in by_priority
            ],
            "avg_response_minutes": avg_minutes,
            "overdue_count": overdue,
            "month_count": qs.filter(created_at__gte=month_start).count(),
            "recent": recent,
            "fault_summary": fault_summary,
            "plan_summary": plan_summary,
        })


class MaintenancePlanViewSet(viewsets.ModelViewSet):
    """维保计划：管理员配置。"""

    permission_classes = [IsAuthenticated, IsMaintenanceAdmin]
    serializer_class = MaintenancePlanSerializer
    ordering = ["next_due_date"]

    def get_queryset(self):
        qs = MaintenancePlan.objects.select_related(
            "device", "device_category", "laboratory", "responsible",
        )
        return scope_queryset_by_user(qs, self.request.user, applicant_field=None, lab_field="laboratory")

    @action(detail=False, methods=["get"], url_path="overdue")
    def overdue(self, request):
        """即将到期 / 已逾期计划。"""
        today = date.today()
        qs = self.get_queryset().filter(is_active=True, next_due_date__lte=today + timedelta(days=7))
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(MaintenancePlanSerializer(page, many=True).data)
        return _ok(data=MaintenancePlanSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, pk=None):
        """立即执行一次巡检，生成巡检记录。"""
        plan = self.get_object()
        if not plan.is_active:
            return _err("计划已停用")
        result = request.data.get("result") or InspectRecord.Result.NORMAL
        issues = request.data.get("issues") or ""
        checklist_result = request.data.get("checklist_result") or []
        images = request.data.get("images") or []

        record = InspectRecord.objects.create(
            plan=plan,
            device=plan.device,
            laboratory=plan.laboratory or (
                plan.device.laboratory if plan.device else None
            ),
            inspector=request.user,
            inspector_name=request.user.real_name or request.user.username,
            inspected_at=timezone.now(),
            result=result,
            issues=issues,
            checklist_result=checklist_result,
            images=images,
        )
        # 如需维修，自动派单给自己实验室管理员
        order_data = None
        if result == InspectRecord.Result.NEED_REPAIR and plan.device_id:
            handler_id = request.data.get("handler_id") or plan.responsible_id
            handler = None
            if handler_id:
                from apps.accounts.models import User
                try:
                    handler = User.objects.get(pk=handler_id)
                except User.DoesNotExist:
                    handler = None
            order = MaintenanceOrder.objects.create(
                title=f"维保巡检-{plan.device.name}",
                source=MaintenanceOrder.Source.INSPECT,
                device=plan.device,
                laboratory=plan.laboratory or plan.device.laboratory,
                plan=plan,
                priority=MaintenanceOrder.Priority.P2,
                status=MaintenanceOrder.Status.PENDING,
                handler=handler,
                handler_name=(handler.real_name or handler.username) if handler else "",
                dispatcher=request.user,
                dispatcher_name=request.user.real_name or request.user.username,
                fault_desc=issues or "巡检发现需维修",
                started_time=timezone.now(),
            )
            record.order = order
            record.save(update_fields=["order"])
            order_data = MaintenanceOrderSerializer(order).data
        return _ok(
            "巡检完成",
            {
                "record": InspectRecordSerializer(record).data,
                "order": order_data,
            },
        )


class InspectRecordViewSet(viewsets.ModelViewSet):
    """巡检记录：管理员 / 实验室管理员维护。"""

    permission_classes = [IsAuthenticated, IsMaintenanceAdmin]
    serializer_class = InspectRecordSerializer
    ordering = ["-inspected_at"]

    def get_queryset(self):
        qs = InspectRecord.objects.select_related(
            "plan", "device", "laboratory", "inspector", "order",
        )
        return scope_inspect_records(qs, self.request.user)

    def perform_create(self, serializer):
        instance = serializer.save(
            inspector=self.request.user,
            inspector_name=self.request.user.real_name or self.request.user.username,
        )
        # 巡检结果为需维修时，自动开单
        if instance.result == InspectRecord.Result.NEED_REPAIR and instance.device_id:
            order = MaintenanceOrder.objects.create(
                title=f"巡检-{instance.device.name}",
                source=MaintenanceOrder.Source.INSPECT,
                device=instance.device,
                laboratory=instance.laboratory,
                plan=instance.plan,
                priority=MaintenanceOrder.Priority.P2,
                status=MaintenanceOrder.Status.PENDING,
                dispatcher=self.request.user,
                dispatcher_name=self.request.user.real_name or self.request.user.username,
                fault_desc=instance.issues or "巡检发现需维修",
                started_time=timezone.now(),
            )
            instance.order = order
            instance.save(update_fields=["order"])
            instance._auto_order = order  # 给前端提示
        # 若是维保计划，更新计划的上次/下次时间
        plan = instance.plan
        if plan:
            plan.last_done_date = instance.inspected_at.date()
            plan.next_due_date = plan.last_done_date + timedelta(days=plan.interval_days or 30)
            plan.save(update_fields=["last_done_date", "next_due_date", "updated_at"])
        # 站内通知：巡检结果异常/需维修时通知实验室管理员
        if instance.result in (InspectRecord.Result.ABNORMAL, InspectRecord.Result.NEED_REPAIR):
            if instance.laboratory_id:
                from apps.notifications.services import create_notification
                for manager in instance.laboratory.managers.all():
                    if manager.id == request.user.id:
                        continue
                    create_notification(
                        user=manager,
                        notify_type="system",
                        title=f"巡检发现{instance.get_result_display()}",
                        content=(
                            f"设备 {instance.device.name} 巡检结果为"
                            f"{instance.get_result_display()}：{instance.issues or '请查看详情'}。"
                            + ("已自动派单。" if instance.order_id else "")
                        ),
                        dedupe_key=f"inspect_abnormal:{instance.id}:{manager.id}",
                        level="warning" if instance.result == InspectRecord.Result.ABNORMAL else "danger",
                    )