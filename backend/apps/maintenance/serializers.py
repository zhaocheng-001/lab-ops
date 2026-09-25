"""运维模块序列化器。"""
from django.utils import timezone

from rest_framework import serializers

from apps.labs.models import Device, Laboratory

from .models import FaultReport, InspectRecord, MaintenanceOrder, MaintenancePlan


class FaultReportSerializer(serializers.ModelSerializer):
    """故障报修列表 / 详情。"""

    fault_type_display = serializers.CharField(source="get_fault_type_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True, default="")
    device_code = serializers.CharField(source="device.code", read_only=True, default="")
    laboratory_name = serializers.CharField(source="laboratory.name", read_only=True, default="")

    class Meta:
        model = FaultReport
        fields = [
            "id", "no", "device", "device_name", "device_code",
            "laboratory", "laboratory_name",
            "reporter", "reporter_name", "reporter_role", "reporter_phone",
            "fault_type", "fault_type_display",
            "severity", "severity_display",
            "description", "images",
            "status", "status_display",
            "order", "reject_reason",
            "created_at", "updated_at", "resolved_at",
        ]
        read_only_fields = [
            "no", "reporter", "reporter_name", "reporter_role",
            "order", "created_at", "updated_at", "resolved_at",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        validated_data["reporter"] = user
        validated_data["reporter_name"] = user.real_name or user.username
        validated_data["reporter_role"] = user.role
        if hasattr(user, "phone"):
            validated_data["reporter_phone"] = user.phone
        # 同时联动设备状态为「维修中」（便于在设备台账可见）
        device = validated_data["device"]
        if device.status == Device.Status.AVAILABLE:
            device.set_status(Device.Status.REPAIRING, operator=user, reason="故障报修触发")
        return super().create(validated_data)


class FaultReportCreateSerializer(serializers.ModelSerializer):
    """学生 / 教师发起报修的精简提交。"""

    class Meta:
        model = FaultReport
        fields = ["device", "fault_type", "severity", "description", "images"]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        instance = FaultReport(
            device=validated_data["device"],
            fault_type=validated_data.get("fault_type", FaultReport.FaultType.HARDWARE),
            severity=validated_data.get("severity", FaultReport.Severity.NORMAL),
            description=validated_data["description"],
            images=validated_data.get("images", []),
            reporter=user,
            reporter_name=user.real_name or user.username,
            reporter_role=user.role,
            reporter_phone=getattr(user, "phone", "") or "",
        )
        instance.save()
        return instance


class MaintenanceOrderSerializer(serializers.ModelSerializer):
    """维修工单。"""

    source_display = serializers.CharField(source="get_source_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True, default="")
    device_code = serializers.CharField(source="device.code", read_only=True, default="")
    laboratory_name = serializers.CharField(source="laboratory.name", read_only=True, default="")
    duration_hours = serializers.FloatField(read_only=True)
    response_minutes = serializers.IntegerField(read_only=True)
    fault_no = serializers.CharField(source="fault.no", read_only=True, default="")
    plan_name = serializers.CharField(source="plan.name", read_only=True, default="")

    class Meta:
        model = MaintenanceOrder
        fields = [
            "id", "no", "title", "source", "source_display",
            "device", "device_name", "device_code",
            "laboratory", "laboratory_name",
            "fault", "fault_no", "plan", "plan_name",
            "priority", "priority_display",
            "status", "status_display",
            "handler", "handler_name",
            "dispatcher", "dispatcher_name",
            "scheduled_time", "started_time", "completed_time", "verified_time", "verifier",
            "fault_desc", "solution", "parts_replaced", "cost", "images", "cancel_reason",
            "duration_hours", "response_minutes",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "no", "dispatcher", "dispatcher_name",
            "started_time", "completed_time", "verified_time", "verifier",
            "created_at", "updated_at",
        ]


class MaintenancePlanSerializer(serializers.ModelSerializer):
    """维保计划。"""

    cycle_display = serializers.CharField(source="get_cycle_display", read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True, default="")
    device_category_name = serializers.CharField(
        source="device_category.name", read_only=True, default="",
    )
    laboratory_name = serializers.CharField(source="laboratory.name", read_only=True, default="")
    is_overdue = serializers.BooleanField(read_only=True)
    overdue_days = serializers.IntegerField(read_only=True)
    completed_rate = serializers.SerializerMethodField()

    class Meta:
        model = MaintenancePlan
        fields = [
            "id", "name",
            "device", "device_name",
            "device_category", "device_category_name",
            "laboratory", "laboratory_name",
            "cycle", "cycle_display", "interval_days",
            "checklist", "responsible", "responsible_name",
            "next_due_date", "last_done_date",
            "is_overdue", "overdue_days", "completed_rate",
            "description", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_completed_rate(self, obj):
        from .models import InspectRecord

        total = InspectRecord.objects.filter(plan=obj).count()
        if total == 0:
            return 0
        normal = InspectRecord.objects.filter(plan=obj, result=InspectRecord.Result.NORMAL).count()
        return round(normal / total * 100, 1)


class InspectRecordSerializer(serializers.ModelSerializer):
    """巡检记录。"""

    result_display = serializers.CharField(source="get_result_display", read_only=True)
    laboratory_name = serializers.CharField(source="laboratory.name", read_only=True, default="")
    device_name = serializers.CharField(source="device.name", read_only=True, default="")
    plan_name = serializers.CharField(source="plan.name", read_only=True, default="")
    order_no = serializers.CharField(source="order.no", read_only=True, default="")

    class Meta:
        model = InspectRecord
        fields = [
            "id", "plan", "plan_name",
            "device", "device_name",
            "laboratory", "laboratory_name",
            "inspector", "inspector_name",
            "inspected_at", "result", "result_display",
            "issues", "checklist_result", "images",
            "order", "order_no", "created_at",
        ]
        read_only_fields = ["inspector", "inspector_name", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        validated_data["inspector"] = user
        validated_data["inspector_name"] = user.real_name or user.username
        record = super().create(validated_data)
        # 若是维保计划巡检，更新计划的上次执行日和下次到期日
        plan = record.plan
        if plan:
            plan.last_done_date = record.inspected_at.date()
            plan.next_due_date = plan.last_done_date + timezone.timedelta(days=plan.interval_days or 30)
            plan.save(update_fields=["last_done_date", "next_due_date", "updated_at"])
        return record