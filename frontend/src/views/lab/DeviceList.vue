<template>
  <div class="page-container">
    <div class="stat-grid mb-16">
      <StatCard icon="Cpu" color="#2f6fed" :value="stats.total" label="设备总数" />
      <StatCard icon="CircleCheckFilled" color="#17a673" :value="statusCount('available')"
                label="可预约" />
      <StatCard icon="Tools" color="#f5a524" :value="statusCount('repairing')" label="维修中" />
      <StatCard icon="Delete" color="#909399" :value="statusCount('scrapped')" label="已报废" />
    </div>

    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">设备台账</h3>
          <p class="page-subtitle">维护设备基础信息与状态，支持 Excel 批量导入导出；停用设备不可再被预约</p>
        </div>
        <div v-if="canManage" class="header-actions">
          <el-button :icon="Download" @click="doExport">导出台账</el-button>
          <el-button :icon="Upload" @click="importVisible = true">批量导入</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增设备</el-button>
        </div>
      </div>

      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="编号 / 名称 / 型号" clearable style="width: 200px"
                  @keyup.enter="load" @clear="load" />
        <el-select v-model="query.laboratory" placeholder="实验室" clearable filterable
                   style="width: 180px" @change="load">
          <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-select v-model="query.category" placeholder="设备分类" clearable style="width: 150px"
                   @change="load">
          <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-select v-model="query.status" placeholder="设备状态" clearable style="width: 130px"
                   @change="load">
          <el-option v-for="item in DEVICE_STATUS_OPTIONS" :key="item.value" :label="item.label"
                     :value="item.value" />
        </el-select>
        <el-select v-model="query.is_active" placeholder="启用状态" clearable style="width: 130px"
                   @change="load">
          <el-option label="启用" :value="1" />
          <el-option label="停用" :value="0" />
        </el-select>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="reset">重置</el-button>
          <el-button :icon="Search" type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="code" label="设备编号" width="140" show-overflow-tooltip />
        <el-table-column prop="name" label="设备名称" min-width="130" show-overflow-tooltip />
        <el-table-column prop="model" label="型号" width="150" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="120" show-overflow-tooltip />
        <el-table-column prop="laboratory_name" label="所属实验室" width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="deviceStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="占用至" width="150">
          <template #default="{ row }">
            <span v-if="row.current_occupied_until" class="text-warning">
              {{ formatDateTime(row.current_occupied_until) }}
            </span>
            <span v-else class="text-success">空闲</span>
          </template>
        </el-table-column>
        <el-table-column prop="manufacturer" label="生产厂商" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.manufacturer || '—' }}</template>
        </el-table-column>
        <el-table-column label="单价" width="100" align="right">
          <template #default="{ row }">￥{{ Number(row.price || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">查看</el-button>
            <el-button link type="warning" size="small" @click="openHistory(row)">运维历史</el-button>
            <template v-if="canManage">
              <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="doRemove(row)">停用</el-button>
            </template>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无设备数据</div>
        </template>
      </el-table>

      <el-pagination class="mt-16" v-model:current-page="query.page" v-model:page-size="query.page_size"
                     :page-sizes="[10, 20, 50]" :total="total"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="load" @current-change="load" />
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑设备' : '新增设备'" width="720px"
               @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备编号" prop="code">
              <el-input v-model="form.code" placeholder="如：DEV-2026-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备名称" prop="name">
              <el-input v-model="form.name" placeholder="如：数字示波器" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备分类" prop="category">
              <el-select v-model="form.category" placeholder="请选择分类" filterable style="width: 100%">
                <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属实验室" prop="laboratory">
              <el-select v-model="form.laboratory" placeholder="请选择实验室" filterable style="width: 100%">
                <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option v-for="item in DEVICE_STATUS_OPTIONS" :key="item.value" :label="item.label"
                           :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生产厂商">
              <el-input v-model="form.manufacturer" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="购置日期">
              <el-date-picker v-model="form.purchase_date" type="date" format="YYYY-MM-DD"
                              value-format="YYYY-MM-DD" placeholder="选填" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单价（元）">
              <el-input-number v-model="form.price" :min="0" :precision="2" :step="100"
                               style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态">
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="规格参数">
              <el-input v-model="form.specification" type="textarea" :rows="2" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备图片">
              <el-upload :auto-upload="false" :show-file-list="false" accept="image/*"
                         :on-change="onPickImage">
                <el-button size="small" :icon="Picture">选择图片</el-button>
              </el-upload>
              <span v-if="form.image_name" class="text-muted" style="margin-left: 8px">
                {{ form.image_name }}
              </span>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="Excel 批量导入设备" width="680px">
      <el-alert type="info" :closable="false" class="mb-16">
        请先下载模板，按模板列填写后上传。设备编号与名称必填，实验室需填写已存在的实验室编号或名称。
      </el-alert>
      <div class="import-row">
        <el-button :icon="Download" @click="downloadTemplate">下载导入模板</el-button>
        <el-upload :auto-upload="false" :show-file-list="false" accept=".xlsx,.xlsm"
                   :on-change="onPickImport">
          <el-button type="primary" :icon="Upload">选择 Excel 文件</el-button>
        </el-upload>
        <span v-if="importFile" class="text-muted">{{ importFile.name }}</span>
        <el-checkbox v-model="dryRun">仅校验不导入</el-checkbox>
      </div>
      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="doImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resultVisible" title="导入结果" width="640px">
      <el-result v-if="importResult" :icon="importResult.failed ? 'warning' : 'success'"
                 :title="`成功 ${importResult.success} 条，失败 ${importResult.failed} 条`"
                 sub-title="详细的失败原因见下方列表" />
      <el-table v-if="importResult && importResult.errors.length" :data="importResult.errors"
                max-height="260" border>
        <el-table-column prop="row" label="行号" width="80" />
        <el-table-column prop="message" label="失败原因" />
      </el-table>
      <template #footer>
        <el-button type="primary" @click="resultVisible = false">我知道了</el-button>
      </template>
    </el-dialog>

    <!-- 设备运维历史 -->
    <el-drawer v-model="historyVisible" :title="`设备运维历史 · ${historyTarget?.name || ''}`"
               size="640px" direction="rtl">
      <div v-loading="historyLoading" class="history-wrap">
        <template v-if="historyData">
          <div class="history-summary">
            <div class="summary-item">
              <div class="summary-num summary-warn">{{ historyData.fault_count }}</div>
              <div class="summary-label">累计报修</div>
            </div>
            <div class="summary-item">
              <div class="summary-num">{{ historyData.order_count }}</div>
              <div class="summary-label">维修工单</div>
            </div>
            <div class="summary-item">
              <div class="summary-num summary-ok">{{ historyData.resolved_count }}</div>
              <div class="summary-label">已验收</div>
            </div>
            <div class="summary-item">
              <div class="summary-num">{{ historyData.recent_faults?.length || 0 }}</div>
              <div class="summary-label">近期记录</div>
            </div>
          </div>

          <el-descriptions :column="2" border class="mt-16">
            <el-descriptions-item label="最近巡检">
              {{ historyData.last_inspection_at ? formatDateTimeFull(historyData.last_inspection_at) : '尚无巡检' }}
            </el-descriptions-item>
            <el-descriptions-item label="最近报修">
              {{ historyData.last_fault_at ? formatDateTimeFull(historyData.last_fault_at) : '尚无报修' }}
            </el-descriptions-item>
            <el-descriptions-item label="最近工单" :span="2">
              {{ historyData.last_order_at ? formatDateTimeFull(historyData.last_order_at) : '尚无工单' }}
            </el-descriptions-item>
          </el-descriptions>

          <el-tabs class="mt-16">
            <el-tab-pane label="报修记录">
              <el-empty v-if="!historyData.recent_faults?.length" description="暂无报修" :image-size="60" />
              <el-table v-else :data="historyData.recent_faults" border size="small">
                <el-table-column prop="no" label="编号" width="170" />
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="faultTag(row.status)" size="small">{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="严重度" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.severity === 'urgent' ? 'danger' : row.severity === 'high' ? 'warning' : 'info'"
                            size="small">
                      {{ row.severity === 'urgent' ? '紧急' : row.severity === 'high' ? '严重' : '一般' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="时间">
                  <template #default="{ row }">{{ formatDateTimeFull(row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="维修工单">
              <el-empty v-if="!historyData.recent_orders?.length" description="暂无工单" :image-size="60" />
              <el-table v-else :data="historyData.recent_orders" border size="small">
                <el-table-column prop="no" label="工单编号" width="170" />
                <el-table-column label="标题" prop="title" show-overflow-tooltip />
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="优先级" width="80">
                  <template #default="{ row }">
                    <el-tag :type="priorityTag(row.priority)" size="small">{{ row.priority }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatDateTimeFull(row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="巡检记录">
              <el-empty v-if="!historyData.recent_inspections?.length" description="暂无巡检" :image-size="60" />
              <el-table v-else :data="historyData.recent_inspections" border size="small">
                <el-table-column label="结果" width="100">
                  <template #default="{ row }">
                    <el-tag :type="recordTag(row.result)" size="small">{{ recordLabel(row.result) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="inspector_name" label="巡检人" />
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatDateTimeFull(row.inspected_at) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>

          <div class="history-actions mt-16">
            <el-button type="primary" :icon="Document" @click="$router.push('/maintenance/faults')">
              报修中心
            </el-button>
            <el-button type="warning" @click="$router.push('/maintenance/orders')">维修工单</el-button>
            <el-button @click="$router.push('/maintenance/inspections')">巡检记录</el-button>
          </div>
        </template>
        <el-empty v-else-if="!historyLoading" description="暂无运维数据" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Download, Picture, Plus, Refresh, Search, Upload } from '@element-plus/icons-vue'
import StatCard from '@/components/StatCard.vue'
import { categoryApi, deviceApi, labApi, maintenanceApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { DEVICE_STATUS_OPTIONS, deviceStatusType, formatDateTime, formatDateTimeFull } from '@/utils/dict'

const route = useRoute()
const userStore = useUserStore()
const canManage = computed(() => userStore.isAdminRole)

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const total = ref(0)
const labs = ref([])
const categories = ref([])
const dialogVisible = ref(false)
const formRef = ref()
const stats = ref({ total: 0, by_status: [] })

const importVisible = ref(false)
const importing = ref(false)
const importFile = ref(null)
const dryRun = ref(false)
const resultVisible = ref(false)
const importResult = ref(null)

const historyVisible = ref(false)
const historyLoading = ref(false)
const historyTarget = ref(null)
const historyData = ref(null)

function priorityTag(p) {
  return { P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' }[p] || 'info'
}
function statusTag(s) {
  return {
    pending: 'warning', dispatched: 'primary', repairing: 'warning',
    resolved: 'success', closed: 'info', rejected: 'danger',
    processing: 'processing', verified: 'success', cancelled: 'info'
  }[s] || 'info'
}
function faultTag(s) {
  return {
    pending: 'warning', dispatched: 'primary', repairing: 'warning',
    resolved: 'success', closed: 'info', rejected: 'danger'
  }[s] || 'info'
}
function recordTag(r) {
  return { normal: 'success', abnormal: 'warning', need_repair: 'danger' }[r] || 'info'
}
function recordLabel(r) {
  return { normal: '正常', abnormal: '异常', need_repair: '需维修' }[r] || r
}

async function openHistory(row) {
  historyTarget.value = row
  historyData.value = null
  historyVisible.value = true
  historyLoading.value = true
  try {
    const res = await maintenanceApi.deviceSummary(row.id)
    historyData.value = res.data
  } catch (e) {
    historyData.value = null
  } finally {
    historyLoading.value = false
  }
}

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  laboratory: '',
  category: '',
  status: '',
  is_active: '',
  ordering: 'id'
})

const form = ref(emptyForm())

function emptyForm() {
  return {
    id: null,
    code: '',
    name: '',
    model: '',
    category: '',
    laboratory: '',
    status: 'available',
    manufacturer: '',
    purchase_date: '',
    price: 0,
    specification: '',
    remark: '',
    is_active: true,
    image: null,
    image_name: ''
  }
}

const rules = {
  code: [{ required: true, message: '请输入设备编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择设备分类', trigger: 'change' }],
  laboratory: [{ required: true, message: '请选择所属实验室', trigger: 'change' }],
  status: [{ required: true, message: '请选择设备状态', trigger: 'change' }]
}

function statusCount(status) {
  const item = (stats.value.by_status || []).find((row) => row.status === status)
  return item ? item.count : 0
}

function buildParams() {
  const params = { page: query.page, page_size: query.page_size, ordering: query.ordering }
  if (query.keyword) params.keyword = query.keyword
  if (query.laboratory) params.laboratory = query.laboratory
  if (query.category) params.category = query.category
  if (query.status) params.status = query.status
  if (query.is_active !== '') params.is_active = query.is_active
  return params
}

async function load() {
  loading.value = true
  try {
    const res = await deviceApi.list(buildParams())
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  const res = await deviceApi.statistics(buildParams())
  stats.value = res.data
}

function reset() {
  query.keyword = ''
  query.laboratory = ''
  query.category = ''
  query.status = ''
  query.is_active = ''
  query.page = 1
  load()
}

function resetForm() {
  form.value = emptyForm()
  formRef.value?.clearValidate()
}

function openCreate() {
  resetForm()
  if (query.laboratory) form.value.laboratory = query.laboratory
  dialogVisible.value = true
}

function openEdit(row) {
  resetForm()
  form.value = {
    id: row.id,
    code: row.code,
    name: row.name,
    model: row.model || '',
    category: row.category,
    laboratory: row.laboratory,
    status: row.status,
    manufacturer: row.manufacturer || '',
    purchase_date: row.purchase_date || '',
    price: Number(row.price || 0),
    specification: row.specification || '',
    remark: row.remark || '',
    is_active: row.is_active,
    image: null,
    image_name: row.image ? '已上传图片（重新选择将覆盖）' : ''
  }
  dialogVisible.value = true
}

function onPickImage(uploadFile) {
  form.value.image = uploadFile.raw
  form.value.image_name = uploadFile.name
}

function buildFormData() {
  const data = new FormData()
  Object.entries({
    code: form.value.code,
    name: form.value.name,
    model: form.value.model || '',
    category: form.value.category,
    laboratory: form.value.laboratory,
    status: form.value.status,
    manufacturer: form.value.manufacturer || '',
    price: form.value.price,
    specification: form.value.specification || '',
    remark: form.value.remark || '',
    is_active: form.value.is_active ? 'true' : 'false'
  }).forEach(([key, value]) => data.append(key, value))
  if (form.value.purchase_date) data.append('purchase_date', form.value.purchase_date)
  if (form.value.image) data.append('image', form.value.image)
  return data
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    const data = buildFormData()
    if (form.value.id) {
      await deviceApi.update(form.value.id, data)
      ElMessage.success('设备信息已更新')
    } else {
      await deviceApi.create(data)
      ElMessage.success('设备创建成功')
    }
    dialogVisible.value = false
    load()
    loadStats()
  } finally {
    saving.value = false
  }
}

async function doRemove(row) {
  await ElMessageBox.confirm(`确认停用设备「${row.name}」吗？停用后不可被预约。`, '停用确认', {
    type: 'warning'
  })
  await deviceApi.remove(row.id)
  ElMessage.success('设备已停用')
  load()
  loadStats()
}

async function doExport() {
  await deviceApi.export(buildParams())
  ElMessage.success('导出任务已开始')
}

function downloadTemplate() {
  deviceApi.importTemplate()
}

function onPickImport(uploadFile) {
  importFile.value = uploadFile.raw
}

async function doImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    formData.append('dry_run', dryRun.value ? 'true' : 'false')
    const res = await deviceApi.importDevices(formData)
    importResult.value = res.data
    importVisible.value = false
    resultVisible.value = true
    importFile.value = null
    load()
    loadStats()
  } finally {
    importing.value = false
  }
}

onMounted(async () => {
  const [labRes, categoryRes] = await Promise.all([labApi.simple(), categoryApi.list()])
  labs.value = labRes.data
  categories.value = categoryRes.data.results
  if (route.query.laboratory) query.laboratory = Number(route.query.laboratory)
  load()
  loadStats()
})
</script>

<style scoped>
.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.import-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
</style>
