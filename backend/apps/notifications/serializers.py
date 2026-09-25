from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    notify_type_display = serializers.CharField(source="get_notify_type_display", read_only=True)
    level_display = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "notify_type", "notify_type_display", "title", "content",
            "level", "level_display", "reservation", "reservation_no",
            "is_read", "read_time", "created_at",
        ]
