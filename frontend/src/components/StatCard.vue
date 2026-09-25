<template>
  <div class="stat-card" :class="{ clickable: clickable }" @click="$emit('click')">
    <div class="stat-icon" :style="{ background: color }">
      <el-icon><component :is="icon" /></el-icon>
    </div>
    <div>
      <div class="stat-value" :style="{ color: valueColor || '#1f2a37' }">
        {{ value }}<small v-if="unit" class="unit">{{ unit }}</small>
      </div>
      <div class="stat-label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: 'DataLine' },
  color: { type: String, default: '#2f6fed' },
  value: { type: [String, Number], default: 0 },
  unit: { type: String, default: '' },
  label: { type: String, default: '' },
  valueColor: { type: String, default: '' },
  clickable: { type: Boolean, default: false }
})

defineEmits(['click'])
</script>

<style scoped>
.clickable {
  cursor: pointer;
}

.unit {
  font-size: 12px;
  font-weight: 400;
  margin-left: 4px;
  color: #8a93a5;
}
</style>
