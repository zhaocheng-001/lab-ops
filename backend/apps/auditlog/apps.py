from django.apps import AppConfig


class AuditlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditlog"
    verbose_name = "查阅与修改日志"
