"""初始化演示数据（毕业设计答辩演示用）。

用法：
    python manage.py init_demo_data           # 已有数据则跳过
    python manage.py init_demo_data --reset   # 清空业务数据后重新生成
"""
import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ClassGroup, College, User
from apps.labs.models import Device, DeviceCategory, Laboratory
from apps.maintenance.models import (
    FaultReport,
    InspectRecord,
    MaintenanceOrder,
    MaintenancePlan,
)
from apps.notifications.models import Notification
from apps.reservations.models import (
    ChatMessage,
    ChatThread,
    Evaluation,
    Reservation,
    ReservationStatusLog,
)
from apps.reservations.services import change_status, generate_reservation_no

DEFAULT_PASSWORD = "123456"

DEVICE_DATA = [
    ("电子测量仪器", "CAT-EM", ["数字示波器", "函数信号发生器", "数字万用表", "频谱分析仪", "直流稳压电源"], "泰克/是德"),
    ("计算机设备", "CAT-PC", ["图形工作站", "高性能服务器", "嵌入式开发板", "树莓派套件", "工业控制计算机"], "联想/戴尔"),
    ("网络设备", "CAT-NET", ["核心交换机", "路由器", "无线AP", "防火墙设备", "网络测试仪"], "华为/新华三"),
    ("光学仪器", "CAT-OPT", ["激光干涉仪", "金相显微镜", "光谱分析仪", "光学平台", "CCD相机"], "尼康/奥林巴斯"),
    ("加工制造设备", "CAT-MFG", ["3D打印机", "激光切割机", "数控铣床", "精密雕刻机", "超声波清洗机"], "创想三维/大族"),
]

LAB_DATA = [
    ("计算机组成原理实验室", "LAB-001", "信息楼 A301", 60, "1,2,3,4,5", 8, 22, 0),
    ("网络工程与安全实验室", "LAB-002", "信息楼 A305", 48, "1,2,3,4,5,6", 8, 21, 1),
    ("电子技术基础实验室", "LAB-003", "电子楼 B201", 40, "1,2,3,4,5", 8, 20, 1),
    ("光电检测实验室", "LAB-004", "光电楼 C102", 30, "1,2,3,4,5", 9, 18, 0),
    ("智能制造实训中心", "LAB-005", "工程实训楼 D101", 50, "1,2,3,4,5,6", 8, 20, 1),
    ("人工智能与嵌入式实验室", "LAB-006", "信息楼 A401", 45, "1,2,3,4,5,6,7", 8, 22, 0),
]


class Command(BaseCommand):
    help = "初始化毕业设计演示数据"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="清空业务数据后重新生成")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write(self.style.WARNING("正在清空业务数据..."))
            Notification.objects.all().delete()
            ChatMessage.objects.all().delete()
            ChatThread.objects.all().delete()
            Evaluation.objects.all().delete()
            ReservationStatusLog.objects.all().delete()
            Reservation.objects.all().delete()
            # 运维数据必须先于设备/实验室删除（PROTECT 外键引用）
            InspectRecord.objects.all().delete()
            MaintenanceOrder.objects.all().delete()
            FaultReport.objects.all().delete()
            MaintenancePlan.objects.all().delete()
            Device.objects.all().delete()
            Laboratory.objects.all().delete()
            DeviceCategory.objects.all().delete()
            User.objects.exclude(username="admin").delete()

        if User.objects.filter(username="admin").exists() and not options["reset"]:
            self.stdout.write(self.style.WARNING(
                "检测到已有数据，如需重建请执行：python manage.py init_demo_data --reset"
            ))
            self._print_accounts()
            return

        random.seed(2026)
        colleges = self._create_colleges()
        classes = self._create_classes(colleges)
        users = self._create_users(colleges, classes)
        categories = self._create_categories()
        labs = self._create_labs(users)
        devices = self._create_devices(categories, labs)
        self._create_reservations(users, labs, devices)

        self.stdout.write(self.style.SUCCESS("演示数据初始化完成！"))
        self._print_accounts()

    # ------------------------------------------------------------------
    def _create_colleges(self):
        data = [
            ("计算机与信息工程学院", "CIE"),
            ("电子与电气工程学院", "EEE"),
            ("光电与智能感知学院", "OIS"),
            ("机械与智能制造学院", "MIM"),
        ]
        colleges = {}
        for name, code in data:
            colleges[code], _ = College.objects.get_or_create(
                name=name, defaults={"code": code}
            )
        self.stdout.write(f"学院：{len(colleges)} 个")
        return colleges

    def _create_classes(self, colleges):
        data = [
            ("CIE", "计算机科学与技术2101班", "2021"),
            ("CIE", "计算机科学与技术2102班", "2021"),
            ("CIE", "软件工程2201班", "2022"),
            ("EEE", "电子信息工程2101班", "2021"),
            ("EEE", "自动化2201班", "2022"),
            ("OIS", "光电信息科学与工程2101班", "2021"),
            ("MIM", "机械设计制造及其自动化2201班", "2022"),
        ]
        classes = []
        for college_code, name, grade in data:
            obj, _ = ClassGroup.objects.get_or_create(
                name=name, college=colleges[college_code], defaults={"grade": grade}
            )
            classes.append(obj)
        self.stdout.write(f"班级：{len(classes)} 个")
        return classes

    def _create_users(self, colleges, classes):
        users = {}

        def make(username, real_name, role, **kwargs):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"real_name": real_name, "role": role, **kwargs},
            )
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
            users[username] = user
            return user

        admin = make(
            "admin", "系统管理员", User.Role.SYS_ADMIN,
            email="admin@university.edu.cn", phone="13800000000",
            student_no="A0001", is_staff=True, is_superuser=True,
        )

        lab_admin1 = make("labadmin1", "赵国栋", User.Role.LAB_ADMIN,
                          email="zhaogd@university.edu.cn", phone="13800000011",
                          student_no="T1001")
        lab_admin2 = make("labadmin2", "孙晓燕", User.Role.LAB_ADMIN,
                          email="sunxy@university.edu.cn", phone="13800000012",
                          student_no="T1002")
        lab_admin3 = make("labadmin3", "陈国强", User.Role.LAB_ADMIN,
                          email="chengq@university.edu.cn", phone="13800000013",
                          student_no="T1003")

        teacher_data = [
            ("teacher1", "张伟", "CIE", 0),
            ("teacher2", "李静", "EEE", 3),
            ("teacher3", "王海涛", "OIS", 5),
        ]
        for username, real_name, college_code, class_index in teacher_data:
            make(username, real_name, User.Role.TEACHER,
                 college=colleges[college_code], class_group=classes[class_index],
                 phone=f"139{random.randint(10000000, 99999999)}",
                 student_no=f"T2{random.randint(100, 999)}",
                 email=f"{username}@university.edu.cn")

        student_names = [
            ("student1", "李明", 0), ("student2", "王芳", 0), ("student3", "刘洋", 1),
            ("student4", "赵敏", 2), ("student5", "周杰", 3), ("student6", "吴倩", 4),
            ("student7", "郑凯", 5), ("student8", "冯雪", 6),
        ]
        for index, (username, real_name, class_index) in enumerate(student_names, start=1):
            class_obj = classes[class_index]
            make(
                username, real_name, User.Role.STUDENT,
                college=class_obj.college, class_group=class_obj,
                student_no=f"2022{class_obj.grade[-2:]}{index:04d}",
                phone=f"137{random.randint(10000000, 99999999)}",
                email=f"{username}@stu.university.edu.cn",
            )

        self.stdout.write(f"用户：{len(users)} 个（默认密码 {DEFAULT_PASSWORD}）")
        return users

    def _create_categories(self):
        categories = []
        for index, (name, code, _, _) in enumerate(DEVICE_DATA):
            obj, _ = DeviceCategory.objects.get_or_create(
                name=name, defaults={"code": code, "sort_order": index,
                                     "description": f"{name}类设备"}
            )
            categories.append(obj)
        self.stdout.write(f"设备分类：{len(categories)} 个")
        return categories

    def _create_labs(self, users):
        labs = []
        manager_map = {
            "LAB-001": ["labadmin1"],
            "LAB-002": ["labadmin1", "labadmin3"],
            "LAB-003": ["labadmin2"],
            "LAB-004": ["labadmin2"],
            "LAB-005": ["labadmin3"],
            "LAB-006": ["labadmin1", "labadmin2"],
        }
        for name, code, location, capacity, weekdays, start, end, _ in LAB_DATA:
            lab, created = Laboratory.objects.get_or_create(
                code=code,
                defaults={
                    "name": name, "location": location, "capacity": capacity,
                    "open_weekdays": weekdays,
                    "open_time_start": datetime.time(start, 0),
                    "open_time_end": datetime.time(end, 0),
                    "description": f"{name}，可容纳 {capacity} 人，配备多类教学科研设备。",
                },
            )
            if created:
                lab.managers.set([users[u] for u in manager_map.get(code, [])])
            labs.append(lab)
        self.stdout.write(f"实验室：{len(labs)} 个")
        return labs

    def _create_devices(self, categories, labs):
        devices = []
        seq = 1
        manufacturers = ["泰克", "是德科技", "华为", "联想", "戴尔", "大族激光", "创想三维", "尼康"]
        for lab in labs:
            for index, category in enumerate(categories):
                if index >= len(DEVICE_DATA):
                    continue
                names = DEVICE_DATA[index][2]
                for name in names[:2]:
                    code = f"DEV-{2026}-{seq:04d}"
                    device, created = Device.objects.get_or_create(
                        code=code,
                        defaults={
                            "name": name,
                            "model": f"{name[:2].upper()}-{random.randint(100, 999)}",
                            "category": category,
                            "laboratory": lab,
                            "status": Device.Status.AVAILABLE,
                            "specification": f"教学科研级{name}，标准配置",
                            "manufacturer": random.choice(manufacturers),
                            "purchase_date": datetime.date(2024, random.randint(1, 12), random.randint(1, 28)),
                            "price": round(random.uniform(2000, 68000), 2),
                            "remark": "正常在用",
                        },
                    )
                    if created:
                        devices.append(device)
                        seq += 1

        # 少量设备设为维修中 / 已报废，便于演示状态区分
        for device in devices[:4]:
            device.status = Device.Status.REPAIRING
            device.remark = "故障送修中"
        for device in devices[4:6]:
            device.status = Device.Status.SCRAPPED
            device.is_active = False
            device.remark = "已达报废年限"
        Device.objects.bulk_update(devices[:6], ["status", "is_active", "remark"])

        all_devices = list(Device.objects.all())
        self.stdout.write(f"设备：{len(all_devices)} 台")
        return all_devices

    def _create_reservations(self, users, labs, devices):
        applicants = [
            users["student1"], users["student2"], users["student3"], users["student4"],
            users["student5"], users["student6"], users["student7"], users["student8"],
            users["teacher1"], users["teacher2"], users["teacher3"],
        ]
        purposes = [
            "课程设计实验验证", "毕业设计数据采集", "科研项目测试", "学科竞赛作品调试",
            "开放性实验项目", "课程实验教学演示", "设备功能测试与标定", "创新实验项目研究",
        ]
        now = timezone.now()
        created_count = 0

        plans = [
            # (天数偏移, 起始小时, 时长小时, 状态)
            (-20, 9, 3, Reservation.Status.COMPLETED),
            (-18, 14, 2, Reservation.Status.COMPLETED),
            (-15, 10, 4, Reservation.Status.COMPLETED),
            (-12, 15, 3, Reservation.Status.COMPLETED),
            (-10, 9, 2, Reservation.Status.REJECTED),
            (-9, 13, 4, Reservation.Status.COMPLETED),
            (-7, 10, 3, Reservation.Status.CANCELLED),
            (-5, 14, 2, Reservation.Status.COMPLETED),
            (-3, 9, 4, Reservation.Status.COMPLETED),
            (-2, 16, 2, Reservation.Status.COMPLETED),
            (-1, 10, 3, Reservation.Status.COMPLETED),
            (0, 8, 4, Reservation.Status.IN_USE),
            (0, 13, 3, Reservation.Status.PENDING),
            (0, 15, 2, Reservation.Status.PENDING),
            (1, 9, 4, Reservation.Status.WAITING_USE),
            (1, 14, 3, Reservation.Status.APPROVED),
            (2, 10, 4, Reservation.Status.PENDING),
            (2, 15, 2, Reservation.Status.APPROVED),
            (3, 9, 3, Reservation.Status.PENDING),
            (4, 13, 4, Reservation.Status.APPROVED),
            (-4, 9, 3, Reservation.Status.IN_USE),  # 用于演示逾期
        ]

        reservable = [d for d in devices if d.is_active and d.status == Device.Status.AVAILABLE]
        if not reservable:
            reservable = devices
        index = 0

        for offset, hour, duration, target_status in plans:
            device = reservable[index % len(reservable)]
            index += 1
            lab = device.laboratory
            applicant = applicants[index % len(applicants)]

            base_date = (now + datetime.timedelta(days=offset)).date()
            if not lab.open_weekday_list or base_date.isoweekday() not in lab.open_weekday_list:
                for shift in range(1, 8):
                    candidate = base_date + datetime.timedelta(days=shift)
                    if candidate.isoweekday() in lab.open_weekday_list:
                        base_date = candidate
                        break

            start = datetime.datetime.combine(base_date, datetime.time(hour, 0))
            limit_hours = applicant.max_reserve_hours
            duration = min(duration, limit_hours, 4 if applicant.is_student else 8)
            end = start + datetime.timedelta(hours=duration)
            if end.time() > lab.open_time_end:
                end = datetime.datetime.combine(base_date, lab.open_time_end)
                start = end - datetime.timedelta(hours=duration)

            reservation = Reservation.objects.create(
                no=generate_reservation_no(lab),
                applicant=applicant,
                applicant_name=applicant.real_name,
                applicant_role=applicant.role,
                college_name=applicant.college.name if applicant.college else "",
                class_name=applicant.class_group.name if applicant.class_group else "",
                contact_phone=applicant.phone,
                laboratory=lab,
                device=device,
                start_time=start,
                end_time=end,
                purpose=random.choice(purposes),
                urgency=random.choice([Reservation.Urgency.NORMAL] * 4 + [Reservation.Urgency.URGENT]),
                status=Reservation.Status.PENDING,
                submit_time=start - datetime.timedelta(days=2),
            )
            created_count += 1

            manager = lab.managers.first() or users["labadmin1"]
            self._advance(reservation, target_status, applicant, manager, lab, now)
            self._maybe_chat(reservation, applicant, manager, target_status)
            self._maybe_evaluate(reservation, applicant, target_status)

        self.stdout.write(f"预约单：{created_count} 条")

    def _advance(self, reservation, target_status, applicant, manager, lab, now):
        """按目标状态补全流转数据与状态日志。"""
        status = Reservation.Status

        def log(from_s, to_s, action, operator, remark):
            ReservationStatusLog.objects.create(
                reservation=reservation, from_status=from_s, to_status=to_s,
                action=action,
                operator=operator, operator_name=operator.real_name or operator.username,
                remark=remark,
            )

        if target_status == status.PENDING:
            log("", status.PENDING, "submit", applicant, "提交预约申请")
            return

        reservation.approver = manager
        reservation.approver_name = manager.real_name
        reservation.approve_time = reservation.submit_time + datetime.timedelta(hours=6)
        log(status.PENDING, status.PENDING, "submit", applicant, "提交预约申请")

        if target_status == status.REJECTED:
            reservation.reject_reason = random.choice(
                ["该时段设备已被占用，建议改期", "预约用途说明不充分，请补充后重新提交",
                 "设备近期需进行校准维护，暂不可用"]
            )
            reservation.status = status.REJECTED
            reservation.save()
            log(status.PENDING, status.REJECTED, "reject", manager, f"驳回：{reservation.reject_reason}")
            return

        reservation.approve_remark = random.choice(
            ["同意使用，请按时归还", "审批通过，注意设备安全", "同意，使用完毕请签退"]
        )
        reservation.status = status.APPROVED
        reservation.save()
        log(status.PENDING, status.APPROVED, "approve", manager, "审批通过")

        if target_status == status.CANCELLED:
            reservation.cancel_reason = "因课程安排冲突，主动取消"
            reservation.status = status.CANCELLED
            reservation.save()
            log(status.APPROVED, status.CANCELLED, "cancel", applicant, "取消预约：课程冲突")
            return

        if target_status == status.WAITING_USE:
            reservation.status = status.WAITING_USE
            reservation.save()
            return

        if target_status in (status.IN_USE, status.COMPLETED):
            reservation.sign_in_time = reservation.start_time + datetime.timedelta(minutes=5)
            reservation.status = status.IN_USE
            reservation.save()
            log(status.APPROVED, status.IN_USE, "sign_in", applicant, "签到开始使用")

        if target_status == status.COMPLETED:
            reservation.sign_out_time = reservation.end_time - datetime.timedelta(minutes=5)
            reservation.device_status_after = random.choice(
                [Device.Status.AVAILABLE] * 4 + [Device.Status.REPAIRING]
            )
            if reservation.device_status_after == Device.Status.REPAIRING:
                reservation.abnormal_note = random.choice(
                    ["设备读数异常，需检查", "接口松动，已现场处理", "风扇异响，建议检修"]
                )
            reservation.status = status.COMPLETED
            reservation.return_confirmed = True
            reservation.completion_time = reservation.end_time + datetime.timedelta(minutes=15)
            reservation.completion_operator = manager
            reservation.completion_remark = "设备已归还，外观与功能核验正常"
            reservation.save()
            log(status.IN_USE, status.COMPLETED, "complete", manager, "设备已归还并核验完成")
            reservation.device.status = Device.Status.AVAILABLE
            reservation.device.save(update_fields=["status", "updated_at"])

    def _maybe_chat(self, reservation, applicant, manager, target_status):
        """为部分预约生成图文沟通记录。"""
        if target_status in (Reservation.Status.REJECTED, Reservation.Status.CANCELLED):
            return
        if random.random() > 0.55:
            return

        thread = ChatThread.objects.create(
            reservation=reservation,
            status=ChatThread.Status.PENDING_REPLY,
            message_count=2,
            last_sender=manager,
        )
        questions = [
            "老师您好，请问设备使用前需要做哪些准备？",
            "管理员您好，我可以提前 15 分钟到实验室吗？",
            "请问这个设备需要自带数据线吗？",
        ]
        answers = [
            "同学你好，设备已检查可用，按时签到即可。",
            "可以提前到场，请先在实验室门禁处登记。",
            "设备配套线材齐全，无需自带。",
        ]
        msg1 = ChatMessage.objects.create(
            thread=thread, sender=applicant,
            sender_name=applicant.real_name or applicant.username,
            sender_role=applicant.role, is_admin_side=False,
            content=random.choice(questions), is_read=True,
            created_at=reservation.submit_time + datetime.timedelta(minutes=30),
        )
        ChatMessage.objects.create(
            thread=thread, sender=manager,
            sender_name=manager.real_name or manager.username,
            sender_role=manager.role, is_admin_side=True,
            content=random.choice(answers), reply_to=msg1, is_read=True,
            created_at=reservation.submit_time + datetime.timedelta(hours=2),
        )
        thread.status = ChatThread.Status.REPLIED
        thread.last_message_time = reservation.submit_time + datetime.timedelta(hours=2)
        thread.save()

    def _maybe_evaluate(self, reservation, applicant, target_status):
        if target_status != Reservation.Status.COMPLETED:
            return
        if random.random() > 0.7:
            return
        evaluation = Evaluation.objects.create(
            reservation=reservation,
            device_score=random.randint(3, 5),
            speed_score=random.randint(3, 5),
            service_score=random.randint(4, 5),
            content=random.choice([
                "设备状态良好，管理员响应及时，体验不错。",
                "实验室环境整洁，设备精度满足实验要求。",
                "审批速度很快，希望增加更多同型号设备。",
                "整体满意，管理老师很热心。",
            ]),
            evaluator=applicant,
            evaluator_name=applicant.real_name or applicant.username,
        )
        evaluation.average_score = evaluation.compute_average()
        evaluation.save(update_fields=["average_score"])
        reservation.is_evaluated = True
        reservation.save(update_fields=["is_evaluated", "updated_at"])

    def _print_accounts(self):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=" * 66))
        self.stdout.write(self.style.HTTP_INFO("演示账号（密码统一为 123456）"))
        self.stdout.write(self.style.HTTP_INFO("=" * 66))
        rows = [
            ("admin", "系统管理员", "全部数据 / 用户管理 / 统计与日志"),
            ("labadmin1", "实验室管理员", "LAB-001、LAB-002、LAB-006"),
            ("labadmin2", "实验室管理员", "LAB-003、LAB-004、LAB-006"),
            ("labadmin3", "实验室管理员", "LAB-002、LAB-005"),
            ("teacher1", "教师", "张伟（计算机与信息工程学院）"),
            ("student1", "学生", "李明（计算机科学与技术2101班）"),
            ("student2", "学生", "王芳（计算机科学与技术2101班）"),
            ("student3", "学生", "刘洋（计算机科学与技术2102班）"),
        ]
        for username, role, remark in rows:
            self.stdout.write(f"  {username:<12}{role:<10}{remark}")
        self.stdout.write(self.style.HTTP_INFO("=" * 66))
