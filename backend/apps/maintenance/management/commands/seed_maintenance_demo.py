"""补充运维演示数据：故障报修、维修工单、维保计划、巡检记录。

依赖：先执行 `python manage.py init_demo_data`。
用法：
    python manage.py seed_maintenance_demo           # 仅补充运维数据
    python manage.py seed_maintenance_demo --reset   # 清空运维数据后重建
"""
import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.labs.models import Device, DeviceCategory, Laboratory
from apps.maintenance.models import (
    FaultReport,
    InspectRecord,
    MaintenanceOrder,
    MaintenancePlan,
)


class Command(BaseCommand):
    help = "为运维模块补充演示数据"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="清空运维数据后重建")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write(self.style.WARNING("清空运维数据..."))
            InspectRecord.objects.all().delete()
            MaintenancePlan.objects.all().delete()
            MaintenanceOrder.objects.all().delete()
            FaultReport.objects.all().delete()
            # 把所有因维修中而改的设备恢复到可用
            Device.objects.filter(status=Device.Status.REPAIRING).update(
                status=Device.Status.AVAILABLE
            )

        if FaultReport.objects.exists() and not options["reset"]:
            self.stdout.write(self.style.WARNING("运维数据已存在，跳过。使用 --reset 重建。"))
            return

        random.seed(20260920)

        devices = list(Device.objects.select_related("laboratory", "category").all())
        if not devices:
            self.stdout.write(self.style.ERROR(
                "未找到任何设备，请先执行 init_demo_data"
            ))
            return

        managers = list(User.objects.filter(
            role__in=[User.Role.LAB_ADMIN, User.Role.SYS_ADMIN], is_active=True
        ))
        students = list(User.objects.filter(role=User.Role.STUDENT, is_active=True)[:5])
        if not managers or not students:
            self.stdout.write(self.style.ERROR("缺少管理员或学生账号，请先初始化用户。"))
            return

        plans = self._create_plans(devices, managers)
        faults = self._create_faults(devices, students, managers)
        orders = self._create_orders(faults, devices, managers)
        self._update_orders_progress(orders, managers)
        self._create_records(devices, managers, plans)

        self.stdout.write(self.style.SUCCESS("运维演示数据初始化完成！"))
        self.stdout.write(self.style.HTTP_INFO(
            f"  故障报修 {FaultReport.objects.count()} 条"
        ))
        self.stdout.write(self.style.HTTP_INFO(
            f"  维修工单 {MaintenanceOrder.objects.count()} 个"
        ))
        self.stdout.write(self.style.HTTP_INFO(
            f"  维保计划 {MaintenancePlan.objects.count()} 条"
        ))
        self.stdout.write(self.style.HTTP_INFO(
            f"  巡检记录 {InspectRecord.objects.count()} 条"
        ))

    # ----------------------------------------------------------
    def _create_plans(self, devices, managers):
        plans = []
        samples = [
            ("显微镜月度校准", "monthly", 30, [
                {"item": "清洁镜头", "required": True},
                {"item": "校准焦距", "required": True},
                {"item": "检查光源", "required": True},
                {"item": "登记使用记录", "required": False},
            ], "确保成像精度"),
            ("计算机季度深度维护", "quarterly", 90, [
                {"item": "清灰", "required": True},
                {"item": "系统补丁升级", "required": True},
                {"item": "硬盘健康检测", "required": True},
                {"item": "外设接口检查", "required": False},
            ], "延长设备寿命"),
            ("网络设备周巡检", "weekly", 7, [
                {"item": "指示灯检查", "required": True},
                {"item": "端口流量", "required": False},
                {"item": "日志巡检", "required": True},
            ], "及时发现网络异常"),
        ]
        categories = list(DeviceCategory.objects.all())
        for i, (name, cycle, days, checklist, desc) in enumerate(samples):
            device = devices[i % len(devices)]
            responsible = managers[i % len(managers)]
            due = datetime.date.today() + datetime.timedelta(days=(i - 1) * 3)
            plan = MaintenancePlan.objects.create(
                name=name,
                device=device,
                device_category=device.category,
                laboratory=device.laboratory,
                cycle=cycle,
                interval_days=days,
                checklist=checklist,
                responsible=responsible,
                responsible_name=responsible.real_name or responsible.username,
                next_due_date=due,
                last_done_date=due - datetime.timedelta(days=days),
                description=desc,
                is_active=True,
            )
            plans.append(plan)
        return plans

    def _create_faults(self, devices, students, managers):
        """生成若干故障报修单。"""
        faults = []
        samples = [
            ("数字示波器开机无显示", "hardware", "urgent",
             "通电后指示灯不亮，屏幕无任何反应，疑似电源板故障。"),
            ("3D 打印机喷头堵塞", "hardware", "high",
             "打印中途喷头温度异常报警，已暂停任务。"),
            ("频谱分析仪连接异常", "software", "normal",
             "上位机软件识别不到设备，USB 接口疑似松动。"),
            ("图形工作站蓝屏", "software", "high",
             "运行仿真软件时频繁蓝屏，已重启多次。"),
            ("金相显微镜光源不亮", "hardware", "high",
             "调节亮度旋钮无效，光源模块疑似损坏。"),
            ("路由器端口异常", "hardware", "normal",
             "实验室局域网丢包严重，部分端口无响应。"),
            ("操作异常：实验预约时段设备被占用", "operation", "normal",
             "签到后设备仍提示有人占用，请管理员核实。"),
            ("工控机开机报警", "hardware", "urgent",
             "开机风扇异响并伴随三短一长 BIOS 报警。"),
        ]
        for i, (title, ftype, sev, desc) in enumerate(samples):
            device = devices[i % len(devices)]
            reporter = students[i % len(students)]
            fault = FaultReport.objects.create(
                device=device,
                laboratory=device.laboratory,
                reporter=reporter,
                reporter_name=reporter.real_name or reporter.username,
                reporter_role=reporter.role,
                reporter_phone=reporter.phone or "",
                fault_type=ftype,
                severity=sev,
                description=f"{title}：{desc}",
                images=[],
                status=FaultReport.Status.PENDING,
            )
            faults.append((fault, title, sev))
        return faults

    def _create_orders(self, faults, devices, managers):
        """将前几条报修转为维修工单并补充几个非报修来源的工单。"""
        orders = []
        # 来自报修
        for i, (fault, title, sev) in enumerate(faults[:5]):
            priority = {
                "urgent": MaintenanceOrder.Priority.P0,
                "high": MaintenanceOrder.Priority.P1,
                "normal": MaintenanceOrder.Priority.P2,
            }.get(sev, MaintenanceOrder.Priority.P2)
            handler = managers[i % len(managers)]
            order = MaintenanceOrder.objects.create(
                title=f"维修-{title}",
                source=MaintenanceOrder.Source.FAULT,
                device=fault.device,
                laboratory=fault.laboratory,
                fault=fault,
                priority=priority,
                status=MaintenanceOrder.Status.PENDING,
                handler=handler,
                handler_name=handler.real_name or handler.username,
                dispatcher=managers[0],
                dispatcher_name=managers[0].real_name or managers[0].username,
                fault_desc=fault.description,
                scheduled_time=timezone.now() + datetime.timedelta(hours=4),
            )
            fault.status = FaultReport.Status.DISPATCHED
            fault.order = order
            fault.save(update_fields=["status", "order", "updated_at"])
            orders.append(order)

        # 计划性维护工单
        device = devices[len(devices) // 2]
        plan_order = MaintenanceOrder.objects.create(
            title="计划维护-计算机季度深度维护",
            source=MaintenanceOrder.Source.PLAN,
            device=device,
            laboratory=device.laboratory,
            priority=MaintenanceOrder.Priority.P3,
            status=MaintenanceOrder.Status.PENDING,
            handler=managers[1 % len(managers)],
            handler_name=(managers[1 % len(managers)].real_name
                          or managers[1 % len(managers)].username),
            dispatcher=managers[0],
            dispatcher_name=managers[0].real_name or managers[0].username,
            fault_desc="按维保计划执行季度深度维护",
            scheduled_time=timezone.now() + datetime.timedelta(days=2),
        )
        orders.append(plan_order)

        # 主动维护工单
        device2 = devices[(len(devices) + 1) % len(devices)]
        routine = MaintenanceOrder.objects.create(
            title="主动维护-光电检测室显微镜清洁",
            source=MaintenanceOrder.Source.ROUTINE,
            device=device2,
            laboratory=device2.laboratory,
            priority=MaintenanceOrder.Priority.P3,
            status=MaintenanceOrder.Status.PENDING,
            handler=managers[2 % len(managers)],
            handler_name=(managers[2 % len(managers)].real_name
                          or managers[2 % len(managers)].username),
            dispatcher=managers[0],
            dispatcher_name=managers[0].real_name or managers[0].username,
            fault_desc="学期中例行清洁保养",
            scheduled_time=timezone.now() + datetime.timedelta(days=3),
        )
        orders.append(routine)
        return orders

    def _update_orders_progress(self, orders, managers):
        """让部分工单进入处理中 / 已修复 / 已验收，让数据看起来真实。"""
        # 让第一个工单完整闭环
        o = orders[0]
        o.status = MaintenanceOrder.Status.PROCESSING
        o.started_time = o.created_at + datetime.timedelta(minutes=45)
        o.save(update_fields=["status", "started_time", "updated_at"])

        if len(orders) > 1:
            o2 = orders[1]
            o2.status = MaintenanceOrder.Status.RESOLVED
            o2.started_time = o2.created_at + datetime.timedelta(hours=2)
            o2.completed_time = o2.started_time + datetime.timedelta(hours=3)
            o2.solution = "更换电源板后通电测试正常，示波器各档位输出符合指标。"
            o2.parts_replaced = "电源模块 ×1"
            o2.cost = 280
            o2.images = []
            o2.save()

        if len(orders) > 2:
            o3 = orders[2]
            o3.status = MaintenanceOrder.Status.VERIFIED
            o3.started_time = o3.created_at + datetime.timedelta(hours=1)
            o3.completed_time = o3.started_time + datetime.timedelta(hours=1)
            o3.solution = "清理喷头残留物并重新调平，温度恢复稳定。"
            o3.parts_replaced = "喷嘴组件 ×1"
            o3.cost = 150
            o3.verified_time = o3.completed_time + datetime.timedelta(hours=1)
            o3.verifier = managers[0]
            o3.save()

    def _create_records(self, devices, managers, plans):
        """为部分计划生成已执行记录。"""
        for i, plan in enumerate(plans):
            if not plan.device_id:
                continue
            for j in range(2):
                record_time = timezone.now() - datetime.timedelta(days=(j + 1) * (plan.interval_days or 30))
                result = (
                    InspectRecord.Result.NORMAL if j == 0 else random.choice([
                        InspectRecord.Result.NORMAL,
                        InspectRecord.Result.NORMAL,
                        InspectRecord.Result.ABNORMAL,
                    ])
                )
                InspectRecord.objects.create(
                    plan=plan,
                    device=plan.device,
                    laboratory=plan.laboratory or plan.device.laboratory,
                    inspector=managers[i % len(managers)],
                    inspector_name=(managers[i % len(managers)].real_name
                                    or managers[i % len(managers)].username),
                    inspected_at=record_time,
                    result=result,
                    issues="发现设备外壳积灰，建议下次维护时清理。" if result == InspectRecord.Result.ABNORMAL else "",
                    checklist_result=[
                        {"item": item["item"], "ok": True} for item in plan.checklist
                    ],
                    images=[],
                )