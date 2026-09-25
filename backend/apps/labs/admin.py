from django.contrib import admin

from .models import Device, DeviceCategory, Laboratory


@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "sort_order")
    search_fields = ("name", "code")


@admin.register(Laboratory)
class LaboratoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "location", "capacity", "open_time_start",
                    "open_time_end", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "location")
    filter_horizontal = ("managers",)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "model", "category", "laboratory", "status", "is_active")
    list_filter = ("status", "is_active", "category", "laboratory")
    search_fields = ("code", "name", "model")
