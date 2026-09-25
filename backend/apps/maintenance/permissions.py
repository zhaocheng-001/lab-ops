"""运维模块权限类。"""
from rest_framework.permissions import BasePermission

from apps.accounts.permissions import IsAdminRole, scope_queryset_by_user


class IsReporterOrAdmin(BasePermission):
    """报修本人或管理员可见/编辑。"""

    message = "仅报修本人或管理员可访问"

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_sys_admin or user.is_lab_admin:
            return True
        return obj.reporter_id == user.id


class IsMaintenanceAdmin(BasePermission):
    """维修工单处理权限：实验室管理员/系统管理员。"""

    message = "仅管理员可处理维修工单"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and IsAdminRole().has_permission(request, view))


def scope_orders(queryset, user):
    """维修工单按用户可见范围裁剪。"""
    return scope_queryset_by_user(queryset, user, applicant_field=None, lab_field="laboratory")


def scope_inspect_records(queryset, user):
    return scope_queryset_by_user(queryset, user, applicant_field=None, lab_field="laboratory")