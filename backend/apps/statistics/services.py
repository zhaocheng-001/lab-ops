"""统计服务：数据范围过滤、指标计算。"""
import datetime

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from apps.labs.models import Device, Laboratory
from apps.reservations.models import Evaluation, Reservation

OVERDUE_Q = Q(
    status__in=[Reservation.Status.APPROVED, Reservation.Status.WAITING_USE,
                Reservation.Status.IN_USE],
    end_time__lt=timezone.now(),
)


def parse_date(value):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def build_scope(user):
    """构造数据访问范围。"""
    return {"user": user, "is_sys_admin": user.is_sys_admin,
            "is_lab_admin": user.is_lab_admin, "lab_ids": user.managed_lab_ids}


def base_queryset(user, params=None):
    """按角色确定统计基础数据集。"""
    params = params or {}
    queryset = Reservation.objects.all()
    if user.is_sys_admin:
        pass
    elif user.is_lab_admin:
        queryset = queryset.filter(laboratory_id__in=user.managed_lab_ids)
    else:
        queryset = queryset.filter(applicant=user)

    laboratory = params.get("laboratory")
    if laboratory:
        queryset = queryset.filter(laboratory_id=laboratory)
    category = params.get("category")
    if category:
        queryset = queryset.filter(device__category_id=category)
    device = params.get("device")
    if device:
        queryset = queryset.filter(device_id=device)
    applicant = params.get("applicant")
    if applicant:
        queryset = queryset.filter(applicant_id=applicant)
    status_value = params.get("status")
    if status_value:
        queryset = queryset.filter(status__in=status_value.split(","))

    start_date = parse_date(params.get("start_date", ""))
    end_date = parse_date(params.get("end_date", ""))
    if start_date:
        queryset = queryset.filter(end_time__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(start_time__date__lte=end_date)
    return queryset


def overdue_queryset(user, params=None):
    return base_queryset(user, params).filter(OVERDUE_Q)


def overall_statistics(user, params=None):
    """总览指标：预约总数、待处理、使用中、已完成、逾期数、设备使用率。"""
    queryset = base_queryset(user, params)
    now = timezone.now()

    total = queryset.count()
    pending = queryset.filter(status=Reservation.Status.PENDING).count()
    approved = queryset.filter(status=Reservation.Status.APPROVED).count()
    waiting_use = queryset.filter(status=Reservation.Status.WAITING_USE).count()
    in_use = queryset.filter(status=Reservation.Status.IN_USE).count()
    completed = queryset.filter(status=Reservation.Status.COMPLETED).count()
    rejected = queryset.filter(status=Reservation.Status.REJECTED).count()
    cancelled = queryset.filter(status=Reservation.Status.CANCELLED).count()
    draft = queryset.filter(status=Reservation.Status.DRAFT).count()
    overdue = queryset.filter(OVERDUE_Q).count()
    to_evaluate = queryset.filter(status=Reservation.Status.COMPLETED, is_evaluated=False).count()

    duration_expr = ExpressionWrapper(F("end_time") - F("start_time"), output_field=DurationField())
    valid = queryset.exclude(status__in=[Reservation.Status.REJECTED, Reservation.Status.CANCELLED,
                                         Reservation.Status.DRAFT])
    total_hours = valid.annotate(d=duration_expr).aggregate(total=Sum("d"))["total"]
    used_hours = round(total_hours.total_seconds() / 3600, 2) if total_hours else 0

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "waiting_use": waiting_use,
        "in_use": in_use,
        "completed": completed,
        "rejected": rejected,
        "cancelled": cancelled,
        "draft": draft,
        "overdue": overdue,
        "to_evaluate": to_evaluate,
        "to_handle": pending + overdue + to_evaluate,
        "used_hours": used_hours,
        "completion_rate": round(completed / total * 100, 2) if total else 0,
        "approval_rate": round((approved + waiting_use + in_use + completed) / total * 100, 2) if total else 0,
        "device_usage_rate": device_usage_rate(user, params),
        "average_score": average_score(user, params),
    }


def device_usage_rate(user, params=None):
    """
    设备使用率 = 有效预约占用时长 / 可预约总时长。
    可预约总时长 = 范围内启用设备数 × 天数 × 实验室日均开放小时数。
    """
    params = params or {}
    queryset = base_queryset(user, params)
    duration_expr = ExpressionWrapper(F("end_time") - F("start_time"), output_field=DurationField())
    reserved = (
        queryset.exclude(status__in=[Reservation.Status.REJECTED, Reservation.Status.CANCELLED,
                                     Reservation.Status.DRAFT])
        .annotate(d=duration_expr)
        .aggregate(total=Sum("d"))["total"]
    )
    reserved_hours = reserved.total_seconds() / 3600 if reserved else 0

    device_qs = Device.objects.filter(is_active=True)
    lab_qs = Laboratory.objects.filter(is_active=True)
    if not user.is_sys_admin:
        if user.is_lab_admin:
            device_qs = device_qs.filter(laboratory_id__in=user.managed_lab_ids)
            lab_qs = lab_qs.filter(id__in=user.managed_lab_ids)
        else:
            device_qs = device_qs.filter(reservations__applicant=user).distinct()
            lab_qs = lab_qs.filter(reservations__applicant=user).distinct()
    if params.get("laboratory"):
        device_qs = device_qs.filter(laboratory_id=params["laboratory"])
        lab_qs = lab_qs.filter(id=params["laboratory"])
    if params.get("category"):
        device_qs = device_qs.filter(category_id=params["category"])

    device_count = device_qs.count()
    if device_count == 0:
        return 0

    days = _range_days(params) or 30.0
    open_hours_per_day = 0.0
    labs = list(lab_qs)
    for lab in labs:
        open_hours_per_day += (
            _time_to_hours(lab.open_time_end) - _time_to_hours(lab.open_time_start)
        ) * max(1, len(lab.open_weekday_list)) / 7
    if not labs:
        open_hours_per_day = 12
    available_hours = device_count * days * open_hours_per_day
    if available_hours <= 0:
        return 0
    return round(min(100, reserved_hours / available_hours * 100), 2)


def _time_to_hours(value):
    return value.hour + value.minute / 60


def _range_days(params):
    start = parse_date(params.get("start_date", ""))
    end = parse_date(params.get("end_date", ""))
    if start and end and end >= start:
        return float((end - start).days + 1)
    return None


def average_score(user, params=None):
    """平均评价得分。"""
    queryset = Evaluation.objects.all()
    if user.is_sys_admin:
        pass
    elif user.is_lab_admin:
        queryset = queryset.filter(reservation__laboratory_id__in=user.managed_lab_ids)
    else:
        queryset = queryset.filter(evaluator=user)
    if params and params.get("laboratory"):
        queryset = queryset.filter(reservation__laboratory_id=params["laboratory"])
    value = queryset.aggregate(avg=Avg("average_score"))["avg"]
    return round(float(value), 2) if value else 0


def status_distribution(user, params=None):
    """预约状态分布。"""
    queryset = base_queryset(user, params)
    status_map = dict(Reservation.Status.choices)
    data = queryset.values("status").annotate(count=Count("id")).order_by("-count")
    return [
        {"status": item["status"], "status_display": status_map.get(item["status"], item["status"]),
         "count": item["count"]}
        for item in data
    ]


def by_laboratory(user, params=None):
    """按实验室统计。"""
    queryset = base_queryset(user, params)
    duration_expr = ExpressionWrapper(F("end_time") - F("start_time"), output_field=DurationField())
    rows = (
        queryset.values("laboratory_id", "laboratory__name", "laboratory__location")
        .annotate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=Reservation.Status.PENDING)),
            in_use=Count("id", filter=Q(status=Reservation.Status.IN_USE)),
            completed=Count("id", filter=Q(status=Reservation.Status.COMPLETED)),
            overdue=Count("id", filter=OVERDUE_Q),
            hours=Sum(duration_expr),
        )
        .order_by("-total")
    )
    result = []
    for row in rows:
        hours = row["hours"].total_seconds() / 3600 if row["hours"] else 0
        result.append({
            "laboratory_id": row["laboratory_id"],
            "laboratory": row["laboratory__name"],
            "location": row["laboratory__location"],
            "total": row["total"],
            "pending": row["pending"],
            "in_use": row["in_use"],
            "completed": row["completed"],
            "overdue": row["overdue"],
            "hours": round(hours, 2),
        })
    return result


def by_category(user, params=None):
    """按设备类型统计。"""
    queryset = base_queryset(user, params)
    duration_expr = ExpressionWrapper(F("end_time") - F("start_time"), output_field=DurationField())
    rows = (
        queryset.values("device__category_id", "device__category__name")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status=Reservation.Status.COMPLETED)),
            overdue=Count("id", filter=OVERDUE_Q),
            hours=Sum(duration_expr),
        )
        .order_by("-total")
    )
    return [
        {
            "category_id": row["device__category_id"],
            "category": row["device__category__name"],
            "total": row["total"],
            "completed": row["completed"],
            "overdue": row["overdue"],
            "hours": round(row["hours"].total_seconds() / 3600, 2) if row["hours"] else 0,
        }
        for row in rows
    ]


def trend(user, params=None, group="day"):
    """预约趋势（按日 / 按月）。"""
    queryset = base_queryset(user, params)
    trunc = TruncDate("created_at") if group == "day" else TruncMonth("created_at")
    rows = (
        queryset.annotate(period=trunc)
        .values("period")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status=Reservation.Status.COMPLETED)),
            rejected=Count("id", filter=Q(status=Reservation.Status.REJECTED)),
            cancelled=Count("id", filter=Q(status=Reservation.Status.CANCELLED)),
        )
        .order_by("period")
    )
    return [
        {
            "period": row["period"].strftime("%Y-%m-%d") if row["period"] else "",
            "total": row["total"],
            "completed": row["completed"],
            "rejected": row["rejected"],
            "cancelled": row["cancelled"],
        }
        for row in rows
        if row["period"]
    ]


def device_ranking(user, params=None, limit=10):
    """设备使用率排行。"""
    queryset = base_queryset(user, params)
    duration_expr = ExpressionWrapper(F("end_time") - F("start_time"), output_field=DurationField())
    rows = (
        queryset.values("device_id", "device__name", "device__code", "device__category__name",
                        "device__laboratory__name")
        .annotate(total=Count("id"), hours=Sum(duration_expr))
        .order_by("-total")[:limit]
    )
    days = _range_days(params or {}) or 30.0
    result = []
    for row in rows:
        hours = row["hours"].total_seconds() / 3600 if row["hours"] else 0
        result.append({
            "device_id": row["device_id"],
            "device": row["device__name"],
            "code": row["device__code"],
            "category": row["device__category__name"],
            "laboratory": row["device__laboratory__name"],
            "total": row["total"],
            "hours": round(hours, 2),
            "usage_rate": round(min(100, hours / (days * 10) * 100), 2) if days else 0,
        })
    return result


def applicant_ranking(user, params=None, limit=10):
    """预约次数排行（管理员视角）。"""
    queryset = base_queryset(user, params)
    rows = (
        queryset.values("applicant_id", "applicant_name", "applicant_role")
        .annotate(total=Count("id"),
                  completed=Count("id", filter=Q(status=Reservation.Status.COMPLETED)))
        .order_by("-total")[:limit]
    )
    role_map = {"student": "学生", "teacher": "教师", "lab_admin": "实验室管理员", "sys_admin": "系统管理员"}
    return [
        {
            "applicant_id": row["applicant_id"],
            "applicant": row["applicant_name"],
            "role": role_map.get(row["applicant_role"], row["applicant_role"]),
            "total": row["total"],
            "completed": row["completed"],
        }
        for row in rows
    ]
