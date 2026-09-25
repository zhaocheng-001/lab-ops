<template>
  <div class="page-container">
    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">我的预约</h3>
          <p class="page-subtitle">
            共 {{ total }} 条预约记录，单次预约时长上限 {{ userStore.maxReserveHours }} 小时
          </p>
        </div>
        <el-button type="primary" :icon="Plus" @click="$router.push('/reservations/create')">
          发起预约
        </el-button>
      </div>

      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="预约编号 / 设备名称 / 用途" clearable
                  style="width: 230px" @keyup.enter="load" @clear="load" />
        <el-select v-model="query.status" placeholder="预约状态" clearable multiple collapse-tags
                   style="width: 220px" @change="load">
          <el-option v-for="item in RESERVATION_STATUS_OPTIONS" :key="item.value"
                     :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="query.laboratory" placeholder="实验室" clearable filterable
                   style="width: 190px" @change="load">
          <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
                        start-placeholder="开始日期" end-placeholder="结束日期" style="width: 250px"
                        @change="load" />
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="reset">重置</el-button>
          <el-button :icon="Search" type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="no" label="预约编号" width="185" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row)">{{ row.no }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="设备" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.device_name }}</div>
            <div class="text-muted" style="font-size: 12px">
              {{ row.device_code }} · {{ row.category_name }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="laboratory_name" label="实验室" min-width="140" show-overflow-tooltip />
        <el-table-column label="使用时间" width="210">
          <template #default="{ row }">
            <div>{{ formatDateTime(row.start_time) }}</div>
            <div class="text-muted" style="font-size: 12px">
              至 {{ formatDateTime(row.end_time) }}（{{ row.duration_hours }}h）
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            <el-tag v-if="row.is_overdue" type="danger" size="small" effect="dark"
                    style="margin-left: 4px">逾期</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_percent" :stroke-width="10"
                         :status="row.status === 'completed' ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
            <el-button v-if="canEdit(row)" link type="primary" size="small"
                       @click="$router.push(`/reservations/${row.id}/edit`)">修改</el-button>
            <el-button v-if="canEdit(row)" link type="success" size="small"
                       @click="doSubmit(row)">{{ row.status === 'rejected' ? '重新提交' : '提交' }}</el-button>
            <el-button v-if="row.status === 'pending'" link type="warning" size="small"
                       @click="doWithdraw(row)">撤回</el-button>
            <el-button v-if="['approved', 'waiting_use'].includes(row.status)" link type="danger"
                       size="small" @click="doCancel(row)">取消</el-button>
            <el-button v-if="row.can_sign_in && canSignInNow(row)" link type="success" size="small"
                       @click="doSignIn(row)">签到</el-button>
            <el-button v-if="row.status === 'in_use'" link type="primary" size="small"
                       @click="goSignOut(row)">签退</el-button>
            <el-button v-if="row.can_evaluate" link type="warning" size="small"
                       @click="goEvaluate(row)">评价</el-button>
            <el-button v-if="['draft', 'cancelled'].includes(row.status)" link type="danger"
                       size="small" @click="doDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无预约记录，点击右上角「发起预约」开始申请</div>
        </template>
      </el-table>

      <el-pagination
        class="mt-16"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="load"
        @current-change="load"
      />
    </div>

    <SignOutDialog v-model="signOutVisible" :reservation="currentRow" @success="load" />
    <EvaluateDialog v-model="evaluateVisible" :reservation="currentRow" @success="load" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { labApi, reservationApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { RESERVATION_STATUS_OPTIONS, formatDateTime, statusLabel, statusType } from '@/utils/dict'
import SignOutDialog from './components/SignOutDialog.vue'
import EvaluateDialog from './components/EvaluateDialog.vue'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const list = ref([])
const total = ref(0)
const labs = ref([])
const dateRange = ref([])
const currentRow = ref(null)
const signOutVisible = ref(false)
const evaluateVisible = ref(false)

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: [],
  laboratory: '',
  start_date: '',
  end_date: '',
  ordering: '-created_at'
})

function buildParams() {
  const params = {
    page: query.page,
    page_size: query.page_size,
    ordering: query.ordering
  }
  if (query.keyword) params.keyword = query.keyword
  if (query.status?.length) params.status = query.status.join(',')
  if (query.laboratory) params.laboratory = query.laboratory
  if (dateRange.value?.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
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

function reset() {
  query.keyword = ''
  query.status = []
  query.laboratory = ''
  query.page = 1
  dateRange.value = []
  load()
}

function goDetail(row) {
  router.push(`/reservations/${row.id}`)
}

const canEdit = (row) => ['draft', 'rejected'].includes(row.status)

function canSignInNow(row) {
  const now = Date.now()
  const start = new Date(row.start_time).getTime() - 30 * 60 * 1000
  const end = new Date(row.end_time).getTime()
  return now >= start && now <= end
}

async function doSubmit(row) {
  await ElMessageBox.confirm(`确认提交预约 ${row.no} 吗？提交后将进入审批流程。`, '提交预约', {
    type: 'warning'
  })
  await reservationApi.submit(row.id)
  ElMessage.success('预约已提交，等待管理员审批')
  load()
}

async function doWithdraw(row) {
  const { value } = await ElMessageBox.prompt('请输入撤回原因（可留空）', '撤回预约', {
    inputPlaceholder: '如：课程时间冲突',
    confirmButtonText: '确认撤回',
    cancelButtonText: '取消'
  })
  await reservationApi.withdraw(row.id, { reason: value || '' })
  ElMessage.success('预约已撤回')
  load()
}

async function doCancel(row) {
  const { value } = await ElMessageBox.prompt('请输入取消原因（可留空）', '取消预约', {
    inputPlaceholder: '如：临时有事无法使用',
    confirmButtonText: '确认取消',
    cancelButtonText: '取消'
  })
  await reservationApi.cancel(row.id, { cancel_reason: value || '' })
  ElMessage.success('预约已取消')
  load()
}

function doSignIn(row) {
  ElMessageBox.confirm(
    `确认对预约 ${row.no} 进行签到？签到后开始计时使用。`,
    '签到确认',
    { type: 'info' }
  )
    .then(async () => {
      await reservationApi.signIn(row.id, {})
      ElMessage.success('签到成功，开始计时')
      load()
    })
    .catch(() => {})
}

function goSignOut(row) {
  currentRow.value = row
  signOutVisible.value = true
}

function goEvaluate(row) {
  currentRow.value = row
  evaluateVisible.value = true
}

async function doDelete(row) {
  await ElMessageBox.confirm(`确认删除预约 ${row.no} 吗？删除后不可恢复。`, '删除确认', {
    type: 'warning'
  })
  await reservationApi.remove(row.id)
  ElMessage.success('预约已删除')
  load()
}

onMounted(async () => {
  const labRes = await labApi.simple()
  labs.value = labRes.data
  load()
})
</script>
