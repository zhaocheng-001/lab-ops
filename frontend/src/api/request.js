import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const service = axios.create({
  baseURL: '/api',
  timeout: 20000
})

let sessionExpiredNotified = false

service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('lab_access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

service.interceptors.response.use(
  (response) => {
    // 二进制流（导出）直接返回
    if (response.config.responseType === 'blob') {
      return response
    }
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body && body.code !== 0) {
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body
  },
  (error) => {
    const status = error.response?.status
    const body = error.response?.data
    let message = body?.message || error.message || '网络异常'

    if (status === 401) {
      if (!sessionExpiredNotified) {
        sessionExpiredNotified = true
        ElMessageBox.alert('登录状态已失效，请重新登录', '提示', {
          type: 'warning',
          confirmButtonText: '重新登录',
          callback: () => {
            localStorage.removeItem('lab_access_token')
            localStorage.removeItem('lab_refresh_token')
            localStorage.removeItem('lab_user')
            window.location.href = '/login'
          }
        })
      }
      return Promise.reject(error)
    }

    if (status === 403) {
      message = body?.message || '当前角色无权执行该操作'
    }
    if (status === 404) {
      message = body?.message || '请求的资源不存在或不在您的数据权限范围内'
    }
    if (status === 500) {
      message = body?.message || '服务器内部错误，请稍后重试'
    }
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default service

/** 下载文件（导出 Excel） */
export async function downloadFile(url, params = {}, filename = 'export.xlsx') {
  const response = await service.get(url, { params, responseType: 'blob' })
  const blob = new Blob([response.data])
  const link = document.createElement('a')
  link.href = window.URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(link.href)
}
