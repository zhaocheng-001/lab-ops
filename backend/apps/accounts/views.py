"""账号与权限视图。"""
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ClassGroup, College, User
from .permissions import IsLabAdminOrSystemAdmin, IsSystemAdmin
from .serializers import (
    ChangePasswordSerializer,
    ClassGroupSerializer,
    CollegeSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    ResetPasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
    build_user_filter,
)


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class LoginView(APIView):
    """登录：返回 JWT 与当前用户信息。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        ip = get_client_ip(request)
        User.objects.filter(pk=user.pk).update(last_login_ip=ip)
        user.last_login_ip = ip

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "code": 0,
                "message": "登录成功",
                "data": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": UserSerializer(user).data,
                },
            }
        )


class LogoutView(APIView):
    """退出登录：客户端清除 token；服务端记录日志。"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:  # noqa: BLE001 - 黑名单未启用时忽略
                pass
        return Response({"code": 0, "message": "已退出登录", "data": None})


class ProfileView(APIView):
    """当前登录用户资料：查看与修改。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"code": 0, "message": "success", "data": UserSerializer(request.user).data})

    def put(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"code": 0, "message": "资料已更新", "data": UserSerializer(request.user).data})


class ChangePasswordView(APIView):
    """修改密码。"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"code": 0, "message": "密码修改成功，请使用新密码重新登录", "data": None})


class UserViewSet(viewsets.ModelViewSet):
    """
    用户管理：
    - 系统管理员：可增删改查全部用户
    - 实验室管理员：只能查看学生/教师信息
    """

    queryset = User.objects.select_related("college", "class_group").prefetch_related("managed_labs")
    permission_classes = [IsAuthenticated]
    search_fields = ["username", "real_name", "student_no", "phone"]
    ordering_fields = ["id", "created_at", "username"]
    ordering = ["-id"]

    def get_permissions(self):
        # simple 仅用于下拉选择（如实验室负责管理员、转派审批人），实验室管理员也需要使用
        if self.action in ("list", "retrieve", "simple"):
            return [IsLabAdminOrSystemAdmin()]
        return [IsSystemAdmin()]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_sys_admin:
            # 实验室管理员只能看到非管理员账号
            queryset = queryset.exclude(role__in=[User.Role.LAB_ADMIN, User.Role.SYS_ADMIN])
        queryset = queryset.filter(build_user_filter(self.request.query_params)).distinct()
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"code": 0, "message": "用户创建成功", "data": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"code": 0, "message": "用户信息已更新", "data": UserSerializer(user).data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.pk == request.user.pk:
            return Response(
                {"code": 400, "message": "不能删除当前登录账号", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        return Response({"code": 0, "message": "该账号已停用", "data": None})

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """系统管理员重置指定用户密码。"""
        user = self.get_object()
        serializer = ResetPasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"code": 0, "message": "密码已重置", "data": None})

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        """启用/停用账号。"""
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response(
                {"code": 400, "message": "不能停用当前登录账号", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = not user.is_active
        user.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"code": 0, "message": "账号已启用" if user.is_active else "账号已停用", "data": {"is_active": user.is_active}}
        )

    @action(detail=False, methods=["get"], url_path="simple")
    def simple(self, request):
        """精简用户列表，用于下拉选择（如转派审批人）。"""
        queryset = User.objects.filter(is_active=True)
        if not request.user.is_sys_admin:
            # 非系统管理员不暴露系统管理员账号
            queryset = queryset.exclude(role=User.Role.SYS_ADMIN)
        role = request.query_params.get("role")
        if role:
            queryset = queryset.filter(role__in=role.split(","))
        data = [
            {"id": u.id, "real_name": u.real_name or u.username, "username": u.username,
             "role": u.role, "role_display": u.get_role_display()}
            for u in queryset.order_by("id")
        ]
        return Response({"code": 0, "message": "success", "data": data})


class CollegeViewSet(viewsets.ModelViewSet):
    """学院管理。"""

    queryset = College.objects.all()
    serializer_class = CollegeSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "code"]
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsSystemAdmin()]


class ClassGroupViewSet(viewsets.ModelViewSet):
    """班级管理。"""

    queryset = ClassGroup.objects.select_related("college").all()
    serializer_class = ClassGroupSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "grade"]
    filterset_fields = ["college"]

    def get_queryset(self):
        queryset = super().get_queryset()
        college = self.request.query_params.get("college_id")
        if college:
            queryset = queryset.filter(college_id=college)
        return queryset

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsSystemAdmin()]
