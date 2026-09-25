<template>
  <div class="page-container">
    <div class="page-card" v-loading="loading">
      <div class="page-header">
        <div>
          <h3 class="page-title">{{ isEdit ? '修改预约' : '发起预约' }}</h3>
          <p class="page-subtitle">
            单次预约时长上限 {{ userStore.maxReserveHours }} 小时；提交前系统自动校验开放时间与设备时段冲突
          </p>
        </div>
        <el-button :icon="Back" @click="goBack">返回</el-button>
      </div>

      <el-alert v-if="isEdit && reservationNo" type="info" :closable="false" class="mb-16">
        正在修改预约 <strong>{{ reservationNo }}</strong>，当前状态：{{ statusLabel(originalStatus) }}
      </el-alert>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" style="max-width: 880px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="实验室" prop="laboratory">
              <el-select v-model="form.laboratory" placeholder="请选择实验室" filterable clearable
                         style="width: 100%" @change="onLabChange">
                <el-option v-for="lab in labs" :key="lab.id" :value="lab.id"
                           :label="`${lab.name}（${lab.code}）`">
                  <div class="option-row">
                    <span>{{ lab.name }}（{{ lab.code }}）</span>
                    <span class="option-sub">{{ lab.location }}</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="预约设备" prop="device">
              <el-select v-model="form.device" placeholder="请先选择实验室" filterable
                         :loading="deviceLoading" :disabled="!form.laboratory"
                         style="width: 100%" @change="onDeviceChange">
                <el-option v-for="d in devices" :key="d.id" :value="d.id"
                           :disabled="!isDeviceSelectable(d)"
                           :label="`${d.name}（${d.code}）`">
                  <div class="option-row">
                    <span>{{ d.name }}（{{ d.code }}）</span>
                    <span class="option-sub">{{ d.status_display }} · {{ d.category_name }}</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-alert v-if="labInfo" type="info" :closable="false" class="mb-16">
          开放时间 {{ labInfo.open_time_start }} - {{ labInfo.open_time_end }}，
          开放日：{{ weekdayText(labInfo.open_weekdays) }}
        </el-alert>

        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker v-model="form.start_time" type="datetime" placeholder="选择开始时间"
                              format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm"
                              style="width: 100%" @change="conflictResult = null" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="结束时间" prop="end_time">
              <el-date-picker v-model="form.end_time" type="datetime" placeholder="选择结束时间"
                              format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm"
                              style="width: 100%" @change="conflictResult = null" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="紧急程度" prop="urgency">
          <el-radio-group v-model="form.urgency">
            <el-radio v-for="item in URGENCY_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="用途说明" prop="purpose">
          <el-input v-model="form.purpose" type="textarea" :rows="4" maxlength="200" show-word-limit
                    placeholder="请说明实验内容、使用需求等，作为管理员审批参考（提交预约时必填）" />
        </el-form-item>

        <el-form-item label="可用性校验">
          <el-button :icon="Search" :loading="checking" :disabled="!canCheck" @click="checkConflict">
            校验所选时段
          </el-button>
          <span v-if="durationText" class="text-muted" style="margin-left: 12px">{{ durationText }}</span>
        </el-form-item>

        <el-alert v-if="conflictResult" :type="conflictResult.available ? 'success' : 'error'"
                  :closable="false" show-icon class="mb-16">
          {{ conflictResult.available ? '该时段设备空闲，可以预约' : conflictResult.reason }}
        </el-alert>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit(true)">
            {{ isEdit ? '保存并重新提交' : '提交预约' }}
          </el-button>
          <el-button :loading="saving" @click="handleSubmit(false)">
            {{ isEdit ? '仅保存修改' : '暂存草稿' }}
          </el-button>
          <el-button @click="goBack">取消</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { deviceApi, labApi, reservationApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { URGENCY_OPTIONS, statusLabel, weekdayText } from '@/utils/dict'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isEdit = computed(() => route.name === 'ReservationEdit')
const reservationId = computed(() => Number(route.params.id))

const loading = ref(false)
const saving = ref(false)
const submitting = ref(false)
const checking = ref(false)
const deviceLoading = ref(false)
const formRef = ref()
const labs = ref([])
const devices = ref([])
const labInfo = ref(null)
const conflictResult = ref(null)
const originalStatus = ref('')
const reservationNo = ref('')

const form = ref({
  laboratory: '',
  device: '',
  start_time: '',
  end_time: '',
  purpose: '',
  urgency: 'normal'
})

const rules = {
  laboratory: [{ required: true, message: '请选择实验室', trigger: 'change' }],
  device: [{ required: true, message: '请选择设备', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
}

const canCheck = computed(
  () => Boolean(form.value.device && form.value.start_time && form.value.end_time)
)

const durationText = computed(() => {
  if (!form.value.start_time || !form.value.end_time) return ''
  const hours = dayjs(form.value.end_time).diff(dayjs(form.value.start_time), 'minute') / 60
  return `预约时长 ${hours.toFixed(2)} 小时（上限 ${userStore.maxReserveHours} 小时）`
})

function isDeviceSelectable(device) {
  return device.status === 'available' || device.id === Number(form.value.device)
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/reservations')
}

async function loadLabs() {
  const res = await labApi.simple()
  labs.value = res.data
}

async function loadDevices(labId) {
  if (!labId) {
    devices.value = []
    return
  }
  deviceLoading.value = true
  try {
    const params = { laboratory: labId, is_active: 1, page_size: 200 }
    if (!isEdit.value) params.bookable = 1
    const res = await deviceApi.list(params)
    devices.value = res.data.results
  } finally {
    deviceLoading.value = false
  }
}

async function onLabChange(labId) {
  form.value.device = ''
  conflictResult.value = null
  labInfo.value = labs.value.find((item) => item.id === labId) || null
  await loadDevices(labId)
}

function onDeviceChange() {
  conflictResult.value = null
}

function validateTime() {
  if (!form.value.start_time || !form.value.end_time) return '请完整选择开始与结束时间'
  const start = dayjs(form.value.start_time)
  const end = dayjs(form.value.end_time)
  if (!end.isAfter(start)) return '结束时间必须晚于开始时间'
  const hours = end.diff(start, 'minute') / 60
  if (hours > userStore.maxReserveHours) {
    return `单次预约时长不得超过 ${userStore.maxReserveHours} 小时`
  }
  return ''
}

async function checkConflict() {
  const error = validateTime()
  if (error) {
    conflictResult.value = { available: false, reason: error }
    return
  }
  checking.value = true
  try {
    const res = await reservationApi.checkConflict({
      laboratory: form.value.laboratory,
      device: form.value.device,
      start_time: form.value.start_time,
      end_time: form.value.end_time,
      exclude_id: isEdit.value ? reservationId.value : undefined
    })
    conflictResult.value = res.data
  } finally {
    checking.value = false
  }
}

async function handleSubmit(submitFlag) {
  await formRef.value.validate()
  const timeError = validateTime()
  if (timeError) {
    ElMessage.warning(timeError)
    return
  }
  if (submitFlag && !form.value.purpose.trim()) {
    ElMessage.warning('请填写用途说明后再提交')
    return
  }

  const payload = {
    laboratory: form.value.laboratory,
    device: form.value.device,
    start_time: form.value.start_time,
    end_time: form.value.end_time,
    purpose: form.value.purpose,
    urgency: form.value.urgency
  }

  if (submitFlag) {
    const check = await reservationApi.checkConflict({
      ...payload,
      exclude_id: isEdit.value ? reservationId.value : undefined
    })
    if (!check.data.available) {
      conflictResult.value = check.data
      ElMessage.error(check.data.reason || '该时段不可预约')
      return
    }
  }

  const flag = submitFlag ? submitting : saving
  flag.value = true
  try {
    if (isEdit.value) {
      await reservationApi.update(reservationId.value, payload)
      if (submitFlag) {
        await reservationApi.submit(reservationId.value)
        ElMessage.success('修改已保存并重新提交，等待管理员审批')
      } else {
        ElMessage.success('修改已保存')
      }
      router.push(`/reservations/${reservationId.value}`)
    } else {
      const res = await reservationApi.create({ ...payload, submit: submitFlag })
      ElMessage.success(res.message || '操作成功')
      router.push(submitFlag ? `/reservations/${res.data.id}` : '/reservations')
    }
  } finally {
    flag.value = false
  }
}

onMounted(async () => {
  await loadLabs()
  if (!isEdit.value) return
  loading.value = true
  try {
    const res = await reservationApi.detail(reservationId.value)
    const data = res.data
    originalStatus.value = data.status
    reservationNo.value = data.no
    form.value = {
      laboratory: data.laboratory,
      device: data.device,
      start_time: dayjs(data.start_time).format('YYYY-MM-DD HH:mm'),
      end_time: dayjs(data.end_time).format('YYYY-MM-DD HH:mm'),
      purpose: data.purpose || '',
      urgency: data.urgency || 'normal'
    }
    labInfo.value = labs.value.find((item) => item.id === data.laboratory) || null
    await loadDevices(data.laboratory)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.option-sub {
  font-size: 12px;
  color: var(--text-sub);
}
</style>
