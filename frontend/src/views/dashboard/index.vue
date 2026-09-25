<template>
  <div class="page-container">
    <el-card shadow="never" class="welcome-card">
      <div class="welcome">
        <div>
          <h2>{{ greeting }}，{{ userStore.displayName }}</h2>
          <p class="welcome-sub">
            {{ roleLabel(userStore.role) }} ·
            <template v-if="userStore.user?.college_name">
              {{ userStore.user.college_name }}
            </template>
            <template v-else-if="userStore.user?.managed_labs?.length">
              负责 {{ userStore.user.managed_labs.length }} 个实验室
            </template>
            <template v-else>系统管理账号</template>
            · 单次预约时长上限 {{ userStore.maxReserveHours }} 小时
          </p>
          <p class="welcome-hint">
            <el-icon><BellFilled /></el-icon>
            <span>{{ todayText }} · {{ todayHint }}</span>
          </p>
        </div>
        <div class="welcome-actions">
          <el-button v-if="userStore.isApplicant" type="primary" :icon="Plus"
                     @click="$router.push('/reservations/create')">
            发起预约
          </el-button>
          <el-button v-if="userStore.isAdminRole" type="primary" :icon="CircleCheck"
                     @click="$router.push('/approvals')">
            去审批
          </el-button>
          <el-button :icon="DataAnalysis" @click="$router.push('/statistics')">查看统计</el-button>
        </div>
      </div>
    </el-card>

    <div class="stat-grid mt-16">
      <StatCard icon="Tickets" color="#2f6fed" :value="overview.total" label="预约总数"
                clickable @click="$router.push(statLink)" />
      <StatCard icon="AlarmClock" color="#f5a524" :value="overview.pending" label="待处理" />
      <StatCard icon="Timer" color="#17a673" :value="overview.in_use" label="使用中" />
      <StatCard icon="CircleCheckFilled" color="#00b4d8" :value="overview.completed" label="已完成" />
      <StatCard icon="WarningFilled" color="#e5484d" :value="overview.overdue" label="逾期数"
                :value-color="overview.overdue ? '#e5484d' : ''" />
      <StatCard icon="PieChart" color="#8b5cf6" :value="overview.device_usage_rate" unit="%"
                label="设备使用率" />
    </div>

    <el-card v-if="asset && userStore.isSysAdmin" shadow="never" class="asset-card mt-16">
      <div class="asset-row">
        <div class="asset-item">
          <span class="asset-label">在册用户</span>
          <span class="asset-value">{{ asset.user_count }}</span>
        </div>
        <div class="asset-item">
          <span class="asset-label">实验室</span>
          <span class="asset-value">{{ asset.lab_count }}</span>
        </div>
        <div class="asset-item">
          <span class="asset-label">设备总数</span>
          <span class="asset-value">{{ asset.device_count }}</span>
        </div>
        <div class="asset-item">
          <span class="asset-label">累计预约</span>
          <span class="asset-value">{{ asset.reservation_total }}</span>
        </div>
        <div class="asset-item">
          <span class="asset-label">履约完成率</span>
          <span class="asset-value">{{ asset.completion_rate }}%</span>
        </div>
        <div class="asset-links">
          <el-button link type="primary" @click="$router.push('/labs')">实验室台账</el-button>
          <el-button link type="primary" @click="$router.push('/devices')">设备台账</el-button>
        </div>
      </div>
    </el-card>

    <el-card v-if="userStore.isAdminRole && opsKpi" shadow="never" class="ops-card mt-16">
      <div class="ops-head">
        <h3 class="chart-title">
          <el-icon><Warning /></el-icon>
          设备运维概览
          <el-tag size="small" type="info">{{ opsKpi.overdue_count }} 个工单超时</el-tag>
        </h3>
        <div class="ops-links">
          <el-button link type="primary" @click="$router.push('/maintenance/faults')">报修单</el-button>
          <el-button link type="primary" @click="$router.push('/maintenance/orders')">维修工单</el-button>
          <el-button link type="primary" @click="$router.push('/maintenance/plans')">维保计划</el-button>
          <el-button link type="primary" @click="$router.push('/maintenance/inspections')">巡检记录</el-button>
        </div>
      </div>

      <div class="ops-grid">
        <div class="ops-item">
          <span class="ops-num">{{ opsKpi.fault_summary?.pending || 0 }}</span>
          <span class="ops-label">待派单报修</span>
        </div>
        <div class="ops-item">
          <span class="ops-num">{{ opsKpi.fault_summary?.month_total || 0 }}</span>
          <span class="ops-label">本月新增报修</span>
        </div>
        <div class="ops-item">
          <span class="ops-num ops-warn">{{ opsKpi.overdue_count }}</span>
          <span class="ops-label">超时未完结工单</span>
        </div>
        <div class="ops-item">
          <span class="ops-num">{{ opsKpi.avg_response_minutes || 0 }}<small>分</small></span>
          <span class="ops-label">平均响应时长</span>
        </div>
        <div class="ops-item">
          <span class="ops-num ops-warn">{{ opsKpi.plan_summary?.overdue || 0 }}</span>
          <span class="ops-label">维保计划逾期</span>
        </div>
        <div class="ops-item">
          <span class="ops-num">{{ opsKpi.plan_summary?.due_soon || 0 }}</span>
          <span class="ops-label">7 日内待巡检</span>
        </div>
      </div>

      <div v-if="opsKpi.recent?.length" class="ops-recent">
        <div class="ops-recent-title">最近工单</div>
        <div class="ops-recent-list">
          <div v-for="r in opsKpi.recent" :key="r.id" class="ops-recent-item">
            <el-tag size="small" :type="r.priority === 'urgent' ? 'danger' : r.priority === 'high' ? 'warning' : 'info'">
              {{ priorityLabel(r.priority) }}
            </el-tag>
            <span class="ops-recent-no">{{ r.no }}</span>
            <span class="ops-recent-title-text">{{ r.title }}</span>
            <el-tag size="small" effect="plain">{{ r.status_display }}</el-tag>
            <span class="ops-recent-time">{{ formatDateTime(r.created_at) }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16" class="mt-16">
      <el-col :xs="24" :lg="16">
        <div class="chart-card">
          <h3 class="chart-title">
            预约趋势
            <el-radio-group v-model="trendGroup" size="small" @change="loadDashboard">
              <el-radio-button value="day">按日</el-radio-button>
              <el-radio-button value="month">按月</el-radio-button>
            </el-radio-group>
          </h3>
          <ChartBox :option="trendOption" height="300px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="chart-card">
          <h3 class="chart-title">预约状态分布</h3>
          <ChartBox :option="statusOption" height="300px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-16">
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <h3 class="chart-title">按实验室统计</h3>
          <ChartBox :option="labOption" height="300px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <h3 class="chart-title">设备使用排行 TOP10</h3>
          <ChartBox :option="deviceOption" height="300px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-16">
      <el-col :xs="24" :lg="14">
        <div class="page-card">
          <h3 class="chart-title">
            近期预约
            <el-button link type="primary" @click="$router.push(statLink)">查看全部</el-button>
          </h3>
          <el-table :data="recentReservations" size="small" v-loading="loading">
            <el-table-column prop="no" label="预约编号" width="180" show-overflow-tooltip />
            <el-table-column prop="device_name" label="设备" show-overflow-tooltip />
            <el-table-column prop="laboratory_name" label="实验室" show-overflow-tooltip />
            <el-table-column label="使用时间" width="180">
              <template #default="{ row }">
                <div>{{ formatDateTime(row.start_time) }}</div>
                <div class="text-muted" style="font-size: 12px">
                  至 {{ formatDateTime(row.end_time) }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :xs="24" :lg="10">
        <div class="page-card">
          <h3 class="chart-title">
            我的待办
            <el-button link type="primary" @click="$router.push(todoLink)">去处理</el-button>
          </h3>
          <div class="todo-list">
            <div v-for="item in todoItems" :key="item.label" class="todo-item">
              <div class="todo-left">
                <el-icon :style="{ color: item.color }"><component :is="item.icon" /></el-icon>
                <span>{{ item.label }}</span>
              </div>
              <el-badge :value="item.value" :type="item.value ? 'danger' : 'info'"
                        :show-zero="true" class="todo-badge" />
            </div>
          </div>
          <el-divider />
          <h3 class="chart-title">最新提醒</h3>
          <div v-if="notifications.length" class="notice-list">
            <div v-for="item in notifications" :key="item.id" class="notice-item">
              <el-tag :type="notifyTypeTag(item.notify_type)" size="small">
                {{ notifyTypeLabel(item.notify_type) }}
              </el-tag>
              <div class="notice-content">
                <div class="notice-title">{{ item.title }}</div>
                <div class="notice-time">{{ formatDateTimeFull(item.created_at) }}</div>
              </div>
            </div>
          </div>
          <div v-else class="empty-tip">暂无提醒</div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Plus, BellFilled, Box, CircleCheck, Clock, DataAnalysis, Star, Timer, Warning } from '@element-plus/icons-vue'
import StatCard from '@/components/StatCard.vue'
import ChartBox from '@/components/ChartBox.vue'
import { dashboardApi, maintenanceApi, notificationApi, reservationApi, statisticsApi } from '@/api'
import { roleLabel, useUserStore } from '@/stores/user'
import {
  formatDateTime,
  formatDateTimeFull,
  notifyTypeLabel,
  notifyTypeTag,
  statusLabel,
  statusType,
  RESERVATION_STATUS
} from '@/utils/dict'

const userStore = useUserStore()
const loading = ref(false)
const trendGroup = ref('day')
const overview = ref({
  total: 0, pending: 0, in_use: 0, completed: 0, overdue: 0,
  device_usage_rate: 0, to_handle: 0, draft: 0, approved: 0, waiting_use: 0,
  rejected: 0, cancelled: 0, to_evaluate: 0, used_hours: 0, average_score: 0
})
const statusDistribution = ref([])
const byLaboratory = ref([])
const deviceRanking = ref([])
const trend = ref([])
const recentReservations = ref([])
const todo = ref({})
const notifications = ref([])
const asset = ref(null)
const opsKpi = ref(null)

const priorityLabel = computed(() => (p) =>
  ({ urgent: '紧急', high: '高', normal: '普通' }[p] || '普通')
)

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const todayText = computed(() => {
  const date = new Date()
  const week = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return `今天 ${date.getMonth() + 1} 月 ${date.getDate()} 日 ${week[date.getDay()]}`
})

const totalTodo = computed(() =>
  todoItems.value.reduce((sum, item) => sum + (item.value || 0), 0)
)

const todayHint = computed(() => {
  if (totalTodo.value > 0) {
    return `有 ${totalTodo.value} 项待办等你处理，别忘记啦`
  }
  return '暂无待办事项，今天可以安心做自己的事'
})

const statLink = computed(() => (userStore.isApplicant ? '/reservations' : '/approvals'))
const todoLink = computed(() => (userStore.isApplicant ? '/usage' : '/approvals'))

const ICON_MAP = { Clock, Timer, Star, Warning, CircleCheck, Box }

const todoItems = computed(() => {
  const data = todo.value || {}
  if (userStore.isApplicant) {
    return [
      { label: '待签到', value: data.pending_sign_in || 0, icon: Clock, color: '#2f6fed' },
      { label: '使用中/待签退', value: data.pending_return || 0, icon: Timer, color: '#17a673' },
      { label: '待评价', value: data.pending_evaluate || 0, icon: Star, color: '#f5a524' },
      { label: '已逾期', value: data.overdue || 0, icon: Warning, color: '#e5484d' }
    ]
  }
  return [
    { label: '待我审批', value: data.pending_approval || 0, icon: CircleCheck, color: '#f5a524' },
    { label: '待核验归还', value: data.pending_return || 0, icon: Box, color: '#17a673' },
    { label: '已逾期', value: data.overdue || 0, icon: Warning, color: '#e5484d' }
  ]
})

const trendOption = computed(() => {
  const periods = trend.value.map((item) => item.period)
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['预约总数', '已完成', '已驳回'], bottom: 0 },
    grid: { left: 40, right: 20, top: 30, bottom: 46 },
    xAxis: { type: 'category', data: periods, axisLabel: { rotate: periods.length > 10 ? 35 : 0 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '预约总数', type: 'line', smooth: true, areaStyle: { opacity: 0.12 },
        itemStyle: { color: '#2f6fed' }, data: trend.value.map((i) => i.total) },
      { name: '已完成', type: 'line', smooth: true, itemStyle: { color: '#17a673' },
        data: trend.value.map((i) => i.completed) },
      { name: '已驳回', type: 'line', smooth: true, itemStyle: { color: '#e5484d' },
        data: trend.value.map((i) => i.rejected) }
    ]
  }
})

const statusOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, type: 'scroll' },
  series: [
    {
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c}' },
      data: statusDistribution.value.map((item) => ({
        name: item.status_display,
        value: item.count,
        itemStyle: { color: RESERVATION_STATUS[item.status]?.color }
      }))
    }
  ]
}))

const labOption = computed(() => {
  const rows = byLaboratory.value.slice(0, 8).reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['预约总数', '已完成'], bottom: 0 },
    grid: { left: 130, right: 24, top: 20, bottom: 44 },
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: { type: 'category', data: rows.map((i) => i.laboratory), axisLabel: { fontSize: 11 } },
    series: [
      { name: '预约总数', type: 'bar', barWidth: 12, itemStyle: { color: '#2f6fed' },
        data: rows.map((i) => i.total) },
      { name: '已完成', type: 'bar', barWidth: 12, itemStyle: { color: '#17a673' },
        data: rows.map((i) => i.completed) }
    ]
  }
})

const deviceOption = computed(() => {
  const rows = deviceRanking.value.slice(0, 10)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 42, right: 20, top: 24, bottom: 60 },
    xAxis: {
      type: 'category',
      data: rows.map((i) => i.device),
      axisLabel: { rotate: 32, fontSize: 11, interval: 0 }
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '预约次数',
        type: 'bar',
        barWidth: 20,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#6a97f2' },
              { offset: 1, color: '#2f6fed' }
            ]
          }
        },
        data: rows.map((i) => i.total)
      }
    ]
  }
})

async function loadDashboard() {
  loading.value = true
  try {
    const [dash, recent, todoRes, noticeRes] = await Promise.all([
      statisticsApi.dashboard({ group: trendGroup.value }),
      reservationApi.list({ page_size: 6, ordering: '-created_at' }),
      reservationApi.todo(),
      notificationApi.list({ page_size: 5, scan: 1 })
    ])
    overview.value = dash.data.overview
    statusDistribution.value = dash.data.status_distribution
    byLaboratory.value = dash.data.by_laboratory
    deviceRanking.value = dash.data.device_ranking
    trend.value = dash.data.trend
    recentReservations.value = recent.data.results
    todo.value = todoRes.data
    notifications.value = noticeRes.data.results
    userStore.loadBadges()
  } finally {
    loading.value = false
  }
}

/** 平台资产总览：用户 / 实验室 / 设备 / 累计预约 / 履约完成率（仅系统管理员可见） */
async function loadAsset() {
  if (!userStore.isSysAdmin) {
    asset.value = null
    return
  }
  try {
    const res = await dashboardApi.overview()
    asset.value = res.data
  } catch (e) {
    asset.value = null
  }
}

/** 运维 KPI：报修 / 工单 / 维保计划（实验室管理员 / 系统管理员可见） */
async function loadOpsKpi() {
  if (!userStore.isAdminRole) {
    opsKpi.value = null
    return
  }
  try {
    const res = await maintenanceApi.orderDashboard()
    opsKpi.value = res.data
  } catch {
    opsKpi.value = null
  }
}

onMounted(() => {
  loadAsset()
  loadOpsKpi()
  loadDashboard()
})
</script>

<style scoped lang="scss">
.welcome-card {
  border: none;
  background: linear-gradient(120deg, #2f6fed 0%, #4f8af5 55%, #6fa8ff 100%);
  color: #fff;
  border-radius: 14px;
}

.welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.welcome h2 {
  margin: 0 0 8px;
  font-size: 22px;
}

.welcome-sub {
  margin: 0;
  font-size: 13px;
  opacity: 0.9;
}

.welcome-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 10px 0 0;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.18);
  font-size: 12px;
  line-height: 1.6;
}

.welcome-actions {
  display: flex;
  gap: 10px;
}

:deep(.welcome-actions .el-button) {
  border: none;
}

:deep(.welcome-actions .el-button--default) {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.asset-card {
  border-radius: 12px;
}

.ops-card {
  border-radius: 12px;
  background: linear-gradient(180deg, #fff 0%, #f8faff 100%);
}

.ops-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.ops-head .chart-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.ops-links {
  display: flex;
  gap: 4px;
}

.ops-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

@media (max-width: 1200px) {
  .ops-grid { grid-template-columns: repeat(3, 1fr); }
}

.ops-item {
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ops-num {
  font-size: 22px;
  font-weight: 700;
  color: #2f6fed;
  font-variant-numeric: tabular-nums;
}

.ops-num small {
  font-size: 12px;
  font-weight: 500;
  margin-left: 2px;
  color: var(--text-sub);
}

.ops-num.ops-warn { color: #e5484d; }

.ops-label {
  font-size: 12px;
  color: #8a93a5;
}

.ops-recent {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-soft);
}

.ops-recent-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-sub);
  margin-bottom: 8px;
}

.ops-recent-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ops-recent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--border-soft);
  font-size: 13px;
}

.ops-recent-no {
  font-weight: 600;
  color: #2f6fed;
  font-variant-numeric: tabular-nums;
}

.ops-recent-title-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ops-recent-time {
  font-size: 12px;
  color: #8a93a5;
}

.asset-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 32px;
}

.asset-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.asset-label {
  font-size: 12px;
  color: var(--text-sub);
}

.asset-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--brand-primary);
}

.asset-links {
  margin-left: auto;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 12px;
  border-radius: 8px;
}

.todo-item:hover {
  background: #f7f9fc;
}

.todo-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}

.todo-left .el-icon {
  font-size: 17px;
}

.todo-badge {
  margin-right: 8px;
}

.notice-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 210px;
  overflow-y: auto;
}

.notice-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.notice-title {
  font-size: 13px;
  line-height: 1.5;
}

.notice-time {
  font-size: 12px;
  color: #9aa3b5;
  margin-top: 2px;
}
</style>
