"""预约申请 / 审批 / 使用进度 / 图文沟通 / 完工评价 数据模型。"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.labs.models import Device, Laboratory


class Reservation(models.Model):
    """预约单"""

    class Status(models.TextChoices):
        DRAFT = "draft", "暂存"
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"
        WAITING_USE = "waiting_use", "待使用"
        IN_USE = "in_use", "使用中"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已取消"

    class Urgency(models.TextChoices):
        NORMAL = "normal", "普通"
        URGENT = "urgent", "紧急"

    # 会占用设备的有效状态（冲突判定依据）
    ACTIVE_STATUSES = ["pending", "approved", "waiting_use", "in_use"]
    FINISHED_STATUSES = ["rejected", "completed", "cancelled"]
    # 已进入审批流程的状态
    SUBMITTED_STATUSES = ["pending", "approved", "rejected", "waiting_use", "in_use", "completed", "cancelled"]

    no = models.CharField("预约编号", max_length=32, unique=True, db_index=True)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="reservations", verbose_name="预约人",
    )
    applicant_name = models.CharField("预约人姓名", max_length=32, blank=True, default="")
    applicant_role = models.CharField("预约人角色", max_length=16, blank=True, default="")
    college_name = models.CharField("所属学院", max_length=64, blank=True, default="")
    class_name = models.CharField("所属班级", max_length=64, blank=True, default="")
    contact_phone = models.CharField("联系电话", max_length=11, blank=True, default="")

    laboratory = models.ForeignKey(
        Laboratory, on_delete=models.PROTECT, related_name="reservations", verbose_name="实验室"
    )
    device = models.ForeignKey(
        Device, on_delete=models.PROTECT, related_name="reservations", verbose_name="设备"
    )
    start_time = models.DateTimeField("开始时间", db_index=True)
    end_time = models.DateTimeField("结束时间", db_index=True)
    purpose = models.TextField("用途说明", blank=True, default="")
    urgency = models.CharField(
        "紧急程度", max_length=8, choices=Urgency.choices, default=Urgency.NORMAL
    )
    status = models.CharField(
        "预约状态", max_length=16, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_reservations", verbose_name="审批人",
    )
    approver_name = models.CharField("审批人姓名", max_length=32, blank=True, default="")
    approve_time = models.DateTimeField("审批时间", blank=True, null=True)
    approve_remark = models.CharField("审批意见", max_length=255, blank=True, default="")
    reject_reason = models.CharField("驳回原因", max_length=255, blank=True, default="")
    transferred_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transferred_to", verbose_name="转派来源",
    )

    submit_time = models.DateTimeField("提交时间", blank=True, null=True)
    withdraw_time = models.DateTimeField("撤回时间", blank=True, null=True)
    cancel_reason = models.CharField("取消原因", max_length=255, blank=True, default="")

    sign_in_time = models.DateTimeField("签到时间", blank=True, null=True)
    sign_out_time = models.DateTimeField("签退时间", blank=True, null=True)
    device_status_after = models.CharField(
        "使用后设备状态", max_length=16, blank=True, default="", choices=Device.Status.choices
    )
    abnormal_note = models.CharField("异常情况说明", max_length=255, blank=True, default="")

    completion_time = models.DateTimeField("完工确认时间", blank=True, null=True)
    completion_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="completed_reservations", verbose_name="完工确认人",
    )
    return_confirmed = models.BooleanField("设备已归还", default=False)
    completion_remark = models.CharField("完工备注", max_length=255, blank=True, default="")

    is_evaluated = models.BooleanField("是否已评价", default=False, db_index=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "biz_reservation"
        verbose_name = "预约单"
        verbose_name_plural = verbose_name
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["device", "start_time", "end_time"]),
            models.Index(fields=["applicant", "status"]),
            models.Index(fields=["laboratory", "status"]),
        ]

    def __str__(self):
        return f"{self.no}"

    # ---------------- 属性 ----------------
    @property
    def duration_hours(self):
        if not self.start_time or not self.end_time:
            return 0
        return round((self.end_time - self.start_time).total_seconds() / 3600, 2)

    @property
    def status_display(self):
        return self.get_status_display()

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_overdue(self):
        """是否逾期：已通过/待使用/使用中，且已过结束时间仍未完成。"""
        if self.status not in (self.Status.APPROVED, self.Status.WAITING_USE, self.Status.IN_USE):
            return False
        return bool(self.end_time and timezone.now() > self.end_time)

    @property
    def overdue_minutes(self):
        if not self.is_overdue:
            return 0
        return int((timezone.now() - self.end_time).total_seconds() // 60)

    @property
    def progress_percent(self):
        """使用进度百分比。"""
        if self.status == self.Status.COMPLETED:
            return 100
        if self.status in (self.Status.REJECTED, self.Status.CANCELLED):
            return 0
        total = (self.end_time - self.start_time).total_seconds()
        if total <= 0:
            return 0
        elapsed = (timezone.now() - self.start_time).total_seconds()
        return max(0, min(100, round(elapsed / total * 100)))

    @property
    def can_withdraw(self):
        """未审批的预约可撤回。"""
        return self.status == self.Status.PENDING

    @property
    def can_evaluate(self):
        return self.status == self.Status.COMPLETED and not self.is_evaluated

    @property
    def can_sign_in(self):
        return self.status in (self.Status.APPROVED, self.Status.WAITING_USE)


class ReservationStatusLog(models.Model):
    """预约状态流转记录。"""

    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE, related_name="status_logs", verbose_name="预约单"
    )
    from_status = models.CharField("原状态", max_length=16, blank=True, default="")
    to_status = models.CharField("新状态", max_length=16, blank=True, default="")
    action = models.CharField("操作", max_length=32, blank=True, default="")
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reservation_status_logs", verbose_name="操作人",
    )
    operator_name = models.CharField("操作人姓名", max_length=32, blank=True, default="")
    remark = models.CharField("说明", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        db_table = "biz_reservation_status_log"
        verbose_name = "预约状态流转"
        verbose_name_plural = verbose_name
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.reservation_id}: {self.from_status}->{self.to_status}"


class ChatThread(models.Model):
    """预约沟通会话（一个预约单一条会话）。"""

    class Status(models.TextChoices):
        PENDING_REPLY = "pending_reply", "待回复"
        REPLIED = "replied", "已回复"
        CLOSED = "closed", "已结束"

    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="chat_thread", verbose_name="预约单"
    )
    status = models.CharField(
        "会话状态", max_length=16, choices=Status.choices, default=Status.PENDING_REPLY
    )
    last_message_time = models.DateTimeField("最后消息时间", blank=True, null=True)
    last_sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="chat_threads", verbose_name="最后发言人",
    )
    message_count = models.IntegerField("消息数", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "biz_chat_thread"
        verbose_name = "沟通会话"
        verbose_name_plural = verbose_name
        ordering = ["-last_message_time", "-id"]

    def __str__(self):
        return f"会话-{self.reservation.no}"


class ChatMessage(models.Model):
    """预约图文沟通消息。"""

    thread = models.ForeignKey(
        ChatThread, on_delete=models.CASCADE, related_name="messages", verbose_name="会话"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="chat_messages", verbose_name="发送人",
    )
    sender_name = models.CharField("发送人姓名", max_length=32, blank=True, default="")
    sender_role = models.CharField("发送人角色", max_length=16, blank=True, default="")
    is_admin_side = models.BooleanField("是否为管理员发言", default=False)
    content = models.TextField("内容", blank=True, default="")
    image = models.ImageField("图片", upload_to="chat/%Y%m/", blank=True, null=True)
    reply_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="replies", verbose_name="回复的消息",
    )
    is_read = models.BooleanField("对方是否已读", default=False)
    created_at = models.DateTimeField("发送时间", auto_now_add=True)

    class Meta:
        db_table = "biz_chat_message"
        verbose_name = "沟通消息"
        verbose_name_plural = verbose_name
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.sender_name}: {self.content[:20]}"


class Evaluation(models.Model):
    """学生对完工预约的评价。"""

    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="evaluation", verbose_name="预约单"
    )
    device_score = models.PositiveSmallIntegerField("设备状态评分", default=5)
    speed_score = models.PositiveSmallIntegerField("响应速度评分", default=5)
    service_score = models.PositiveSmallIntegerField("管理服务评分", default=5)
    average_score = models.DecimalField("综合评分", max_digits=3, decimal_places=1, default=5.0)
    content = models.TextField("文字评价", blank=True, default="")
    images = models.JSONField("评价图片", default=list, blank=True)
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="evaluations", verbose_name="评价人",
    )
    evaluator_name = models.CharField("评价人姓名", max_length=32, blank=True, default="")
    reply_content = models.TextField("管理员回复", blank=True, default="")
    reply_time = models.DateTimeField("回复时间", blank=True, null=True)
    created_at = models.DateTimeField("评价时间", auto_now_add=True)

    class Meta:
        db_table = "biz_evaluation"
        verbose_name = "完工评价"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"评价-{self.reservation.no}-{self.average_score}"

    def compute_average(self):
        total = self.device_score + self.speed_score + self.service_score
        return round(total / 3, 1)
