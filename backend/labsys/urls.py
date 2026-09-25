"""根路由配置。"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    # 认证
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/labs/", include("apps.labs.urls")),
    path("api/reservations/", include("apps.reservations.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/audit-logs/", include("apps.auditlog.urls")),
    path("api/statistics/", include("apps.statistics.urls")),
    path("api/maintenance/", include("apps.maintenance.urls")),
    path("api/common/", include("apps.common.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
