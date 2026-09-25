<template>
  <div class="page-container">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2 class="page-title">设备故障报修</h2>
          <p class="page-subtitle">
            <span v-if="isAdmin">查看所辖实验室全部报修单，可派单 / 驳回；</span>
            发现设备异常？填写报修信息，管理员将第一时间处理。
          </p>
        </div>
        <el-button type="primary" :icon="Plus" @click="dialogVisible = true">
          发起报修
        </el-button>
      </div>

      <div v-if="isAdmin" class="kpi-row">
        <div class="kpi">
          <span class="kpi-num kpi-warn">{{ kpi.pending }}</span>
          <span class="kpi-label">待派单</span>
        </div>
        <div class="kpi">
          <span class="kpi-num">{{ kpi.dispatched + kpi.repairing }}</span>
          <span class="kpi-label">处理中</span>
        </div>
        <div class="kpi">
          <span class="kpi-num kpi-ok">{{ kpi.resolved + kpi.closed }}</span>
          <span class="kpi-label">已解决</span>
        </div>
        <div class="kpi">
          <span class="kpi-num kpi-bad">{{ kpi.rejected }}</span>
          <span class="kpi-label">已驳回</span>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="tab" class="mt-16">
      <el-tab-pane label="我的报修" name="mine">
        <el-card shadow="never">
          <div class="filter-bar">
            <el-select v-model="statusFilter" placeholder="状态" clearable style="width:160px">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-input v-model="keyword" placeholder="报修编号 / 设备名称" clearable
                      style="width:240px" @change="loadList" />
            <el-button :icon="Refresh" @click="loadList">刷新</el-button>
          </div>

          <el-table v-loading="loading" :data="list" border stripe>
            <el-table-column prop="no" label="报修编号" width="180" />
            <el-table-column label="设备" min-width="200">
              <template #default="{ row }">
                <div class="device-cell">
                  <strong>{{ row.device_name }}</strong>
                  <span class="muted">{{ row.device_code }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="故障类别" width="110">
              <template #default="{ row }">
                <el-tag size="small">{{ row.fault_type_display || faultTypeMap[row.fault_type] }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="严重度" width="90">
              <template #default="{ row }">
                <el-tag :type="severityType(row.severity)" size="small">
                  {{ row.severity_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" effect="light">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="报修时间" width="170" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDetail(row)">查看</el-button>
                <el-button v-if="canDispatch(row)" link type="warning"
                           @click="openDispatch(row)">派单</el-button>
                <el-button v-if="canDispatch(row)" link type="danger"
                           @click="openReject(row)">驳回</el-button>
                <el-button v-if="row.status === 'resolved' && (isAdmin || row.reporter === userStore.userInfo?.id)"
                           link type="success" @click="closeFault(row)">关闭</el-button>
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
              @current-change="loadList"
              @size-change="loadList"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane v-if="isAdmin" label="全部报修（所辖）" name="all">
        <el-card shadow="never">
          <p class="tab-hint">
            <el-icon><InfoFilled /></el-icon>
            仅显示你所在实验室的全部报修单；点击"派单"为它生成维修工单，或"驳回"不予受理。
          </p>
          <div class="filter-bar">
            <el-select v-model="statusFilter" placeholder="状态" clearable style="width:160px">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-input v-model="keyword" placeholder="报修编号 / 设备名称" clearable
                      style="width:240px" @change="loadList" />
            <el-button :icon="Refresh" @click="loadList">刷新</el-button>
          </div>

          <el-table v-loading="loading" :data="list" border stripe>
            <el-table-column prop="no" label="报修编号" width="180" />
            <el-table-column label="设备" min-width="180">
              <template #default="{ row }">
                <div class="device-cell">
                  <strong>{{ row.device_name }}</strong>
                  <span class="muted">{{ row.device_code }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="实验室" width="140">
              <template #default="{ row }">{{ row.laboratory_name }}</template>
            </el-table-column>
            <el-table-column label="报修人" width="100">
              <template #default="{ row }">{{ row.reporter_name }}</template>
            </el-table-column>
            <el-table-column label="故障类别" width="110">
              <template #default="{ row }">
                <el-tag size="small">{{ row.fault_type_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="严重度" width="90">
              <template #default="{ row }">
                <el-tag :type="severityType(row.severity)" size="small">
                  {{ row.severity_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" effect="light">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="报修时间" width="170" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDetail(row)">查看</el-button>
                <el-button v-if="canDispatch(row)" link type="warning"
                           @click="openDispatch(row)">派单</el-button>
                <el-button v-if="canDispatch(row)" link type="danger"
                           @click="openReject(row)">驳回</el-button>
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
              @current-change="loadList"
              @size-change="loadList"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 发起报修 -->
    <el-dialog v-model="dialogVisible" title="发起故障报修" width="560px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="故障设备" prop="device">
          <el-select v-model="form.device" placeholder="请选择要报修的设备" filterable style="width:100%">
            <el-option v-for="d in devices" :key="d.id"
                       :label="`${d.name} (${d.code}) · ${d.laboratory_name}`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="故障类别" prop="fault_type">
          <el-select v-model="form.fault_type" placeholder="请选择">
            <el-option label="硬件故障" value="hardware" />
            <el-option label="软件故障" value="software" />
            <el-option label="操作异常" value="operation" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重程度" prop="severity">
          <el-radio-group v-model="form.severity">
            <el-radio-button value="normal">一般</el-radio-button>
            <el-radio-button value="high">严重</el-radio-button>
            <el-radio-button value="urgent">紧急</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="故障描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4"
                    placeholder="请尽可能详尽地描述故障现象、影响范围、是否影响教学/科研等" />
        </el-form-item>
        <el-form-item label="现场照片" v-if="form.images !== undefined">
          <el-input v-model="form.images" type="textarea" :rows="2"
                    placeholder="可选，粘贴图片 URL（多张用换行分隔）" />
          <div class="img-preview" v-if="form.images">
            <el-image v-for="(url, idx) in form.images.split(/\n/).filter(Boolean)" :key="idx"
                      :src="url" :preview-src-list="form.images.split(/\n/).filter(Boolean)"
                      :initial-index="idx" fit="cover"
                      style="width:64px;height:64px;margin-right:6px;border-radius:6px" />
          </div>
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            提交后设备状态将自动置为"维修中"，管理员将根据紧急程度派单处理。
          </template>
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交报修</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="报修详情" width="600px">
      <el-descriptions v-if="current" :column="2" border>
        <el-descriptions-item label="编号" :span="2">{{ current.no }}</el-descriptions-item>
        <el-descriptions-item label="设备" :span="2">
          {{ current.device_name }} ({{ current.device_code }}) · {{ current.laboratory_name }}
        </el-descriptions-item>
        <el-descriptions-item label="报修人">{{ current.reporter_name }}</el-descriptions-item>
        <el-descriptions-item label="报修时间">{{ current.created_at }}</el-descriptions-item>
        <el-descriptions-item label="故障类别">{{ current.fault_type_display }}</el-descriptions-item>
        <el-descriptions-item label="严重程度">
          <el-tag :type="severityType(current.severity)" size="small">
            {{ current.severity_display }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(current.status)">{{ current.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="工单" :span="2">
          <span v-if="current.order_no">{{ current.order_no }}</span>
          <span v-else class="muted">尚未派单</span>
        </el-descriptions-item>
        <el-descriptions-item label="故障描述" :span="2">{{ current.description }}</el-descriptions-item>
        <el-descriptions-item v-if="current.images && current.images.length" label="现场照片" :span="2">
          <el-image v-for="(url, idx) in current.images" :key="idx"
                    :src="url" :preview-src-list="current.images"
                    :initial-index="idx" fit="cover"
                    style="width:88px;height:88px;margin-right:8px;border-radius:6px" />
        </el-descriptions-item>
        <el-descriptions-item v-if="current.reject_reason" label="驳回原因" :span="2">
          {{ current.reject_reason }}
        </el-descriptions-item>
        <el-descriptions-item v-if="current.resolved_at" label="修复时间" :span="2">
          {{ current.resolved_at }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer v-if="current && canDispatch(current)">
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="danger" @click="openReject(current)">驳回</el-button>
        <el-button type="warning" @click="openDispatch(current)">派单</el-button>
      </template>
    </el-dialog>

    <!-- 派单对话框 -->
    <el-dialog v-model="dispatchVisible" title="派发维修工单" width="520px">
      <el-alert v-if="dispatchTarget" type="info" :closable="false" show-icon style="margin-bottom:14px">
        <template #title>
          报修单 {{ dispatchTarget.no }}（{{ dispatchTarget.device_name }}）
        </template>
      </el-alert>
      <el-form :model="dispatchForm" label-width="90px">
        <el-form-item label="优先级" required>
          <el-select v-model="dispatchForm.priority" style="width:100%">
            <el-option label="P3 低" value="P3" />
            <el-option label="P2 中" value="P2" />
            <el-option label="P1 高" value="P1" />
            <el-option label="P0 紧急" value="P0" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理人" required>
          <el-select v-model="dispatchForm.handler" filterable placeholder="选择处理人（实验室管理员 / 系统管理员）" style="width:100%">
            <el-option v-for="u in adminUsers" :key="u.id" :label="`${u.real_name || u.username}（${u.role_display || u.role}）`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="故障原因">
          <el-input v-model="dispatchForm.root_cause" type="textarea" :rows="2"
                    placeholder="可选，初步判断的故障原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dispatchVisible = false">取消</el-button>
        <el-button type="primary" :loading="dispatching" @click="confirmDispatch">生成工单</el-button>
      </template>
    </el-dialog>

    <!-- 驳回对话框 -->
    <el-dialog v-model="rejectVisible" title="驳回报修" width="460px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="驳回原因" required>
          <el-input v-model="rejectForm.reason" type="textarea" :rows="3"
                    placeholder="请说明驳回原因，便于报修人理解" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="confirmReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, InfoFilled } from '@element-plus/icons-vue'
import { deviceApi, maintenanceApi, userApi } from '@/api'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.isLabAdmin || userStore.isSysAdmin)

const tab = ref('mine')
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const dispatchVisible = ref(false)
const dispatching = ref(false)
const rejectVisible = ref(false)
const rejecting = ref(false)
const current = ref(null)
const formRef = ref()
const form = ref({ device: null, fault_type: 'hardware', severity: 'normal', description: '', images: '' })
const rules = {
  device: [{ required: true, message: '请选择故障设备', trigger: 'change' }],
  fault_type: [{ required: true, message: '请选择故障类别', trigger: 'change' }],
  severity: [{ required: true, message: '请选择严重程度', trigger: 'change' }],
  description: [{ required: true, message: '请填写故障描述', trigger: 'blur' },
                { min: 5, message: '描述至少 5 个字符', trigger: 'blur' }]
}
const devices = ref([])
const adminUsers = ref([])
const list = ref([])
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const query = reactive({ page: 1, page_size: 10 })

const kpi = reactive({ pending: 0, dispatched: 0, repairing: 0, resolved: 0, closed: 0, rejected: 0 })

const faultTypeMap = { hardware: '硬件故障', software: '软件故障', operation: '操作异常', other: '其他' }
const statusOptions = [
  { value: 'pending', label: '待派单' },
  { value: 'dispatched', label: '已派单' },
  { value: 'repairing', label: '维修中' },
  { value: 'resolved', label: '已修复' },
  { value: 'closed', label: '已关闭' },
  { value: 'rejected', label: '已驳回' }
]

function severityType(s) {
  return { urgent: 'danger', high: 'warning', normal: 'info' }[s] || 'info'
}

function statusType(s) {
  return {
    pending: 'warning', dispatched: 'primary', repairing: 'warning',
    resolved: 'success', closed: 'info', rejected: 'danger'
  }[s] || 'info'
}

function canDispatch(row) {
  return isAdmin.value && row.status === 'pending'
}

async function loadList() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (statusFilter.value) params.status = statusFilter.value
    if (keyword.value) params.search = keyword.value
    const api = tab.value === 'all' ? maintenanceApi.listFaults : maintenanceApi.myFaults
    const res = await api(params)
    list.value = res.data.results
    total.value = res.data.count
    if (tab.value === 'all') refreshKpi()
  } finally {
    loading.value = false
  }
}

async function refreshKpi() {
  const counts = { pending: 0, dispatched: 0, repairing: 0, resolved: 0, closed: 0, rejected: 0 }
  await Promise.all(Object.keys(counts).map(async (s) => {
    try {
      const r = await maintenanceApi.listFaults({ status: s, page_size: 1 })
      counts[s] = r.data.count
    } catch { /* noop */ }
  }))
  Object.assign(kpi, counts)
}

async function loadDevices() {
  try {
    const res = await deviceApi.list({ page_size: 200, is_active: true })
    devices.value = res.data.results
  } catch {
    devices.value = []
  }
}

async function loadAdmins() {
  try {
    const res = await userApi.simple({ role: 'lab_admin,sys_admin' })
    adminUsers.value = res.data || []
  } catch {
    adminUsers.value = []
  }
}

function resetForm() {
  form.value = { device: null, fault_type: 'hardware', severity: 'normal', description: '', images: '' }
  formRef.value?.clearValidate()
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = { ...form.value }
    if (payload.images) {
      payload.images = payload.images.split(/\n/).map(s => s.trim()).filter(Boolean)
    } else {
      delete payload.images
    }
    await maintenanceApi.createFault(payload)
    ElMessage.success('报修已提交，管理员将尽快处理')
    dialogVisible.value = false
    resetForm()
    loadList()
    userStore.loadBadges()
  } finally {
    submitting.value = false
  }
}

async function openDetail(row) {
  const res = await maintenanceApi.faultDetail(row.id)
  current.value = res.data
  detailVisible.value = true
}

async function closeFault(row) {
  await ElMessageBox.confirm('确认关闭该报修单？', '提示', { type: 'warning' })
  await maintenanceApi.closeFault(row.id)
  ElMessage.success('已关闭')
  loadList()
}

// 派单
const dispatchTarget = ref(null)
const dispatchForm = reactive({ priority: 'P2', handler: null, root_cause: '' })

function openDispatch(row) {
  dispatchTarget.value = row
  dispatchForm.priority = row.severity === 'urgent' ? 'P0'
                       : row.severity === 'high' ? 'P1' : 'P2'
  dispatchForm.handler = null
  dispatchForm.root_cause = ''
  dispatchVisible.value = true
}

async function confirmDispatch() {
  if (!dispatchForm.handler) {
    ElMessage.warning('请选择处理人')
    return
  }
  dispatching.value = true
  try {
    const res = await maintenanceApi.dispatchFault(dispatchTarget.value.id, {
      priority: dispatchForm.priority,
      handler_id: dispatchForm.handler,
      root_cause: dispatchForm.root_cause,
    })
    ElMessage.success(`已派单，工单号 ${res.data.no || ''}`)
    dispatchVisible.value = false
    detailVisible.value = false
    loadList()
    userStore.loadBadges()
  } finally {
    dispatching.value = false
  }
}

// 驳回
const rejectTarget = ref(null)
const rejectForm = reactive({ reason: '' })

function openReject(row) {
  rejectTarget.value = row
  rejectForm.reason = ''
  rejectVisible.value = true
}

async function confirmReject() {
  if (!rejectForm.reason.trim()) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  rejecting.value = true
  try {
    await maintenanceApi.rejectFault(rejectTarget.value.id, { reason: rejectForm.reason })
    ElMessage.success('已驳回')
    rejectVisible.value = false
    detailVisible.value = false
    loadList()
  } finally {
    rejecting.value = false
  }
}

watch(tab, () => {
  query.page = 1
  loadList()
})

onMounted(() => {
  loadList()
  loadDevices()
  if (isAdmin.value) loadAdmins()
})
</script>

<style scoped lang="scss">
.page-container {
  padding: 18px;
}

.header-card {
  border-radius: 12px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-title {
  margin: 0 0 4px;
  font-size: 18px;
}

.page-subtitle {
  margin: 0;
  color: var(--text-sub);
  font-size: 13px;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-soft);
}

.kpi {
  background: #fafbff;
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.kpi-num {
  font-size: 22px;
  font-weight: 700;
  color: #2f6fed;
  font-variant-numeric: tabular-nums;
}

.kpi-warn { color: #f5a524; }
.kpi-ok { color: #17a673; }
.kpi-bad { color: #e5484d; }

.kpi-label {
  font-size: 12px;
  color: #8a93a5;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.tab-hint {
  margin: 0 0 14px;
  padding: 10px 14px;
  background: #f4f7ff;
  color: #4b5b8a;
  font-size: 13px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.device-cell strong {
  display: block;
  font-size: 14px;
}

.device-cell .muted {
  color: var(--text-sub);
  font-size: 12px;
}

.muted {
  color: var(--text-sub);
}

.pagination-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.mt-16 {
  margin-top: 16px;
}

.img-preview {
  margin-top: 8px;
}
</style>