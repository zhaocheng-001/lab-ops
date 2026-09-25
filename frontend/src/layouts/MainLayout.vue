<template>
  <el-container class="app-wrapper">
    <el-aside :width="collapsed ? '64px' : '230px'" class="app-aside">
      <div class="logo">
        <el-icon class="logo-icon"><School /></el-icon>
        <span v-show="!collapsed" class="logo-text">实验室设备预约运维系统</span>
      </div>
      <div v-show="!collapsed" class="greet-bar">
        <span class="greet-text">{{ greeting }}，{{ userStore.displayName }}</span>
        <span class="greet-sub">{{ todayText }} · {{ weekText }}</span>
      </div>
      <el-scrollbar class="menu-scroll">
        <el-menu
          :default-active="activeMenu"
          :collapse="collapsed"
          :collapse-transition="false"
          background-color="#1f2a44"
          text-color="#c8d0e0"
          active-text-color="#ffffff"
          router
          unique-opened
        >
          <template v-for="group in menuGroups" :key="group.name">
            <el-menu-item v-if="group.items.length === 1" :index="group.items[0].path">
              <el-icon><component :is="group.items[0].icon" /></el-icon>
              <template #title>{{ group.items[0].title }}</template>
            </el-menu-item>
            <el-sub-menu v-else :index="group.name">
              <template #title>
                <el-icon><component :is="group.icon" /></el-icon>
                <span>{{ group.name }}</span>
              </template>
              <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
                <el-icon><component :is="item.icon" /></el-icon>
                <template #title>{{ item.title }}</template>
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <el-tooltip :content="collapsed ? '展开侧边栏' : '收起侧边栏'" placement="bottom">
            <el-icon class="collapse-btn" @click="collapsed = !collapsed">
              <component :is="collapsed ? 'Expand' : 'Fold'" />
            </el-icon>
          </el-tooltip>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentGroup">{{ currentGroup }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-tooltip :content="`当前时间：${clockText}`" placement="bottom">
            <span class="header-clock">
              <el-icon><Clock /></el-icon>{{ clockText }}
            </span>
          </el-tooltip>

          <el-tag :color="roleColor" effect="dark" class="role-tag" size="small">
            {{ roleText }}
          </el-tag>

          <el-badge :value="todoCount" :hidden="!todoCount" class="badge-item">
            <el-tooltip :content="todoTip" placement="bottom">
              <el-icon class="header-icon" @click="goTodo"><List /></el-icon>
            </el-tooltip>
          </el-badge>

          <el-badge :value="userStore.unreadCount" :hidden="!userStore.unreadCount" class="badge-item">
            <el-tooltip :content="unreadTip" placement="bottom">
              <el-icon class="header-icon" @click="router.push('/notifications')"><Bell /></el-icon>
            </el-tooltip>
          </el-badge>

          <el-dropdown @command="handleCommand">
            <div class="user-info">
              <el-avatar :size="30" :src="userStore.user?.avatar || ''" class="user-avatar">
                {{ (userStore.displayName || 'U').charAt(0) }}
              </el-avatar>
              <span class="user-name">{{ userStore.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item command="password">
                  <el-icon><Lock /></el-icon>修改密码
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <el-dialog v-model="passwordVisible" title="修改密码" width="420px" @closed="resetPasswordForm">
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="90px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password
                    placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password
                    placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password
                    placeholder="请再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordLoading" @click="submitPassword">确定</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { authApi, reservationApi } from '@/api'
import { ROLE_OPTIONS, useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const collapsed = ref(false)
const todoCount = ref(0)
const now = ref(new Date())
const passwordVisible = ref(false)
const passwordLoading = ref(false)
const passwordFormRef = ref()
const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })

const greeting = computed(() => {
  const hour = now.value.getHours()
  if (hour < 6) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const todayText = computed(
  () => `${now.value.getMonth() + 1} 月 ${now.value.getDate()} 日`
)

const weekText = computed(
  () => ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][now.value.getDay()]
)

const clockText = computed(() => {
  const pad = (value) => String(value).padStart(2, '0')
  const date = now.value
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
})

const todoTip = computed(() =>
  todoCount.value ? `我的待办（${todoCount.value} 项待处理）` : '我的待办：暂无待处理事项'
)

const unreadTip = computed(() =>
  userStore.unreadCount ? `站内提醒（${userStore.unreadCount} 条未读）` : '站内提醒：暂无未读消息'
)

const passwordRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不少于 6 位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.value.new_password) {
          callback(new Error('两次输入的新密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const allMenus = computed(() => {
  const layout = router.getRoutes().find((item) => item.path === '/')
  if (!layout) return []
  return layout.children
    .map((child) => ({
      path: `/${child.path}`.replace('//', '/'),
      title: child.meta?.title,
      icon: child.meta?.icon,
      menu: child.meta?.menu,
      roles: child.meta?.roles,
      group: child.meta?.group
    }))
    .filter((item) => item.menu && item.title)
    .filter((item) => !item.roles || item.roles.includes(userStore.role))
})

const GROUP_ICONS = {
  预约管理: 'Calendar',
  使用管理: 'Tools',
  '设备与实验室': 'Box',
  设备运维: 'WarningFilled',
  统计分析: 'PieChart',
  系统管理: 'Setting'
}

const menuGroups = computed(() => {
  const map = new Map()
  allMenus.value.forEach((item) => {
    const name = item.group || '其他'
    if (!map.has(name)) {
      map.set(name, { name, icon: GROUP_ICONS[name] || 'Menu', items: [] })
    }
    map.get(name).items.push(item)
  })
  return Array.from(map.values())
})

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/reservations/')) return path
  return path
})

const currentGroup = computed(() => route.meta?.group || '')

const roleText = computed(
  () => ROLE_OPTIONS.find((item) => item.value === userStore.role)?.label || '访客'
)
const roleColor = computed(
  () => ROLE_OPTIONS.find((item) => item.value === userStore.role)?.color || '#2f6fed'
)

async function loadTodo() {
  try {
    const res = await reservationApi.todo()
    todoCount.value = Object.values(res.data).reduce((sum, value) => sum + (value || 0), 0)
  } catch (error) {
    todoCount.value = 0
  }
}

function goTodo() {
  if (userStore.isApplicant) {
    router.push('/usage')
  } else {
    router.push('/approvals')
  }
}

function handleCommand(command) {
  if (command === 'profile') router.push('/profile')
  if (command === 'password') passwordVisible.value = true
  if (command === 'logout') {
    ElMessageBox.confirm('退出后需要重新输入账号密码，确定要退出吗？', '退出登录', {
      type: 'warning',
      confirmButtonText: '退出登录',
      cancelButtonText: '再想想'
    })
      .then(() => {
        userStore.logout()
        router.replace('/login')
        ElMessage.success('已安全退出，期待下次见')
      })
      .catch(() => {})
  }
}

function resetPasswordForm() {
  passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  passwordFormRef.value?.clearValidate()
}

async function submitPassword() {
  await passwordFormRef.value.validate()
  passwordLoading.value = true
  try {
    await authApi.changePassword(passwordForm.value)
    ElMessage.success('密码修改成功，请重新登录')
    passwordVisible.value = false
    setTimeout(() => {
      userStore.logout()
      router.replace('/login')
    }, 800)
  } finally {
    passwordLoading.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    loadTodo()
    userStore.loadBadges()
  }
)

let badgeTimer = null
let clockTimer = null

onMounted(() => {
  loadTodo()
  userStore.loadBadges()
  badgeTimer = setInterval(() => {
    userStore.loadBadges()
  }, 60000)
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onBeforeUnmount(() => {
  if (badgeTimer) clearInterval(badgeTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style scoped lang="scss">
.app-wrapper {
  height: 100vh;
}

.app-aside {
  background: linear-gradient(180deg, #1f2a44 0%, #243352 100%);
  transition: width 0.25s;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  color: #fff;
  font-weight: 600;
  font-size: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  white-space: nowrap;
}

.logo-icon {
  font-size: 22px;
  color: #6a97f2;
  flex-shrink: 0;
}

.greet-bar {
  padding: 0 16px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  white-space: nowrap;
}

.greet-text {
  display: block;
  font-size: 13px;
  color: #dfe6f5;
}

.greet-sub {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: #8b96ae;
  font-variant-numeric: tabular-nums;
}

.menu-scroll {
  flex: 1;
  padding-top: 8px;
}

:deep(.el-menu) {
  border-right: none;
}

:deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(47, 111, 237, 0.35), rgba(47, 111, 237, 0.06)) !important;
}

:deep(.el-menu-item:hover),
:deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.06) !important;
}

.app-header {
  height: 60px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(24, 39, 75, 0.06);
  border-bottom: 1px solid var(--border-soft);
  padding: 0 18px;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #5a6478;
}

.collapse-btn:hover {
  color: var(--brand-primary);
}

.header-clock {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #6b7280;
  font-variant-numeric: tabular-nums;
  padding: 3px 10px;
  border-radius: 20px;
  background: #f4f6fb;
  cursor: default;
}

.user-avatar {
  background: linear-gradient(135deg, #2f6fed, #6a97f2);
  color: #fff;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.role-tag {
  border: none;
  color: #fff;
}

.header-icon {
  font-size: 19px;
  cursor: pointer;
  color: #5a6478;
}

.header-icon:hover {
  color: var(--brand-primary);
}

.badge-item {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
}

.user-info:hover {
  background: #f4f6fb;
}

.user-name {
  font-size: 14px;
  color: var(--text-main);
}

.app-main {
  background: var(--bg-page);
  padding: 0;
  overflow-y: auto;
}
</style>
