"""角色相关权限类。"""
from rest_framework.permissions import BasePermission


class IsSystemAdmin(BasePermission):
    """仅系统管理员。"""

    message = "仅系统管理员可执行该操作"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_sys_admin)


class IsLabAdminOrSystemAdmin(BasePermission):
    """实验室管理员或系统管理员。"""

    message = "仅实验室管理员可执行该操作"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_lab_admin or user.is_sys_admin)
        )


class IsApplicant(BasePermission):
    """学生或教师（可提交预约）。"""

    message = "仅学生或教师可执行该操作"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_applicant)


class IsAdminRole(BasePermission):
    """任意管理角色（实验室管理员 / 系统管理员）。"""

    message = "需要管理员权限"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_lab_admin or user.is_sys_admin)
        )


class RolePermission(BasePermission):
    """通用角色校验：视图上声明 `allowed_roles = [...]`。"""

    message = "当前角色无权访问该资源"

    def has_permission(self, request, view):
        allowed = getattr(view, "allowed_roles", None)
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if allowed is None:
            return True
        return user.role in allowed or user.is_sys_admin


def scope_queryset_by_user(queryset, user, applicant_field="applicant", lab_field="lab"):
    """
    数据访问范围限制：
    - 学生 / 教师：只能看到自己的数据
    - 实验室管理员：只能看到自己负责实验室的数据
    - 系统管理员：全部
    """
    if user.is_sys_admin:
        return queryset
    if user.is_lab_admin:
        lab_field_path = f"{lab_field}__in" if lab_field else None
        if lab_field_path:
            return queryset.filter(**{lab_field_path: user.managed_lab_ids})
        return queryset.none()
    if applicant_field:
        return queryset.filter(**{applicant_field: user})
    return queryset.none()
