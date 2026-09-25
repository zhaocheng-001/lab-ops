<template>
  <div class="page-container">
    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">设备分类</h3>
          <p class="page-subtitle">用于设备归集与统计维度划分，分类下的设备数量为启用设备数量</p>
        </div>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增分类</el-button>
      </div>

      <div class="toolbar">
        <el-input v-model="keyword" placeholder="分类名称 / 编码" clearable style="width: 220px" />
      </div>

      <el-table :data="filteredList" v-loading="loading" border stripe>
        <el-table-column prop="name" label="分类名称" min-width="160" />
        <el-table-column prop="code" label="分类编码" width="160">
          <template #default="{ row }">{{ row.code || '—' }}</template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="设备数量" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.device_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="排序" width="90" align="center">
          <template #default="{ row }">{{ row.sort_order }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="doRemove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无设备分类</div>
        </template>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑分类' : '新增分类'" width="520px"
               @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" placeholder="如：电子测量仪器" />
        </el-form-item>
        <el-form-item label="分类编码">
          <el-input v-model="form.code" placeholder="选填，如：CAT-01" />
        </el-form-item>
        <el-form-item label="排序值">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { categoryApi } from '@/api'
import { formatDateTime } from '@/utils/dict'

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const keyword = ref('')
const dialogVisible = ref(false)
const formRef = ref()

const form = ref(emptyForm())

function emptyForm() {
  return { id: null, name: '', code: '', sort_order: 0, description: '' }
}

const rules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }]
}

const filteredList = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  if (!key) return list.value
  return list.value.filter(
    (item) =>
      item.name.toLowerCase().includes(key) || (item.code || '').toLowerCase().includes(key)
  )
})

async function load() {
  loading.value = true
  try {
    const res = await categoryApi.list()
    list.value = res.data.results
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.value = emptyForm()
  formRef.value?.clearValidate()
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  resetForm()
  form.value = {
    id: row.id,
    name: row.name,
    code: row.code || '',
    sort_order: row.sort_order,
    description: row.description || ''
  }
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      code: form.value.code,
      sort_order: form.value.sort_order,
      description: form.value.description
    }
    if (form.value.id) {
      await categoryApi.update(form.value.id, payload)
      ElMessage.success('分类已更新')
    } else {
      await categoryApi.create(payload)
      ElMessage.success('分类创建成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function doRemove(row) {
  await ElMessageBox.confirm(`确认删除分类「${row.name}」吗？`, '删除确认', { type: 'warning' })
  await categoryApi.remove(row.id)
  ElMessage.success('分类已删除')
  load()
}

onMounted(load)
</script>
