"""中间件：自动记录对预约单的查阅行为。"""
import re

from django.conf import settings

from .services import log_operation

# 匹配 /api/reservations/<id>/ 形式的详情访问
DETAIL_PATTERN = re.compile(r"^/api/reservations/(?P<pk>\d+)/?$")
# 需要记录查阅的其它资源
RESOURCE_PATTERNS = [
    (re.compile(r"^/api/labs/(?P<pk>\d+)/?$"), "laboratory"),
    (re.compile(r"^/api/labs/devices/(?P<pk>\d+)/?$"), "device"),
]


class AuditLogMiddleware:
    """记录用户对关键业务对象的查阅（只读 GET 请求）。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_log(request, response)
        except Exception:  # noqa: BLE001 - 日志失败不影响响应
            pass
        return response

    def _maybe_log(self, request, response):
        if not getattr(settings, "AUDIT_LOG_ENABLED", True):
            return
        if request.method != "GET" or response.status_code != 200:
            return
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return

        path = request.path
        match = DETAIL_PATTERN.match(path)
        if match:
            pk = int(match.group("pk"))
            self._log_reservation_view(request, user, pk)
            return

        for pattern, target_type in RESOURCE_PATTERNS:
            m = pattern.match(path)
            if m:
                log_operation(
                    operator=user,
                    action="view",
                    target_type=target_type,
                    target_id=int(m.group("pk")),
                    target_repr=f"{target_type}#{m.group('pk')}",
                    remark="查阅资源详情",
                    request=request,
                )
                return

    def _log_reservation_view(self, request, user, pk):
        from apps.reservations.models import Reservation

        reservation = (
            Reservation.objects.select_related("laboratory", "device", "applicant")
            .filter(pk=pk)
            .first()
        )
        if reservation is None:
            return
        log_operation(
            operator=user,
            action="view",
            target_type="reservation",
            target_id=reservation.id,
            target_repr=reservation.no,
            lab=reservation.laboratory,
            detail={"预约编号": [reservation.no, reservation.no]},
            remark=f"查阅预约单 {reservation.no}（{reservation.applicant_name}）",
            request=request,
        )
