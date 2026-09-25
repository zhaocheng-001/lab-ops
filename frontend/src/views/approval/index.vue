<template>
  <div class="page-container">
    <div class="stat-grid mb-16">
      <StatCard icon="CircleCheck" color="#f5a524" :value="todo.pending_approval" label="待我审批"
                clickable @click="switchTab('pending')" />
      <StatCard icon="Timer" color="#17a673" :value="todo.pending_return" label="待核验归还"
                clickable @click="switchTab('in_use')" />
      <StatCard icon="WarningFilled" color="#e5484d" :value="todo.overdue" label="已逾期"
                clickable @click="switchTab('overdue')" />
    </div>

    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">预约审批</h3>
          <p class="page-subtitle">审批本实验室的预约申请，支持通过、驳回与转派，全流程自动留痕并通知申请人</p>
        </div>
      </div>

      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane v-for="tab in tabs" :key="tab.key" :label="tab.label" :name="tab.key" />
      </el-tabs>

      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="预约编号 / 申请人 / 设备" clearable
                  style="width: 220px" @keyup.enter="load" @clear="load" />
        <el-select v-model="query.laboratory" placeholder="实验室" clearable filterable
                   style="width: 190px" @change="load">
          <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-select v-model="query.category" placeholder="设备类型" clearable style="width: 160px"
                   @change="load">
          <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-select v-model="query.urgency" placeholder="紧急程度" clearable style="width: 130px"
                   @change="load">
          <el-option v-for="item in URGENCY_OPTIONS" :key="item.value" :label="item.label"
                     :value="item.value" />
        </el-select>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="reset">重置</el-button>
          <el-button :icon="Search" type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="no" label="预约编号" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row)">{{ row.no }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="申请人" width="130">
          <template #default="{ row }">
            <div>{{ row.applicant_name }}</div>
            <div class="text-muted" style="font-size: 12px">{{ roleLabel(row.applicant_role) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="设备 / 实验室" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.device_name }}（{{ row.device_code }}）</div>
            <div class="text-muted" style="font-size: 12px">{{ row.laboratory_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="使用时间" width="200">
          <template #default="{ row }">
            <div>{{ formatDateTime(row.start_time) }}</div>
            <div class="text-muted" style="font-size: 12px">至 {{ formatDateTime(row.end_time) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="紧急程度" width="90">
          <template #default="{ row }">
            <el-tag :type="row.urgency === 'urgent' ? 'danger' : 'info'" size="small">
              {{ urgencyLabel(row.urgency) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            <el-tag v-if="row.is_overdue" type="danger" size="small" effect="dark"
                    style="margin-top: 4px">逾期</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
            <template v-if="row.status === 'pending'">
              <el-button link type="success" size="small" @click="openApprove(row)">通过</el-button>
              <el-button link type="danger" size="small" @click="openReject(row)">驳回</el-button>
              <el-button link type="warning" size="small" @click="openTransfer(row)">转派</el-button>
            </template>
            <el-button v-if="row.status === 'in_use'" link type="primary" size="small"
                       @click="openComplete(row)">核验完工</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">当前筛选条件下暂无预约记录</div>
        </template>
      </el-table>

      <el-pagination class="mt-16" v-model:current-page="query.page" v-model:page-size="query.page_size"
                     :page-sizes="[10, 20, 50]" :total="total"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="load" @current-change="load" />
    </div>

    <el-dialog v-model="approveVisible" title="审批通过" width="480px">
      <el-alert v-if="currentRow" type="info" :closable="false" class="mb-16">
        {{ currentRow.no }} · {{ currentRow.applicant_name }} · {{ currentRow.device_name }}
      </el-alert>
      <el-form label-width="90px">
        <el-form-item label="审批意见">
          <el-input v-model="approveForm.approve_remark" type="textarea" :rows="3"
                    placeholder="可填写使用注意事项（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="doApprove">确认通过</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="驳回申请" width="480px">
      <el-form label-width="90px">
        <el-form-item label="驳回原因" required>
          <el-input v-model="rejectForm.reject_reason" type="textarea" :rows="3"
                    placeholder="请说明驳回原因，将同步通知申请人" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="actionLoading" @click="doReject">确认驳回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="transferVisible" title="转派审批" width="480px">
      <el-form label-width="90px">
        <el-form-item label="转派给" required>
          <el-select v-model="transferForm.approver" placeholder="请选择管理员" filterable style="width: 100%">
            <el-option v-for="item in approvers" :key="item.id" :value="item.id"
                       :label="`${item.real_name}（${item.role_display}）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="转派说明">
          <el-input v-model="transferForm.remark" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="doTransfer">确认转派</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="completeVisible" title="核验完工" width="520px">
      <el-alert v-if="currentRow" type="info" :closable="false" class="mb-16">
        {{ currentRow.no }} · 签退时间 {{ formatDateTime(currentRow.sign_out_time) }}
      </el-alert>
      <el-form label-width="120px">
        <el-form-item label="设备已归还">
          <el-switch v-model="completeForm.return_confirmed" />
        </el-form-item>
        <el-form-item label="核验设备状态">
          <el-select v-model="completeForm.device_status_after" placeholder="不修改可留空" clearable
                     style="width: 100%">
            <el-option v-for="item in DEVICE_STATUS_OPTIONS" :key="item.value" :value="item.value"
                       :label="item.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="完工备注">
          <el-input v-model="completeForm.completion_remark" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="doComplete">确认完工</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import StatCard from '@/components/StatCard.vue'
import { categoryApi, labApi, reservationApi, userApi } from '@/api'
import { roleLabel } from '@/stores/user'
import {
  DEVICE_STATUS_OPTIONS,
  URGENCY_OPTIONS,
  formatDateTime,
  statusLabel,
  statusType,
  urgencyLabel
} from '@/utils/dict'

const router = useRouter()

const tabs = [
  { key: 'pending', label: '待我审批', status: 'pending' },
  { key: 'in_use', label: '待核验归还', status: 'in_use' },
  { key: 'approved', label: '已通过', status: 'approved,waiting_use' },
  { key: 'rejected', label: '已驳回', status: 'rejected' },
  { key: 'overdue', label: '已逾期', status: '' },
  { key: 'all', label: '全部', status: '' }
]

const activeTab = ref('pending')
const loading = ref(false)
const actionLoading = ref(false)
const list = ref([])
const total = ref(0)
const labs = ref([])
const categories = ref([])
const approvers = ref([])
const todo = ref({ pending_approval: 0, pending_return: 0, overdue: 0 })
const currentRow = ref(null)

const approveVisible = ref(false)
const rejectVisible = ref(false)
const transferVisible = ref(false)
const completeVisible = ref(false)

const approveForm = ref({ approve_remark: '' })
const rejectForm = ref({ reject_reason: '' })
const transferForm = ref({ approver: '', remark: '' })
const completeForm = ref({ return_confirmed: true, device_status_after: '', completion_remark: '' })

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  laboratory: '',
  category: '',
  urgency: '',
  ordering: '-created_at'
})

function buildParams() {
  const tab = tabs.find((item) => item.key === activeTab.value) || tabs[0]
  const params = {
    page: query.page,
    page_size: query.page_size,
    ordering: query.ordering,
    status: tab.status
  }
  if (tab.key === 'overdue') params.only_overdue = 1
  if (query.keyword) params.keyword = query.keyword
  if (query.laboratory) params.laboratory = query.laboratory
  if (query.category) params.category = query.category
  if (query.urgency) params.urgency = query.urgency
  return params
}

async function load() {
  loading.value = true
  try {
    const res = await reservationApi.list(buildParams())
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

async function loadTodo() {
  const res = await reservationApi.todo()
  todo.value = res.data
}

function switchTab(key) {
  activeTab.value = key
  query.page = 1
  load()
}

function onTabChange() {
  query.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.laboratory = ''
  query.category = ''
  query.urgency = ''
  query.page = 1
  load()
}

function goDetail(row) {
  router.push(`/reservations/${row.id}`)
}

function openApprove(row) {
  currentRow.value = row
  approveForm.value = { approve_remark: '' }
  approveVisible.value = true
}

function openReject(row) {
  currentRow.value = row
  rejectForm.value = { reject_reason: '' }
  rejectVisible.value = true
}

async function openTransfer(row) {
  currentRow.value = row
  if (!approvers.value.length) {
    const res = await userApi.simple({ role: 'lab_admin,sys_admin' })
    approvers.value = res.data
  }
  transferForm.value = { approver: '', remark: '' }
  transferVisible.value = true
}

function openComplete(row) {
  currentRow.value = row
  completeForm.value = { return_confirmed: true, device_status_after: '', completion_remark: '' }
  completeVisible.value = true
}

async function afterAction() {
  await Promise.all([load(), loadTodo()])
}

async function doApprove() {
  actionLoading.value = true
  try {
    await reservationApi.approve(currentRow.value.id, approveForm.value)
    ElMessage.success('审批通过')
    approveVisible.value = false
    afterAction()
  } finally {
    actionLoading.value = false
  }
}

async function doReject() {
  if (!rejectForm.value.reject_reason.trim()) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  actionLoading.value = true
  try {
    await reservationApi.reject(currentRow.value.id, rejectForm.value)
    ElMessage.success('已驳回该预约')
    rejectVisible.value = false
    afterAction()
  } finally {
    actionLoading.value = false
  }
}

async function doTransfer() {
  if (!transferForm.value.approver) {
    ElMessage.warning('请选择转派对象')
    return
  }
  actionLoading.value = true
  try {
    await reservationApi.transfer(currentRow.value.id, transferForm.value)
    ElMessage.success('已转派')
    transferVisible.value = false
    afterAction()
  } finally {
    actionLoading.value = false
  }
}

async function doComplete() {
  actionLoading.value = true
  try {
    const payload = { ...completeForm.value }
    if (!payload.device_status_after) delete payload.device_status_after
    await reservationApi.complete(currentRow.value.id, payload)
    ElMessage.success('已确认完工，预约完成')
    completeVisible.value = false
    afterAction()
  } finally {
    actionLoading.value = false
  }
}

onMounted(async () => {
  const [labRes, categoryRes] = await Promise.all([
    labApi.simple({ mine: 1 }),
    categoryApi.list()
  ])
  labs.value = labRes.data
  categories.value = categoryRes.data
  loadTodo()
  load()
})
</script>
