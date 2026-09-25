"""账号模块序列化器。"""
from django.contrib.auth import authenticate, password_validation
from django.db.models import Q
from rest_framework import serializers

from .models import ClassGroup, College, User


class CollegeSerializer(serializers.ModelSerializer):
    class Meta:
        model = College
        fields = ["id", "name", "code", "remark", "created_at"]
        read_only_fields = ["created_at"]


class ClassGroupSerializer(serializers.ModelSerializer):
    college_name = serializers.CharField(source="college.name", read_only=True)

    class Meta:
        model = ClassGroup
        fields = ["id", "name", "college", "college_name", "grade", "remark", "created_at"]
        read_only_fields = ["created_at"]


class ManagedLabBriefSerializer(serializers.Serializer):
    """负责实验室简要信息。"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    location = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    """用户详情/列表。"""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    college_name = serializers.CharField(source="college.name", read_only=True, default="")
    class_group_name = serializers.CharField(source="class_group.name", read_only=True, default="")
    managed_labs = serializers.SerializerMethodField()
    max_reserve_hours = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "real_name", "role", "role_display", "phone",
            "college", "college_name", "class_group", "class_group_name",
            "student_no", "avatar", "email", "is_active", "managed_labs",
            "max_reserve_hours", "last_login", "last_login_ip", "remark",
            "created_at", "updated_at",
        ]
        read_only_fields = ["last_login", "last_login_ip", "created_at", "updated_at"]

    def get_managed_labs(self, obj):
        if obj.role != User.Role.LAB_ADMIN:
            return []
        return [
            {"id": lab.id, "name": lab.name, "location": lab.location}
            for lab in obj.managed_labs.all()
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """新增用户。"""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    lab_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "password", "real_name", "role", "phone",
            "college", "class_group", "student_no", "email", "is_active",
            "remark", "lab_ids",
        ]

    def validate(self, attrs):
        role = attrs.get("role", User.Role.STUDENT)
        if role == User.Role.STUDENT:
            if not attrs.get("student_no"):
                raise serializers.ValidationError({"student_no": "学生必须填写学号"})
            if not attrs.get("college"):
                raise serializers.ValidationError({"college": "学生必须选择所属学院"})
        if role == User.Role.LAB_ADMIN and not attrs.get("lab_ids"):
            raise serializers.ValidationError({"lab_ids": "实验室管理员必须至少负责一个实验室"})
        class_group = attrs.get("class_group")
        college = attrs.get("college")
        if class_group and college and class_group.college_id != college.id:
            raise serializers.ValidationError({"class_group": "班级所属学院与所选学院不一致"})
        return attrs

    def create(self, validated_data):
        lab_ids = validated_data.pop("lab_ids", [])
        password = validated_data.pop("password", "") or "123456"
        validated_data["username"] = validated_data["username"].strip()
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if user.role == User.Role.LAB_ADMIN and lab_ids:
            from apps.labs.models import Laboratory

            user.managed_labs.set(Laboratory.objects.filter(id__in=lab_ids))
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    lab_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True
    )

    class Meta:
        model = User
        fields = [
            "real_name", "role", "phone", "college", "class_group",
            "student_no", "email", "is_active", "remark", "avatar", "lab_ids",
        ]

    def validate(self, attrs):
        user = self.instance
        role = attrs.get("role", user.role)
        college = attrs.get("college", user.college)
        class_group = attrs.get("class_group", user.class_group)
        if role == User.Role.STUDENT and college is None:
            raise serializers.ValidationError({"college": "学生必须选择所属学院"})
        if class_group and college and class_group.college_id != college.id:
            raise serializers.ValidationError({"class_group": "班级所属学院与所选学院不一致"})
        return attrs

    def update(self, instance, validated_data):
        lab_ids = validated_data.pop("lab_ids", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if lab_ids is not None:
            from apps.labs.models import Laboratory

            instance.managed_labs.set(Laboratory.objects.filter(id__in=lab_ids))
        return instance


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(label="登录账号")
    password = serializers.CharField(label="密码", write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("账号或密码错误")
        if not user.is_active:
            raise serializers.ValidationError("该账号已被停用，请联系系统管理员")
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(label="原密码", write_only=True)
    new_password = serializers.CharField(label="新密码", write_only=True, min_length=6)
    confirm_password = serializers.CharField(label="确认新密码", write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("原密码不正确")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "两次输入的新密码不一致"})
        if attrs["new_password"] == attrs["old_password"]:
            raise serializers.ValidationError({"new_password": "新密码不能与原密码相同"})
        password_validation.validate_password(attrs["new_password"], self.context["request"].user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return user


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(label="新密码", write_only=True, min_length=6)

    def save(self, **kwargs):
        user = self.context["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return user


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["real_name", "phone", "email", "avatar"]


class SimpleUserSerializer(serializers.ModelSerializer):
    """其它模块内嵌展示用的极简用户信息。"""

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "real_name", "role", "role_display", "phone", "student_no"]


def build_user_filter(params):
    """构造用户检索条件。"""
    query = Q()
    role = params.get("role")
    keyword = params.get("keyword")
    college = params.get("college")
    class_group = params.get("class_group")
    is_active = params.get("is_active")
    lab = params.get("lab")

    if role:
        query &= Q(role=role)
    if keyword:
        query &= (
            Q(username__icontains=keyword)
            | Q(real_name__icontains=keyword)
            | Q(student_no__icontains=keyword)
            | Q(phone__icontains=keyword)
        )
    if college:
        query &= Q(college_id=college)
    if class_group:
        query &= Q(class_group_id=class_group)
    if is_active not in (None, ""):
        query &= Q(is_active=str(is_active).lower() in ("1", "true", "yes"))
    if lab and role == User.Role.LAB_ADMIN:
        query &= Q(managed_labs__id=lab)
    return query
