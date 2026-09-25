"""运维子模块应用配置。"""
from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    name = "apps.maintenance"
    verbose_name = "设备运维"