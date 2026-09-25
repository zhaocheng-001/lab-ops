from rest_framework import serializers

from .models import OperationLog


class OperationLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    lab_name = serializers.CharField(source="lab.name", read_only=True, default="")
    change_summary = serializers.SerializerMethodField()

    class Meta:
        model = OperationLog
        fields = [
            "id", "operator", "operator_name", "operator_role", "action", "action_display",
            "target_type", "target_id", "target_repr", "lab", "lab_name", "detail",
            "change_summary", "remark", "ip", "created_at",
        ]

    def get_change_summary(self, obj):
        """把变更明细拼成可读文本，例如：状态: 待审批 → 已通过；审批人: 空 → 张三"""
        if not obj.detail:
            return ""
        parts = []
        for field, values in obj.detail.items():
            if isinstance(values, (list, tuple)) and len(values) == 2:
                old, new = values
                if str(old) == str(new):
                    parts.append(f"{field}: {new}")
                else:
                    parts.append(f"{field}: {old or '空'} → {new or '空'}")
            else:
                parts.append(f"{field}: {values}")
        return "；".join(parts)
