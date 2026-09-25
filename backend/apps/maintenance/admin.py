"""运维模块 Django Admin。"""
from django.contrib import admin

from .models import FaultReport, InspectRecord, MaintenanceOrder, MaintenancePlan


@admin.register(FaultReport)
class FaultReportAdmin(admin.ModelAdmin):
    list_display = ("no", "device", "severity", "fault_type", "status", "reporter_name", "created_at")
    list_filter = ("status", "severity", "fault_type")
    search_fields = ("no", "reporter_name", "device__name")


@admin.register(MaintenanceOrder)
class MaintenanceOrderAdmin(admin.ModelAdmin):
    list_display = ("no", "title", "device", "priority", "status", "handler_name", "created_at")
    list_filter = ("status", "priority", "source")
    search_fields = ("no", "title", "handler_name")


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = ("name", "cycle", "interval_days", "next_due_date", "is_active")
    list_filter = ("cycle", "is_active")
    search_fields = ("name",)


@admin.register(InspectRecord)
class InspectRecordAdmin(admin.ModelAdmin):
    list_display = ("laboratory", "device", "result", "inspector_name", "inspected_at")
    list_filter = ("result",)
    search_fields = ("inspector_name", "device__name")