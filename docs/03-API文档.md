# 03 - API 文档

> 基址：`http://<host>/api`  
> 鉴权：`Authorization: Bearer <access_token>`  
> 统一响应：`{ code: 0, message: "success", data: ... }`，错误时 `code != 0`。

---

## 一、认证

### POST /api/auth/login/
请求：
```json
{ "username": "admin", "password": "123456" }
```
响应 `data`：
```json
{ "access": "...", "refresh": "...", "user": { ... } }
```

### POST /api/auth/refresh/
请求：`{ "refresh": "..." }` → 返回新 `access`。

### POST /api/auth/change-password/
请求：`{ "old_password": "...", "new_password": "..." }`

---

## 二、用户与权限 `/api/accounts/`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /users/ | 用户列表（分页） | 系统管理员 |
| GET | /users/simple/?role=lab_admin,sys_admin | 下拉用 | 实验室管理员+ |
| POST | /users/ | 新建用户 | 系统管理员 |
| GET/PUT/DELETE | /users/{id}/ | 详情/更新/删除 | 系统管理员 |
| GET | /colleges/ | 学院列表（全量） | 已登录 |
| GET/POST | /classes/ | 班级列表/新增 | 系统管理员 |

---

## 三、实验室与设备 `/api/labs/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /laboratories/ | 实验室列表（分页） |
| POST | /laboratories/ | 新建实验室 |
| GET | /laboratories/simple/ | 下拉用全量 |
| GET | /devices/ | 设备列表（支持 ?category=&laboratory=&is_active=） |
| GET | /devices/simple/ | 下拉用 |
| POST | /devices/{id}/set-status/ | 修改设备状态 `{status, reason}` |
| GET | /categories/ | 设备分类（全量） |

---

## 四、预约 `/api/reservations/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /reservations/ | 列表（按角色裁剪） |
| POST | /reservations/ | 创建预约 |
| POST | /reservations/{id}/approve/ | 审批通过 |
| POST | /reservations/{id}/reject/ | 驳回 |
| POST | /reservations/{id}/transfer/ | 转派 `{target_user_id, reason}` |
| POST | /reservations/{id}/withdraw/ | 申请人撤回 |
| POST | /reservations/{id}/sign-in/ | 签到 |
| POST | /reservations/{id}/sign-out/ | 签退 `{evaluation_score, evaluation_comment}` |
| GET | /reservations/mine/ | 我的预约 |
| GET | /reservations/todo/ | 待办（按角色） |
| GET | /reservations/{id}/chats/ | 沟通记录 |
| POST | /reservations/{id}/chats/ | 发送消息 |
| GET | /reservations/evaluations/ | 评价列表 |
| GET | /reservations/device-usage/ | 设备使用率统计 |

---

## 五、通知 `/api/notifications/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /notifications/ | 我的通知（分页） |
| POST | /notifications/{id}/read/ | 标记已读 |
| POST | /notifications/batch-read/ | 批量已读 `{ids: [1,2,3]}` |
| POST | /notifications/read-all/ | 全部已读 |
| DELETE | /notifications/clear-read/ | 清除已读 |
| GET | /notifications/summary/ | 未读数量 |

---

## 六、操作日志 `/api/audit-logs/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /audit-logs/ | 日志列表 |
| GET | /audit-logs/{id}/ | 详情 |
| GET | /audit-logs/summary/ | 操作类型统计 |

---

## 七、统计分析 `/api/statistics/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /overview/ | 资产总览 |
| GET | /by-category/ | 按设备分类 |
| GET | /applicant-ranking/ | 申请人排行 |
| GET | /dashboard/overview/ | 仪表盘概览 |
| GET | /reservations/device-usage/ | 设备使用率 |

---

## 八、设备运维 `/api/maintenance/`（本设计核心）

### 8.1 故障报修 `/maintenance/faults/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /faults/ | 报修列表（管理员见全部，学生/教师见本人） |
| GET | /faults/my/ | 我的报修 |
| GET | /faults/{id}/ | 详情 |
| POST | /faults/ | 发起报修 `{device, fault_type, severity, description, images}` |
| POST | /faults/{id}/dispatch/ | 派单 `{handler_id, priority?, title?, scheduled_time?}` → 返回创建的工单 |
| POST | /faults/{id}/reject/ | 驳回 `{reason}` |
| POST | /faults/{id}/close/ | 关闭已修复报修 |

### 8.2 维修工单 `/maintenance/orders/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /orders/ | 列表 |
| GET | /orders/{id}/ | 详情 |
| POST | /orders/ | 新建 `{title, source, device, handler, priority, fault_desc, scheduled_time?}` |
| PUT | /orders/{id}/ | 更新 |
| POST | /orders/{id}/assign/ | 指派 `{handler_id}` |
| POST | /orders/{id}/start/ | 开始处理 |
| POST | /orders/{id}/complete/ | 完成 `{solution, parts_replaced?, cost?, images?}` |
| POST | /orders/{id}/verify/ | 验收 |
| POST | /orders/{id}/cancel/ | 取消 `{reason}` |
| GET | /orders/dashboard/ | 运维仪表盘 |

**运维仪表盘响应示例**：
```json
{
  "by_status": [
    {"status": "pending", "status_display": "待处理", "count": 3},
    {"status": "processing", "status_display": "处理中", "count": 1}
  ],
  "by_priority": [
    {"priority": "P0", "priority_display": "P0 / 紧急", "count": 1}
  ],
  "avg_response_minutes": 42,
  "overdue_count": 0,
  "month_count": 8,
  "recent": [...]
}
```

### 8.3 维保计划 `/maintenance/plans/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /plans/ | 列表 |
| GET | /plans/{id}/ | 详情 |
| POST | /plans/ | 创建 `{name, device? / device_category? / laboratory?, cycle, interval_days, responsible, checklist, description?}` |
| PUT | /plans/{id}/ | 更新 |
| DELETE | /plans/{id}/ | 删除 |
| GET | /plans/overdue/ | 即将到期 / 已逾期 |
| POST | /plans/{id}/execute/ | 执行一次巡检 `{result, issues?, checklist_result?, images?}` |

### 8.4 巡检记录 `/maintenance/records/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /records/ | 列表（按实验室裁剪） |
| GET | /records/{id}/ | 详情 |
| POST | /records/ | 创建巡检（结果为"需维修"时自动派生工单） |

---

## 九、WebSocket

`ws://<host>/ws/notifications/`  
鉴权：`?token=<access_token>`  
推送：审批结果、派单通知、维修完成等。消息格式：
```json
{ "type": "notification", "data": { "id": 12, "title": "...", "level": "warning" } }
```

---

## 十、错误码

| HTTP | 业务 code | 含义 |
|------|----------|------|
| 400 | 1 | 参数校验失败 |
| 401 | 401 | 未登录或 token 过期 |
| 403 | 403 | 权限不足 |
| 404 | 404 | 资源不存在 |
| 409 | 9 | 状态冲突（如已完成工单不可取消） |
| 500 | 500 | 服务异常 |

错误响应示例：
```json
{
  "code": 403,
  "message": "仅管理员可处理维修工单",
  "data": null
}
```

---

> 完整接口清单以代码为准，可通过 `python manage.py show_urls` 查看。