"""实验室与设备视图，含 Excel 批量导入导出。"""
import datetime
import io

from django.db.models import Count, Q
from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsLabAdminOrSystemAdmin, IsSystemAdmin
from apps.auditlog.services import build_change_detail, log_operation

from .models import Device, DeviceCategory, Laboratory
from .serializers import (
    DeviceCategorySerializer,
    DeviceSerializer,
    DeviceSimpleSerializer,
    LaboratorySerializer,
)

STATUS_TEXT_TO_VALUE = {
    "可预约": Device.Status.AVAILABLE,
    "维修中": Device.Status.REPAIRING,
    "已报废": Device.Status.SCRAPPED,
    "available": Device.Status.AVAILABLE,
    "repairing": Device.Status.REPAIRING,
    "scrapped": Device.Status.SCRAPPED,
}


class LaboratoryViewSet(viewsets.ModelViewSet):
    """实验室管理：管理员维护，全体用户可查看自己有权访问的实验室。"""

    queryset = Laboratory.objects.prefetch_related("managers").all()
    serializer_class = LaboratorySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "code", "location"]
    ordering_fields = ["id", "name", "capacity", "created_at"]
    lookup_value_regex = r"\d+"

    def get_permissions(self):
        if self.action in ("list", "retrieve", "options", "simple"):
            return [IsAuthenticated()]
        return [IsLabAdminOrSystemAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_sys_admin:
            # 实验室管理员默认只看自己负责的实验室；学生/教师可查看全部启用实验室
            if user.is_lab_admin and self.request.query_params.get("mine") == "1":
                queryset = queryset.filter(id__in=user.managed_lab_ids)

        params = self.request.query_params
        if params.get("keyword"):
            keyword = params["keyword"]
            queryset = queryset.filter(
                Q(name__icontains=keyword) | Q(code__icontains=keyword) | Q(location__icontains=keyword)
            )
        if params.get("is_active") not in (None, ""):
            queryset = queryset.filter(is_active=params["is_active"] in ("1", "true", "True"))
        if params.get("manager"):
            queryset = queryset.filter(managers__id=params["manager"])
        if params.get("min_capacity"):
            queryset = queryset.filter(capacity__gte=params["min_capacity"])
        return queryset.distinct()

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lab = serializer.save()
        log_operation(
            operator=request.user, action="create", target_type="laboratory",
            target_id=lab.id, target_repr=str(lab), lab=lab,
            detail={"名称": ["", lab.name], "位置": ["", lab.location], "容纳人数": ["", lab.capacity]},
            remark="新增实验室", request=request,
        )
        return Response(
            {"code": 0, "message": "实验室创建成功", "data": self.get_serializer(lab).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        self._check_lab_permission(request.user, instance)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        old = Laboratory.objects.get(pk=instance.pk)
        lab = serializer.save()
        detail = build_change_detail(old, serializer.validated_data)
        if detail:
            log_operation(
                operator=request.user, action="update", target_type="laboratory",
                target_id=lab.id, target_repr=str(lab), lab=lab, detail=detail,
                remark="修改实验室信息", request=request,
            )
        return Response({"code": 0, "message": "实验室信息已更新", "data": self.get_serializer(lab).data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._check_lab_permission(request.user, instance)
        if instance.devices.exists():
            return Response(
                {"code": 400, "message": "该实验室下仍有设备，无法删除。请先转移或删除设备", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_operation(
            operator=request.user, action="delete", target_type="laboratory",
            target_id=instance.id, target_repr=str(instance), lab=None,
            remark="删除实验室", request=request,
        )
        instance.delete()
        return Response({"code": 0, "message": "实验室已删除", "data": None})

    @staticmethod
    def _check_lab_permission(user, lab):
        if user.is_sys_admin:
            return
        if user.is_lab_admin and lab.managers.filter(pk=user.pk).exists():
            return
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("您不是该实验室的负责管理员，无权操作")

    @action(detail=False, methods=["get"], url_path="simple")
    def simple(self, request):
        """实验室下拉列表。"""
        queryset = Laboratory.objects.filter(is_active=True)
        if request.query_params.get("mine") == "1" and not request.user.is_sys_admin:
            queryset = queryset.filter(id__in=request.user.managed_lab_ids)
        queryset = queryset.order_by("id")
        return Response(
            {
                "code": 0,
                "message": "success",
                "data": [
                    {"id": lab.id, "name": lab.name, "code": lab.code, "location": lab.location,
                     "capacity": lab.capacity, "open_time_start": lab.open_time_start.strftime("%H:%M"),
                     "open_time_end": lab.open_time_end.strftime("%H:%M"),
                     "open_weekdays": lab.open_weekdays}
                    for lab in queryset
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """导出实验室清单。"""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "实验室清单"
        headers = ["实验室编号", "实验室名称", "位置", "容纳人数", "开放时间", "开放日", "负责人", "状态"]
        sheet.append(headers)
        _style_header(sheet)
        for lab in self.get_queryset():
            sheet.append([
                lab.code, lab.name, lab.location, lab.capacity,
                f"{lab.open_time_start.strftime('%H:%M')}-{lab.open_time_end.strftime('%H:%M')}",
                lab.open_weekdays, "、".join(u.real_name or u.username for u in lab.managers.all()),
                "启用" if lab.is_active else "停用",
            ])
        return _workbook_response(workbook, "实验室清单")


class DeviceCategoryViewSet(viewsets.ModelViewSet):
    """设备分类管理。"""

    queryset = DeviceCategory.objects.all()
    serializer_class = DeviceCategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    search_fields = ["name", "code"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsLabAdminOrSystemAdmin()]


class DeviceViewSet(viewsets.ModelViewSet):
    """设备台账管理：支持 Excel 批量导入与多条件检索。"""

    queryset = Device.objects.select_related("category", "laboratory").all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, *viewsets.ModelViewSet.parser_classes]
    search_fields = ["code", "name", "model", "manufacturer", "specification"]
    ordering_fields = ["id", "code", "name", "created_at", "status"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "options", "available", "check_available",
                           "device_statistics"):
            return [IsAuthenticated()]
        return [IsLabAdminOrSystemAdmin()]

    def get_serializer_class(self):
        if self.action in ("available", "simple"):
            return DeviceSimpleSerializer
        return DeviceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_sys_admin and user.is_lab_admin and self.request.query_params.get("mine") == "1":
            queryset = queryset.filter(laboratory_id__in=user.managed_lab_ids)

        params = self.request.query_params
        keyword = params.get("keyword")
        if keyword:
            queryset = queryset.filter(
                Q(code__icontains=keyword) | Q(name__icontains=keyword) | Q(model__icontains=keyword)
            )
        if params.get("laboratory"):
            queryset = queryset.filter(laboratory_id=params["laboratory"])
        if params.get("category"):
            category = params["category"]
            queryset = queryset.filter(
                Q(category_id=category) if str(category).isdigit() else Q(category__name=category)
            )
        status_value = params.get("status")
        if status_value:
            queryset = queryset.filter(status__in=status_value.split(","))
        if params.get("is_active") not in (None, ""):
            queryset = queryset.filter(is_active=params["is_active"] in ("1", "true", "True"))
        if params.get("bookable") == "1":
            queryset = queryset.filter(status=Device.Status.AVAILABLE, is_active=True)

        # 时间区间过滤：只返回该时段空闲的设备
        start = params.get("start_time")
        end = params.get("end_time")
        if start and end:
            from apps.reservations.models import Reservation

            busy_ids = Reservation.objects.filter(
                status__in=[
                    Reservation.Status.PENDING, Reservation.Status.APPROVED,
                    Reservation.Status.WAITING_USE, Reservation.Status.IN_USE,
                ],
                start_time__lt=end, end_time__gt=start,
            ).values_list("device_id", flat=True)
            queryset = queryset.exclude(id__in=list(busy_ids))
        return queryset.distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = serializer.save()
        log_operation(
            operator=request.user, action="create", target_type="device",
            target_id=device.id, target_repr=str(device), lab=device.laboratory,
            detail={"编号": ["", device.code], "名称": ["", device.name],
                    "分类": ["", device.category.name], "状态": ["", device.get_status_display()]},
            remark="新增设备", request=request,
        )
        return Response(
            {"code": 0, "message": "设备创建成功", "data": DeviceSerializer(device).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        old = Device.objects.select_related("category").get(pk=instance.pk)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        device = serializer.save()
        detail = build_change_detail(old, serializer.validated_data)
        if detail:
            log_operation(
                operator=request.user, action="update", target_type="device",
                target_id=device.id, target_repr=str(device), lab=device.laboratory,
                detail=detail, remark="修改设备信息", request=request,
            )
        return Response({"code": 0, "message": "设备信息已更新", "data": DeviceSerializer(device).data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        log_operation(
            operator=request.user, action="delete", target_type="device",
            target_id=instance.id, target_repr=str(instance), lab=instance.laboratory,
            remark="停用设备", request=request,
        )
        return Response({"code": 0, "message": "设备已停用", "data": None})

    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        """可预约设备列表（含预计可用时间），供预约页面选择。"""
        queryset = self.get_queryset().filter(status=Device.Status.AVAILABLE, is_active=True)
        page = self.paginate_queryset(queryset)
        serializer = DeviceSimpleSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"], url_path="check-available")
    def check_available(self, request, pk=None):
        """校验某设备在指定时段是否可预约。"""
        device = self.get_object()
        start = request.query_params.get("start_time")
        end = request.query_params.get("end_time")
        if not start or not end:
            return Response(
                {"code": 400, "message": "请提供 start_time 与 end_time", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.reservations.services import parse_datetime

        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end)
        from apps.reservations.services import validate_device_conflict

        error = validate_device_conflict(device, start_dt, end_dt)
        occupied_until = device.next_available_time()
        return Response(
            {
                "code": 0,
                "message": "该时段可预约" if not error else error,
                "data": {
                    "available": error is None,
                    "reason": error or "",
                    "status": device.status,
                    "status_display": device.get_status_display(),
                    "occupied_until": occupied_until.strftime("%Y-%m-%d %H:%M:%S") if occupied_until else None,
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request):
        """下载设备导入模板。"""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "设备导入模板"
        headers = ["设备编号*", "设备名称*", "型号", "设备分类*", "所属实验室编号*",
                   "设备状态", "规格参数", "生产厂商", "购置日期", "单价", "备注"]
        sheet.append(headers)
        _style_header(sheet)
        sheet.append(["DEV-2026-001", "示波器", "Tektronix TBS1102", "电子测量仪器",
                      "LAB-001", "可预约", "100MHz 双通道", "泰克", "2025-09-01", 3200, "示例数据"])
        for column, width in zip("ABCDEFGHIJK", [18, 20, 22, 18, 20, 12, 24, 18, 14, 10, 20]):
            sheet.column_dimensions[column].width = width
        return _workbook_response(workbook, "设备导入模板")

    @action(detail=False, methods=["post"], url_path="import",
            parser_classes=[MultiPartParser, FormParser])
    def import_devices(self, request):
        """Excel 批量导入设备。支持 .xlsx / .xlsm。"""
        file_obj = request.FILES.get("file")
        if file_obj is None:
            return Response(
                {"code": 400, "message": "请上传 Excel 文件（字段名 file）", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not file_obj.name.lower().endswith((".xlsx", ".xlsm")):
            return Response(
                {"code": 400, "message": "仅支持 .xlsx / .xlsm 格式文件", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dry_run = str(request.data.get("dry_run", "false")).lower() == "true"
        try:
            workbook = load_workbook(file_obj, data_only=True)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"code": 400, "message": f"Excel 解析失败：{exc}", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if len(rows) < 2:
            return Response(
                {"code": 400, "message": "表格中没有数据行", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
        errors = []
        created_ids = []
        updated_count = 0

        lab_map = {}
        for lab in Laboratory.objects.all():
            lab_map[lab.code.strip().lower()] = lab
            lab_map[lab.name.strip().lower()] = lab
        category_map = {c.name.strip().lower(): c for c in DeviceCategory.objects.all()}

        for index, row in enumerate(rows[1:], start=2):
            if row is None or all(cell in (None, "") for cell in row):
                continue
            data = {header[i] if i < len(header) else f"列{i}": row[i] for i in range(len(row))}

            def pick(*names):
                for name in names:
                    for key in data:
                        if key.replace("*", "").strip() == name:
                            value = data[key]
                            return str(value).strip() if value is not None else ""
                return ""

            code = pick("设备编号")
            name = pick("设备名称")
            if not code or not name:
                errors.append({"row": index, "message": "设备编号与设备名称为必填项"})
                continue
            if Device.objects.filter(code=code).exists():
                errors.append({"row": index, "message": f"设备编号 {code} 已存在"})
                continue

            category_name = pick("设备分类")
            category = category_map.get(category_name.lower())
            if category is None:
                if not category_name:
                    errors.append({"row": index, "message": "设备分类不能为空"})
                    continue
                if dry_run:
                    category = DeviceCategory(name=category_name)
                else:
                    category, _ = DeviceCategory.objects.get_or_create(
                        name=category_name, defaults={"code": ""}
                    )
                    category_map[category_name.lower()] = category

            lab_key = pick("所属实验室编号", "所属实验室").lower()
            laboratory = lab_map.get(lab_key)
            if laboratory is None:
                errors.append({"row": index, "message": f"实验室 {lab_key} 不存在，请先创建实验室"})
                continue

            status_text = pick("设备状态") or "可预约"
            status_value = STATUS_TEXT_TO_VALUE.get(status_text)
            if status_value is None:
                errors.append({"row": index, "message": f"设备状态 {status_text} 无效（可预约/维修中/已报废）"})
                continue

            price_text = pick("单价")
            try:
                price = float(price_text) if price_text else 0
            except ValueError:
                errors.append({"row": index, "message": f"单价 {price_text} 不是数字"})
                continue

            purchase_date = None
            date_text = pick("购置日期")
            if date_text:
                purchase_date = _parse_date(date_text)

            if dry_run:
                continue

            device = Device.objects.create(
                code=code, name=name, model=pick("型号"),
                category=category, laboratory=laboratory, status=status_value,
                specification=pick("规格参数"), manufacturer=pick("生产厂商"),
                purchase_date=purchase_date, price=price, remark=pick("备注"),
            )
            created_ids.append(device.id)

        if not dry_run:
            log_operation(
                operator=request.user, action="import", target_type="device",
                target_id=None, target_repr=f"批量导入设备 {len(created_ids)} 条",
                detail={"成功": ["", len(created_ids)], "失败": ["", len(errors)]},
                remark="Excel 批量导入设备", request=request,
            )

        return Response(
            {
                "code": 0,
                "message": f"导入完成：成功 {len(created_ids) + updated_count} 条，失败 {len(errors)} 条",
                "data": {
                    "dry_run": dry_run,
                    "total": len(rows) - 1,
                    "success": len(created_ids) + updated_count,
                    "failed": len(errors),
                    "errors": errors[:200],
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """导出设备台账。"""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "设备台账"
        sheet.append(["设备编号", "设备名称", "型号", "设备分类", "所属实验室",
                      "设备状态", "规格参数", "生产厂商", "购置日期", "单价", "备注"])
        _style_header(sheet)
        for device in self.get_queryset():
            sheet.append([
                device.code, device.name, device.model, device.category.name,
                device.laboratory.name, device.get_status_display(),
                device.specification, device.manufacturer,
                device.purchase_date.strftime("%Y-%m-%d") if device.purchase_date else "",
                float(device.price), device.remark,
            ])
        return _workbook_response(workbook, "设备台账")

    @action(detail=False, methods=["get"], url_path="statistics")
    def device_statistics(self, request):
        """设备状态分布统计。"""
        queryset = self.get_queryset()
        data = list(queryset.values("status").annotate(count=Count("id")))
        status_map = dict(Device.Status.choices)
        by_category = list(
            queryset.values("category__name").annotate(count=Count("id")).order_by("-count")
        )
        return Response(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "by_status": [
                        {"status": item["status"], "status_display": status_map.get(item["status"], item["status"]),
                         "count": item["count"]}
                        for item in data
                    ],
                    "by_category": [
                        {"name": item["category__name"], "count": item["count"]} for item in by_category
                    ],
                    "total": queryset.count(),
                },
            }
        )


class AdminDashboardViewSet(viewsets.ViewSet):
    """控制台首页概览（仅管理员）。"""

    permission_classes = [IsSystemAdmin]

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        from apps.reservations.models import Reservation
        from apps.accounts.models import User

        status_counts = dict(
            Reservation.objects.values_list("status").annotate(count=Count("id"))
        )
        total = Reservation.objects.count()
        completed = status_counts.get(Reservation.Status.COMPLETED, 0)
        return Response(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "user_count": User.objects.filter(is_active=True).count(),
                    "lab_count": Laboratory.objects.filter(is_active=True).count(),
                    "device_count": Device.objects.filter(is_active=True).count(),
                    "reservation_total": total,
                    "completion_rate": round(completed / total * 100, 2) if total else 0,
                    "status_counts": status_counts,
                },
            }
        )


def _parse_date(text):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _style_header(sheet):
    fill = PatternFill("solid", fgColor="4472C4")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"


def _workbook_response(workbook, filename):
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f"attachment; filename={filename}.xlsx; filename*=UTF-8''{filename}.xlsx"
    )
    return response
