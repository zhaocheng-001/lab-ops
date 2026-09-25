"""预约业务服务层：编号生成、冲突校验、状态流转、通知派发。"""
import datetime
import random

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.auditlog.services import log_operation
from apps.labs.models import Device

from .models import ChatThread, Reservation, ReservationStatusLog

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d",
)

STATUS_TEXT = dict(Reservation.Status.choices)


class ReservationError(Exception):
    """业务校验异常。"""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


def parse_datetime(value):
    """解析前端传入的时间字符串（兼容多种格式）。"""
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return _ensure_naive(value)
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time(8, 0))
    text = str(value).strip().replace("Z", "")
    if "+" in text:
        text = text.split("+")[0].strip()
    for fmt in DATETIME_FORMATS:
        try:
            return _ensure_naive(datetime.datetime.strptime(text, fmt))
        except ValueError:
            continue
    try:
        from django.utils.dateparse import parse_datetime as dj_parse

        parsed = dj_parse(str(value))
        return _ensure_naive(parsed) if parsed else None
    except Exception:  # noqa: BLE001
        return None


def _ensure_naive(value):
    if value is not None and timezone.is_aware(value):
        return timezone.make_naive(value, timezone.get_current_timezone())
    return value


def generate_reservation_no(laboratory=None):
    """生成预约编号：BK + 年月日 + 实验室编号 + 4位随机序列。"""
    today = timezone.now().date()
    lab_part = f"-{laboratory.code}" if laboratory is not None and laboratory.code else ""
    for _ in range(30):
        candidate = f"BK{today.strftime('%Y%m%d')}{lab_part}-{random.randint(1000, 9999)}"
        if not Reservation.objects.filter(no=candidate).exists():
            return candidate
    return f"BK{today.strftime('%Y%m%d')}{lab_part}-{int(timezone.now().timestamp()) % 100000}"


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def validate_time_range(start_time, end_time, user=None, check_advance=True):
    """基础时间校验：非空、先后顺序、时长上限、提前提交。"""
    if not start_time or not end_time:
        raise ReservationError("请填写完整的开始时间与结束时间")
    if end_time <= start_time:
        raise ReservationError("结束时间必须晚于开始时间")

    duration = (end_time - start_time).total_seconds() / 3600
    if duration < 0.5:
        raise ReservationError("单次预约时长不得少于 0.5 小时")

    if user is not None:
        limit = settings.ROLE_MAX_RESERVE_HOURS.get(user.role, 4)
        if duration > limit:
            raise ReservationError(
                f"当前角色单次预约时长上限为 {limit} 小时，您填写的是 {duration:.1f} 小时"
            )

    now = timezone.now()
    if check_advance:
        advance_minutes = settings.RESERVE_MIN_ADVANCE_MINUTES
        if end_time <= now:
            raise ReservationError("结束时间已过，无法提交预约")
        if (start_time - now).total_seconds() < advance_minutes * 60:
            raise ReservationError(f"请至少提前 {advance_minutes} 分钟提交预约")
    return duration


def validate_lab_open(laboratory, start_time, end_time):
    """校验实验室开放时段与开放日。"""
    if laboratory is None:
        raise ReservationError("请选择实验室")
    if not laboratory.is_active:
        raise ReservationError("该实验室已停用，无法预约")

    current = start_time
    while current.date() <= end_time.date():
        if not laboratory.is_open_at(current):
            raise ReservationError(
                f"所选时间超出实验室开放时段（开放日：{laboratory.open_weekdays}，"
                f"开放时间：{laboratory.open_time_start.strftime('%H:%M')}-"
                f"{laboratory.open_time_end.strftime('%H:%M')}）"
            )
        current += datetime.timedelta(days=1)
    if end_time.time() > laboratory.open_time_end:
        raise ReservationError("结束时间超出实验室当天开放时段")
    return True


def validate_device_conflict(device, start_time, end_time, exclude_reservation_id=None):
    """
    冲突控制：同一设备同一时段不允许重复预约。
    返回 None 表示无冲突，否则返回冲突提示文本。
    """
    if device is None:
        return "请选择设备"
    if not device.is_active:
        return "该设备已停用，无法预约"
    if device.status == Device.Status.REPAIRING:
        return "该设备正在维修中，暂不可预约"
    if device.status == Device.Status.SCRAPPED:
        return "该设备已报废，无法预约"

    queryset = Reservation.objects.filter(
        device=device,
        status__in=Reservation.ACTIVE_STATUSES,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_reservation_id:
        queryset = queryset.exclude(pk=exclude_reservation_id)
    conflict = queryset.select_related("applicant").first()
    if conflict:
        return (
            f"该设备在 {conflict.start_time.strftime('%Y-%m-%d %H:%M')} ~ "
            f"{conflict.end_time.strftime('%Y-%m-%d %H:%M')} 已被预约（编号 {conflict.no}），"
            "请调整时间或更换设备"
        )
    return None


def validate_applicant_daily_limit(user, start_time, exclude_reservation_id=None, max_count=5):
    """同一用户同一天预约数量限制，避免恶意占位。"""
    queryset = Reservation.objects.filter(
        applicant=user, status__in=Reservation.ACTIVE_STATUSES,
        start_time__date=start_time.date(),
    )
    if exclude_reservation_id:
        queryset = queryset.exclude(pk=exclude_reservation_id)
    if queryset.count() >= max_count:
        raise ReservationError(f"您当天已有 {max_count} 个有效预约，请先完成或取消后再预约")
    return True


def validate_full_reservation(user, laboratory, device, start_time, end_time,
                              exclude_reservation_id=None, check_advance=True):
    """预约提交/暂存的完整校验。"""
    validate_time_range(start_time, end_time, user=user, check_advance=check_advance)
    validate_lab_open(laboratory, start_time, end_time)
    conflict = validate_device_conflict(device, start_time, end_time, exclude_reservation_id)
    if conflict:
        raise ReservationError(conflict)
    if device and laboratory and device.laboratory_id != laboratory.id:
        raise ReservationError("所选设备不属于该实验室，请重新选择")
    validate_applicant_daily_limit(user, start_time, exclude_reservation_id)
    return True


# --------------------------------------------------------------------------
# 状态流转
# --------------------------------------------------------------------------
def change_status(reservation, to_status, operator=None, action="", remark=""):
    """统一状态变更入口：写流转记录 + 操作日志。"""
    from_status = reservation.status
    reservation.status = to_status
    reservation.save(update_fields=["status", "updated_at"])

    operator_name = ""
    if operator is not None:
        operator_name = operator.real_name or operator.username

    ReservationStatusLog.objects.create(
        reservation=reservation,
        from_status=from_status,
        to_status=to_status,
        action=action,
        operator=operator if getattr(operator, "pk", None) else None,
        operator_name=operator_name,
        remark=remark,
    )

    log_operation(
        operator=operator,
        action=_map_action(action),
        target_type="reservation",
        target_id=reservation.id,
        target_repr=reservation.no,
        lab=reservation.laboratory,
        detail={"状态": [STATUS_TEXT.get(from_status, from_status), STATUS_TEXT.get(to_status, to_status)]},
        remark=remark or f"{action}：{reservation.no}",
    )
    return reservation


def _map_action(action):
    mapping = {
        "submit": "submit", "withdraw": "withdraw", "approve": "approve",
        "reject": "reject", "transfer": "transfer", "cancel": "cancel",
        "sign_in": "sign_in", "sign_out": "sign_out", "complete": "complete",
    }
    return mapping.get(action, "update")


def ensure_chat_thread(reservation):
    """为预约单创建（或获取）沟通会话。"""
    thread, created = ChatThread.objects.get_or_create(
        reservation=reservation,
        defaults={"status": ChatThread.Status.PENDING_REPLY},
    )
    return thread


def close_chat_thread(reservation):
    ChatThread.objects.filter(reservation=reservation).update(status=ChatThread.Status.CLOSED)


# --------------------------------------------------------------------------
# 通知派发（站内提醒）
# --------------------------------------------------------------------------
def notify_pending_approval(reservation):
    """通知该实验室的管理员有新预约待审批。"""
    from apps.notifications.services import create_notification

    managers = reservation.laboratory.managers.all()
    for manager in managers:
        create_notification(
            user=manager,
            notify_type="pending_approval",
            title="有新的预约待审批",
            content=(
                f"{reservation.applicant_name} 提交了 {reservation.device.name} 的预约申请"
                f"（{reservation.no}），时间：{_fmt(reservation.start_time)} ~ {_fmt(reservation.end_time)}，"
                f"紧急程度：{reservation.get_urgency_display()}"
            ),
            reservation=reservation,
            dedupe_key=f"pending_approval:{reservation.id}:{manager.id}",
        )


def notify_approve_result(reservation, approved, remark=""):
    """通知预约人审批结果。"""
    from apps.notifications.services import create_notification

    if approved:
        title = "预约审批已通过"
        content = (
            f"您提交的预约 {reservation.no}（{reservation.device.name}）已通过审批。"
            f"使用时间：{_fmt(reservation.start_time)} ~ {_fmt(reservation.end_time)}，请按时签到使用。"
        )
    else:
        title = "预约审批已驳回"
        content = f"您提交的预约 {reservation.no} 已被驳回。驳回原因：{remark or '未填写'}"

    create_notification(
        user=reservation.applicant,
        notify_type="approval_result",
        title=title,
        content=content,
        reservation=reservation,
        dedupe_key=f"approval_result:{reservation.id}:{reservation.status}",
    )


def notify_transfer(reservation, new_approver, operator=None):
    """通知被转派的审批人。"""
    from apps.notifications.services import create_notification

    create_notification(
        user=new_approver,
        notify_type="transfer_approval",
        title="有预约转派给您审批",
        content=(
            f"{operator.real_name if operator else '管理员'} 将预约 {reservation.no}"
            f"（{reservation.device.name}）转派给您审批，请及时处理。"
        ),
        reservation=reservation,
        dedupe_key=f"transfer:{reservation.id}:{new_approver.id}:{timezone.now().timestamp():.0f}",
    )


def notify_sign_out_to_admin(reservation):
    """签退后通知管理员核验归还。"""
    from apps.notifications.services import create_notification

    for manager in reservation.laboratory.managers.all():
        create_notification(
            user=manager,
            notify_type="pending_return",
            title="有预约已签退待核验",
            content=(
                f"{reservation.applicant_name} 的预约 {reservation.no}"
                f"（{reservation.device.name}）已签退，请核验设备归还与状态。"
            ),
            reservation=reservation,
            dedupe_key=f"sign_out:{reservation.id}:{manager.id}",
        )


def notify_completed(reservation):
    """完工后通知预约人进行评价。"""
    from apps.notifications.services import create_notification

    create_notification(
        user=reservation.applicant,
        notify_type="pending_evaluate",
        title="预约已完成，请进行评价",
        content=f"您的预约 {reservation.no} 已完工确认，欢迎对设备状态与服务进行评价。",
        reservation=reservation,
        dedupe_key=f"evaluate:{reservation.id}",
    )


def notify_chat_reply(reservation, receiver, sender, content):
    """沟通消息提醒。"""
    from apps.notifications.services import create_notification

    preview = (content or "[图片]")[:40]
    create_notification(
        user=receiver,
        notify_type="chat_message",
        title="收到新的预约沟通消息",
        content=f"{sender.real_name or sender.username} 就预约 {reservation.no} 回复：{preview}",
        reservation=reservation,
        dedupe_key=f"chat:{reservation.id}:{receiver.id}:{timezone.now().timestamp():.0f}",
    )


def _fmt(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


# --------------------------------------------------------------------------
# 自动状态推进
# --------------------------------------------------------------------------
def auto_update_statuses(now=None):
    """
    自动推进状态：
    - 已通过且已到使用时间窗口 → 待使用
    """
    now = now or timezone.now()
    threshold = now - datetime.timedelta(minutes=0)
    updated = (
        Reservation.objects.filter(status=Reservation.Status.APPROVED,
                                   start_time__lte=threshold)
        .update(status=Reservation.Status.WAITING_USE)
    )
    return updated


@transaction.atomic
def create_reservation(user, validated_data, submit=True):
    """创建预约单（暂存或直接提交）。"""
    laboratory = validated_data["laboratory"]
    device = validated_data["device"]
    start_time = validated_data["start_time"]
    end_time = validated_data["end_time"]

    validate_full_reservation(
        user, laboratory, device, start_time, end_time, check_advance=submit
    )

    reservation = Reservation.objects.create(
        no=generate_reservation_no(laboratory),
        applicant=user,
        applicant_name=user.real_name or user.username,
        applicant_role=user.role,
        college_name=user.college.name if user.college else "",
        class_name=user.class_group.name if user.class_group else "",
        contact_phone=user.phone,
        laboratory=laboratory,
        device=device,
        start_time=start_time,
        end_time=end_time,
        purpose=validated_data.get("purpose", ""),
        urgency=validated_data.get("urgency", Reservation.Urgency.NORMAL),
        status=Reservation.Status.DRAFT if not submit else Reservation.Status.PENDING,
        submit_time=None if not submit else timezone.now(),
    )

    ReservationStatusLog.objects.create(
        reservation=reservation,
        from_status="",
        to_status=reservation.status,
        action="submit" if submit else "draft",
        operator=user,
        operator_name=user.real_name or user.username,
        remark="提交预约申请" if submit else "暂存预约申请",
    )
    log_operation(
        operator=user, action="create", target_type="reservation",
        target_id=reservation.id, target_repr=reservation.no, lab=laboratory,
        detail={
            "设备": ["", str(device)],
            "开始时间": ["", _fmt(start_time)],
            "结束时间": ["", _fmt(end_time)],
            "用途说明": ["", reservation.purpose[:60]],
            "紧急程度": ["", reservation.get_urgency_display()],
        },
        remark="暂存预约" if not submit else "提交预约申请",
    )

    if submit:
        notify_pending_approval(reservation)
    return reservation
