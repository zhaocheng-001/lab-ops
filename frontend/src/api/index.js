import request, { downloadFile } from './request'

/**
 * 统一列表返回结构。
 * 后端分页接口返回 { code, message, data: { count, results, ... } }，
 * 而不分页的全量列表接口（学院、设备分类）直接返回裸数组。
 * 这里统一包装成分页结构，使各页面统一使用 res.data.results 取值，避免出现 undefined。
 */
function asPagedList(promise) {
  return promise.then((res) => {
    const rows = Array.isArray(res) ? res : res?.data || []
    return {
      code: 0,
      message: 'success',
      data: {
        count: rows.length,
        page: 1,
        page_size: rows.length,
        total_pages: 1,
        results: rows
      }
    }
  })
}

/* ---------------- 账号与权限 ---------------- */
export const authApi = {
  login: (data) => request.post('/auth/login/', data),
  logout: (data) => request.post('/accounts/logout/', data || {}),
  profile: () => request.get('/accounts/profile/'),
  updateProfile: (data) => request.put('/accounts/profile/', data),
  changePassword: (data) => request.post('/accounts/change-password/', data)
}

export const userApi = {
  list: (params) => request.get('/accounts/users/', { params }),
  create: (data) => request.post('/accounts/users/', data),
  update: (id, data) => request.patch(`/accounts/users/${id}/`, data),
  remove: (id) => request.delete(`/accounts/users/${id}/`),
  resetPassword: (id, data) => request.post(`/accounts/users/${id}/reset-password/`, data),
  toggleActive: (id) => request.post(`/accounts/users/${id}/toggle-active/`),
  simple: (params) => request.get('/accounts/users/simple/', { params })
}

export const collegeApi = {
  list: (params) => asPagedList(request.get('/accounts/colleges/', { params })),
  create: (data) => request.post('/accounts/colleges/', data),
  update: (id, data) => request.patch(`/accounts/colleges/${id}/`, data),
  remove: (id) => request.delete(`/accounts/colleges/${id}/`)
}

export const classApi = {
  list: (params) => request.get('/accounts/classes/', { params }),
  create: (data) => request.post('/accounts/classes/', data),
  update: (id, data) => request.patch(`/accounts/classes/${id}/`, data),
  remove: (id) => request.delete(`/accounts/classes/${id}/`)
}

/* ---------------- 实验室与设备 ---------------- */
export const labApi = {
  list: (params) => request.get('/labs/', { params }),
  detail: (id) => request.get(`/labs/${id}/`),
  create: (data) => request.post('/labs/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  update: (id, data) => request.patch(`/labs/${id}/`, data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  remove: (id) => request.delete(`/labs/${id}/`),
  simple: (params) => request.get('/labs/simple/', { params }),
  export: (params) => downloadFile('/labs/export/', params, '实验室清单.xlsx')
}

export const deviceApi = {
  list: (params) => request.get('/labs/devices/', { params }),
  detail: (id) => request.get(`/labs/devices/${id}/`),
  create: (data) => request.post('/labs/devices/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  update: (id, data) => request.patch(`/labs/devices/${id}/`, data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  remove: (id) => request.delete(`/labs/devices/${id}/`),
  available: (params) => request.get('/labs/devices/available/', { params }),
  checkAvailable: (id, params) => request.get(`/labs/devices/${id}/check-available/`, { params }),
  statistics: (params) => request.get('/labs/devices/statistics/', { params }),
  export: (params) => downloadFile('/labs/devices/export/', params, '设备台账.xlsx'),
  importTemplate: () => downloadFile('/labs/devices/import-template/', {}, '设备导入模板.xlsx'),
  importDevices: (formData) =>
    request.post('/labs/devices/import/', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export const categoryApi = {
  list: (params) => asPagedList(request.get('/labs/categories/', { params })),
  create: (data) => request.post('/labs/categories/', data),
  update: (id, data) => request.patch(`/labs/categories/${id}/`, data),
  remove: (id) => request.delete(`/labs/categories/${id}/`)
}

export const dashboardApi = {
  overview: () => request.get('/labs/dashboard/overview/')
}

/* ---------------- 预约 / 审批 / 使用 ---------------- */
export const reservationApi = {
  list: (params) => request.get('/reservations/', { params }),
  detail: (id) => request.get(`/reservations/${id}/`),
  create: (data) => request.post('/reservations/', data),
  update: (id, data) => request.patch(`/reservations/${id}/`, data),
  remove: (id) => request.delete(`/reservations/${id}/`),
  checkConflict: (data) => request.post('/reservations/check-conflict/', data),
  submit: (id) => request.post(`/reservations/${id}/submit/`),
  withdraw: (id, data) => request.post(`/reservations/${id}/withdraw/`, data),
  cancel: (id, data) => request.post(`/reservations/${id}/cancel/`, data),
  approve: (id, data) => request.post(`/reservations/${id}/approve/`, data),
  reject: (id, data) => request.post(`/reservations/${id}/reject/`, data),
  transfer: (id, data) => request.post(`/reservations/${id}/transfer/`, data),
  signIn: (id, data) => request.post(`/reservations/${id}/sign-in/`, data || {}),
  signOut: (id, data) => request.post(`/reservations/${id}/sign-out/`, data),
  complete: (id, data) => request.post(`/reservations/${id}/complete/`, data),
  evaluate: (id, data) => request.post(`/reservations/${id}/evaluate/`, data),
  myProgress: () => request.get('/reservations/my-progress/'),
  deviceUsage: (params) => request.get('/reservations/device-usage/', { params }),
  todo: () => request.get('/reservations/todo/'),
  statusLogs: (params) => request.get('/reservations/status-logs/', { params })
}

/* ---------------- 图文沟通 ---------------- */
export const chatApi = {
  list: (params) => request.get('/reservations/chats/', { params }),
  messages: (id) => request.get(`/reservations/chats/${id}/messages/`),
  byReservation: (params) => request.get('/reservations/chats/by-reservation/', { params }),
  send: (formData) =>
    request.post('/reservations/chats/send/', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  close: (id) => request.post(`/reservations/chats/${id}/close/`),
  markRead: (id) => request.post(`/reservations/chats/${id}/read/`),
  unansweredCount: () => request.get('/reservations/chats/unanswered-count/')
}

/* ---------------- 完工与评价 ---------------- */
export const evaluationApi = {
  list: (params) => request.get('/reservations/evaluations/', { params }),
  detail: (id) => request.get(`/reservations/evaluations/${id}/`),
  statistics: (params) => request.get('/reservations/evaluations/statistics/', { params }),
  reply: (id, data) => request.post(`/reservations/evaluations/${id}/reply/`, data)
}

/* ---------------- 站内提醒 ---------------- */
export const notificationApi = {
  list: (params) => request.get('/notifications/', { params }),
  unreadCount: () => request.get('/notifications/unread-count/'),
  summary: () => request.get('/notifications/summary/'),
  markRead: (id) => request.post(`/notifications/${id}/read/`),
  markUnread: (id) => request.post(`/notifications/${id}/unread/`),
  readAll: (data) => request.post('/notifications/read-all/', data || {}),
  batchRead: (ids) => request.post('/notifications/batch-read/', { ids }),
  clear: () => request.post('/notifications/clear/')
}

/* ---------------- 统计 ---------------- */
export const statisticsApi = {
  overview: (params) => request.get('/statistics/overview/', { params }),
  dashboard: (params) => request.get('/statistics/dashboard/', { params }),
  byLaboratory: (params) => request.get('/statistics/by-laboratory/', { params }),
  byCategory: (params) => request.get('/statistics/by-category/', { params }),
  trend: (params) => request.get('/statistics/trend/', { params }),
  deviceRanking: (params) => request.get('/statistics/device-ranking/', { params }),
  applicantRanking: (params) => request.get('/statistics/applicant-ranking/', { params }),
  export: (params) => downloadFile('/statistics/export/', params, '统计报表.xlsx')
}

/* ---------------- 操作日志 ---------------- */
export const logApi = {
  list: (params) => request.get('/audit-logs/', { params }),
  detail: (id) => request.get(`/audit-logs/${id}/`),
  summary: (params) => request.get('/audit-logs/summary/', { params })
}

/* ---------------- 通用：图片 / 文件上传 ---------------- */
export const commonApi = {
  uploadImage: (formData) =>
    request.post('/common/upload-image/', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  uploadFile: (formData) =>
    request.post('/common/upload/', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
}

/* ---------------- 设备运维 ---------------- */
export const maintenanceApi = {
  /* 故障报修 */
  listFaults: (params) => request.get('/maintenance/faults/', { params }),
  myFaults: (params) => request.get('/maintenance/faults/my/', { params }),
  faultDetail: (id) => request.get(`/maintenance/faults/${id}/`),
  deviceSummary: (deviceId) => request.get('/maintenance/faults/device-summary/', { params: { device_id: deviceId } }),
  createFault: (data) => request.post('/maintenance/faults/', data),
  dispatchFault: (id, data) => request.post(`/maintenance/faults/${id}/dispatch/`, data),
  rejectFault: (id, data) => request.post(`/maintenance/faults/${id}/reject/`, data),
  closeFault: (id) => request.post(`/maintenance/faults/${id}/close/`),
  /* 维修工单 */
  listOrders: (params) => request.get('/maintenance/orders/', { params }),
  orderDetail: (id) => request.get(`/maintenance/orders/${id}/`),
  createOrder: (data) => request.post('/maintenance/orders/', data),
  updateOrder: (id, data) => request.put(`/maintenance/orders/${id}/`, data),
  assignOrder: (id, data) => request.post(`/maintenance/orders/${id}/assign/`, data),
  startOrder: (id) => request.post(`/maintenance/orders/${id}/start/`),
  completeOrder: (id, data) => request.post(`/maintenance/orders/${id}/complete/`, data),
  verifyOrder: (id) => request.post(`/maintenance/orders/${id}/verify/`),
  cancelOrder: (id, data) => request.post(`/maintenance/orders/${id}/cancel/`, data),
  orderDashboard: () => request.get('/maintenance/orders/dashboard/'),
  /* 维保计划 */
  listPlans: (params) => request.get('/maintenance/plans/', { params }),
  overduePlans: () => request.get('/maintenance/plans/overdue/'),
  planDetail: (id) => request.get(`/maintenance/plans/${id}/`),
  createPlan: (data) => request.post('/maintenance/plans/', data),
  updatePlan: (id, data) => request.put(`/maintenance/plans/${id}/`, data),
  deletePlan: (id) => request.delete(`/maintenance/plans/${id}/`),
  executePlan: (id, data) => request.post(`/maintenance/plans/${id}/execute/`, data),
  /* 巡检记录 */
  listRecords: (params) => request.get('/maintenance/records/', { params }),
  recordDetail: (id) => request.get(`/maintenance/records/${id}/`),
  createRecord: (data) => request.post('/maintenance/records/', data)
}
