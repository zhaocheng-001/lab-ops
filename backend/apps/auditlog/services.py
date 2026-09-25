"""日志记录服务。"""
import logging

from apps.auditlog.models import OperationLog

logger = logging.getLogger(__name__)

# 字段中文名映射，用于生成可读的变更明细
FIELD_LABELS = {
    "status": "状态",
    "start_time": "开始时间",
    "end_time": "结束时间",
    "purpose": "用途说明",
    "urgency": "紧急程度",
    "device": "设备",
    "laboratory": "实验室",
    "approver": "审批人",
    "approve_remark": "审批意见",
    "remark": "备注",
    "name": "名称",
    "code": "编号",
    "location": "位置",
    "capacity": "容纳人数",
    "model": "型号",
    "category": "分类",
    "is_active": "是否启用",
    "sign_in_time": "签到时间",
    "sign_out_time": "签退时间",
    "device_status_after": "使用后设备状态",
    "abnormal_note": "异常说明",
}


def get_client_ip(request):
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def format_value(value):
    if value is None:
        return ""
    if hasattr(value, "pk"):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (list, tuple)):
        return "、".join(format_value(v) for v in value)
    return str(value)


def build_change_detail(old_obj, new_data):
    """对比新旧数据，返回 {字段中文名: [旧值, 新值]}"""
    detail = {}
    for field, new_value in new_data.items():
        label = FIELD_LABELS.get(field, field)
        old_value = getattr(old_obj, field, None) if old_obj is not None else None
        old_text = format_value(old_value)
        new_text = format_value(new_value)
        if old_text != new_text:
            detail[label] = [old_text, new_text]
    return detail


def log_operation(
    operator=None,
    action="view",
    target_type="",
    target_id=None,
    target_repr="",
    lab=None,
    detail=None,
    remark="",
    request=None,
):
    """写入一条操作日志。日志失败不能影响主流程。"""
    try:
        OperationLog.objects.create(
            operator=operator if getattr(operator, "pk", None) else None,
            operator_name=(
                (getattr(operator, "real_name", "") or getattr(operator, "username", ""))
                if operator
                else "匿名"
            ),
            operator_role=getattr(operator, "role", "") or "",
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_repr=(target_repr or "")[:255],
            lab=lab,
            detail=detail or {},
            remark=(remark or "")[:255],
            ip=get_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入操作日志失败: %s", exc)
