<template>
  <div class="page-container">
    <div class="stat-grid mb-16">
      <StatCard icon="Tickets" color="#2f6fed" :value="statistics.total" label="预约总数" />
      <StatCard icon="Clock" color="#00b4d8" :value="statistics.pending" label="待审批" />
      <StatCard icon="Timer" color="#17a673" :value="statistics.using" label="使用中" />
      <StatCard icon="CircleCheckFilled" color="#2f6fed" :value="statistics.completed" label="已完成" />
      <StatCard icon="Star" color="#f5a524" :value="statistics.to_evaluate" label="待评价" />
      <StatCard icon="WarningFilled" color="#e5484d" :value="statistics.overdue" label="已逾期"
                :value-color="statistics.overdue ? '#e5484d' : ''" />
    </div>

    <!-- 学生 / 教师：我的使用进度 -->
    <div v-if="userStore.isApplicant" class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">使用进度跟踪</h3>
          <p class="page-subtitle">
            已通过审核的预约可按时间签到使用，使用结束请及时签退并登记设备状态
          </p>
        </div>
        <el-button :icon="Refresh" @click="loadProgress">刷新</el-button>
      </div>

      <el-table :data="current" v-loading="progressLoading" border stripe>
        <el-table-column prop="no" label="预约编号" width="180" show-overflow-tooltip />
        <el-table-column label="设备 / 实验室" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.device_name }}</div>
            <div class="text-muted" style="font-size: 12px">{{ row.laboratory_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="计划使用时间" width="210">
          <template #default="{ row }">
            <div>{{ formatDateTime(row.start_time) }}</div>
            <div class="text-muted" style="font-size: 12px">至 {{ formatDateTime(row.end_time) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="剩余时间" width="120">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.is_overdue }">
              {{ row.is_overdue ? '已超时' : formatRemaining(row.remaining_minutes) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_percent" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.can_sign_in" link type="success" size="small"
                       @click="doSignIn(row)">签到</el-button>
            <el-button v-if="row.can_sign_out" link type="primary" size="small"
                       @click="openSignOut(row)">签退归还</el-button>
            <el-button link type="primary" size="small" @click="$router.push(`/reservations/${row.id}`)">
              详情
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">当前没有进行中的预约，去发起一个新的预约吧</div>
        </template>
      </el-table>
    </div>

    <!-- 管理员：使用监控与核验 -->
    <div v-else class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">设备使用监控</h3>
          <p class="page-subtitle">跟踪设备使用与归还情况，签退后请核验设备状态并确认完工</p>
        </div>
      </div>

      <el-tabs v-model="adminTab" @tab-change="onAdminTabChange">
        <el-tab-pane label="使用中" name="in_use" />
        <el-tab-pane label="待签到使用" name="waiting" />
        <el-tab-pane label="已逾期" name="overdue" />
      </el-tabs>

      <div class="toolbar">
        <el-input v-model="adminQuery.keyword" placeholder="预约编号 / 申请人 / 设备" clearable
                  style="width: 220px" @keyup.enter="loadAdmin" @clear="loadAdmin" />
        <el-select v-model="adminQuery.laboratory" placeholder="实验室" clearable filterable
                   style="width: 190px" @change="loadAdmin">
          <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadAdmin">刷新</el-button>
        </div>
      </div>

      <el-table :data="adminList" v-loading="adminLoading" border stripe>
        <el-table-column prop="no" label="预约编号" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/reservations/${row.id}`)">{{ row.no }}</el-link>
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
        <el-table-column label="签到 / 签退" width="180">
          <template #default="{ row }">
            <div>签：{{ formatDateTime(row.sign_in_time) }}</div>
            <div class="text-muted" style="font-size: 12px">退：{{ formatDateTime(row.sign_out_time) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            <el-tag v-if="row.is_overdue" type="danger" size="small" effect="dark"
                    style="margin-top: 4px">逾期</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'in_use'" link type="primary" size="small"
                       @click="openComplete(row)">核验完工</el-button>
            <el-button link type="primary" size="small" @click="$router.push(`/reservations/${row.id}`)">
              详情
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无需要关注的预约</div>
        </template>
      </el-table>

      <el-pagination class="mt-16" v-model:current-page="adminQuery.page"
                     v-model:page-size="adminQuery.page_size" :page-sizes="[10, 20, 50]" :total="adminTotal"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="loadAdmin" @current-change="loadAdmin" />
    </div>

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

    <SignOutDialog v-model="signOutVisible" :reservation="currentRow" @success="loadProgress" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import StatCard from '@/components/StatCard.vue'
import { labApi, reservationApi } from '@/api'
import { roleLabel, useUserStore } from '@/stores/user'
import { DEVICE_STATUS_OPTIONS, formatDateTime, statusLabel, statusType } from '@/utils/dict'
import SignOutDialog from '../reservation/components/SignOutDialog.vue'

const userStore = useUserStore()

/* ---------------- 申请人视角 ---------------- */
const progressLoading = ref(false)
const current = ref([])
const statistics = ref({
  total: 0, pending: 0, using: 0, completed: 0, overdue: 0, to_evaluate: 0
})
const signOutVisible = ref(false)

/* ---------------- 管理员视角 ---------------- */
const adminTab = ref('in_use')
const adminLoading = ref(false)
const adminList = ref([])
const adminTotal = ref(0)
const labs = ref([])
const actionLoading = ref(false)
const completeVisible = ref(false)
const currentRow = ref(null)
const completeForm = ref({ return_confirmed: true, device_status_after: '', completion_remark: '' })

const adminQuery = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  laboratory: '',
  ordering: '-start_time'
})

function formatRemaining(minutes) {
  const value = Number(minutes || 0)
  if (value <= 0) return '—'
  const hours = Math.floor(value / 60)
  const mins = value % 60
  return hours ? `${hours} 小时 ${mins} 分钟` : `${mins} 分钟`
}

/* ---------------- 申请人逻辑 ---------------- */
async function loadProgress() {
  progressLoading.value = true
  try {
    const res = await reservationApi.myProgress()
    current.value = res.data.current
    statistics.value = res.data.statistics
  } finally {
    progressLoading.value = false
  }
}

async function doSignIn(row) {
  await ElMessageBox.confirm(`确认对预约 ${row.no} 签到？签到后开始计时使用。`, '签到确认', {
    type: 'info'
  })
  await reservationApi.signIn(row.id, {})
  ElMessage.success('签到成功，开始计时')
  loadProgress()
}

function openSignOut(row) {
  currentRow.value = row
  signOutVisible.value = true
}

/* ---------------- 管理员逻辑 ---------------- */
function adminParams() {
  const params = {
    page: adminQuery.page,
    page_size: adminQuery.page_size,
    ordering: adminQuery.ordering
  }
  if (adminTab.value === 'in_use') params.status = 'in_use'
  if (adminTab.value === 'waiting') params.status = 'approved,waiting_use'
  if (adminTab.value === 'overdue') params.only_overdue = 1
  if (adminQuery.keyword) params.keyword = adminQuery.keyword
  if (adminQuery.laboratory) params.laboratory = adminQuery.laboratory
  return params
}

async function loadAdmin() {
  adminLoading.value = true
  try {
    const res = await reservationApi.list(adminParams())
    adminList.value = res.data.results
    adminTotal.value = res.data.count
  } finally {
    adminLoading.value = false
  }
}

function onAdminTabChange() {
  adminQuery.page = 1
  loadAdmin()
}

function openComplete(row) {
  currentRow.value = row
  completeForm.value = { return_confirmed: true, device_status_after: '', completion_remark: '' }
  completeVisible.value = true
}

async function doComplete() {
  actionLoading.value = true
  try {
    const payload = { ...completeForm.value }
    if (!payload.device_status_after) delete payload.device_status_after
    await reservationApi.complete(currentRow.value.id, payload)
    ElMessage.success('已确认完工，预约完成')
    completeVisible.value = false
    loadAdmin()
  } finally {
    actionLoading.value = false
  }
}

onMounted(async () => {
  if (userStore.isApplicant) {
    loadProgress()
    return
  }
  const res = await labApi.simple({ mine: 1 })
  labs.value = res.data
  loadAdmin()
})
</script>
