"""预约、沟通、评价序列化器。"""
from rest_framework import serializers

from apps.accounts.models import User
from apps.labs.serializers import DeviceSimpleSerializer, LaboratoryBriefSerializer

from .models import ChatMessage, ChatThread, Evaluation, Reservation, ReservationStatusLog
from .services import parse_datetime


class ReservationStatusLogSerializer(serializers.ModelSerializer):
    from_status_display = serializers.SerializerMethodField()
    to_status_display = serializers.SerializerMethodField()

    class Meta:
        model = ReservationStatusLog
        fields = [
            "id", "from_status", "from_status_display", "to_status", "to_status_display",
            "action", "operator", "operator_name", "remark", "created_at",
        ]

    def get_from_status_display(self, obj):
        return dict(Reservation.Status.choices).get(obj.from_status, obj.from_status or "—")

    def get_to_status_display(self, obj):
        return dict(Reservation.Status.choices).get(obj.to_status, obj.to_status or "—")


class EvaluationSerializer(serializers.ModelSerializer):
    evaluator_display = serializers.CharField(source="evaluator_name", read_only=True)
    reservation_no = serializers.CharField(source="reservation.no", read_only=True)
    device_name = serializers.CharField(source="reservation.device.name", read_only=True)
    laboratory_name = serializers.CharField(source="reservation.laboratory.name", read_only=True)

    class Meta:
        model = Evaluation
        fields = [
            "id", "reservation", "reservation_no", "device_name", "laboratory_name",
            "device_score", "speed_score", "service_score",
            "average_score", "content", "images", "evaluator", "evaluator_name",
            "evaluator_display", "reply_content", "reply_time", "created_at",
        ]
        read_only_fields = ["reservation", "evaluator", "evaluator_name", "average_score",
                            "reply_content", "reply_time", "created_at"]

    def validate(self, attrs):
        for field in ("device_score", "speed_score", "service_score"):
            score = attrs.get(field, 5)
            if not 1 <= int(score) <= 5:
                raise serializers.ValidationError({field: "评分需在 1~5 之间"})
        return attrs


class ReservationListSerializer(serializers.ModelSerializer):
    """列表展示。"""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    urgency_display = serializers.CharField(source="get_urgency_display", read_only=True)
    laboratory_name = serializers.CharField(source="laboratory.name", read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_code = serializers.CharField(source="device.code", read_only=True)
    device_status = serializers.CharField(source="device.status", read_only=True)
    category_name = serializers.CharField(source="device.category.name", read_only=True)
    duration_hours = serializers.FloatField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    overdue_minutes = serializers.IntegerField(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)
    can_withdraw = serializers.BooleanField(read_only=True)
    can_sign_in = serializers.BooleanField(read_only=True)
    can_evaluate = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id", "no", "applicant", "applicant_name", "applicant_role",
            "college_name", "class_name", "laboratory", "laboratory_name",
            "device", "device_name", "device_code", "device_status", "category_name",
            "start_time", "end_time", "duration_hours", "purpose", "urgency",
            "urgency_display", "status", "status_display", "approver", "approver_name",
            "approve_time", "reject_reason", "sign_in_time", "sign_out_time",
            "completion_time", "is_evaluated", "is_overdue", "overdue_minutes",
            "progress_percent", "can_withdraw", "can_sign_in", "can_evaluate",
            "created_at", "updated_at", "submit_time",
        ]


class ReservationDetailSerializer(ReservationListSerializer):
    """详情展示：额外包含设备、实验室、状态流转、沟通、评价。"""

    device_detail = DeviceSimpleSerializer(source="device", read_only=True)
    laboratory_detail = LaboratoryBriefSerializer(source="laboratory", read_only=True)
    status_logs = ReservationStatusLogSerializer(many=True, read_only=True)
    evaluation = EvaluationSerializer(read_only=True)
    chat_status = serializers.SerializerMethodField()
    chat_unread = serializers.SerializerMethodField()
    approve_remark = serializers.CharField(read_only=True)
    abnormal_note = serializers.CharField(read_only=True)
    device_status_after = serializers.CharField(read_only=True)
    completion_remark = serializers.CharField(read_only=True)
    return_confirmed = serializers.BooleanField(read_only=True)

    class Meta(ReservationListSerializer.Meta):
        fields = ReservationListSerializer.Meta.fields + [
            "device_detail", "laboratory_detail", "status_logs", "evaluation",
            "chat_status", "chat_unread", "approve_remark", "abnormal_note",
            "device_status_after", "completion_remark", "return_confirmed",
            "transferred_from", "cancel_reason", "withdraw_time", "contact_phone",
        ]

    def get_chat_status(self, obj):
        thread = getattr(obj, "chat_thread", None)
        return thread.status if thread else None

    def get_chat_unread(self, obj):
        thread = getattr(obj, "chat_thread", None)
        if not thread:
            return 0
        user = self.context.get("request").user if self.context.get("request") else None
        if user is None:
            return 0
        return thread.messages.filter(is_read=False).exclude(sender=user).count()


class ReservationCreateSerializer(serializers.Serializer):
    """新建/暂存预约。"""

    laboratory = serializers.IntegerField(label="实验室ID")
    device = serializers.IntegerField(label="设备ID")
    start_time = serializers.CharField(label="开始时间")
    end_time = serializers.CharField(label="结束时间")
    purpose = serializers.CharField(label="用途说明", allow_blank=True, required=False, default="")
    urgency = serializers.ChoiceField(
        choices=Reservation.Urgency.choices, required=False, default=Reservation.Urgency.NORMAL
    )
    submit = serializers.BooleanField(label="是否直接提交", required=False, default=True)

    def validate(self, attrs):
        from apps.labs.models import Device, Laboratory

        if not attrs.get("purpose", "").strip() and attrs.get("submit", True):
            raise serializers.ValidationError({"purpose": "提交预约时请填写用途说明"})

        attrs["start_time"] = parse_datetime(attrs["start_time"])
        attrs["end_time"] = parse_datetime(attrs["end_time"])
        if not attrs["start_time"] or not attrs["end_time"]:
            raise serializers.ValidationError("时间格式不正确，应为 YYYY-MM-DD HH:mm")

        laboratory = Laboratory.objects.filter(pk=attrs["laboratory"]).first()
        if laboratory is None:
            raise serializers.ValidationError({"laboratory": "实验室不存在"})
        device = Device.objects.select_related("laboratory", "category").filter(pk=attrs["device"]).first()
        if device is None:
            raise serializers.ValidationError({"device": "设备不存在"})
        attrs["laboratory"] = laboratory
        attrs["device"] = device
        return attrs


class ReservationUpdateSerializer(serializers.Serializer):
    """修改暂存/被驳回的预约。"""

    laboratory = serializers.IntegerField(required=False)
    device = serializers.IntegerField(required=False)
    start_time = serializers.CharField(required=False)
    end_time = serializers.CharField(required=False)
    purpose = serializers.CharField(required=False, allow_blank=True)
    urgency = serializers.ChoiceField(choices=Reservation.Urgency.choices, required=False)

    def validate(self, attrs):
        reservation = self.context["reservation"]
        if "laboratory" in attrs:
            from apps.labs.models import Laboratory

            lab = Laboratory.objects.filter(pk=attrs["laboratory"]).first()
            if lab is None:
                raise serializers.ValidationError({"laboratory": "实验室不存在"})
            attrs["laboratory"] = lab
        if "device" in attrs:
            from apps.labs.models import Device

            device = Device.objects.filter(pk=attrs["device"]).first()
            if device is None:
                raise serializers.ValidationError({"device": "设备不存在"})
            attrs["device"] = device
        for field in ("start_time", "end_time"):
            if field in attrs:
                parsed = parse_datetime(attrs[field])
                if parsed is None:
                    raise serializers.ValidationError({field: "时间格式不正确"})
                attrs[field] = parsed

        attrs.setdefault("laboratory", reservation.laboratory)
        attrs.setdefault("device", reservation.device)
        attrs.setdefault("start_time", reservation.start_time)
        attrs.setdefault("end_time", reservation.end_time)
        return attrs


class ApproveSerializer(serializers.Serializer):
    approve_remark = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_approve_remark(self, value):
        return value


class RejectSerializer(serializers.Serializer):
    reject_reason = serializers.CharField(label="驳回原因")

    def validate_reject_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("驳回必须填写原因")
        return value.strip()


class TransferSerializer(serializers.Serializer):
    approver = serializers.IntegerField(label="被转派人ID")
    remark = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_approver(self, value):
        user = User.objects.filter(pk=value, is_active=True).first()
        if user is None:
            raise serializers.ValidationError("被转派用户不存在或已停用")
        if not (user.is_lab_admin or user.is_sys_admin):
            raise serializers.ValidationError("只能转派给实验室管理员或系统管理员")
        return value


class WithdrawSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class CancelSerializer(serializers.Serializer):
    cancel_reason = serializers.CharField(required=False, allow_blank=True, default="")


class SignInSerializer(serializers.Serializer):
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    device_status = serializers.ChoiceField(
        choices=[("available", "可预约"), ("repairing", "维修中")],
        required=False, default="available",
    )


class SignOutSerializer(serializers.Serializer):
    device_status_after = serializers.ChoiceField(
        label="使用后设备状态",
        choices=[("available", "可预约"), ("repairing", "维修中"), ("scrapped", "已报废")],
        default="available",
    )
    abnormal_note = serializers.CharField(
        label="异常情况说明", required=False, allow_blank=True, default=""
    )


class CompleteSerializer(serializers.Serializer):
    return_confirmed = serializers.BooleanField(label="设备是否已归还", default=True)
    device_status_after = serializers.ChoiceField(
        label="核验后的设备状态",
        choices=[("available", "可预约"), ("repairing", "维修中"), ("scrapped", "已报废")],
        required=False,
    )
    completion_remark = serializers.CharField(required=False, allow_blank=True, default="")


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_display = serializers.CharField(source="sender_name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id", "thread", "sender", "sender_name", "sender_display", "sender_role",
            "is_admin_side", "content", "image", "image_url", "reply_to", "is_read",
            "created_at",
        ]
        read_only_fields = ["thread", "sender", "sender_name", "sender_role",
                            "is_admin_side", "is_read", "created_at"]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class ChatThreadSerializer(serializers.ModelSerializer):
    reservation_no = serializers.CharField(source="reservation.no", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)
    applicant_name = serializers.CharField(source="reservation.applicant_name", read_only=True)
    device_name = serializers.CharField(source="reservation.device.name", read_only=True)
    laboratory_name = serializers.CharField(source="reservation.laboratory.name", read_only=True)
    last_sender_name = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatThread
        fields = [
            "id", "reservation", "reservation_no", "status", "status_display",
            "last_message_time", "last_sender", "last_sender_name", "message_count",
            "messages", "applicant_name", "device_name", "laboratory_name", "updated_at",
            "unread_count",
        ]

    def get_last_sender_name(self, obj):
        return (obj.last_sender.real_name or obj.last_sender.username) if obj.last_sender else ""

    def get_unread_count(self, obj):
        """当前用户未读的对方消息数（复用已预取的 messages，不产生额外查询）。"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        user_id = request.user.id
        return sum(1 for msg in obj.messages.all() if not msg.is_read and msg.sender_id != user_id)


class EvaluationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = ["device_score", "speed_score", "service_score", "content", "images"]

    def validate(self, attrs):
        for field in ("device_score", "speed_score", "service_score"):
            score = attrs.get(field, 5)
            if not 1 <= int(score) <= 5:
                raise serializers.ValidationError({field: "评分需在 1~5 之间"})
        return attrs


class EvaluationReplySerializer(serializers.Serializer):
    reply_content = serializers.CharField(label="回复内容")

    def validate_reply_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("回复内容不能为空")
        return value.strip()
