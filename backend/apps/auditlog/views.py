"""日志查询视图：支持按操作者、实验室和时间查询。"""
import datetime

from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import OperationLog
from .serializers import OperationLogSerializer


class OperationLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    操作日志（只读）。
    - 系统管理员：查看全部
    - 实验室管理员：查看本人负责实验室 + 本人操作的日志
    - 学生/教师：仅查看自己的日志
    """

    serializer_class = OperationLogSerializer
    permission_classes = [IsAuthenticated]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = OperationLog.objects.select_related("operator", "lab")
        user = self.request.user
        if user.is_sys_admin:
            pass
        elif user.is_lab_admin:
            queryset = queryset.filter(Q(lab__in=user.managed_lab_ids) | Q(operator=user))
        else:
            queryset = queryset.filter(operator=user)

        params = self.request.query_params
        operator = params.get("operator")
        lab = params.get("lab")
        target_type = params.get("target_type")
        target_id = params.get("target_id")
        action_type = params.get("action")
        keyword = params.get("keyword")
        start = params.get("start_date")
        end = params.get("end_date")

        if operator:
            condition = Q(operator_name__icontains=operator)
            if str(operator).isdigit():
                condition |= Q(operator_id=int(operator))
            queryset = queryset.filter(condition)
        if lab:
            queryset = queryset.filter(lab_id=lab)
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        if action_type:
            queryset = queryset.filter(action__in=action_type.split(","))
        if keyword:
            queryset = queryset.filter(
                Q(target_repr__icontains=keyword)
                | Q(remark__icontains=keyword)
                | Q(operator_name__icontains=keyword)
            )
        if start:
            queryset = queryset.filter(created_at__date__gte=to_date(start))
        if end:
            queryset = queryset.filter(created_at__date__lte=to_date(end))
        return queryset

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """日志概览：按操作类型统计。"""
        from django.db.models import Count

        queryset = self.get_queryset()
        data = list(
            queryset.values("action").annotate(count=Count("id")).order_by("-count")
        )
        action_map = dict(OperationLog.Action.choices)
        return Response(
            {
                "code": 0,
                "message": "success",
                "data": [
                    {"action": item["action"], "action_display": action_map.get(item["action"], item["action"]),
                     "count": item["count"]}
                    for item in data
                ],
            }
        )


def to_date(value):
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
