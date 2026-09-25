"""查阅与修改日志模型：记录谁在什么时间查阅或修改了哪条预约、改了哪些字段。"""
from django.conf import settings
from django.db import models


class OperationLog(models.Model):
    """操作日志"""

    class Action(models.TextChoices):
        VIEW = "view", "查阅"
        CREATE = "create", "新增"
        UPDATE = "update", "修改"
        DELETE = "delete", "删除"
        SUBMIT = "submit", "提交"
        WITHDRAW = "withdraw", "撤回"
        APPROVE = "approve", "审批通过"
        REJECT = "reject", "审批驳回"
        TRANSFER = "transfer", "转派"
        CANCEL = "cancel", "取消"
        SIGN_IN = "sign_in", "签到"
        SIGN_OUT = "sign_out", "签退"
        COMPLETE = "complete", "完工确认"
        EVALUATE = "evaluate", "评价"
        MESSAGE = "message", "沟通"
        IMPORT = "import", "导入"
        EXPORT = "export", "导出"
        LOGIN = "login", "登录"

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_logs",
        verbose_name="操作者",
    )
    operator_name = models.CharField("操作者名称", max_length=64, blank=True, default="")
    operator_role = models.CharField("操作者角色", max_length=16, blank=True, default="")
    action = models.CharField("操作类型", max_length=16, choices=Action.choices, db_index=True)
    target_type = models.CharField("目标类型", max_length=32, blank=True, default="")
    target_id = models.BigIntegerField("目标ID", blank=True, null=True, db_index=True)
    target_repr = models.CharField("目标描述", max_length=255, blank=True, default="")
    lab = models.ForeignKey(
        "labs.Laboratory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_logs",
        verbose_name="所属实验室",
    )
    detail = models.JSONField("变更明细", default=dict, blank=True)
    remark = models.CharField("说明", max_length=255, blank=True, default="")
    ip = models.CharField("IP地址", max_length=64, blank=True, default="")
    user_agent = models.CharField("客户端", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("操作时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "sys_operation_log"
        verbose_name = "操作日志"
        verbose_name_plural = verbose_name
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["operator", "created_at"]),
        ]

    def __str__(self):
        return f"{self.operator_name}-{self.get_action_display()}-{self.target_repr}"
