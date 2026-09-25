import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '首页概览', icon: 'HomeFilled', menu: true }
      },
      {
        path: 'reservations',
        name: 'MyReservations',
        component: () => import('@/views/reservation/MyReservations.vue'),
        meta: { title: '我的预约', icon: 'Tickets', menu: true, roles: ['student', 'teacher'], group: '预约管理' }
      },
      {
        path: 'reservations/create',
        name: 'ReservationCreate',
        component: () => import('@/views/reservation/ReservationForm.vue'),
        meta: { title: '发起预约', icon: 'DocumentAdd', menu: true, roles: ['student', 'teacher'], group: '预约管理' }
      },
      {
        path: 'reservations/:id',
        name: 'ReservationDetail',
        component: () => import('@/views/reservation/ReservationDetail.vue'),
        meta: { title: '预约详情', roles: ['student', 'teacher', 'lab_admin', 'sys_admin'], group: '预约管理' }
      },
      {
        path: 'reservations/:id/edit',
        name: 'ReservationEdit',
        component: () => import('@/views/reservation/ReservationForm.vue'),
        meta: { title: '修改预约', roles: ['student', 'teacher'], group: '预约管理' }
      },
      {
        path: 'approvals',
        name: 'ApprovalList',
        component: () => import('@/views/approval/index.vue'),
        meta: { title: '预约审批', icon: 'CircleCheck', menu: true, roles: ['lab_admin', 'sys_admin'], group: '预约管理' }
      },
      {
        path: 'usage',
        name: 'UsageProgress',
        component: () => import('@/views/usage/index.vue'),
        meta: { title: '使用进度', icon: 'Timer', menu: true, group: '使用管理' }
      },
      {
        path: 'faults',
        name: 'FaultReport',
        component: () => import('@/views/maintenance/FaultReport.vue'),
        meta: { title: '设备报修', icon: 'WarningFilled', menu: true, roles: ['student', 'teacher', 'lab_admin', 'sys_admin'], group: '设备运维' }
      },
      {
        path: 'maintenance/orders',
        name: 'MaintenanceOrders',
        component: () => import('@/views/maintenance/OrderList.vue'),
        meta: { title: '维修工单', icon: 'Tools', menu: true, roles: ['lab_admin', 'sys_admin'], group: '设备运维' }
      },
      {
        path: 'maintenance/plans',
        name: 'MaintenancePlans',
        component: () => import('@/views/maintenance/PlanList.vue'),
        meta: { title: '维保计划', icon: 'Calendar', menu: true, roles: ['lab_admin', 'sys_admin'], group: '设备运维' }
      },
      {
        path: 'maintenance/records',
        name: 'InspectRecords',
        component: () => import('@/views/maintenance/InspectionList.vue'),
        meta: { title: '巡检记录', icon: 'Notebook', menu: true, roles: ['lab_admin', 'sys_admin'], group: '设备运维' }
      },
      {
        path: 'chats',
        name: 'ChatCenter',
        component: () => import('@/views/chat/index.vue'),
        meta: { title: '图文沟通', icon: 'ChatDotRound', menu: true, group: '使用管理' }
      },
      {
        path: 'evaluations',
        name: 'EvaluationList',
        component: () => import('@/views/evaluation/index.vue'),
        meta: { title: '完工评价', icon: 'Star', menu: true, group: '使用管理' }
      },
      {
        path: 'notifications',
        name: 'NotificationCenter',
        component: () => import('@/views/notification/index.vue'),
        meta: { title: '站内提醒', icon: 'Bell', menu: true, group: '使用管理' }
      },
      {
        path: 'labs',
        name: 'LaboratoryList',
        component: () => import('@/views/lab/LaboratoryList.vue'),
        meta: { title: '实验室管理', icon: 'OfficeBuilding', menu: true, group: '设备与实验室' }
      },
      {
        path: 'devices',
        name: 'DeviceList',
        component: () => import('@/views/lab/DeviceList.vue'),
        meta: { title: '设备台账', icon: 'Cpu', menu: true, group: '设备与实验室' }
      },
      {
        path: 'categories',
        name: 'DeviceCategory',
        component: () => import('@/views/lab/DeviceCategory.vue'),
        meta: { title: '设备分类', icon: 'Files', menu: true, roles: ['lab_admin', 'sys_admin'], group: '设备与实验室' }
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('@/views/statistics/index.vue'),
        meta: { title: '统计分析', icon: 'DataAnalysis', menu: true, group: '统计分析' }
      },
      {
        path: 'logs',
        name: 'OperationLog',
        component: () => import('@/views/log/index.vue'),
        meta: { title: '操作日志', icon: 'Document', menu: true, group: '统计分析' }
      },
      {
        path: 'users',
        name: 'UserList',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理', icon: 'UserFilled', menu: true, roles: ['lab_admin', 'sys_admin'], group: '系统管理' }
      },
      {
        path: 'colleges',
        name: 'CollegeList',
        component: () => import('@/views/system/CollegeList.vue'),
        meta: { title: '学院与班级', icon: 'School', menu: true, roles: ['sys_admin'], group: '系统管理' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/system/Profile.vue'),
        meta: { title: '个人中心', icon: 'Setting' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  userStore.restoreFromStorage()

  document.title = to.meta.title ? `${to.meta.title} - 高校实验室设备预约运维系统` : '高校实验室设备预约运维系统'

  if (to.meta.public) {
    if (userStore.isLogin && to.path === '/login') {
      next('/dashboard')
      return
    }
    next()
    return
  }

  if (!userStore.isLogin) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  const roles = to.meta.roles
  if (roles && roles.length && !roles.includes(userStore.role)) {
    ElMessage.error('当前角色无权访问该页面')
    next(from.path && from.path !== to.path ? from.path : '/dashboard')
    return
  }

  next()
})

export default router
