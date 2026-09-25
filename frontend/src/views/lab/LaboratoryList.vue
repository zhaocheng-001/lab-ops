<template>
  <div class="page-container">
    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">实验室管理</h3>
          <p class="page-subtitle">维护实验室基础信息、开放时间与负责管理员，实验室下存在设备时不可删除</p>
        </div>
        <div v-if="canManage" class="header-actions">
          <el-button :icon="Download" @click="doExport">导出清单</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增实验室</el-button>
        </div>
      </div>

      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="名称 / 编号 / 位置" clearable style="width: 220px"
                  @keyup.enter="load" @clear="load" />
        <el-select v-model="query.is_active" placeholder="状态" clearable style="width: 140px" @change="load">
          <el-option label="启用" :value="1" />
          <el-option label="停用" :value="0" />
        </el-select>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="reset">重置</el-button>
          <el-button :icon="Search" type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="code" label="实验室编号" width="130" />
        <el-table-column prop="name" label="实验室名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="location" label="位置" width="150" show-overflow-tooltip />
        <el-table-column label="容纳人数" width="90" align="center">
          <template #default="{ row }">{{ row.capacity }}</template>
        </el-table-column>
        <el-table-column label="开放时间" width="140">
          <template #default="{ row }">
            {{ (row.open_time_start || '').slice(0, 5) }} - {{ (row.open_time_end || '').slice(0, 5) }}
          </template>
        </el-table-column>
        <el-table-column label="开放日" width="190" show-overflow-tooltip>
          <template #default="{ row }">{{ row.open_weekday_display || '—' }}</template>
        </el-table-column>
        <el-table-column label="负责人" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ (row.manager_names || []).join('、') || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="设备数" width="120" align="center">
          <template #default="{ row }">
            <span class="text-success">{{ row.available_device_count }}</span> / {{ row.device_count }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small"
                       @click="$router.push({ path: '/devices', query: { laboratory: row.id } })">
              设备
            </el-button>
            <template v-if="canManage">
              <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="doRemove(row)">删除</el-button>
            </template>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无实验室数据</div>
        </template>
      </el-table>

      <el-pagination class="mt-16" v-model:current-page="query.page" v-model:page-size="query.page_size"
                     :page-sizes="[10, 20, 50]" :total="total"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="load" @current-change="load" />
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑实验室' : '新增实验室'" width="720px"
               @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="实验室名称" prop="name">
              <el-input v-model="form.name" placeholder="如：电子信息实验室" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实验室编号" prop="code">
              <el-input v-model="form.code" placeholder="如：LAB-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="位置" prop="location">
              <el-input v-model="form.location" placeholder="如：实验楼 A302" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="容纳人数" prop="capacity">
              <el-input-number v-model="form.capacity" :min="1" :max="500" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开放开始" prop="open_time_start">
              <el-time-picker v-model="form.open_time_start" format="HH:mm" value-format="HH:mm"
                              placeholder="开放开始时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开放结束" prop="open_time_end">
              <el-time-picker v-model="form.open_time_end" format="HH:mm" value-format="HH:mm"
                              placeholder="开放结束时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="开放日" prop="open_weekdays">
              <el-checkbox-group v-model="form.open_weekdays">
                <el-checkbox v-for="item in WEEKDAY_OPTIONS" :key="item.value" :value="item.value">
                  {{ item.label }}
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="负责管理员">
              <el-select v-model="form.manager_ids" multiple filterable placeholder="选择实验室管理员"
                         style="width: 100%">
                <el-option v-for="item in managers" :key="item.id" :value="item.id"
                           :label="`${item.real_name}（${item.username}）`" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="实验室简介">
              <el-input v-model="form.description" type="textarea" :rows="2" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实验室图片">
              <el-upload :auto-upload="false" :show-file-list="false" accept="image/*"
                         :on-change="onPickImage">
                <el-button size="small" :icon="Picture">选择图片</el-button>
              </el-upload>
              <span v-if="form.image_name" class="text-muted" style="margin-left: 8px">
                {{ form.image_name }}
              </span>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Picture, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { labApi, userApi } from '@/api'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const canManage = computed(() => userStore.isAdminRole)

const WEEKDAY_OPTIONS = [
  { value: '1', label: '周一' },
  { value: '2', label: '周二' },
  { value: '3', label: '周三' },
  { value: '4', label: '周四' },
  { value: '5', label: '周五' },
  { value: '6', label: '周六' },
  { value: '7', label: '周日' }
]

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const total = ref(0)
const managers = ref([])
const dialogVisible = ref(false)
const formRef = ref()

const query = reactive({ page: 1, page_size: 10, keyword: '', is_active: '', ordering: 'id' })

const form = ref(emptyForm())

function emptyForm() {
  return {
    id: null,
    name: '',
    code: '',
    location: '',
    capacity: 30,
    open_time_start: '08:00',
    open_time_end: '22:00',
    open_weekdays: ['1', '2', '3', '4', '5'],
    manager_ids: [],
    description: '',
    is_active: true,
    image: null,
    image_name: ''
  }
}

const rules = {
  name: [{ required: true, message: '请输入实验室名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入实验室编号', trigger: 'blur' }],
  location: [{ required: true, message: '请输入位置', trigger: 'blur' }],
  open_time_start: [{ required: true, message: '请选择开放开始时间', trigger: 'change' }],
  open_time_end: [{ required: true, message: '请选择开放结束时间', trigger: 'change' }],
  open_weekdays: [
    { required: true, type: 'array', min: 1, message: '请至少选择一个开放日', trigger: 'change' }
  ]
}

function buildParams() {
  const params = { page: query.page, page_size: query.page_size, ordering: query.ordering }
  if (query.keyword) params.keyword = query.keyword
  if (query.is_active !== '') params.is_active = query.is_active
  return params
}

async function load() {
  loading.value = true
  try {
    const res = await labApi.list(buildParams())
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

function reset() {
  query.keyword = ''
  query.is_active = ''
  query.page = 1
  load()
}

function resetForm() {
  form.value = emptyForm()
  formRef.value?.clearValidate()
}

async function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  resetForm()
  form.value = {
    id: row.id,
    name: row.name,
    code: row.code,
    location: row.location,
    capacity: row.capacity,
    open_time_start: (row.open_time_start || '08:00:00').slice(0, 5),
    open_time_end: (row.open_time_end || '22:00:00').slice(0, 5),
    open_weekdays: (row.open_weekdays || '').split(',').filter(Boolean),
    manager_ids: (row.manager_list || []).map((item) => item.id),
    description: row.description || '',
    is_active: row.is_active,
    image: null,
    image_name: row.image ? '已上传图片（重新选择将覆盖）' : ''
  }
  dialogVisible.value = true
}

function onPickImage(uploadFile) {
  form.value.image = uploadFile.raw
  form.value.image_name = uploadFile.name
}

function buildFormData() {
  const data = new FormData()
  data.append('name', form.value.name)
  data.append('code', form.value.code)
  data.append('location', form.value.location)
  data.append('capacity', form.value.capacity)
  data.append('open_time_start', form.value.open_time_start)
  data.append('open_time_end', form.value.open_time_end)
  data.append('open_weekdays', form.value.open_weekdays.join(','))
  data.append('is_active', form.value.is_active ? 'true' : 'false')
  data.append('description', form.value.description || '')
  form.value.manager_ids.forEach((id) => data.append('manager_ids', id))
  if (form.value.image) data.append('image', form.value.image)
  return data
}

async function submit() {
  await formRef.value.validate()
  if (form.value.open_time_start >= form.value.open_time_end) {
    ElMessage.warning('开放结束时间必须晚于开始时间')
    return
  }
  saving.value = true
  try {
    const data = buildFormData()
    if (form.value.id) {
      await labApi.update(form.value.id, data)
      ElMessage.success('实验室信息已更新')
    } else {
      await labApi.create(data)
      ElMessage.success('实验室创建成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function doRemove(row) {
  await ElMessageBox.confirm(`确认删除实验室「${row.name}」吗？`, '删除确认', { type: 'warning' })
  await labApi.remove(row.id)
  ElMessage.success('实验室已删除')
  load()
}

async function doExport() {
  await labApi.export(buildParams())
  ElMessage.success('导出任务已开始')
}

onMounted(async () => {
  // 负责人下拉仅管理员维护实验室时需要，普通用户不请求，避免无权限报错
  if (canManage.value) {
    const res = await userApi.simple({ role: 'lab_admin' })
    managers.value = res.data
  }
  load()
})
</script>

<style scoped>
.header-actions {
  display: flex;
  gap: 10px;
}
</style>
