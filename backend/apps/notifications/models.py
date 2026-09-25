"""站内提醒模型。"""
from django.conf import settings
from django.db import models


class Notification(models.Model):
    """站内消息提醒"""

    class Type(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "待审批"
        APPROVAL_RESULT = "approval_result", "审批结果"
        TRANSFER_APPROVAL = "transfer_approval", "转派审批"
        PENDING_SIGN_IN = "pending_sign_in", "待签到"
        PENDING_RETURN = "pending_return", "待归还"
        EXPIRING = "expiring", "即将到期"
        OVERDUE = "overdue", "已逾期"
        PENDING_EVALUATE = "pending_evaluate", "待评价"
        CHAT_MESSAGE = "chat_message", "沟通消息"
        SYSTEM = "system", "系统通知"

    LEVELS = [
        ("info", "普通"),
        ("warning", "警告"),
        ("danger", "紧急"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications", verbose_name="接收人",
    )
    notify_type = models.CharField("提醒类型", max_length=24, choices=Type.choices, db_index=True)
    title = models.CharField("标题", max_length=128)
    content = models.TextField("内容", blank=True, default="")
    level = models.CharField("级别", max_length=8, choices=LEVELS, default="info")
    reservation = models.ForeignKey(
        "reservations.Reservation", on_delete=models.CASCADE, null=True, blank=True,
        related_name="notifications", verbose_name="关联预约单",
    )
    reservation_no = models.CharField("预约编号", max_length=32, blank=True, default="")
    dedupe_key = models.CharField("去重标识", max_length=128, unique=True, null=True, blank=True)
    is_read = models.BooleanField("是否已读", default=False, db_index=True)
    read_time = models.DateTimeField("阅读时间", blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "sys_notification"
        verbose_name = "站内提醒"
        verbose_name_plural = verbose_name
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.user_id}-{self.get_notify_type_display()}-{self.title}"
