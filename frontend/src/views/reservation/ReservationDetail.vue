<template>
  <div class="page-container" v-loading="loading">
    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">
            预约详情
            <el-tag v-if="detail" :type="statusType(detail.status)" size="small">
              {{ statusLabel(detail.status) }}
            </el-tag>
            <el-tag v-if="detail?.is_overdue" type="danger" size="small" effect="dark">已逾期</el-tag>
          </h3>
          <p class="page-subtitle">
            预约编号 {{ detail?.no || '—' }} · 提交于 {{ formatDateTime(detail?.created_at) }}
          </p>
        </div>
        <div class="header-actions">
          <el-button :icon="ChatDotRound" @click="goChat">图文沟通</el-button>
          <el-button :icon="Back" @click="goBack">返回</el-button>
        </div>
      </div>

      <template v-if="detail">
        <el-progress v-if="['approved', 'waiting_use', 'in_use', 'completed'].includes(detail.status)"
                     :percentage="detail.progress_percent" :stroke-width="14"
                     :status="detail.status === 'completed' ? 'success' : ''" class="mb-16" />

        <div class="action-bar">
          <template v-if="isOwner">
            <el-button v-if="detail.status === 'draft'" type="success" @click="doSubmit">提交预约</el-button>
            <el-button v-if="['draft', 'rejected'].includes(detail.status)" type="primary"
                       @click="goEdit">修改预约</el-button>
            <el-button v-if="detail.status === 'pending'" type="warning" @click="doWithdraw">撤回预约</el-button>
            <el-button v-if="['approved', 'waiting_use'].includes(detail.status)" type="danger"
                       @click="doCancel">取消预约</el-button>
            <el-button v-if="canSignIn" type="success" @click="doSignIn">签到使用</el-button>
            <el-button v-if="detail.status === 'in_use'" type="primary" @click="signOutVisible = true">
              签退归还
            </el-button>
            <el-button v-if="detail.can_evaluate" type="warning" @click="evaluateVisible = true">
              提交评价
            </el-button>
            <el-button v-if="['draft', 'cancelled'].includes(detail.status)" type="danger" plain
                       @click="doDelete">删除</el-button>
          </template>

          <template v-if="canManage">
            <el-button v-if="detail.status === 'pending'" type="success" @click="approveVisible = true">
              审批通过
            </el-button>
            <el-button v-if="detail.status === 'pending'" type="danger" @click="rejectVisible = true">
              驳回申请
            </el-button>
            <el-button v-if="detail.status === 'pending'" type="warning" @click="openTransfer">
              转派审批
            </el-button>
            <el-button v-if="detail.status === 'in_use'" type="primary" @click="completeVisible = true">
              核验完工
            </el-button>
          </template>
        </div>

        <h4 class="section-title">基础信息</h4>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="申请人">{{ detail.applicant_name }}</el-descriptions-item>
          <el-descriptions-item label="申请人角色">{{ roleLabel(detail.applicant_role) }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">
            {{ detail.contact_phone || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="学院">{{ detail.college_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="班级">{{ detail.class_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="紧急程度">
            <el-tag :type="detail.urgency === 'urgent' ? 'danger' : 'info'" size="small">
              {{ urgencyLabel(detail.urgency) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="实验室">
            {{ detail.laboratory_name }}
            <span class="text-muted">（{{ detail.laboratory_detail?.code }} · {{ detail.laboratory_detail?.location }}）</span>
          </el-descriptions-item>
          <el-descriptions-item label="设备">
            {{ detail.device_name }}（{{ detail.device_code }}）
          </el-descriptions-item>
          <el-descriptions-item label="设备类型">{{ detail.category_name }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDateTime(detail.start_time) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatDateTime(detail.end_time) }}</el-descriptions-item>
          <el-descriptions-item label="使用时长">{{ detail.duration_hours }} 小时</el-descriptions-item>
          <el-descriptions-item label="用途说明" :span="3">
            {{ detail.purpose || '—' }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">流程信息</h4>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="提交时间">{{ formatDateTime(detail.submit_time) }}</el-descriptions-item>
          <el-descriptions-item label="审批人">{{ detail.approver_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="审批时间">{{ formatDateTime(detail.approve_time) }}</el-descriptions-item>
          <el-descriptions-item label="签到时间">{{ formatDateTime(detail.sign_in_time) }}</el-descriptions-item>
          <el-descriptions-item label="签退时间">{{ formatDateTime(detail.sign_out_time) }}</el-descriptions-item>
          <el-descriptions-item label="完工时间">{{ formatDateTime(detail.completion_time) }}</el-descriptions-item>
          <el-descriptions-item label="审批意见" :span="3">
            {{ detail.approve_remark || '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.reject_reason" label="驳回原因" :span="3">
            <span class="text-danger">{{ detail.reject_reason }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.cancel_reason" label="取消/撤回原因" :span="3">
            {{ detail.cancel_reason }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.device_status_after" label="设备归还状态">
            {{ deviceStatusLabel(detail.device_status_after) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.abnormal_note" label="异常情况说明" :span="2">
            {{ detail.abnormal_note }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.completion_remark" label="完工备注" :span="3">
            {{ detail.completion_remark }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">状态流转</h4>
        <el-timeline v-if="statusLogs.length">
          <el-timeline-item v-for="log in statusLogs" :key="log.id"
                            :timestamp="formatDateTimeFull(log.created_at)" placement="top"
                            :type="logActionType(log.action)">
            <div class="timeline-title">
              {{ log.action_display || logActionLabel(log.action) }}
              <span v-if="log.from_status !== log.to_status" class="text-muted">
                {{ log.from_status_display }} → {{ log.to_status_display }}
              </span>
            </div>
            <div class="text-muted" style="font-size: 12px">
              操作人：{{ log.operator_name || '系统' }}
              <template v-if="log.remark"> · {{ log.remark }}</template>
            </div>
          </el-timeline-item>
        </el-timeline>
        <div v-else class="empty-tip">暂无流转记录</div>

        <template v-if="detail.evaluation">
          <h4 class="section-title">完工评价</h4>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="设备状态评分">
              <el-rate :model-value="detail.evaluation.device_score" disabled />
            </el-descriptions-item>
            <el-descriptions-item label="响应速度评分">
              <el-rate :model-value="detail.evaluation.speed_score" disabled />
            </el-descriptions-item>
            <el-descriptions-item label="管理服务评分">
              <el-rate :model-value="detail.evaluation.service_score" disabled />
            </el-descriptions-item>
            <el-descriptions-item label="综合评分">{{ detail.evaluation.average_score }}</el-descriptions-item>
            <el-descriptions-item label="评价人">{{ detail.evaluation.evaluator_name }}</el-descriptions-item>
            <el-descriptions-item label="评价时间">
              {{ formatDateTime(detail.evaluation.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="评价内容" :span="3">
              {{ detail.evaluation.content || '—' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="detail.evaluation.reply_content" label="管理员回复" :span="3">
              {{ detail.evaluation.reply_content }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </template>
    </div>

    <el-dialog v-model="approveVisible" title="审批通过" width="480px">
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

    <SignOutDialog v-model="signOutVisible" :reservation="detail" @success="load" />
    <EvaluateDialog v-model="evaluateVisible" :reservation="detail" @success="load" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, ChatDotRound } from '@element-plus/icons-vue'
import { reservationApi, userApi } from '@/api'
import { roleLabel, useUserStore } from '@/stores/user'
import {
  DEVICE_STATUS_OPTIONS,
  deviceStatusLabel,
  formatDateTime,
  formatDateTimeFull,
  logActionLabel,
  logActionType,
  statusLabel,
  statusType,
  urgencyLabel
} from '@/utils/dict'
import SignOutDialog from './components/SignOutDialog.vue'
import EvaluateDialog from './components/EvaluateDialog.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const actionLoading = ref(false)
const detail = ref(null)
const statusLogs = ref([])
const approvers = ref([])

const approveVisible = ref(false)
const rejectVisible = ref(false)
const transferVisible = ref(false)
const completeVisible = ref(false)
const signOutVisible = ref(false)
const evaluateVisible = ref(false)

const approveForm = ref({ approve_remark: '' })
const rejectForm = ref({ reject_reason: '' })
const transferForm = ref({ approver: '', remark: '' })
const completeForm = ref({ return_confirmed: true, device_status_after: '', completion_remark: '' })

const isOwner = computed(
  () => detail.value && userStore.user && detail.value.applicant === userStore.user.id
)

const canManage = computed(() => {
  if (!detail.value) return false
  if (userStore.isSysAdmin) return true
  if (userStore.isLabAdmin) {
    const ids = (userStore.user?.managed_labs || []).map((item) => item.id)
    return ids.includes(detail.value.laboratory)
  }
  return false
})

const canSignIn = computed(() => {
  if (!detail.value || !detail.value.can_sign_in) return false
  if (!isOwner.value) return false
  const now = Date.now()
  return (
    now >= new Date(detail.value.start_time).getTime() - 30 * 60 * 1000 &&
    now <= new Date(detail.value.end_time).getTime()
  )
})

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/reservations')
}

function goEdit() {
  router.push(`/reservations/${detail.value.id}/edit`)
}

function goChat() {
  router.push({ path: '/chats', query: { reservation: detail.value.id } })
}

async function load() {
  loading.value = true
  try {
    const res = await reservationApi.detail(route.params.id)
    detail.value = res.data
    statusLogs.value = [...(res.data.status_logs || [])].reverse()
  } finally {
    loading.value = false
  }
}

async function doSubmit() {
  await ElMessageBox.confirm('确认提交该预约吗？提交后将进入审批流程。', '提交预约', {
    type: 'warning'
  })
  await reservationApi.submit(detail.value.id)
  ElMessage.success('预约已提交，等待管理员审批')
  load()
}

async function doWithdraw() {
  const { value } = await ElMessageBox.prompt('请输入撤回原因（可留空）', '撤回预约', {
    inputPlaceholder: '如：课程时间冲突'
  })
  await reservationApi.withdraw(detail.value.id, { reason: value || '' })
  ElMessage.success('预约已撤回')
  load()
}

async function doCancel() {
  const { value } = await ElMessageBox.prompt('请输入取消原因（可留空）', '取消预约', {
    inputPlaceholder: '如：临时有事无法使用'
  })
  await reservationApi.cancel(detail.value.id, { cancel_reason: value || '' })
  ElMessage.success('预约已取消')
  load()
}

async function doSignIn() {
  await ElMessageBox.confirm('确认签到并开始计时使用吗？', '签到确认', { type: 'info' })
  await reservationApi.signIn(detail.value.id, {})
  ElMessage.success('签到成功，开始计时')
  load()
}

async function doDelete() {
  await ElMessageBox.confirm('确认删除该预约吗？删除后不可恢复。', '删除确认', { type: 'warning' })
  await reservationApi.remove(detail.value.id)
  ElMessage.success('预约已删除')
  router.push('/reservations')
}

async function doApprove() {
  actionLoading.value = true
  try {
    await reservationApi.approve(detail.value.id, approveForm.value)
    ElMessage.success('审批通过')
    approveVisible.value = false
    approveForm.value = { approve_remark: '' }
    load()
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
    await reservationApi.reject(detail.value.id, rejectForm.value)
    ElMessage.success('已驳回该预约')
    rejectVisible.value = false
    rejectForm.value = { reject_reason: '' }
    load()
  } finally {
    actionLoading.value = false
  }
}

async function openTransfer() {
  if (!approvers.value.length) {
    const res = await userApi.simple({ role: 'lab_admin,sys_admin' })
    approvers.value = res.data.filter((item) => item.id !== userStore.user?.id)
  }
  transferForm.value = { approver: '', remark: '' }
  transferVisible.value = true
}

async function doTransfer() {
  if (!transferForm.value.approver) {
    ElMessage.warning('请选择转派对象')
    return
  }
  actionLoading.value = true
  try {
    await reservationApi.transfer(detail.value.id, transferForm.value)
    ElMessage.success('已转派')
    transferVisible.value = false
    load()
  } finally {
    actionLoading.value = false
  }
}

async function doComplete() {
  actionLoading.value = true
  try {
    const payload = { ...completeForm.value }
    if (!payload.device_status_after) delete payload.device_status_after
    await reservationApi.complete(detail.value.id, payload)
    ElMessage.success('已确认完工，预约完成')
    completeVisible.value = false
    completeForm.value = { return_confirmed: true, device_status_after: '', completion_remark: '' }
    load()
  } finally {
    actionLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.header-actions {
  display: flex;
  gap: 10px;
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 14px;
  background: #f7f9fc;
  border-radius: 10px;
  margin-bottom: 18px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 22px 0 12px;
  padding-left: 10px;
  border-left: 3px solid var(--brand-primary);
}

.timeline-title {
  font-size: 14px;
  display: flex;
  gap: 10px;
  align-items: center;
}
</style>
