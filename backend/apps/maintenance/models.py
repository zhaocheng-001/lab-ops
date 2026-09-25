"""设备运维数据模型。

- FaultReport: 故障报修（任何角色发起）
- MaintenanceOrder: 维修工单（管理员处理闭环）
- MaintenancePlan: 维保计划（周期性预防维护）
- InspectRecord: 巡检记录（例行巡检 / 计划执行）
"""
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


_no_counter = {"i": 0}


def _gen_no(prefix: str) -> str:
    """生成业务编号：{prefix}-yyyyMMddHHmmss-序号，避免同秒冲突。"""
    _no_counter["i"] += 1
    return datetime.now().strftime(f"{prefix}-%Y%m%d%H%M%S") + f"-{_no_counter['i']:03d}"


class FaultReport(models.Model):
    """设备故障报修单。"""

    class FaultType(models.TextChoices):
        HARDWARE = "hardware", "硬件故障"
        SOFTWARE = "software", "软件故障"
        OPERATION = "operation", "操作异常"
        OTHER = "other", "其他"

    class Severity(models.TextChoices):
        NORMAL = "normal", "一般"
        HIGH = "high", "严重"
        URGENT = "urgent", "紧急"

    class Status(models.TextChoices):
        PENDING = "pending", "待派单"
        DISPATCHED = "dispatched", "已派单"
        REPAIRING = "repairing", "维修中"
        RESOLVED = "resolved", "已修复"
        CLOSED = "closed", "已关闭"
        REJECTED = "rejected", "已驳回"

    no = models.CharField("报修编号", max_length=32, unique=True, db_index=True)
    device = models.ForeignKey(
        "labs.Device", on_delete=models.PROTECT,
        related_name="fault_reports", verbose_name="故障设备",
    )
    laboratory = models.ForeignKey(
        "labs.Laboratory", on_delete=models.PROTECT,
        related_name="fault_reports", verbose_name="所属实验室",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fault_reports", verbose_name="报修人",
    )
    reporter_name = models.CharField("报修人姓名", max_length=32, blank=True, default="")
    reporter_role = models.CharField("报修人角色", max_length=16, blank=True, default="")
    reporter_phone = models.CharField("联系电话", max_length=11, blank=True, default="")

    fault_type = models.CharField(
        "故障类别", max_length=16, choices=FaultType.choices, default=FaultType.HARDWARE,
    )
    severity = models.CharField(
        "严重程度", max_length=8, choices=Severity.choices, default=Severity.NORMAL, db_index=True,
    )
    description = models.TextField("故障描述")
    images = models.JSONField("现场图片", default=list, blank=True)

    status = models.CharField(
        "状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True,
    )
    order = models.ForeignKey(
        "MaintenanceOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="source_faults", verbose_name="关联工单",
    )

    reject_reason = models.CharField("驳回原因", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("报修时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    resolved_at = models.DateTimeField("解决时间", blank=True, null=True)

    class Meta:
        db_table = "ops_fault_report"
        verbose_name = "故障报修"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.no} {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.no:
            self.no = _gen_no("FR")
        if self.device_id and not self.laboratory_id:
            self.laboratory_id = self.device.laboratory_id
        super().save(*args, **kwargs)


class MaintenanceOrder(models.Model):
    """维修工单（运维核心流程）。"""

    class Source(models.TextChoices):
        FAULT = "fault", "故障报修"
        INSPECT = "inspect", "巡检发现"
        PLAN = "plan", "计划性维护"
        ROUTINE = "routine", "主动维护"

    class Priority(models.TextChoices):
        P3 = "P3", "P3 / 低"
        P2 = "P2", "P2 / 中"
        P1 = "P1", "P1 / 高"
        P0 = "P0", "P0 / 紧急"

    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        PROCESSING = "processing", "处理中"
        RESOLVED = "resolved", "已修复"
        VERIFIED = "verified", "已验收"
        CANCELLED = "cancelled", "已取消"

    no = models.CharField("工单编号", max_length=32, unique=True, db_index=True)
    title = models.CharField("工单标题", max_length=128)
    source = models.CharField("来源", max_length=16, choices=Source.choices, default=Source.FAULT)
    device = models.ForeignKey(
        "labs.Device", on_delete=models.PROTECT,
        related_name="maintenance_orders", verbose_name="设备",
    )
    laboratory = models.ForeignKey(
        "labs.Laboratory", on_delete=models.PROTECT,
        related_name="maintenance_orders", verbose_name="实验室",
    )
    fault = models.ForeignKey(
        FaultReport, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders", verbose_name="关联报修",
    )
    plan = models.ForeignKey(
        "MaintenancePlan", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders", verbose_name="关联计划",
    )
    priority = models.CharField(
        "优先级", max_length=4, choices=Priority.choices, default=Priority.P2, db_index=True,
    )
    status = models.CharField(
        "状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True,
    )

    handler = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="handled_orders", verbose_name="处理人",
    )
    handler_name = models.CharField("处理人姓名", max_length=32, blank=True, default="")
    dispatcher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="dispatched_orders", verbose_name="派单人",
    )
    dispatcher_name = models.CharField("派单人姓名", max_length=32, blank=True, default="")

    scheduled_time = models.DateTimeField("计划开始时间", blank=True, null=True)
    started_time = models.DateTimeField("实际开始时间", blank=True, null=True)
    completed_time = models.DateTimeField("修复完成时间", blank=True, null=True)
    verified_time = models.DateTimeField("验收时间", blank=True, null=True)
    verifier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="verified_orders", verbose_name="验收人",
    )

    fault_desc = models.TextField("故障描述", blank=True, default="")
    solution = models.TextField("处理方案", blank=True, default="")
    parts_replaced = models.CharField("更换配件", max_length=255, blank=True, default="")
    cost = models.DecimalField("维修费用(元)", max_digits=10, decimal_places=2, default=0)
    images = models.JSONField("过程图片", default=list, blank=True)
    cancel_reason = models.CharField("取消原因", max_length=255, blank=True, default="")

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "ops_maintenance_order"
        verbose_name = "维修工单"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["device", "status"]),
        ]

    def __str__(self):
        return f"{self.no} {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.no:
            self.no = _gen_no("WO")
        super().save(*args, **kwargs)

    @property
    def duration_hours(self):
        if not self.started_time or not self.completed_time:
            return 0
        return round((self.completed_time - self.started_time).total_seconds() / 3600, 2)

    @property
    def response_minutes(self):
        """响应时长：从创建到开始处理。"""
        if not self.started_time:
            return 0
        return int((self.started_time - self.created_at).total_seconds() // 60)


class MaintenancePlan(models.Model):
    """维保计划：周期性预防维护。"""

    class Cycle(models.TextChoices):
        WEEKLY = "weekly", "每周"
        MONTHLY = "monthly", "每月"
        QUARTERLY = "quarterly", "每季度"
        SEMI_YEARLY = "semi_yearly", "每半年"
        YEARLY = "yearly", "每年"

    name = models.CharField("计划名称", max_length=128)
    device = models.ForeignKey(
        "labs.Device", on_delete=models.CASCADE, null=True, blank=True,
        related_name="maintenance_plans", verbose_name="适用设备",
    )
    device_category = models.ForeignKey(
        "labs.DeviceCategory", on_delete=models.CASCADE, null=True, blank=True,
        related_name="maintenance_plans", verbose_name="适用分类",
    )
    laboratory = models.ForeignKey(
        "labs.Laboratory", on_delete=models.CASCADE, null=True, blank=True,
        related_name="maintenance_plans", verbose_name="适用实验室",
    )
    cycle = models.CharField("周期", max_length=16, choices=Cycle.choices, default=Cycle.MONTHLY)
    interval_days = models.PositiveIntegerField("间隔天数", default=30)
    checklist = models.JSONField("检查清单", default=list, blank=True,
                                  help_text="每项：{item: 名称, required: 是否必须}")
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="maintenance_plans", verbose_name="负责人",
    )
    responsible_name = models.CharField("负责人姓名", max_length=32, blank=True, default="")
    next_due_date = models.DateField("下次到期日", db_index=True)
    last_done_date = models.DateField("上次执行日", blank=True, null=True)
    description = models.CharField("说明", max_length=255, blank=True, default="")
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "ops_maintenance_plan"
        verbose_name = "维保计划"
        verbose_name_plural = verbose_name
        ordering = ["next_due_date", "id"]

    def __str__(self):
        return f"{self.name}（{self.get_cycle_display()}）"

    @property
    def is_overdue(self):
        return self.is_active and self.next_due_date < date.today()

    @property
    def overdue_days(self):
        if not self.is_overdue:
            return 0
        return (date.today() - self.next_due_date).days

    def save(self, *args, **kwargs):
        # 若未指定下次到期日，根据周期推算
        if not self.next_due_date:
            base = self.last_done_date or date.today()
            self.next_due_date = base + timedelta(days=self.interval_days or 30)
        super().save(*args, **kwargs)


class InspectRecord(models.Model):
    """巡检记录（针对设备 / 计划的执行结果）。"""

    class Result(models.TextChoices):
        NORMAL = "normal", "正常"
        ABNORMAL = "abnormal", "异常"
        NEED_REPAIR = "need_repair", "需维修"

    plan = models.ForeignKey(
        MaintenancePlan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="records", verbose_name="对应计划",
    )
    device = models.ForeignKey(
        "labs.Device", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inspect_records", verbose_name="巡检设备",
    )
    laboratory = models.ForeignKey(
        "labs.Laboratory", on_delete=models.PROTECT,
        related_name="inspect_records", verbose_name="实验室",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inspect_records", verbose_name="巡检人",
    )
    inspector_name = models.CharField("巡检人姓名", max_length=32, blank=True, default="")
    inspected_at = models.DateTimeField("巡检时间", db_index=True)
    result = models.CharField(
        "巡检结果", max_length=16, choices=Result.choices, default=Result.NORMAL, db_index=True,
    )
    issues = models.TextField("问题描述", blank=True, default="")
    checklist_result = models.JSONField("清单执行结果", default=list, blank=True)
    images = models.JSONField("现场图片", default=list, blank=True)
    order = models.ForeignKey(
        MaintenanceOrder, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="source_records", verbose_name="派生的工单",
    )
    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)

    class Meta:
        db_table = "ops_inspect_record"
        verbose_name = "巡检记录"
        verbose_name_plural = verbose_name
        ordering = ["-inspected_at"]

    def __str__(self):
        return f"{self.laboratory.name} {self.inspected_at:%Y-%m-%d} {self.get_result_display()}"