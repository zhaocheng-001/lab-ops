import { defineStore } from 'pinia'
import { authApi, notificationApi } from '@/api'

export const ROLE = {
  STUDENT: 'student',
  TEACHER: 'teacher',
  LAB_ADMIN: 'lab_admin',
  SYS_ADMIN: 'sys_admin'
}

export const ROLE_OPTIONS = [
  { value: ROLE.STUDENT, label: '学生', color: '#2f6fed' },
  { value: ROLE.TEACHER, label: '教师', color: '#17a673' },
  { value: ROLE.LAB_ADMIN, label: '实验室管理员', color: '#f5a524' },
  { value: ROLE.SYS_ADMIN, label: '系统管理员', color: '#8b5cf6' }
]

export const roleLabel = (role) =>
  ROLE_OPTIONS.find((item) => item.value === role)?.label || role

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('lab_access_token') || '',
    refreshToken: localStorage.getItem('lab_refresh_token') || '',
    user: JSON.parse(localStorage.getItem('lab_user') || 'null'),
    unreadCount: 0,
    todoCount: 0
  }),

  getters: {
    isLogin: (state) => !!state.token && !!state.user,
    role: (state) => state.user?.role || '',
    isStudent: (state) => state.user?.role === ROLE.STUDENT,
    isTeacher: (state) => state.user?.role === ROLE.TEACHER,
    isLabAdmin: (state) => state.user?.role === ROLE.LAB_ADMIN,
    isSysAdmin: (state) => state.user?.role === ROLE.SYS_ADMIN,
    isApplicant: (state) => [ROLE.STUDENT, ROLE.TEACHER].includes(state.user?.role),
    isAdminRole: (state) => [ROLE.LAB_ADMIN, ROLE.SYS_ADMIN].includes(state.user?.role),
    displayName: (state) => state.user?.real_name || state.user?.username || '',
    maxReserveHours: (state) => state.user?.max_reserve_hours || 4
  },

  actions: {
    restoreFromStorage() {
      const token = localStorage.getItem('lab_access_token')
      const user = localStorage.getItem('lab_user')
      if (token && user) {
        this.token = token
        this.user = JSON.parse(user)
      }
    },

    async login(payload) {
      const res = await authApi.login(payload)
      this.token = res.data.access
      this.refreshToken = res.data.refresh
      this.user = res.data.user
      localStorage.setItem('lab_access_token', this.token)
      localStorage.setItem('lab_refresh_token', this.refreshToken)
      localStorage.setItem('lab_user', JSON.stringify(this.user))
      return this.user
    },

    async fetchProfile() {
      const res = await authApi.profile()
      this.user = res.data
      localStorage.setItem('lab_user', JSON.stringify(this.user))
      return this.user
    },

    async loadBadges() {
      if (!this.token) return
      try {
        const res = await notificationApi.unreadCount()
        this.unreadCount = res.data.total
      } catch (error) {
        this.unreadCount = 0
      }
    },

    hasRole(roles) {
      if (!roles || !roles.length) return true
      return roles.includes(this.user?.role)
    },

    logout() {
      const refresh = this.refreshToken
      authApi.logout({ refresh }).catch(() => {})
      this.token = ''
      this.refreshToken = ''
      this.user = null
      this.unreadCount = 0
      localStorage.removeItem('lab_access_token')
      localStorage.removeItem('lab_refresh_token')
      localStorage.removeItem('lab_user')
    }
  }
})
