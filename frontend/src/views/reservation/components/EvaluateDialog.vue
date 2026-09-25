<template>
  <el-dialog :model-value="modelValue" title="完工评价" width="560px"
             @update:model-value="$emit('update:modelValue', $event)" @closed="reset">
    <el-alert v-if="reservation" type="success" :closable="false" class="mb-16">
      <template #default>
        预约编号 <strong>{{ reservation.no }}</strong> ·
        设备 <strong>{{ reservation.device_name }}</strong> ·
        实验室 {{ reservation.laboratory_name }}
      </template>
    </el-alert>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="设备状态评分" prop="device_score">
        <el-rate v-model="form.device_score" show-score score-template="{value} 分" />
      </el-form-item>
      <el-form-item label="响应速度评分" prop="speed_score">
        <el-rate v-model="form.speed_score" show-score score-template="{value} 分" />
      </el-form-item>
      <el-form-item label="管理服务评分" prop="service_score">
        <el-rate v-model="form.service_score" show-score score-template="{value} 分" />
      </el-form-item>
      <el-form-item label="文字评价">
        <el-input v-model="form.content" type="textarea" :rows="4" maxlength="500" show-word-limit
                  placeholder="请描述设备状态、管理服务体验及改进建议" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">提交评价</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { reservationApi } from '@/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  reservation: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'success'])

const formRef = ref()
const loading = ref(false)
const form = ref({ device_score: 5, speed_score: 5, service_score: 5, content: '' })

const rules = {
  device_score: [{ required: true, message: '请评分', trigger: 'change' }],
  speed_score: [{ required: true, message: '请评分', trigger: 'change' }],
  service_score: [{ required: true, message: '请评分', trigger: 'change' }]
}

function reset() {
  form.value = { device_score: 5, speed_score: 5, service_score: 5, content: '' }
  formRef.value?.clearValidate()
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    await reservationApi.evaluate(props.reservation.id, form.value)
    ElMessage.success('评价提交成功，感谢您的反馈')
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
