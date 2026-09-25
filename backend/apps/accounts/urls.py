from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    ClassGroupViewSet,
    CollegeViewSet,
    LogoutView,
    ProfileView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("colleges", CollegeViewSet, basename="college")
router.register("classes", ClassGroupViewSet, basename="class-group")

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", include(router.urls)),
]
