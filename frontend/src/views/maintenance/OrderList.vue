<template>
  <div class="page-container">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2 class="page-title">维修工单</h2>
          <p class="page-subtitle">查看、派单、处理与验收全生命周期管理</p>
        </div>
        <div class="header-actions">
          <el-button :icon="Refresh" @click="load">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新建工单</el-button>
        </div>
      </div>
    </el-card>

    <!-- 概览数据 -->
    <el-row :gutter="12" class="mt-16">
      <el-col :xs="12" :sm="6">
        <div class="stat-card" @click="filterByStatus('')">
          <div class="stat-label">本月工单</div>
          <div class="stat-value">{{ dashboard.month_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card warn" @click="filterByStatus('pending')">
          <div class="stat-label">待处理</div>
          <div class="stat-value">{{ countByStatus('pending') }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card processing" @click="filterByStatus('processing')">
          <div class="stat-label">处理中</div>
          <div class="stat-value">{{ countByStatus('processing') }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card danger" @click="filterByStatus('overdue')">
          <div class="stat-label">超 24h 未响应</div>
          <div class="stat-value">{{ dashboard.overdue_count || 0 }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="mt-16">
      <div class="filter-bar">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width:160px">
          <el-option label="待处理" value="pending" />
          <el-option label="处理中" value="processing" />
          <el-option label="已修复" value="resolved" />
          <el-option label="已验收" value="verified" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-select v-model="filters.priority" placeholder="优先级" clearable style="width:140px">
          <el-option v-for="p in priorityOptions" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="编号 / 标题 / 设备" clearable
                  style="width:240px" @change="load" />
        <el-button type="primary" @click="load">查询</el-button>
        <el-button v-if="hasFilter" @click="resetFilter">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="工单编号" width="200" />
        <el-table-column label="标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="order-title">{{ row.title }}</span>
            <el-tag v-if="row.source !== 'fault'" size="small" type="info" effect="plain" class="ml-6">
              {{ sourceMap[row.source] || row.source_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设备" width="160">
          <template #default="{ row }">
            <div>{{ row.device_name }}</div>
            <span class="muted">{{ row.device_code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="priorityType(row.priority)" effect="dark">
              {{ row.priority }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="handler_name" label="处理人" width="100" />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ row.created_at }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="['pending','processing'].includes(row.status)"
                       link type="warning" @click="assignDialog(row)">指派</el-button>
            <el-button v-if="row.status === 'pending'" link type="primary"
                       @click="start(row)">开始</el-button>
            <el-button v-if="['pending','processing'].includes(row.status)"
                       link type="success" @click="completeDialog(row)">完成</el-button>
            <el-button v-if="row.status === 'resolved'" link type="success"
                       @click="verify(row)">验收</el-button>
            <el-dropdown v-if="!['verified','cancelled'].includes(row.status)" trigger="click">
              <el-button link type="primary">更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="cancel(row)">取消工单</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="load"
          @size-change="load"
        />
      </div>
    </el-card>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="工单详情" width="640px">
      <el-descriptions v-if="current" :column="2" border>
        <el-descriptions-item label="编号" :span="2">{{ current.no }}</el-descriptions-item>
        <el-descriptions-item label="标题" :span="2">{{ current.title }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ current.source_display }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="priorityType(current.priority)">{{ current.priority }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(current.status)">{{ current.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="处理人">{{ current.handler_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="设备" :span="2">
          {{ current.device_name }} ({{ current.device_code }}) · {{ current.laboratory_name }}
        </el-descriptions-item>
        <el-descriptions-item label="故障描述" :span="2">{{ current.fault_desc || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理方案" :span="2">{{ current.solution || '-' }}</el-descriptions-item>
        <el-descriptions-item label="更换配件">{{ current.parts_replaced || '-' }}</el-descriptions-item>
        <el-descriptions-item label="维修费用">{{ current.cost }} 元</el-descriptions-item>
        <el-descriptions-item label="计划开始">{{ current.scheduled_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际开始">{{ current.started_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="修复完成">{{ current.completed_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="验收时间">{{ current.verified_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="响应时长">
          {{ current.response_minutes ? `${current.response_minutes} 分钟` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="维修耗时">
          {{ current.duration_hours ? `${current.duration_hours} 小时` : '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 指派 -->
    <el-dialog v-model="assignVisible" title="指派处理人" width="420px">
      <el-form label-width="90px">
        <el-form-item label="处理人">
          <el-select v-model="assignForm.handler_id" placeholder="请选择实验室管理员" filterable>
            <el-option v-for="u in admins" :key="u.id"
                       :label="`${u.real_name} (${u.username})`" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAssign">确认</el-button>
      </template>
    </el-dialog>

    <!-- 完成 -->
    <el-dialog v-model="completeVisible" title="标记维修完成" width="540px">
      <el-form :model="completeForm" label-width="100px">
        <el-form-item label="处理方案" required>
          <el-input v-model="completeForm.solution" type="textarea" :rows="3"
                    placeholder="请描述故障原因、处理过程、是否更换配件等" />
        </el-form-item>
        <el-form-item label="更换配件">
          <el-input v-model="completeForm.parts_replaced" placeholder="如：电源模块 ×1" />
        </el-form-item>
        <el-form-item label="维修费用">
          <el-input-number v-model="completeForm.cost" :min="0" :precision="2" />
          <span class="ml-6">元</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmComplete">提交</el-button>
      </template>
    </el-dialog>

    <!-- 新建工单 -->
    <el-dialog v-model="createVisible" title="新建工单" width="560px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="100px">
        <el-form-item label="工单标题" prop="title">
          <el-input v-model="createForm.title" placeholder="如：显微镜深度维护" />
        </el-form-item>
        <el-form-item label="来源" prop="source">
          <el-select v-model="createForm.source">
            <el-option label="计划性维护" value="plan" />
            <el-option label="主动维护" value="routine" />
            <el-option label="巡检发现" value="inspect" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备" prop="device">
          <el-select v-model="createForm.device" placeholder="请选择设备" filterable>
            <el-option v-for="d in devices" :key="d.id"
                       :label="`${d.name} (${d.code})`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理人" prop="handler">
          <el-select v-model="createForm.handler" placeholder="请选择处理人" filterable>
            <el-option v-for="u in admins" :key="u.id"
                       :label="`${u.real_name} (${u.username})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="createForm.priority">
            <el-radio-button v-for="p in priorityOptions" :key="p.value" :value="p.value">
              {{ p.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="createForm.fault_desc" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirmCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { deviceApi, maintenanceApi, userApi } from '@/api'

const loading = ref(false)
const submitting = ref(false)
const list = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10 })
const dashboard = ref({ by_status: [], by_priority: [], overdue_count: 0, month_count: 0 })
const filters = reactive({ status: '', priority: '', keyword: '' })

const detailVisible = ref(false)
const current = ref(null)
const assignVisible = ref(false)
const assignForm = ref({ id: null, handler_id: null })
const completeVisible = ref(false)
const completeForm = ref({ id: null, solution: '', parts_replaced: '', cost: 0 })

const createVisible = ref(false)
const createFormRef = ref()
const createForm = ref({
  title: '', source: 'plan', device: null, handler: null,
  priority: 'P2', fault_desc: ''
})
const createRules = {
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
  source: [{ required: true, message: '请选择来源', trigger: 'change' }],
  device: [{ required: true, message: '请选择设备', trigger: 'change' }],
  handler: [{ required: true, message: '请选择处理人', trigger: 'change' }]
}

const admins = ref([])
const devices = ref([])

const sourceMap = { fault: '故障报修', inspect: '巡检发现', plan: '计划维护', routine: '主动维护' }
const priorityOptions = [
  { value: 'P0', label: 'P0 紧急' },
  { value: 'P1', label: 'P1 高' },
  { value: 'P2', label: 'P2 中' },
  { value: 'P3', label: 'P3 低' }
]

function priorityType(p) {
  return { P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' }[p] || 'info'
}

function statusType(s) {
  return {
    pending: 'warning', processing: 'primary',
    resolved: 'success', verified: 'success', cancelled: 'info'
  }[s] || 'info'
}

const hasFilter = computed(() =>
  Boolean(filters.status || filters.priority || filters.keyword)
)

function countByStatus(s) {
  const item = dashboard.value.by_status.find((x) => x.status === s)
  return item ? item.count : 0
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (filters.status) params.status = filters.status
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.search = filters.keyword
    const res = await maintenanceApi.listOrders(params)
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

async function loadDashboard() {
  try {
    const res = await maintenanceApi.orderDashboard()
    dashboard.value = res.data
  } catch {
    dashboard.value = { by_status: [], by_priority: [], overdue_count: 0, month_count: 0 }
  }
}

async function loadAdmins() {
  try {
    const res = await userApi.simple({ role: 'lab_admin,sys_admin' })
    admins.value = res.data
  } catch {
    admins.value = []
  }
}

async function loadDevices() {
  try {
    const res = await deviceApi.list({ page_size: 200 })
    devices.value = res.data.results
  } catch {
    devices.value = []
  }
}

function filterByStatus(s) {
  filters.status = s
  filters.priority = ''
  filters.keyword = ''
  query.page = 1
  load()
}

function resetFilter() {
  filters.status = ''
  filters.priority = ''
  filters.keyword = ''
  query.page = 1
  load()
}

async function openDetail(row) {
  const res = await maintenanceApi.orderDetail(row.id)
  current.value = res.data
  detailVisible.value = true
}

function assignDialog(row) {
  assignForm.value = { id: row.id, handler_id: row.handler }
  assignVisible.value = true
}

async function confirmAssign() {
  if (!assignForm.value.handler_id) {
    ElMessage.warning('请选择处理人')
    return
  }
  await maintenanceApi.assignOrder(assignForm.value.id, {
    handler_id: assignForm.value.handler_id
  })
  ElMessage.success('已指派')
  assignVisible.value = false
  load()
}

async function start(row) {
  await maintenanceApi.startOrder(row.id)
  ElMessage.success('已开始处理')
  load()
}

function completeDialog(row) {
  completeForm.value = { id: row.id, solution: '', parts_replaced: '', cost: 0 }
  completeVisible.value = true
}

async function confirmComplete() {
  if (!completeForm.value.solution.trim()) {
    ElMessage.warning('请填写处理方案')
    return
  }
  await maintenanceApi.completeOrder(completeForm.value.id, completeForm.value)
  ElMessage.success('已标记完成')
  completeVisible.value = false
  load()
  loadDashboard()
}

async function verify(row) {
  await maintenanceApi.verifyOrder(row.id)
  ElMessage.success('已验收')
  load()
}

async function cancel(row) {
  const { value } = await ElMessageBox.prompt('请输入取消原因', '取消工单', {
    inputPattern: /.+/,
    inputErrorMessage: '原因不能为空'
  })
  await maintenanceApi.cancelOrder(row.id, { reason: value })
  ElMessage.success('已取消')
  load()
}

function openCreate() {
  createForm.value = {
    title: '', source: 'plan', device: null, handler: null,
    priority: 'P2', fault_desc: ''
  }
  createVisible.value = true
}

async function confirmCreate() {
  await createFormRef.value.validate()
  submitting.value = true
  try {
    await maintenanceApi.createOrder(createForm.value)
    ElMessage.success('工单已创建')
    createVisible.value = false
    load()
    loadDashboard()
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  load()
  loadDashboard()
  loadAdmins()
  loadDevices()
})
</script>

<style scoped lang="scss">
.page-container { padding: 18px; }
.header-card { border-radius: 12px; }
.header-row {
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
}
.page-title { margin: 0 0 4px; font-size: 18px; }
.page-subtitle { margin: 0; color: var(--text-sub); font-size: 13px; }
.mt-16 { margin-top: 16px; }
.ml-6 { margin-left: 6px; }
.stat-card {
  background: #fff; border-radius: 10px; padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.05); cursor: pointer;
  transition: transform .2s, box-shadow .2s;
  border-left: 4px solid var(--brand-primary);
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.08); }
.stat-card.warn { border-left-color: #f5a524; }
.stat-card.processing { border-left-color: #2f6fed; }
.stat-card.danger { border-left-color: #e5484d; }
.stat-label { color: var(--text-sub); font-size: 13px; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 14px; }
.pagination-row { margin-top: 16px; display: flex; justify-content: flex-end; }
.order-title { font-weight: 500; color: var(--text-main); }
.muted { color: var(--text-sub); font-size: 12px; }
</style>