<template>
  <div class="page-container">
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div>
          <h2 class="page-title">巡检记录</h2>
          <p class="page-subtitle">日常巡检、维保计划执行情况的真实台账</p>
        </div>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增巡检</el-button>
      </div>
    </el-card>

    <el-row :gutter="12" class="mt-16">
      <el-col :xs="12" :sm="6">
        <div class="stat-card"><div class="stat-label">总记录</div><div class="stat-value">{{ counts.total }}</div></div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card success">
          <div class="stat-label">正常</div><div class="stat-value">{{ counts.normal }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card warn">
          <div class="stat-label">异常</div><div class="stat-value">{{ counts.abnormal }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card danger">
          <div class="stat-label">需维修</div><div class="stat-value">{{ counts.need_repair }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="mt-16">
      <div class="filter-bar">
        <el-select v-model="filters.laboratory" placeholder="实验室" clearable style="width:180px">
          <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
        </el-select>
        <el-select v-model="filters.result" placeholder="结果" clearable style="width:140px">
          <el-option label="正常" value="normal" />
          <el-option label="异常" value="abnormal" />
          <el-option label="需维修" value="need_repair" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button v-if="hasFilter" @click="resetFilter">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="#" width="60" />
        <el-table-column label="实验室" width="160">
          <template #default="{ row }">
            {{ row.laboratory_name }}
          </template>
        </el-table-column>
        <el-table-column label="设备" width="180">
          <template #default="{ row }">
            <div v-if="row.device_name">{{ row.device_name }}</div>
            <span v-else class="muted">未指定</span>
          </template>
        </el-table-column>
        <el-table-column label="关联计划" width="180">
          <template #default="{ row }">
            <span v-if="row.plan_name">{{ row.plan_name }}</span>
            <span v-else class="muted">独立巡检</span>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="resultType(row.result)">{{ row.result_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="巡检人" prop="inspector_name" width="100" />
        <el-table-column label="巡检时间" width="160">
          <template #default="{ row }">{{ row.inspected_at }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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
    <el-dialog v-model="detailVisible" title="巡检详情" width="600px">
      <el-descriptions v-if="current" :column="2" border>
        <el-descriptions-item label="实验室">{{ current.laboratory_name }}</el-descriptions-item>
        <el-descriptions-item label="设备">{{ current.device_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联计划" :span="2">{{ current.plan_name || '独立巡检' }}</el-descriptions-item>
        <el-descriptions-item label="巡检人">{{ current.inspector_name }}</el-descriptions-item>
        <el-descriptions-item label="巡检时间">{{ current.inspected_at }}</el-descriptions-item>
        <el-descriptions-item label="结果" :span="2">
          <el-tag :type="resultType(current.result)">{{ current.result_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="current.issues" label="问题描述" :span="2">
          {{ current.issues }}
        </el-descriptions-item>
        <el-descriptions-item v-if="current.order_no" label="关联工单" :span="2">
          <el-tag type="warning">{{ current.order_no }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="current.checklist_result?.length" label="检查清单" :span="2">
          <ol class="checklist">
            <li v-for="(item, idx) in current.checklist_result" :key="idx">
              <el-icon v-if="item.ok" class="ok-icon"><CircleCheckFilled /></el-icon>
              <el-icon v-else class="fail-icon"><CircleCloseFilled /></el-icon>
              {{ item.item }}
            </li>
          </ol>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 新增 -->
    <el-dialog v-model="createVisible" title="新增巡检记录" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="实验室" prop="laboratory">
          <el-select v-model="form.laboratory" placeholder="选择实验室" style="width:100%">
            <el-option v-for="l in labs" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备" prop="device">
          <el-select v-model="form.device" placeholder="选择设备（可选）" filterable clearable style="width:100%">
            <el-option v-for="d in devices" :key="d.id"
                       :label="`${d.name} (${d.code})`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联计划" prop="plan">
          <el-select v-model="form.plan" placeholder="选择计划（可选）" clearable style="width:100%">
            <el-option v-for="p in plans" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="巡检时间" prop="inspected_at">
          <el-date-picker v-model="form.inspected_at" type="datetime" style="width:100%" />
        </el-form-item>
        <el-form-item label="结果" prop="result">
          <el-radio-group v-model="form.result">
            <el-radio-button value="normal">正常</el-radio-button>
            <el-radio-button value="abnormal">异常</el-radio-button>
            <el-radio-button value="need_repair">需维修</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.result !== 'normal'" label="问题描述">
          <el-input v-model="form.issues" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheckFilled, CircleCloseFilled, Plus } from '@element-plus/icons-vue'
import {
  deviceApi,
  labApi,
  maintenanceApi
} from '@/api'

const loading = ref(false)
const submitting = ref(false)
const list = ref([])
const total = ref(0)
const counts = ref({ total: 0, normal: 0, abnormal: 0, need_repair: 0 })
const query = reactive({ page: 1, page_size: 10 })
const filters = reactive({ laboratory: '', result: '' })

const labs = ref([])
const devices = ref([])
const plans = ref([])

const detailVisible = ref(false)
const current = ref(null)
const createVisible = ref(false)
const formRef = ref()
const form = ref({
  laboratory: null, device: null, plan: null, inspected_at: new Date(),
  result: 'normal', issues: ''
})
const rules = {
  laboratory: [{ required: true, message: '请选择实验室', trigger: 'change' }],
  inspected_at: [{ required: true, message: '请选择时间', trigger: 'change' }],
  result: [{ required: true, message: '请选择结果', trigger: 'change' }]
}

const hasFilter = computed(() => Boolean(filters.laboratory || filters.result))

function resultType(r) {
  return { normal: 'success', abnormal: 'warning', need_repair: 'danger' }[r] || 'info'
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (filters.laboratory) params.laboratory = filters.laboratory
    if (filters.result) params.result = filters.result
    const res = await maintenanceApi.listRecords(params)
    list.value = res.data.results
    total.value = res.data.count
    counts.value = {
      total: res.data.count,
      normal: list.value.filter((x) => x.result === 'normal').length,
      abnormal: list.value.filter((x) => x.result === 'abnormal').length,
      need_repair: list.value.filter((x) => x.result === 'need_repair').length
    }
  } finally {
    loading.value = false
  }
}

async function loadSupport() {
  const [labRes, devRes, planRes] = await Promise.all([
    labApi.simple().catch(() => ({ data: [] })),
    deviceApi.list({ page_size: 200 }).catch(() => ({ data: { results: [] } })),
    maintenanceApi.listPlans({ page_size: 100 }).catch(() => ({ data: { results: [] } }))
  ])
  labs.value = labRes.data
  devices.value = devRes.data.results
  plans.value = planRes.data.results
}

function resetFilter() {
  filters.laboratory = ''
  filters.result = ''
  query.page = 1
  load()
}

async function openDetail(row) {
  const res = await maintenanceApi.recordDetail(row.id)
  current.value = res.data
  detailVisible.value = true
}

function openCreate() {
  form.value = {
    laboratory: null, device: null, plan: null, inspected_at: new Date(),
    result: 'normal', issues: ''
  }
  createVisible.value = true
}

async function save() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      inspected_at: form.value.inspected_at instanceof Date
        ? form.value.inspected_at.toISOString()
        : form.value.inspected_at
    }
    await maintenanceApi.createRecord(payload)
    ElMessage.success(
      payload.result === 'need_repair'
        ? '巡检已记录，已自动派生维修工单'
        : '巡检已记录'
    )
    createVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
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
.muted { color: var(--text-sub); font-size: 12px; }
.stat-card {
  background: #fff; border-radius: 10px; padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
  border-left: 4px solid var(--brand-primary);
}
.stat-card.success { border-left-color: #17a673; }
.stat-card.warn { border-left-color: #f5a524; }
.stat-card.danger { border-left-color: #e5484d; }
.stat-label { color: var(--text-sub); font-size: 13px; margin-bottom: 6px; }
.stat-value { font-size: 22px; font-weight: 600; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 14px; }
.pagination-row { margin-top: 16px; display: flex; justify-content: flex-end; }
.checklist { padding-left: 20px; margin: 0; }
.checklist li { margin: 4px 0; display: flex; gap: 6px; align-items: center; }
.ok-icon { color: #17a673; }
.fail-icon { color: #e5484d; }
</style>