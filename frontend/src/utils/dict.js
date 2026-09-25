import dayjs from 'dayjs'

/* ---------------- 预约状态 ---------------- */
export const RESERVATION_STATUS = {
  draft: { label: '暂存', type: 'info', color: '#909399' },
  pending: { label: '待审批', type: 'warning', color: '#f5a524' },
  approved: { label: '已通过', type: 'primary', color: '#2f6fed' },
  rejected: { label: '已驳回', type: 'danger', color: '#e5484d' },
  waiting_use: { label: '待使用', type: 'primary', color: '#00b4d8' },
  in_use: { label: '使用中', type: 'success', color: '#17a673' },
  completed: { label: '已完成', type: 'success', color: '#17a673' },
  cancelled: { label: '已取消', type: 'info', color: '#909399' }
}

export const RESERVATION_STATUS_OPTIONS = Object.entries(RESERVATION_STATUS).map(
  ([value, item]) => ({ value, label: item.label })
)

export const statusLabel = (status) => RESERVATION_STATUS[status]?.label || status
export const statusType = (status) => RESERVATION_STATUS[status]?.type || 'info'

/* ---------------- 设备状态 ---------------- */
export const DEVICE_STATUS = {
  available: { label: '可预约', type: 'success', color: '#17a673' },
  repairing: { label: '维修中', type: 'warning', color: '#f5a524' },
  scrapped: { label: '已报废', type: 'info', color: '#909399' }
}

export const DEVICE_STATUS_OPTIONS = Object.entries(DEVICE_STATUS).map(([value, item]) => ({
  value,
  label: item.label
}))

export const deviceStatusLabel = (status) => DEVICE_STATUS[status]?.label || status
export const deviceStatusType = (status) => DEVICE_STATUS[status]?.type || 'info'

/* ---------------- 紧急程度 ---------------- */
export const URGENCY_OPTIONS = [
  { value: 'normal', label: '普通' },
  { value: 'urgent', label: '紧急' }
]

export const urgencyLabel = (value) => (value === 'urgent' ? '紧急' : '普通')

/* ---------------- 沟通会话状态 ---------------- */
export const CHAT_STATUS = {
  pending_reply: { label: '待回复', type: 'warning' },
  replied: { label: '已回复', type: 'success' },
  closed: { label: '已结束', type: 'info' }
}

export const chatStatusLabel = (status) => CHAT_STATUS[status]?.label || status
export const chatStatusType = (status) => CHAT_STATUS[status]?.type || 'info'

/* ---------------- 提醒类型 ---------------- */
export const NOTIFY_TYPE = {
  pending_approval: { label: '待审批', type: 'warning' },
  approval_result: { label: '审批结果', type: 'primary' },
  transfer_approval: { label: '转派审批', type: 'primary' },
  pending_sign_in: { label: '待签到', type: 'primary' },
  pending_return: { label: '待归还', type: 'warning' },
  expiring: { label: '即将到期', type: 'warning' },
  overdue: { label: '已逾期', type: 'danger' },
  pending_evaluate: { label: '待评价', type: 'success' },
  chat_message: { label: '沟通消息', type: 'info' },
  system: { label: '系统通知', type: 'info' }
}

export const NOTIFY_TYPE_OPTIONS = Object.entries(NOTIFY_TYPE).map(([value, item]) => ({
  value,
  label: item.label
}))

export const notifyTypeLabel = (type) => NOTIFY_TYPE[type]?.label || type
export const notifyTypeTag = (type) => NOTIFY_TYPE[type]?.type || 'info'

/* ---------------- 日志操作类型 ---------------- */
export const LOG_ACTION = {
  view: { label: '查阅', type: 'info' },
  create: { label: '新增', type: 'success' },
  update: { label: '修改', type: 'primary' },
  delete: { label: '删除', type: 'danger' },
  submit: { label: '提交', type: 'success' },
  withdraw: { label: '撤回', type: 'info' },
  approve: { label: '审批通过', type: 'success' },
  reject: { label: '审批驳回', type: 'danger' },
  transfer: { label: '转派', type: 'warning' },
  cancel: { label: '取消', type: 'info' },
  sign_in: { label: '签到', type: 'success' },
  sign_out: { label: '签退', type: 'primary' },
  complete: { label: '完工确认', type: 'success' },
  evaluate: { label: '评价', type: 'success' },
  message: { label: '沟通', type: 'info' },
  import: { label: '导入', type: 'warning' },
  export: { label: '导出', type: 'warning' },
  login: { label: '登录', type: 'info' }
}

export const LOG_ACTION_OPTIONS = Object.entries(LOG_ACTION).map(([value, item]) => ({
  value,
  label: item.label
}))

export const logActionLabel = (action) => LOG_ACTION[action]?.label || action
export const logActionType = (action) => LOG_ACTION[action]?.type || 'info'

export const TARGET_TYPE_LABEL = {
  reservation: '预约单',
  device: '设备',
  laboratory: '实验室',
  user: '用户'
}

export const targetTypeLabel = (type) => TARGET_TYPE_LABEL[type] || type

/* ---------------- 时间格式化 ---------------- */
export function formatDateTime(value) {
  if (!value) return '—'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export function formatDateTimeFull(value) {
  if (!value) return '—'
  return dayjs(value).format('YYYY-MM-DD HH:mm:ss')
}

export function formatDate(value) {
  if (!value) return '—'
  return dayjs(value).format('YYYY-MM-DD')
}

export function formatHours(value) {
  const num = Number(value || 0)
  return `${num} 小时`
}

/** 根据开放日字符转换显示 */
export function weekdayText(value) {
  const map = { 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' }
  if (!value) return '—'
  return String(value)
    .split(',')
    .map((d) => map[d.trim()] || d)
    .join('、')
}
