"""实验室与设备管理数据模型。"""
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class DeviceCategory(models.Model):
    """设备分类"""

    name = models.CharField("分类名称", max_length=64, unique=True)
    code = models.CharField("分类编码", max_length=32, blank=True, default="")
    description = models.CharField("说明", max_length=255, blank=True, default="")
    sort_order = models.IntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "lab_device_category"
        verbose_name = "设备分类"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class Laboratory(models.Model):
    """实验室"""

    WEEKDAY_CHOICES = [
        ("1", "周一"), ("2", "周二"), ("3", "周三"),
        ("4", "周四"), ("5", "周五"), ("6", "周六"), ("7", "周日"),
    ]

    name = models.CharField("实验室名称", max_length=64, unique=True)
    code = models.CharField("实验室编号", max_length=32, unique=True)
    location = models.CharField("位置", max_length=128)
    capacity = models.PositiveIntegerField("容纳人数", default=30)
    open_time_start = models.TimeField("开放开始时间", default=datetime(2000, 1, 1, 8, 0).time())
    open_time_end = models.TimeField("开放结束时间", default=datetime(2000, 1, 1, 22, 0).time())
    open_weekdays = models.CharField(
        "开放日（1-7，逗号分隔）", max_length=32, default="1,2,3,4,5"
    )
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="managed_labs",
        verbose_name="负责管理员",
        limit_choices_to={"role": "lab_admin"},
    )
    image = models.ImageField("实验室图片", upload_to="labs/%Y%m/", blank=True, null=True)
    description = models.TextField("实验室简介", blank=True, default="")
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "lab_laboratory"
        verbose_name = "实验室"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self):
        return f"{self.name}({self.code})"

    @property
    def open_weekday_list(self):
        return [int(x) for x in self.open_weekdays.split(",") if x.strip().isdigit()]

    @property
    def device_count(self):
        return self.devices.filter(is_active=True).count()

    @property
    def available_device_count(self):
        return self.devices.filter(is_active=True, status=Device.Status.AVAILABLE).count()

    def is_open_at(self, moment):
        """判断某时刻是否处于开放时段（开放日 + 开放时间）。"""
        if moment.isoweekday() not in self.open_weekday_list:
            return False
        return self.open_time_start <= moment.time() <= self.open_time_end

    def clean(self):
        if self.open_time_start and self.open_time_end:
            if self.open_time_start >= self.open_time_end:
                raise ValidationError({"open_time_end": "开放结束时间必须晚于开始时间"})


class Device(models.Model):
    """设备台账"""

    class Status(models.TextChoices):
        AVAILABLE = "available", "可预约"
        REPAIRING = "repairing", "维修中"
        SCRAPPED = "scrapped", "已报废"

    code = models.CharField("设备编号", max_length=64, unique=True)
    name = models.CharField("设备名称", max_length=128)
    model = models.CharField("型号", max_length=128, blank=True, default="")
    category = models.ForeignKey(
        DeviceCategory,
        on_delete=models.PROTECT,
        related_name="devices",
        verbose_name="设备分类",
    )
    laboratory = models.ForeignKey(
        Laboratory, on_delete=models.CASCADE, related_name="devices", verbose_name="所属实验室"
    )
    status = models.CharField(
        "设备状态", max_length=16, choices=Status.choices, default=Status.AVAILABLE, db_index=True
    )
    image = models.ImageField("设备图片", upload_to="devices/%Y%m/", blank=True, null=True)
    specification = models.CharField("规格参数", max_length=255, blank=True, default="")
    manufacturer = models.CharField("生产厂商", max_length=128, blank=True, default="")
    purchase_date = models.DateField("购置日期", blank=True, null=True)
    price = models.DecimalField("单价(元)", max_digits=12, decimal_places=2, default=0)
    remark = models.CharField("备注", max_length=255, blank=True, default="")
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "lab_device"
        verbose_name = "设备"
        verbose_name_plural = verbose_name
        ordering = ["id"]
        indexes = [models.Index(fields=["laboratory", "status"])]

    def __str__(self):
        return f"{self.name}({self.code})"

    @property
    def is_bookable(self):
        """是否可被预约。"""
        return self.is_active and self.status == self.Status.AVAILABLE

    def is_busy_at(self, start_time, end_time, exclude_reservation_id=None):
        """判断指定时间段内是否存在有效占用。"""
        from apps.reservations.models import Reservation

        active_statuses = [
            Reservation.Status.PENDING,
            Reservation.Status.APPROVED,
            Reservation.Status.WAITING_USE,
            Reservation.Status.IN_USE,
        ]
        queryset = Reservation.objects.filter(
            device=self, status__in=active_statuses,
            start_time__lt=end_time, end_time__gt=start_time,
        )
        if exclude_reservation_id:
            queryset = queryset.exclude(pk=exclude_reservation_id)
        return queryset.exists()

    def next_available_time(self, from_time=None):
        """预计可用时间：返回当前占用结束时间，空闲则返回 None。"""
        from apps.reservations.models import Reservation

        from_time = from_time or timezone.now()
        active_statuses = [
            Reservation.Status.PENDING,
            Reservation.Status.APPROVED,
            Reservation.Status.WAITING_USE,
            Reservation.Status.IN_USE,
        ]
        current = (
            Reservation.objects.filter(
                device=self,
                status__in=active_statuses,
                start_time__lte=from_time,
                end_time__gt=from_time,
            )
            .order_by("-end_time")
            .first()
        )
        return current.end_time if current else None

    def set_status(self, status, operator=None, reason=""):
        """变更设备状态并写入操作日志。"""
        if status == self.status:
            return
        old_display = self.get_status_display()
        self.status = status
        self.save(update_fields=["status", "updated_at"])
        from apps.auditlog.services import log_operation

        log_operation(
            operator=operator,
            action="update",
            target_type="device",
            target_id=self.id,
            target_repr=str(self),
            lab=self.laboratory,
            detail={"设备状态": [old_display, self.get_status_display()]},
            remark=reason or "设备状态变更",
        )
