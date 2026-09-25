"""实验室与设备序列化器。"""
from rest_framework import serializers

from apps.accounts.models import User

from .models import Device, DeviceCategory, Laboratory


class LaboratoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Laboratory
        fields = ["id", "name", "code", "location"]


class LaboratorySerializer(serializers.ModelSerializer):
    manager_names = serializers.SerializerMethodField()
    manager_ids = serializers.PrimaryKeyRelatedField(
        source="managers", many=True, queryset=User.objects.all(), required=False, write_only=True
    )
    open_weekday_display = serializers.SerializerMethodField()
    device_count = serializers.IntegerField(read_only=True)
    available_device_count = serializers.IntegerField(read_only=True)
    manager_list = serializers.SerializerMethodField()

    class Meta:
        model = Laboratory
        fields = [
            "id", "name", "code", "location", "capacity",
            "open_time_start", "open_time_end", "open_weekdays", "open_weekday_display",
            "managers", "manager_ids", "manager_names", "manager_list",
            "image", "description", "is_active", "device_count",
            "available_device_count", "created_at", "updated_at",
        ]
        read_only_fields = ["managers", "created_at", "updated_at"]

    def get_manager_names(self, obj):
        return [u.real_name or u.username for u in obj.managers.all()]

    def get_manager_list(self, obj):
        return [
            {"id": u.id, "name": u.real_name or u.username}
            for u in obj.managers.all()
        ]

    def get_open_weekday_display(self, obj):
        mapping = dict(Laboratory.WEEKDAY_CHOICES)
        return "、".join(mapping.get(d, d) for d in obj.open_weekdays.split(",") if d.strip())

    def validate(self, attrs):
        start = attrs.get("open_time_start", getattr(self.instance, "open_time_start", None))
        end = attrs.get("open_time_end", getattr(self.instance, "open_time_end", None))
        if start and end and start >= end:
            raise serializers.ValidationError({"open_time_end": "开放结束时间必须晚于开始时间"})
        weekdays = attrs.get("open_weekdays", getattr(self.instance, "open_weekdays", "1,2,3,4,5"))
        days = [d.strip() for d in weekdays.split(",") if d.strip()]
        if not days or any(d not in "1234567" for d in days):
            raise serializers.ValidationError({"open_weekdays": "开放日只能是 1-7 的逗号分隔数字"})
        return attrs


class DeviceCategorySerializer(serializers.ModelSerializer):
    device_count = serializers.SerializerMethodField()

    class Meta:
        model = DeviceCategory
        fields = ["id", "name", "code", "description", "sort_order", "device_count", "created_at"]
        read_only_fields = ["created_at"]

    def get_device_count(self, obj):
        return obj.devices.filter(is_active=True).count()


class DeviceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    laboratory_name = serializers.CharField(source="laboratory.name", read_only=True)
    manager_names = serializers.SerializerMethodField()
    current_occupied_until = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            "id", "code", "name", "model", "category", "category_name",
            "laboratory", "laboratory_name", "status", "status_display",
            "image", "specification", "manufacturer", "purchase_date", "price",
            "remark", "is_active", "manager_names", "current_occupied_until",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_manager_names(self, obj):
        return [u.real_name or u.username for u in obj.laboratory.managers.all()]

    def get_current_occupied_until(self, obj):
        until = obj.next_available_time()
        return until.strftime("%Y-%m-%d %H:%M:%S") if until else None


class DeviceSimpleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    laboratory_name = serializers.CharField(source="laboratory.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Device
        fields = [
            "id", "code", "name", "model", "category", "category_name",
            "laboratory", "laboratory_name", "status", "status_display", "image",
        ]


class DeviceImportResultSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    success = serializers.IntegerField()
    failed = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField())
