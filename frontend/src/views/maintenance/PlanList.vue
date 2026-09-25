<template>
  <div class="page-container">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2 class="page-title">维保计划</h2>
          <p class="page-subtitle">设置周期性预防维护，逾期提醒，避免设备"带病运行"</p>
        </div>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建计划</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="mt-16">
      <div class="filter-bar">
        <el-select v-model="filters.laboratory" placeholder="实验室" clearable style="width:180px">
          <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
        </el-select>
        <el-select v-model="filters.cycle" placeholder="周期" clearable style="width:140px">
          <el-option v-for="c in cycles" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="name" label="计划名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="适用范围" min-width="220">
          <template #default="{ row }">
            <div v-if="row.device_name">{{ row.device_name }}</div>
            <div v-else-if="row.device_category_name">{{ row.device_category_name }}（分类）</div>
            <div v-else-if="row.laboratory_name">{{ row.laboratory_name }}（实验室）</div>
            <div v-else class="muted">全局</div>
          </template>
        </el-table-column>
        <el-table-column label="周期" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.cycle_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下次到期" width="140">
          <template #default="{ row }">
            <span :class="{ overdue: row.is_overdue }">{{ row.next_due_date }}</span>
            <el-tag v-if="row.is_overdue" type="danger" size="small" effect="dark" class="ml-6">
              已逾期 {{ row.overdue_days }} 天
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="responsible_name" label="负责人" width="110" />
        <el-table-column label="完成率" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.completed_rate" :stroke-width="8"
                         :status="row.completed_rate >= 80 ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="toggle(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link type="warning" @click="openEdit(row)">编辑</el-button>
            <el-button link type="success" @click="executeDialog(row)">执行巡检</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
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
    <el-dialog v-model="detailVisible" title="计划详情" width="600px">
      <el-descriptions v-if="current" :column="2" border>
        <el-descriptions-item label="计划名称" :span="2">{{ current.name }}</el-descriptions-item>
        <el-descriptions-item label="适用设备" :span="2">
          {{ current.device_name || current.device_category_name || current.laboratory_name || '全局' }}
        </el-descriptions-item>
        <el-descriptions-item label="周期">{{ current.cycle_display }}（{{ current.interval_days }} 天）</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ current.responsible_name }}</el-descriptions-item>
        <el-descriptions-item label="上次执行">{{ current.last_done_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="下次到期">
          <span :class="{ overdue: current.is_overdue }">{{ current.next_due_date }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="说明" :span="2">{{ current.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="检查清单" :span="2">
          <ol class="checklist">
            <li v-for="(item, idx) in current.checklist" :key="idx">
              <el-tag v-if="item.required" type="danger" size="small">必检</el-tag>
              <el-tag v-else type="info" size="small">可选</el-tag>
              {{ item.item }}
            </li>
          </ol>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 新建/编辑 -->
    <el-dialog v-model="formVisible" :title="editing ? '编辑计划' : '新建计划'" width="640px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="计划名称" prop="name">
          <el-input v-model="form.name" placeholder="如：显微镜月度校准" />
        </el-form-item>
        <el-form-item label="适用范围">
          <el-radio-group v-model="scopeType" @change="onScopeTypeChange">
            <el-radio-button value="device">指定设备</el-radio-button>
            <el-radio-button value="category">按分类</el-radio-button>
            <el-radio-button value="laboratory">按实验室</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="scopeType === 'device'" label="设备">
          <el-select v-model="form.device" placeholder="选择设备" filterable style="width:100%">
            <el-option v-for="d in devices" :key="d.id"
                       :label="`${d.name} (${d.code})`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="scopeType === 'category'" label="分类">
          <el-select v-model="form.device_category" placeholder="选择分类" style="width:100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="scopeType === 'laboratory'" label="实验室">
          <el-select v-model="form.laboratory" placeholder="选择实验室" style="width:100%">
            <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="周期" prop="cycle">
          <el-select v-model="form.cycle" @change="onCycleChange">
            <el-option v-for="c in cycles" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="间隔天数" prop="interval_days">
          <el-input-number v-model="form.interval_days" :min="1" :max="365" />
          <span class="muted ml-6">根据周期自动推荐</span>
        </el-form-item>
        <el-form-item label="负责人" prop="responsible">
          <el-select v-model="form.responsible" placeholder="选择负责人" filterable>
            <el-option v-for="u in admins" :key="u.id"
                       :label="`${u.real_name} (${u.username})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="检查清单" prop="checklist">
          <div class="checklist-editor">
            <div v-for="(item, idx) in form.checklist" :key="idx" class="checklist-row">
              <el-input v-model="item.item" placeholder="检查项" style="flex:1" />
              <el-switch v-model="item.required" active-text="必检" />
              <el-button link type="danger" @click="removeChecklist(idx)">删除</el-button>
            </div>
            <el-button :icon="Plus" @click="addChecklist">添加检查项</el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 执行巡检 -->
    <el-dialog v-model="executeVisible" title="执行巡检" width="620px">
      <el-form :model="executeForm" label-width="100px">
        <el-alert v-if="executePlanName" type="info" :closable="false" show-icon style="margin-bottom:14px">
          <template #title>
            计划：{{ executePlanName }}
            <template v-if="failedRequiredCount() > 0 || !allChecklistPassed()">
              ，未通过 {{ executeForm.checklist.filter(c => !c.passed).length }} 项
            </template>
          </template>
        </el-alert>
        <el-form-item v-if="executeForm.checklist.length" label="检查清单">
          <div class="exec-checklist">
            <div v-for="(c, idx) in executeForm.checklist" :key="idx" class="exec-check-row">
              <el-checkbox v-model="c.passed">
                <el-tag v-if="c.required" type="danger" size="small" effect="plain" class="ml-6">必检</el-tag>
                <el-tag v-else type="info" size="small" effect="plain" class="ml-6">选检</el-tag>
                <span class="exec-check-text">{{ c.item }}</span>
              </el-checkbox>
              <el-input v-if="!c.passed" v-model="c.note" placeholder="异常说明（可选）"
                        size="small" style="margin-left: 28px; flex:1" />
            </div>
          </div>
        </el-form-item>
        <el-form-item v-else label="检查清单">
          <span class="muted">该计划尚未配置检查清单，请先在编辑页补充</span>
        </el-form-item>
        <el-form-item label="巡检结果">
          <el-radio-group v-model="executeForm.result" @change="setExecuteResult">
            <el-radio-button value="normal">正常</el-radio-button>
            <el-radio-button value="abnormal">异常</el-radio-button>
            <el-radio-button value="need_repair">需维修</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="executeForm.result !== 'normal'" label="问题描述">
          <el-input v-model="executeForm.issues" type="textarea" :rows="3"
                    placeholder="请描述发现的问题、影响范围等" />
        </el-form-item>
        <el-form-item v-if="executeForm.result === 'need_repair'" label="派单给" required>
          <el-select v-model="executeForm.handler_id" placeholder="选择处理人（默认按计划负责人）"
                     filterable style="width:100%">
            <el-option v-for="u in admins" :key="u.id"
                       :label="`${u.real_name || u.username}（${u.role_display || u.role}）`"
                       :value="u.id" />
          </el-select>
        </el-form-item>
        <el-alert v-if="executeForm.result === 'need_repair'" type="warning" :closable="false" show-icon>
          <template #title>勾选"需维修"将自动派生一条维修工单，同时推进计划的下次到期日</template>
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="executeVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirmExecute">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  categoryApi,
  collegeApi,
  deviceApi,
  labApi,
  maintenanceApi,
  userApi
} from '@/api'

const loading = ref(false)
const submitting = ref(false)
const list = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10 })
const filters = reactive({ laboratory: '', cycle: '' })

const cycles = [
  { value: 'weekly', label: '每周', days: 7 },
  { value: 'monthly', label: '每月', days: 30 },
  { value: 'quarterly', label: '每季度', days: 90 },
  { value: 'semi_yearly', label: '每半年', days: 180 },
  { value: 'yearly', label: '每年', days: 365 }
]

const labs = ref([])
const categories = ref([])
const devices = ref([])
const admins = ref([])

const detailVisible = ref(false)
const current = ref(null)
const formVisible = ref(false)
const editing = ref(false)
const formRef = ref()
const scopeType = ref('device')
const form = ref({
  id: null, name: '', device: null, device_category: null, laboratory: null,
  cycle: 'monthly', interval_days: 30, responsible: null,
  checklist: [{ item: '', required: true }], description: ''
})
const rules = {
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  cycle: [{ required: true, message: '请选择周期', trigger: 'change' }],
  interval_days: [{ required: true, message: '请输入间隔天数', trigger: 'blur' }],
  responsible: [{ required: true, message: '请选择负责人', trigger: 'change' }],
  checklist: [{
    validator(rule, value, callback) {
      if (!value || !value.length || !value.some((v) => v.item && v.item.trim())) {
        callback(new Error('请至少添加一项检查'))
      } else {
        callback()
      }
    },
    trigger: 'change'
  }]
}

const executeVisible = ref(false)
const executeForm = ref({ id: null, result: 'normal', issues: '', checklist: [], handler_id: null })
const executePlanName = ref('')

function buildChecklist(items) {
  return (items || []).map((c) => ({
    item: c.item || '',
    required: !!c.required,
    passed: true,
    note: ''
  }))
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (filters.laboratory) params.laboratory = filters.laboratory
    if (filters.cycle) params.cycle = filters.cycle
    const res = await maintenanceApi.listPlans(params)
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

async function loadSupport() {
  const [labRes, catRes, devRes, admRes] = await Promise.all([
    labApi.simple().catch(() => ({ data: [] })),
    categoryApi.list().catch(() => ({ data: { results: [] } })),
    deviceApi.list({ page_size: 200 }).catch(() => ({ data: { results: [] } })),
    userApi.simple({ role: 'lab_admin,sys_admin' }).catch(() => ({ data: [] }))
  ])
  labs.value = labRes.data
  categories.value = catRes.data.results
  devices.value = devRes.data.results
  admins.value = admRes.data
}

function onCycleChange(v) {
  const found = cycles.find((c) => c.value === v)
  if (found) form.value.interval_days = found.days
}

function onScopeTypeChange(v) {
  form.value.device = null
  form.value.device_category = null
  form.value.laboratory = null
}

function addChecklist() {
  form.value.checklist.push({ item: '', required: false })
}

function removeChecklist(idx) {
  form.value.checklist.splice(idx, 1)
}

function openCreate() {
  editing.value = false
  scopeType.value = 'device'
  form.value = {
    id: null, name: '', device: null, device_category: null, laboratory: null,
    cycle: 'monthly', interval_days: 30, responsible: null,
    checklist: [{ item: '', required: true }], description: ''
  }
  formVisible.value = true
}

async function openEdit(row) {
  editing.value = true
  const res = await maintenanceApi.planDetail(row.id)
  const data = res.data
  scopeType.value = data.device ? 'device'
    : data.device_category ? 'category' : data.laboratory ? 'laboratory' : 'device'
  form.value = {
    id: data.id, name: data.name,
    device: data.device, device_category: data.device_category, laboratory: data.laboratory,
    cycle: data.cycle, interval_days: data.interval_days, responsible: data.responsible,
    checklist: data.checklist?.length ? data.checklist : [{ item: '', required: true }],
    description: data.description || ''
  }
  formVisible.value = true
}

async function openDetail(row) {
  const res = await maintenanceApi.planDetail(row.id)
  current.value = res.data
  detailVisible.value = true
}

async function save() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = { ...form.value }
    if (scopeType.value !== 'device') payload.device = null
    if (scopeType.value !== 'category') payload.device_category = null
    if (scopeType.value !== 'laboratory') payload.laboratory = null
    payload.checklist = payload.checklist.filter((c) => c.item && c.item.trim())
    if (payload.responsible) {
      const adm = admins.value.find((a) => a.id === payload.responsible)
      payload.responsible_name = adm?.real_name || adm?.username
    } else {
      payload.responsible_name = ''
    }
    if (editing.value) {
      await maintenanceApi.updatePlan(form.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await maintenanceApi.createPlan(payload)
      ElMessage.success('已创建')
    }
    formVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

async function toggle(row) {
  try {
    await maintenanceApi.updatePlan(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已停用')
  } catch {
    row.is_active = !row.is_active
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除计划 "${row.name}"？`, '提示', { type: 'warning' })
  await maintenanceApi.deletePlan(row.id)
  ElMessage.success('已删除')
  load()
}

async function executeDialog(row) {
  executePlanName.value = row.name || ''
  executeForm.value = {
    id: row.id, result: 'normal', issues: '',
    checklist: buildChecklist(row.checklist || []),
    handler_id: row.responsible || null
  }
  // 当 row.checklist 为空时，主动从详情接口拉取一次
  if (!row.checklist || !row.checklist.length) {
    try {
      const res = await maintenanceApi.planDetail(row.id)
      executeForm.value.checklist = buildChecklist(res.data.checklist || [])
      executePlanName.value = res.data.name || executePlanName.value
      if (!executeForm.value.handler_id) {
        executeForm.value.handler_id = res.data.responsible || null
      }
    } catch { /* swallow */ }
  }
  executeVisible.value = true
}

function setExecuteResult(result) {
  executeForm.value.result = result
}

function allChecklistPassed() {
  return executeForm.value.checklist.every((c) => c.passed)
}

function failedRequiredCount() {
  return executeForm.value.checklist.filter((c) => c.required && !c.passed).length
}

async function confirmExecute() {
  if (!executeForm.value.checklist.length) {
    ElMessage.warning('当前计划未配置检查清单，请先在编辑页补充检查项')
    return
  }
  // 根据必检项失败情况自动提升结果
  if (executeForm.value.result === 'normal' && failedRequiredCount() > 0) {
    executeForm.value.result = 'abnormal'
    ElMessage.info('检测到必检项未通过，结果已自动标记为「异常」')
  }
  const failed = executeForm.value.checklist.filter((c) => !c.passed)
  if (executeForm.value.result === 'normal' && failed.length > 0) {
    executeForm.value.result = 'abnormal'
    ElMessage.info('存在未通过项，结果已自动标记为「异常」')
  }
  if (executeForm.value.result === 'need_repair' && !executeForm.value.handler_id) {
    ElMessage.warning('请选择处理人后再提交')
    return
  }
  // 构造 checklist_result：仅保留关键字段（item / required / passed / note）
  const checklist_result = executeForm.value.checklist.map((c) => ({
    item: c.item,
    required: !!c.required,
    passed: !!c.passed,
    note: c.note || ''
  }))
  const payload = {
    result: executeForm.value.result,
    issues: executeForm.value.issues || '',
    checklist_result,
    handler_id: executeForm.value.handler_id
  }
  const res = await maintenanceApi.executePlan(executeForm.value.id, payload)
  ElMessage.success(
    res.data.order
      ? '巡检完成，已自动派单'
      : '巡检完成'
  )
  executeVisible.value = false
  load()
}

onMounted(() => {
  load()
  loadSupport()
})
</script>

<style scoped lang="scss">
.page-container { padding: 18px; }
.header-card { border-radius: 12px; }
.header-row { display: flex; justify-content: space-between; align-items: center; }
.page-title { margin: 0 0 4px; font-size: 18px; }
.page-subtitle { margin: 0; color: var(--text-sub); font-size: 13px; }
.mt-16 { margin-top: 16px; }
.ml-6 { margin-left: 6px; }
.muted { color: var(--text-sub); font-size: 12px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 14px; }
.pagination-row { margin-top: 16px; display: flex; justify-content: flex-end; }
.overdue { color: #e5484d; font-weight: 600; }
.checklist { padding-left: 20px; margin: 0; }
.checklist li { margin: 4px 0; }
.checklist-editor { width: 100%; }
.checklist-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }

.exec-checklist { width: 100%; }
.exec-check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  flex-wrap: wrap;
}
.exec-check-text {
  font-size: 13px;
  color: #2b3245;
  margin-left: 6px;
}
</style>