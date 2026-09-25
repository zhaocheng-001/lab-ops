"""运维子模块 URL 路由。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    FaultReportViewSet,
    InspectRecordViewSet,
    MaintenanceOrderViewSet,
    MaintenancePlanViewSet,
)

router = DefaultRouter()
router.register("faults", FaultReportViewSet, basename="fault")
router.register("orders", MaintenanceOrderViewSet, basename="order")
router.register("plans", MaintenancePlanViewSet, basename="plan")
router.register("records", InspectRecordViewSet, basename="record")

urlpatterns = [path("", include(router.urls))]