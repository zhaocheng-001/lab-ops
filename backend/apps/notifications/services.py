"""站内提醒服务：去重创建、自动扫描待办。"""
import datetime
import logging

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

LEVEL_BY_TYPE = {
    "overdue": "danger",
    "expiring": "warning",
    "pending_return": "warning",
    "rejected": "warning",
}


def create_notification(user, notify_type, title, content="", reservation=None,
                        dedupe_key=None, level="info"):
    """
    创建一条站内提醒。
    - 通过 dedupe_key 唯一约束避免重复提醒。
    """
    if user is None:
        return None
    level = level or LEVEL_BY_TYPE.get(notify_type, "info")
    try:
        notification = Notification.objects.create(
            user=user,
            notify_type=notify_type,
            title=title,
            content=content,
            level=level,
            reservation=reservation,
            reservation_no=reservation.no if reservation else "",
            dedupe_key=dedupe_key,
        )
        return notification
    except IntegrityError:
        # 已存在相同提醒，直接跳过，实现“避免重复提醒”
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("创建站内提醒失败：%s", exc)
        return None


def scan_pending_sign_in(now=None):
    """扫描待签到：已通过/待使用且临近开始时间。"""
    from apps.reservations.models import Reservation

    now = now or timezone.now()
    before = now + datetime.timedelta(minutes=settings.REMIND_SIGN_IN_BEFORE_MINUTES)
    queryset = Reservation.objects.filter(
        status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE],
        start_time__lte=before,
        start_time__gte=now - datetime.timedelta(hours=1),
    ).select_related("applicant", "device", "laboratory")

    count = 0
    for reservation in queryset:
        result = create_notification(
            user=reservation.applicant,
            notify_type=Notification.Type.PENDING_SIGN_IN,
            title="预约即将开始，请及时签到",
            content=(
                f"预约 {reservation.no}（{reservation.device.name}，"
                f"{reservation.laboratory.name}）将于 {reservation.start_time.strftime('%Y-%m-%d %H:%M')} 开始，"
                "请按时到实验室签到。"
            ),
            reservation=reservation,
            dedupe_key=f"sign_in:{reservation.id}",
            level="info",
        )
        if result:
            count += 1
    return count


def scan_pending_return(now=None):
    """扫描待归还：使用中且临近结束时间。"""
    from apps.reservations.models import Reservation

    now = now or timezone.now()
    before = now + datetime.timedelta(minutes=settings.REMIND_RETURN_BEFORE_MINUTES)
    queryset = Reservation.objects.filter(
        status=Reservation.Status.IN_USE, end_time__lte=before, end_time__gt=now
    ).select_related("applicant", "device", "laboratory")

    count = 0
    for reservation in queryset:
        result = create_notification(
            user=reservation.applicant,
            notify_type=Notification.Type.PENDING_RETURN,
            title="预约即将到期，请按时归还设备",
            content=(
                f"预约 {reservation.no}（{reservation.device.name}）将于 "
                f"{reservation.end_time.strftime('%Y-%m-%d %H:%M')} 到期，请及时签退并归还设备。"
            ),
            reservation=reservation,
            dedupe_key=f"return:{reservation.id}",
            level="warning",
        )
        if result:
            count += 1
    return count


def scan_expiring(now=None):
    """即将到期：未签到且开始时间已过、结束时间临近（30 分钟内）。"""
    from apps.reservations.models import Reservation

    now = now or timezone.now()
    before = now + datetime.timedelta(minutes=settings.REMIND_RETURN_BEFORE_MINUTES)
    queryset = Reservation.objects.filter(
        status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE],
        end_time__lte=before,
        end_time__gt=now,
    ).select_related("applicant", "device")

    count = 0
    for reservation in queryset:
        result = create_notification(
            user=reservation.applicant,
            notify_type=Notification.Type.EXPIRING,
            title="预约即将到期（尚未签到）",
            content=(
                f"预约 {reservation.no} 将于 {reservation.end_time.strftime('%Y-%m-%d %H:%M')} 结束，"
                "若无法使用请及时取消，避免影响后续预约。"
            ),
            reservation=reservation,
            dedupe_key=f"expiring:{reservation.id}",
            level="warning",
        )
        if result:
            count += 1
    return count


def scan_overdue(now=None):
    """已逾期：超过结束时间仍未签退完成。"""
    from apps.reservations.models import Reservation

    now = now or timezone.now()
    deadline = now - datetime.timedelta(minutes=settings.OVERDUE_GRACE_MINUTES)
    queryset = Reservation.objects.filter(
        status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                    Reservation.Status.IN_USE],
        end_time__lt=deadline,
    ).select_related("applicant", "device", "laboratory").prefetch_related("laboratory__managers")

    count = 0
    for reservation in queryset:
        minutes = int((now - reservation.end_time).total_seconds() // 60)
        result = create_notification(
            user=reservation.applicant,
            notify_type=Notification.Type.OVERDUE,
            title="预约已逾期",
            content=(
                f"预约 {reservation.no}（{reservation.device.name}）已超过结束时间 {minutes} 分钟，"
                "请尽快签退归还设备。"
            ),
            reservation=reservation,
            dedupe_key=f"overdue:{reservation.id}",
            level="danger",
        )
        if result:
            count += 1
        # 同步提醒管理员
        for manager in reservation.laboratory.managers.all():
            create_notification(
                user=manager,
                notify_type=Notification.Type.OVERDUE,
                title="有预约逾期未归还",
                content=(
                    f"{reservation.applicant_name} 的预约 {reservation.no}"
                    f"（{reservation.device.name}）已逾期 {minutes} 分钟，请跟进处理。"
                ),
                reservation=reservation,
                dedupe_key=f"overdue_admin:{reservation.id}:{manager.id}",
                level="danger",
            )
    return count


def scan_maintenance_overdue(now=None):
    """维保计划逾期：超过 next_due_date 仍未执行的，通知负责人 + 实验室管理员。"""
    from apps.maintenance.models import MaintenancePlan

    now = now or timezone.now()
    today = now.date()
    queryset = MaintenancePlan.objects.filter(
        is_active=True, next_due_date__lt=today,
    ).select_related("device", "device_category", "laboratory", "responsible")

    count = 0
    for plan in queryset:
        overdue_days = (today - plan.next_due_date).days
        scope = (
            plan.device.name if plan.device_id
            else (plan.device_category.name if plan.device_category_id
                  else (plan.laboratory.name if plan.laboratory_id else "全局"))
        )
        # 负责人
        if plan.responsible_id:
            create_notification(
                user=plan.responsible,
                notify_type=Notification.Type.OVERDUE,
                title="维保计划已逾期",
                content=(
                    f"计划「{plan.name}」（{scope}，{plan.get_cycle_display()}）"
                    f"已逾期 {overdue_days} 天，请尽快执行。"
                ),
                dedupe_key=f"plan_overdue:{plan.id}",
                level="warning",
            )
            count += 1
        # 实验室管理员
        if plan.laboratory_id:
            for manager in plan.laboratory.managers.all():
                create_notification(
                    user=manager,
                    notify_type=Notification.Type.OVERDUE,
                    title="维保计划已逾期",
                    content=(
                        f"计划「{plan.name}」（{scope}）已逾期 {overdue_days} 天，"
                        f"请跟进 {plan.responsible_name or '负责人'}。"
                    ),
                    dedupe_key=f"plan_overdue_admin:{plan.id}:{manager.id}",
                    level="warning",
                )
                count += 1
    return count


def scan_pending_approval(now=None):
    """待审批提醒（给管理员，按预约维度去重）。"""
    from apps.reservations.models import Reservation

    queryset = Reservation.objects.filter(
        status=Reservation.Status.PENDING
    ).select_related("laboratory").prefetch_related("laboratory__managers")

    count = 0
    for reservation in queryset:
        for manager in reservation.laboratory.managers.all():
            result = create_notification(
                user=manager,
                notify_type=Notification.Type.PENDING_APPROVAL,
                title="有预约待审批",
                content=(
                    f"预约 {reservation.no}（{reservation.applicant_name}·"
                    f"{reservation.device.name}）等待审批。"
                ),
                reservation=reservation,
                dedupe_key=f"pending_approval:{reservation.id}:{manager.id}",
            )
            if result:
                count += 1
    return count


def run_all_scanners():
    """执行全部扫描任务，返回统计结果。"""
    result = {
        "pending_approval": scan_pending_approval(),
        "pending_sign_in": scan_pending_sign_in(),
        "pending_return": scan_pending_return(),
        "expiring": scan_expiring(),
        "overdue": scan_overdue(),
        "maintenance_overdue": scan_maintenance_overdue(),
    }
    logger.info("站内提醒扫描完成：%s", result)
    return result


def scan_for_user(user):
    """针对单个用户执行相关扫描（进入系统时即时生成提醒）。"""
    from apps.reservations.models import Reservation

    now = timezone.now()
    if user.is_applicant:
        before_sign = now + datetime.timedelta(minutes=settings.REMIND_SIGN_IN_BEFORE_MINUTES)
        for reservation in Reservation.objects.filter(
            applicant=user,
            status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE],
            start_time__lte=before_sign,
            start_time__gte=now - datetime.timedelta(hours=1),
        ):
            create_notification(
                user=user,
                notify_type=Notification.Type.PENDING_SIGN_IN,
                title="预约即将开始，请及时签到",
                content=f"预约 {reservation.no} 将于 "
                        f"{reservation.start_time.strftime('%Y-%m-%d %H:%M')} 开始。",
                reservation=reservation,
                dedupe_key=f"sign_in:{reservation.id}",
            )
        for reservation in Reservation.objects.filter(
            applicant=user, status=Reservation.Status.IN_USE,
            end_time__lte=now + datetime.timedelta(minutes=settings.REMIND_RETURN_BEFORE_MINUTES),
            end_time__gt=now,
        ):
            create_notification(
                user=user,
                notify_type=Notification.Type.PENDING_RETURN,
                title="预约即将到期，请按时归还设备",
                content=f"预约 {reservation.no} 将于 "
                        f"{reservation.end_time.strftime('%Y-%m-%d %H:%M')} 到期。",
                reservation=reservation,
                dedupe_key=f"return:{reservation.id}",
                level="warning",
            )
    if user.is_lab_admin or user.is_sys_admin:
        labs = user.managed_lab_ids
        for reservation in Reservation.objects.filter(
            status=Reservation.Status.PENDING, laboratory_id__in=labs
        ):
            create_notification(
                user=user,
                notify_type=Notification.Type.PENDING_APPROVAL,
                title="有预约待审批",
                content=f"预约 {reservation.no}（{reservation.applicant_name}）等待审批。",
                reservation=reservation,
                dedupe_key=f"pending_approval:{reservation.id}:{user.id}",
            )
        # 管理员 / 系统管理员：维保计划逾期即时提醒
        from apps.maintenance.models import MaintenancePlan
        today = now.date()
        plan_qs = MaintenancePlan.objects.filter(
            is_active=True, next_due_date__lt=today,
        ).select_related("device", "device_category", "laboratory")
        if user.is_sys_admin:
            plans = plan_qs
        else:
            plans = plan_qs.filter(laboratory_id__in=labs)
        for plan in plans:
            scope = (
                plan.device.name if plan.device_id
                else (plan.device_category.name if plan.device_category_id
                      else (plan.laboratory.name if plan.laboratory_id else "全局"))
            )
            overdue_days = (today - plan.next_due_date).days
            create_notification(
                user=user,
                notify_type=Notification.Type.OVERDUE,
                title="维保计划已逾期",
                content=(
                    f"计划「{plan.name}」（{scope}）已逾期 {overdue_days} 天，"
                    f"请提醒 {plan.responsible_name or '负责人'} 执行。"
                ),
                dedupe_key=f"plan_overdue_admin:{plan.id}:{user.id}",
                level="warning",
            )
