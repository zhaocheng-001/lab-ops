from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminDashboardViewSet,
    DeviceCategoryViewSet,
    DeviceViewSet,
    LaboratoryViewSet,
)

router = DefaultRouter()
router.register("", LaboratoryViewSet, basename="laboratory")
router.register("devices", DeviceViewSet, basename="device")
router.register("categories", DeviceCategoryViewSet, basename="device-category")
router.register("dashboard", AdminDashboardViewSet, basename="dashboard")

urlpatterns = [path("", include(router.urls))]
