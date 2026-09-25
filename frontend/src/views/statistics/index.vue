<template>
  <div class="page-container">
    <div class="stat-grid mb-16">
      <StatCard icon="Tickets" color="#2f6fed" :value="overview.total" label="预约总数" />
      <StatCard icon="CircleCheckFilled" color="#17a673" :value="overview.completed" label="已完成" />
      <StatCard icon="Clock" color="#00b4d8" :value="overview.in_use" label="使用中" />
      <StatCard icon="WarningFilled" color="#e5484d" :value="overview.overdue" label="逾期数" />
      <StatCard icon="Timer" color="#8b5cf6" :value="overview.used_hours" label="累计使用时长"
                unit="h" />
      <StatCard icon="DataLine" color="#f5a524" :value="overview.device_usage_rate" label="设备使用率"
                unit="%" />
      <StatCard icon="Star" color="#f5a524" :value="overview.average_score" label="平均评分" unit="分" />
      <StatCard icon="Finished" color="#2f6fed" :value="overview.completion_rate" label="完成率"
                unit="%" />
    </div>

    <div class="page-card mb-16">
      <div class="toolbar" style="margin-bottom: 0">
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
                        start-placeholder="开始日期" end-placeholder="结束日期"
                        format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width: 260px"
                        @change="onFilterChange" />
        <el-select v-model="query.laboratory" placeholder="实验室" clearable filterable
                   style="width: 180px" @change="onFilterChange">
          <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-select v-model="query.category" placeholder="设备类型" clearable style="width: 160px"
                   @change="onFilterChange">
          <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-radio-group v-model="query.group" @change="onFilterChange">
          <el-radio-button value="day">按日</el-radio-button>
          <el-radio-button value="month">按月</el-radio-button>
        </el-radio-group>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
          <el-button type="primary" :icon="Download" @click="doExport">导出报表</el-button>
        </div>
      </div>
    </div>

    <el-row :gutter="16" class="mb-16">
      <el-col :xs="24" :lg="16">
        <div class="chart-card">
          <h4 class="chart-title">预约趋势</h4>
          <ChartBox :option="trendOption" height="320px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="chart-card">
          <h4 class="chart-title">预约状态分布</h4>
          <ChartBox :option="statusOption" height="320px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mb-16">
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <h4 class="chart-title">各实验室预约量</h4>
          <ChartBox :option="labOption" height="320px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <h4 class="chart-title">设备类型分布</h4>
          <ChartBox :option="categoryOption" height="320px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <h4 class="chart-title">设备使用排行 TOP10</h4>
          <ChartBox :option="deviceOption" height="360px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <h4 class="chart-title">预约人排行 TOP10</h4>
          <el-table :data="dashboard.applicant_ranking" height="360" border stripe size="small">
            <el-table-column type="index" label="排名" width="70" align="center" />
            <el-table-column prop="applicant" label="申请人" min-width="110" />
            <el-table-column prop="role" label="角色" width="120" />
            <el-table-column prop="total" label="预约次数" width="100" align="center" />
            <el-table-column prop="completed" label="已完成" width="90" align="center" />
            <template #empty>
              <div class="empty-tip">暂无数据</div>
            </template>
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import ChartBox from '@/components/ChartBox.vue'
import StatCard from '@/components/StatCard.vue'
import { categoryApi, labApi, statisticsApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { statusLabel } from '@/utils/dict'

const userStore = useUserStore()

const labs = ref([])
const categories = ref([])
const dateRange = ref([])

const query = reactive({ laboratory: '', category: '', group: 'day' })

const emptyDashboard = {
  overview: {
    total: 0, completed: 0, in_use: 0, overdue: 0, used_hours: 0,
    device_usage_rate: 0, average_score: 0, completion_rate: 0
  },
  status_distribution: [],
  by_laboratory: [],
  by_category: [],
  trend: [],
  device_ranking: [],
  applicant_ranking: []
}

const dashboard = ref(emptyDashboard)

const overview = computed(() => dashboard.value.overview || emptyDashboard.overview)

function buildParams() {
  const params = { group: query.group }
  if (query.laboratory) params.laboratory = query.laboratory
  if (query.category) params.category = query.category
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  return params
}

async function load() {
  const res = await statisticsApi.dashboard(buildParams())
  dashboard.value = { ...emptyDashboard, ...res.data }
}

function onFilterChange() {
  load()
}

function resetFilters() {
  dateRange.value = []
  query.laboratory = ''
  query.category = ''
  query.group = 'day'
  load()
}

async function doExport() {
  await statisticsApi.export(buildParams())
  ElMessage.success('统计报表导出已开始')
}

const trendOption = computed(() => {
  const rows = dashboard.value.trend || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['预约总数', '已完成', '已驳回', '已取消'], top: 0 },
    grid: { left: 40, right: 20, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: rows.map((item) => item.period), boundaryGap: false },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '预约总数', type: 'line', smooth: true, data: rows.map((i) => i.total), areaStyle: { opacity: 0.12 } },
      { name: '已完成', type: 'line', smooth: true, data: rows.map((i) => i.completed) },
      { name: '已驳回', type: 'line', smooth: true, data: rows.map((i) => i.rejected) },
      { name: '已取消', type: 'line', smooth: true, data: rows.map((i) => i.cancelled) }
    ]
  }
})

const statusOption = computed(() => {
  const rows = dashboard.value.status_distribution || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '45%'],
        data: rows.map((item) => ({ name: statusLabel(item.status), value: item.count })),
        label: { formatter: '{b}\n{c}' }
      }
    ]
  }
})

const labOption = computed(() => {
  const rows = dashboard.value.by_laboratory || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['总数', '待审批', '使用中', '已完成', '逾期'], top: 0 },
    grid: { left: 50, right: 20, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: rows.map((i) => i.laboratory), axisLabel: { rotate: 25 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '总数', type: 'bar', data: rows.map((i) => i.total) },
      { name: '待审批', type: 'bar', data: rows.map((i) => i.pending) },
      { name: '使用中', type: 'bar', data: rows.map((i) => i.in_use) },
      { name: '已完成', type: 'bar', data: rows.map((i) => i.completed) },
      { name: '逾期', type: 'bar', data: rows.map((i) => i.overdue) }
    ]
  }
})

const categoryOption = computed(() => {
  const rows = dashboard.value.by_category || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 次' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: '60%',
        center: ['50%', '45%'],
        data: rows.map((item) => ({ name: item.category, value: item.total })),
        label: { formatter: '{b}\n{c}' }
      }
    ]
  }
})

const deviceOption = computed(() => {
  const rows = [...(dashboard.value.device_ranking || [])].reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 120, right: 40, top: 20, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: rows.map((i) => i.device) },
    series: [
      {
        type: 'bar',
        data: rows.map((i) => i.hours),
        barMaxWidth: 18,
        label: { show: true, position: 'right', formatter: '{c} h' }
      }
    ]
  }
})

onMounted(async () => {
  const [labRes, categoryRes] = await Promise.all([
    labApi.simple(userStore.isLabAdmin ? { mine: 1 } : {}),
    categoryApi.list()
  ])
  labs.value = labRes.data
  categories.value = categoryRes.data.results
  load()
})
</script>
