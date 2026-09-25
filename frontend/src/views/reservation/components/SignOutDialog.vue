<template>
  <el-dialog :model-value="modelValue" title="签退并登记设备状态" width="520px"
             @update:model-value="$emit('update:modelValue', $event)" @closed="reset">
    <el-alert v-if="reservation" type="info" :closable="false" class="mb-16">
      <template #default>
        预约编号 <strong>{{ reservation.no }}</strong> ·
        设备 <strong>{{ reservation.device_name }}</strong> ·
        计划归还 {{ formatDateTime(reservation.end_time) }}
      </template>
    </el-alert>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
      <el-form-item label="设备状态" prop="device_status_after">
        <el-radio-group v-model="form.device_status_after">
          <el-radio value="available">可预约（正常）</el-radio>
          <el-radio value="repairing">维修中（需检修）</el-radio>
          <el-radio value="scrapped">已报废</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="异常情况说明" prop="abnormal_note">
        <el-input v-model="form.abnormal_note" type="textarea" :rows="3"
                  placeholder="如无异常可留空；如有损坏、读数异常等请详细说明" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">确认签退</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { reservationApi } from '@/api'
import { formatDateTime } from '@/utils/dict'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  reservation: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'success'])

const formRef = ref()
const loading = ref(false)
const form = ref({ device_status_after: 'available', abnormal_note: '' })

const rules = {
  device_status_after: [{ required: true, message: '请选择设备状态', trigger: 'change' }]
}

function reset() {
  form.value = { device_status_after: 'available', abnormal_note: '' }
  formRef.value?.clearValidate()
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    await reservationApi.signOut(props.reservation.id, form.value)
    ElMessage.success('签退成功，等待管理员核验完工')
    emit('update:modelValue', false)
    emit('success')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (value) => {
    if (value) reset()
  }
)
</script>
