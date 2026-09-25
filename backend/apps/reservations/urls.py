from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChatViewSet, EvaluationViewSet, ReservationViewSet

router = DefaultRouter()
router.register("", ReservationViewSet, basename="reservation")
router.register("chats", ChatViewSet, basename="chat")
router.register("evaluations", EvaluationViewSet, basename="evaluation")

urlpatterns = [path("", include(router.urls))]
