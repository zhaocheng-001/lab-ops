"""账号与权限：学院、班级、用户（学生/教师/实验室管理员/系统管理员）。"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models


class College(models.Model):
    """学院"""

    name = models.CharField("学院名称", max_length=64, unique=True)
    code = models.CharField("学院代码", max_length=32, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "sys_college"
        verbose_name = "学院"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self):
        return self.name


class ClassGroup(models.Model):
    """班级"""

    name = models.CharField("班级名称", max_length=64)
    college = models.ForeignKey(
        College, on_delete=models.CASCADE, related_name="classes", verbose_name="所属学院"
    )
    grade = models.CharField("年级", max_length=16, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "sys_class_group"
        verbose_name = "班级"
        verbose_name_plural = verbose_name
        unique_together = ("name", "college")
        ordering = ["id"]

    def __str__(self):
        return f"{self.college.name}-{self.name}"


class UserManager(BaseUserManager):
    """自定义用户管理器，使用 username 作为登录名。"""

    use_in_migrations = True

    def _create_user(self, username, password, **extra_fields):
        if not username:
            raise ValueError("必须填写登录账号")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, password, **extra_fields)

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.SYS_ADMIN)
        extra_fields.setdefault("real_name", "系统管理员")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("超级用户必须 is_staff=True")
        return self._create_user(username, password, **extra_fields)


class User(AbstractUser):
    """系统用户，通过 role 字段区分四类角色。"""

    class Role(models.TextChoices):
        STUDENT = "student", "学生"
        TEACHER = "teacher", "教师"
        LAB_ADMIN = "lab_admin", "实验室管理员"
        SYS_ADMIN = "sys_admin", "系统管理员"

    phone_validator = RegexValidator(
        r"^1[3-9]\d{9}$", "请输入正确的 11 位手机号"
    )

    real_name = models.CharField("姓名", max_length=32, default="")
    role = models.CharField(
        "角色", max_length=16, choices=Role.choices, default=Role.STUDENT, db_index=True
    )
    phone = models.CharField(
        "手机号", max_length=11, blank=True, default="", validators=[phone_validator]
    )
    # 学生：学院 / 班级 / 学号
    college = models.ForeignKey(
        College,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="所属学院",
    )
    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="所属班级",
    )
    student_no = models.CharField("学号/工号", max_length=32, blank=True, default="", db_index=True)
    avatar = models.ImageField("头像", upload_to="avatars/%Y%m/", blank=True, null=True)
    last_login_ip = models.CharField("最后登录IP", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    # 角色常量别名，方便其它模块引用
    ROLE_STUDENT = Role.STUDENT
    ROLE_TEACHER = Role.TEACHER
    ROLE_LAB_ADMIN = Role.LAB_ADMIN
    ROLE_SYS_ADMIN = Role.SYS_ADMIN

    objects = UserManager()

    class Meta:
        db_table = "sys_user"
        verbose_name = "用户"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self):
        return f"{self.real_name or self.username}({self.get_role_display()})"

    # ---------------- 便捷属性 ----------------
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_lab_admin(self):
        return self.role == self.Role.LAB_ADMIN

    @property
    def is_sys_admin(self):
        return self.role == self.Role.SYS_ADMIN or self.is_superuser

    @property
    def is_applicant(self):
        """是否为可提交预约的角色（学生/教师）。"""
        return self.role in (self.Role.STUDENT, self.Role.TEACHER)

    @property
    def managed_lab_ids(self):
        """该管理员负责的实验室 ID 列表。"""
        if self.is_sys_admin:
            from apps.labs.models import Laboratory

            return list(Laboratory.objects.values_list("id", flat=True))
        return list(self.managed_labs.values_list("id", flat=True))

    @property
    def max_reserve_hours(self):
        """单次预约时长上限（小时）。"""
        from django.conf import settings

        return settings.ROLE_MAX_RESERVE_HOURS.get(self.role, 4)
