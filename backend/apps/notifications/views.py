"""站内提醒视图。"""
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer
from .services import scan_for_user


class NotificationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """站内提醒：列表、已读、未读、批量已读、清除。"""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)
        params = self.request.query_params
        if params.get("is_read") not in (None, ""):
            queryset = queryset.filter(is_read=params["is_read"] in ("1", "true", "True"))
        if params.get("notify_type"):
            queryset = queryset.filter(notify_type__in=params["notify_type"].split(","))
        if params.get("unread_only") == "1":
            queryset = queryset.filter(is_read=False)
        return queryset

    def list(self, request, *args, **kwargs):
        # 进入提醒中心时先做一次个人待办扫描，保证提醒及时且不重复
        if request.query_params.get("scan", "1") == "1":
            scan_for_user(request.user)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """未读数量，用于顶部铃铛角标。"""
        queryset = Notification.objects.filter(user=request.user)
        by_type = list(
            queryset.filter(is_read=False).values("notify_type")
            .annotate(count=Count("id")).order_by("-count")
        )
        type_map = dict(Notification.Type.choices)
        return Response(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "total": queryset.filter(is_read=False).count(),
                    "by_type": [
                        {"notify_type": item["notify_type"],
                         "notify_type_display": type_map.get(item["notify_type"], ""),
                         "count": item["count"]}
                        for item in by_type
                    ],
                },
            }
        )

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        """标记单条已读。"""
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_time = timezone.now()
            notification.save(update_fields=["is_read", "read_time"])
        return Response({"code": 0, "message": "已标记为已读", "data": None})

    @action(detail=True, methods=["post"], url_path="unread")
    def mark_unread(self, request, pk=None):
        """标记单条未读。"""
        notification = self.get_object()
        notification.is_read = False
        notification.read_time = None
        notification.save(update_fields=["is_read", "read_time"])
        return Response({"code": 0, "message": "已标记为未读", "data": None})

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        """全部标记已读。"""
        notify_type = request.data.get("notify_type")
        queryset = Notification.objects.filter(user=request.user, is_read=False)
        if notify_type:
            queryset = queryset.filter(notify_type=notify_type)
        count = queryset.update(is_read=True, read_time=timezone.now())
        return Response({"code": 0, "message": f"已标记 {count} 条为已读", "data": {"count": count}})

    @action(detail=False, methods=["post"], url_path="batch-read")
    def batch_read(self, request):
        """批量标记已读：ids=[1,2,3]"""
        ids = request.data.get("ids") or []
        count = Notification.objects.filter(
            user=request.user, id__in=ids, is_read=False
        ).update(is_read=True, read_time=timezone.now())
        return Response({"code": 0, "message": f"已标记 {count} 条为已读", "data": {"count": count}})

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        """清除已读提醒。"""
        count, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        return Response({"code": 0, "message": f"已清除 {count} 条提醒", "data": {"count": count}})

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """提醒总览：按类型统计已读/未读。"""
        queryset = Notification.objects.filter(user=request.user)
        data = list(
            queryset.values("notify_type").annotate(
                total=Count("id"),
                unread=Count("id", filter=Q(is_read=False)),
            ).order_by("-total")
        )
        type_map = dict(Notification.Type.choices)
        return Response(
            {
                "code": 0,
                "message": "success",
                "data": [
                    {
                        "notify_type": item["notify_type"],
                        "notify_type_display": type_map.get(item["notify_type"], ""),
                        "total": item["total"],
                        "unread": item["unread"],
                    }
                    for item in data
                ],
            }
        )
