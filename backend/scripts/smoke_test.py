"""接口冒烟测试：验证四类角色的核心业务流程是否正常。

用法：
    python scripts/smoke_test.py
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "labsys.settings")

import django  # noqa: E402

django.setup()

import datetime  # noqa: E402

from rest_framework.test import APIClient  # noqa: E402

PASSED = 0
FAILED = 0
SKIPPED = 0


def check(name, response, expect_status=200, expect_code=0):
    global PASSED, FAILED
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        body = {}
    ok = response.status_code == expect_status
    if expect_status == 200 and expect_code is not None and isinstance(body, dict):
        if "code" in body:
            ok = ok and body.get("code") == expect_code
    if ok:
        PASSED += 1
        print(f"  [OK]   {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} -> HTTP {response.status_code}  {str(body)[:200]}")
    return body if isinstance(body, dict) else {}


def skip(message):
    global SKIPPED
    SKIPPED += 1
    print(f"  [SKIP] {message}")


def _inc_pass(name):
    global PASSED
    PASSED += 1
    print(f"  [OK]   {name}")


def login(username, password="123456"):
    client = APIClient()
    response = client.post("/api/auth/login/", {"username": username, "password": password},
                           format="json")
    data = response.json()
    assert response.status_code == 200, f"{username} 登录失败: {data}"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['data']['access']}")
    return client, data["data"]["user"]


def next_open_datetime(weekdays, hour=9, days_ahead=2):
    """找到下一个符合实验室开放日的日期时间。"""
    allowed = [int(x) for x in str(weekdays).split(",") if x.strip().isdigit()]
    moment = datetime.datetime.now() + datetime.timedelta(days=days_ahead)
    for _ in range(14):
        if moment.isoweekday() in allowed:
            break
        moment += datetime.timedelta(days=1)
    return moment.replace(hour=hour, minute=0, second=0, microsecond=0)


def find_free_slot(client, devices, lab_weekdays, hours, hour=9, offsets=(2, 3, 5, 7, 11)):
    """遍历设备与日期，返回一个无冲突的 (设备, 开始时间, 结束时间)。"""
    for days in offsets:
        for index, device in enumerate(devices[:12]):
            begin = next_open_datetime(lab_weekdays.get(device["laboratory"], "1,2,3,4,5"),
                                       hour, days)
            finish = begin + datetime.timedelta(hours=hours)
            body = client.post("/api/reservations/check-conflict/", {
                "laboratory": device["laboratory"], "device": device["id"],
                "start_time": begin.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": finish.strftime("%Y-%m-%d %H:%M:%S"),
            }, format="json").json()
            if body.get("data", {}).get("available"):
                return device, begin, finish
    return None, None, None


def main():
    print("=" * 72)
    print("高校实验室设备预约运维系统 —— 接口冒烟测试")
    print("=" * 72)

    # ================= 1. 账号与权限 =================
    print("\n[1] 账号与权限")
    admin, admin_info = login("admin")
    labadmin, labadmin_info = login("labadmin1")
    teacher, teacher_info = login("teacher1")
    student, student_info = login("student1")
    print(f"  登录用户：{admin_info['real_name']} / {labadmin_info['real_name']} / "
          f"{teacher_info['real_name']} / {student_info['real_name']}")

    check("获取个人资料", admin.get("/api/accounts/profile/"))
    check("修改密码-原密码错误拦截",
          student.post("/api/accounts/change-password/",
                       {"old_password": "wrong", "new_password": "1234567",
                        "confirm_password": "1234567"}, format="json"), expect_status=400)
    check("修改密码-两次不一致拦截",
          student.post("/api/accounts/change-password/",
                       {"old_password": "123456", "new_password": "1234567",
                        "confirm_password": "7654321"}, format="json"), expect_status=400)
    check("用户列表（系统管理员）", admin.get("/api/accounts/users/"))
    check("用户列表越权（学生）", student.get("/api/accounts/users/"), expect_status=403)
    check("用户精简列表", admin.get("/api/accounts/users/simple/?role=lab_admin"))
    check("学院列表", student.get("/api/accounts/colleges/"))
    check("班级列表", student.get("/api/accounts/classes/"))

    # ================= 2. 设备与实验室管理 =================
    print("\n[2] 设备与实验室管理")
    check("实验室列表", student.get("/api/labs/"))
    check("实验室检索", student.get("/api/labs/?keyword=实验室"))
    labs_simple = check("实验室下拉", student.get("/api/labs/simple/"))
    lab_weekdays = {item["id"]: item["open_weekdays"] for item in labs_simple.get("data", [])}
    lab_info = {item["id"]: item for item in labs_simple.get("data", [])}
    lab_id = next(iter(lab_weekdays), None)
    check("设备分类", student.get("/api/labs/categories/"))
    check("设备列表", student.get("/api/labs/devices/?page_size=5"))
    check("设备多条件检索", student.get("/api/labs/devices/?status=available&bookable=1&page_size=5"))
    check("设备状态统计", student.get("/api/labs/devices/statistics/"))
    check("设备导入模板下载", admin.get("/api/labs/devices/import-template/"))
    check("设备台账导出", admin.get("/api/labs/devices/export/"))
    check("管理员控制台概览", admin.get("/api/labs/dashboard/overview/"))
    check("控制台越权（学生）", student.get("/api/labs/dashboard/overview/"), expect_status=403)

    devices_body = check("可预约设备", student.get("/api/labs/devices/?bookable=1&page_size=50"))
    device_list = devices_body.get("data", {}).get("results", [])
    if not device_list:
        print("  没有可用设备，测试中止")
        return 1
    device_id = device_list[0]["id"]
    check("设备可用性校验",
          student.get(f"/api/labs/devices/{device_id}/check-available/"
                      f"?start_time={next_open_datetime(lab_weekdays.get(device_list[0]['laboratory'], '1,2,3,4,5'), 9, 2).strftime('%Y-%m-%d %H:%M:%S')}"
                      f"&end_time={next_open_datetime(lab_weekdays.get(device_list[0]['laboratory'], '1,2,3,4,5'), 9, 2).strftime('%Y-%m-%d %H:%M:%S')}"))

    # ================= 3. 预约申请 =================
    print("\n[3] 预约申请")
    device, start, end = find_free_slot(student, device_list, lab_weekdays, hours=3, hour=9)
    if device is None:
        print("  找不到空闲时段，测试中止")
        return 1
    payload = {
        "laboratory": device["laboratory"],
        "device": device["id"],
        "start_time": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end.strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "冒烟测试：课程设计实验验证",
        "urgency": "normal",
        "submit": True,
    }
    check("冲突预校验", student.post("/api/reservations/check-conflict/", payload, format="json"))
    created = check("提交预约并生成编号",
                    student.post("/api/reservations/", payload, format="json"), expect_status=201)
    reservation_id = created.get("data", {}).get("id")
    print(f"  预约编号：{created.get('data', {}).get('no')}  "
          f"时长：{created.get('data', {}).get('duration_hours')} 小时")

    check("学生超时长限制（上限4小时）",
          student.post("/api/reservations/", {
              **payload,
              "end_time": (start + datetime.timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
          }, format="json"), expect_status=400)
    check("同设备同时段冲突拦截",
          student.post("/api/reservations/", {
              **payload,
              "start_time": (start + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
              "end_time": (end + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
          }, format="json"), expect_status=400)
    check("结束时间早于开始时间拦截",
          student.post("/api/reservations/", {
              **payload,
              "start_time": end.strftime("%Y-%m-%d %H:%M:%S"),
              "end_time": start.strftime("%Y-%m-%d %H:%M:%S"),
          }, format="json"), expect_status=400)

    draft_device, draft_start, draft_end = find_free_slot(
        student, [d for d in device_list if d["id"] != device["id"]], lab_weekdays, hours=2, hour=14)
    if draft_device is None:
        print("  找不到第二台设备的空闲时段，跳过暂存/撤回流程")
    else:
        draft_body = check("暂存预约（草稿）",
                           student.post("/api/reservations/", {
                               "laboratory": draft_device["laboratory"],
                               "device": draft_device["id"],
                               "start_time": draft_start.strftime("%Y-%m-%d %H:%M:%S"),
                               "end_time": draft_end.strftime("%Y-%m-%d %H:%M:%S"),
                               "purpose": "", "submit": False,
                           }, format="json"), expect_status=201)
        draft_id = draft_body.get("data", {}).get("id")
        check("暂存单提交", student.post(f"/api/reservations/{draft_id}/submit/", {}, format="json"))
        check("撤回未审批预约",
              student.post(f"/api/reservations/{draft_id}/withdraw/", {"reason": "测试撤回"}, format="json"))

    check("我的预约列表", student.get("/api/reservations/"))
    check("多条件检索（状态+实验室）",
          student.get(f"/api/reservations/?status=pending&laboratory={lab_id}"))
    check("关键词检索", student.get("/api/reservations/?keyword=冒烟测试"))
    check("预约详情（同时写入查阅日志）", student.get(f"/api/reservations/{reservation_id}/"))
    check("我的待办", student.get("/api/reservations/todo/"))
    check("使用进度与预计可用时间", student.get("/api/reservations/my-progress/"))
    check("设备占用情况", student.get(f"/api/reservations/device-usage/?device={device['id']}"))
    check("状态流转记录", student.get(f"/api/reservations/status-logs/?reservation={reservation_id}"))
    check("越权访问他人预约（教师）",
          teacher.get(f"/api/reservations/{reservation_id}/"), expect_status=404)

    # ================= 4. 审批与冲突控制 =================
    print("\n[4] 审批与冲突控制")
    check("管理员待审批列表", labadmin.get("/api/reservations/?status=pending"))
    check("非本实验室管理员数据隔离（无法访问）",
          login("labadmin2")[0].post(f"/api/reservations/{reservation_id}/reject/",
                                     {"reject_reason": "测试越权"}, format="json"),
          expect_status=404)
    check("审批通过", labadmin.post(f"/api/reservations/{reservation_id}/approve/",
                                    {"approve_remark": "同意使用，请按时归还"}, format="json"))

    managed_lab_ids = {m["id"] for m in labadmin_info.get("managed_labs", [])}
    transfer_candidates = [d for d in device_list if d["laboratory"] in managed_lab_ids]
    transfer_device, transfer_start, transfer_end = find_free_slot(
        student, transfer_candidates or device_list, lab_weekdays,
        hours=2, hour=10, offsets=(3, 4, 6, 9))
    transfer_body = check("提交待转派预约",
                          student.post("/api/reservations/", {
                              "laboratory": transfer_device["laboratory"],
                              "device": transfer_device["id"],
                              "start_time": transfer_start.strftime("%Y-%m-%d %H:%M:%S"),
                              "end_time": transfer_end.strftime("%Y-%m-%d %H:%M:%S"),
                              "purpose": "冒烟测试：待转派",
                          }, format="json"), expect_status=201)
    transfer_id = transfer_body.get("data", {}).get("id")
    check("转派给其他管理员",
          labadmin.post(f"/api/reservations/{transfer_id}/transfer/",
                        {"approver": labadmin_info["id"], "remark": "转派处理"}, format="json"))
    check("转派对象非法拦截",
          labadmin.post(f"/api/reservations/{transfer_id}/transfer/",
                        {"approver": student_info["id"]}, format="json"), expect_status=400)
    check("重复审批拦截",
          labadmin.post(f"/api/reservations/{reservation_id}/approve/", {}, format="json"),
          expect_status=400)
    check("驳回未填原因拦截",
          labadmin.post(f"/api/reservations/{transfer_id}/reject/", {}, format="json"),
          expect_status=400)
    check("驳回并填写原因",
          labadmin.post(f"/api/reservations/{transfer_id}/reject/",
                        {"reject_reason": "该时段设备需维护，请改期"}, format="json"))

    # ================= 5. 使用进度 =================
    print("\n[5] 使用进度")
    check("未到签到时间拦截",
          student.post(f"/api/reservations/{reservation_id}/sign-in/", {}, format="json"),
          expect_status=400)

    now = datetime.datetime.now()
    sign_device = sign_start = sign_end = None
    for item in device_list:
        info = lab_info.get(item["laboratory"])
        if not info:
            continue
        days = [int(x) for x in str(info["open_weekdays"]).split(",") if x.strip().isdigit()]
        if now.isoweekday() not in days:
            continue
        open_start = datetime.datetime.strptime(info["open_time_start"], "%H:%M").time()
        open_end = datetime.datetime.strptime(info["open_time_end"], "%H:%M").time()
        candidate_start = (now + datetime.timedelta(minutes=10)).replace(second=0, microsecond=0)
        candidate_end = candidate_start + datetime.timedelta(hours=1)
        # 候选时段须在同一自然日内（否则跨越午夜，时间比较会误判）
        same_day = candidate_end.date() == candidate_start.date()
        if same_day and open_start <= candidate_start.time() and candidate_end.time() <= open_end:
            sign_device, sign_start, sign_end = item, candidate_start, candidate_end
            break

    if sign_device is None:
        skip("当前时刻所有实验室均不在开放时段，跳过签到/签退/完工/评价流程")
    else:
        sign_body = check("提交即时预约",
                          student.post("/api/reservations/", {
                              "laboratory": sign_device["laboratory"],
                              "device": sign_device["id"],
                              "start_time": sign_start.strftime("%Y-%m-%d %H:%M:%S"),
                              "end_time": sign_end.strftime("%Y-%m-%d %H:%M:%S"),
                              "purpose": "冒烟测试：签到签退流程",
                          }, format="json"), expect_status=201)
        sign_id = sign_body.get("data", {}).get("id")
        if sign_id:
            check("审批即时预约",
                  labadmin.post(f"/api/reservations/{sign_id}/approve/", {}, format="json"))
            check("签到开始使用",
                  student.post(f"/api/reservations/{sign_id}/sign-in/", {}, format="json"))
            check("重复签到拦截",
                  student.post(f"/api/reservations/{sign_id}/sign-in/", {}, format="json"),
                  expect_status=400)
            check("签退并登记设备状态与异常",
                  student.post(f"/api/reservations/{sign_id}/sign-out/",
                               {"device_status_after": "available",
                                "abnormal_note": "设备外观正常"}, format="json"))
            check("完工确认（管理员核验归还）",
                  labadmin.post(f"/api/reservations/{sign_id}/complete/",
                                {"return_confirmed": True, "device_status_after": "available",
                                 "completion_remark": "设备已归还并核验正常"}, format="json"))
            check("评分超范围拦截",
                  student.post(f"/api/reservations/{sign_id}/evaluate/",
                               {"device_score": 9, "speed_score": 5, "service_score": 5},
                               format="json"), expect_status=400)
            check("提交评价",
                  student.post(f"/api/reservations/{sign_id}/evaluate/",
                               {"device_score": 5, "speed_score": 4, "service_score": 5,
                                "content": "设备状态良好，管理员响应及时"}, format="json"))
            check("重复评价拦截",
                  student.post(f"/api/reservations/{sign_id}/evaluate/",
                               {"device_score": 5, "speed_score": 5, "service_score": 5},
                               format="json"), expect_status=400)

    # ================= 6. 图文沟通 =================
    print("\n[6] 图文沟通")
    check("学生发起沟通",
          student.post("/api/reservations/chats/send/",
                       {"reservation": reservation_id, "content": "老师您好，设备使用前需要预热吗？"},
                       format="json"), expect_status=201)
    thread_body = check("查看沟通记录（标记已读）",
                        labadmin.get(f"/api/reservations/chats/by-reservation/?reservation={reservation_id}"))
    check("管理员回复沟通",
          labadmin.post("/api/reservations/chats/send/",
                        {"reservation": reservation_id, "content": "需要预热 10 分钟，谢谢配合。"},
                        format="json"), expect_status=201)
    check("会话状态为已回复",
          labadmin.get(f"/api/reservations/chats/by-reservation/?reservation={reservation_id}"))
    check("空消息拦截",
          student.post("/api/reservations/chats/send/",
                       {"reservation": reservation_id, "content": ""}, format="json"),
          expect_status=400)
    check("会话列表", labadmin.get("/api/reservations/chats/"))
    check("待回复会话数", labadmin.get("/api/reservations/chats/unanswered-count/"))
    if thread_body.get("data", {}).get("id"):
        check("会话消息列表",
              labadmin.get(f"/api/reservations/chats/{thread_body['data']['id']}/messages/"))

    # ================= 7. 完工与评价 =================
    print("\n[7] 完工与评价")
    check("评价列表（管理员查看全部）", labadmin.get("/api/reservations/evaluations/"))
    check("评价列表（学生只看本人）", student.get("/api/reservations/evaluations/"))
    check("评价统计", admin.get("/api/reservations/evaluations/statistics/"))
    evaluations = check("评价筛选", labadmin.get("/api/reservations/evaluations/?score=1"))
    if evaluations.get("data", {}).get("results"):
        eval_id = evaluations["data"]["results"][0]["id"]
        check("管理员回复评价",
              labadmin.post(f"/api/reservations/evaluations/{eval_id}/reply/",
                            {"reply_content": "感谢反馈，我们会持续改进。"}, format="json"))

    # ================= 8. 站内提醒 =================
    print("\n[8] 站内提醒")
    check("提醒列表（自动扫描生成）", student.get("/api/notifications/"))
    check("未读数量", student.get("/api/notifications/unread-count/"))
    check("提醒总览", student.get("/api/notifications/summary/"))
    notifications = check("提醒列表取一条", student.get("/api/notifications/?page_size=1&scan=0"))
    items = notifications.get("data", {}).get("results", [])
    if items:
        check("标记已读", student.post(f"/api/notifications/{items[0]['id']}/read/", {}, format="json"))
        check("标记未读", student.post(f"/api/notifications/{items[0]['id']}/unread/", {}, format="json"))
        check("批量已读", student.post("/api/notifications/batch-read/",
                                   {"ids": [items[0]["id"]]}, format="json"))
    check("全部已读", student.post("/api/notifications/read-all/", {}, format="json"))
    check("清除已读提醒", student.post("/api/notifications/clear/", {}, format="json"))
    check("管理员提醒列表", labadmin.get("/api/notifications/"))

    # ================= 9. 基础统计 =================
    print("\n[9] 基础统计")
    check("统计总览（学生仅本人）", student.get("/api/statistics/overview/"))
    check("统计总览（教师仅本人）", teacher.get("/api/statistics/overview/"))
    check("统计总览（管理员全部）", admin.get("/api/statistics/overview/"))
    check("统计看板", labadmin.get("/api/statistics/dashboard/"))
    check("按实验室统计", admin.get("/api/statistics/by-laboratory/"))
    check("按设备类型统计", admin.get("/api/statistics/by-category/"))
    check("按时间趋势统计", admin.get("/api/statistics/trend/?group=day"))
    check("按月趋势统计", admin.get("/api/statistics/trend/?group=month"))
    check("设备使用排行", admin.get("/api/statistics/device-ranking/"))
    check("预约人排行", admin.get("/api/statistics/applicant-ranking/"))
    check("统计报表导出", admin.get("/api/statistics/export/"))
    check("按实验室筛选统计", admin.get(f"/api/statistics/overview/?laboratory={lab_id}"))
    check("按时间筛选统计", admin.get(
        f"/api/statistics/overview/?start_date="
        f"{(datetime.date.today() - datetime.timedelta(days=30))}&end_date={datetime.date.today()}"))
    check("统计越权（学生访问报表导出）", student.get("/api/statistics/export/"))

    # ================= 10. 查阅与修改日志 =================
    print("\n[10] 查阅与修改日志")
    check("日志列表（系统管理员）", admin.get("/api/audit-logs/"))
    check("按预约查阅/修改记录", admin.get(
        f"/api/audit-logs/?target_type=reservation&target_id={reservation_id}"))
    check("按操作者查询", admin.get("/api/audit-logs/?operator=student1"))
    check("按实验室查询", admin.get(f"/api/audit-logs/?lab={lab_id}"))
    check("按操作类型查询", admin.get("/api/audit-logs/?action=view,update,approve"))
    check("按时间范围查询", admin.get(
        f"/api/audit-logs/?start_date={(datetime.date.today() - datetime.timedelta(days=1))}"
        f"&end_date={datetime.date.today()}"))
    check("日志关键词检索", admin.get("/api/audit-logs/?keyword=预约"))
    check("日志类型统计", admin.get("/api/audit-logs/summary/"))
    check("学生仅能查看本人日志", student.get("/api/audit-logs/"))
    check("实验室管理员日志范围", labadmin.get("/api/audit-logs/"))

    # ============================================================
    # 设备运维模块（本设计新增）
    # ============================================================
    print("\n" + "-" * 72)
    print("设备运维模块测试")
    print("-" * 72)

    student_client, _ = login("student1")
    teacher_client, _ = login("teacher1")

    # 接口可访问性
    check("运维-学生可访问my-faults", student_client.get("/api/maintenance/faults/my/"))
    check("运维-学生仅看自己faults", student_client.get("/api/maintenance/faults/"))
    check("运维-学生无法访问orders", student_client.get("/api/maintenance/orders/"), expect_status=403)
    check("运维-学生无法访问plans", student_client.get("/api/maintenance/plans/"), expect_status=403)
    check("运维-学生无法访问records", student_client.get("/api/maintenance/records/"), expect_status=403)

    check("运维-教师无法访问orders", teacher_client.get("/api/maintenance/orders/"), expect_status=403)
    check("运维-教师可访问自己的faults", teacher_client.get("/api/maintenance/faults/my/"))

    check("运维-实验室管理员可见全部orders", labadmin.get("/api/maintenance/orders/"))
    check("运维-实验室管理员可见全部plans", labadmin.get("/api/maintenance/plans/"))
    check("运维-实验室管理员可见plans.overdue", labadmin.get("/api/maintenance/plans/overdue/"))
    check("运维-实验室管理员可见全部records", labadmin.get("/api/maintenance/records/"))
    check("运维-实验室管理员可看orders.dashboard", labadmin.get("/api/maintenance/orders/dashboard/"))

    # 学生提交报修
    devs = labadmin.get("/api/labs/devices/?page_size=200").json()["data"]["results"]
    if devs:
        device_id = devs[0]["id"]
        fault_resp = student_client.post("/api/maintenance/faults/", {
            "device": device_id, "fault_type": "hardware",
            "severity": "high", "description": "冒烟测试自动创建的报修",
            "images": []
        })
        check("运维-学生创建报修", fault_resp, expect_status=201)
        if fault_resp.status_code == 201 and fault_resp.json().get("code") == 0:
            fault_id = fault_resp.json()["data"]["id"]
            check("运维-学生查看自己报修", student_client.get(f"/api/maintenance/faults/{fault_id}/"))

            # 管理员派单
            handlers = labadmin.get("/api/accounts/users/simple/?role=lab_admin").json()["data"]
            if handlers:
                handler_id = handlers[0]["id"]
                dispatch_resp = labadmin.post(
                    f"/api/maintenance/faults/{fault_id}/dispatch/",
                    {"handler_id": handler_id, "priority": "P1",
                     "title": "冒烟测试派单"}
                )
                check("运维-管理员派单成功", dispatch_resp, expect_status=201)
                if dispatch_resp.status_code == 201 and dispatch_resp.json().get("code") == 0:
                    order_id = dispatch_resp.json()["data"]["id"]
                    check("运维-工单start", labadmin.post(f"/api/maintenance/orders/{order_id}/start/"))
                    check("运维-工单complete",
                          labadmin.post(f"/api/maintenance/orders/{order_id}/complete/",
                                       {"solution": "冒烟测试修复",
                                        "parts_replaced": "无", "cost": 0}))
                    check("运维-工单verify",
                          labadmin.post(f"/api/maintenance/orders/{order_id}/verify/"))
                    # 验证设备回到可用
                    dev_resp = labadmin.get(f"/api/labs/devices/?page_size=200")
                    if dev_resp.status_code == 200:
                        devs_now = dev_resp.json()["data"]["results"]
                        target = next((d for d in devs_now if d["id"] == device_id), None)
                        if target:
                            actual_status = target["status"]
                            if actual_status == "available":
                                _inc_pass("运维-设备状态回到available")
                            else:
                                global FAILED
                                FAILED += 1
                                print(f"  [FAIL] 运维-设备状态回到available -> {actual_status}")
            else:
                skip("无可用处理人，跳过派单")
        else:
            skip("报修创建失败，跳过派单流程")
    else:
        skip("无可用设备，跳过运维端到端")

    print("\n" + "=" * 72)
    print(f"测试完成：通过 {PASSED} 项，失败 {FAILED} 项，跳过 {SKIPPED} 项")
    print("=" * 72)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
