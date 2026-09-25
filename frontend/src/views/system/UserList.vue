<template>
  <div class="page-container">
    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">{{ userStore.isSysAdmin ? '用户管理' : '师生信息查询' }}</h3>
          <p class="page-subtitle">
            {{ userStore.isSysAdmin
              ? '维护系统内的学生、教师与管理员账号，可重置密码、启用停用'
              : '实验室管理员可查询学生与教师信息，用于预约审批参考' }}
          </p>
        </div>
        <el-button v-if="userStore.isSysAdmin" type="primary" :icon="Plus" @click="openCreate">
          新增用户
        </el-button>
      </div>

      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="账号 / 姓名 / 学号 / 手机号" clearable
                  style="width: 220px" @keyup.enter="load" @clear="load" />
        <el-select v-model="query.role" placeholder="角色" clearable style="width: 150px" @change="load">
          <el-option v-for="item in roleFilterOptions" :key="item.value" :label="item.label"
                     :value="item.value" />
        </el-select>
        <el-select v-model="query.college" placeholder="学院" clearable filterable style="width: 170px"
                   @change="load">
          <el-option v-for="item in colleges" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-select v-model="query.is_active" placeholder="账号状态" clearable style="width: 130px"
                   @change="load">
          <el-option label="启用" :value="1" />
          <el-option label="停用" :value="0" />
        </el-select>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="reset">重置</el-button>
          <el-button :icon="Search" type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="username" label="账号" width="130" show-overflow-tooltip />
        <el-table-column prop="real_name" label="姓名" width="110" />
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">{{ row.role_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="college_name" label="学院" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.college_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="class_group_name" label="班级" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.class_group_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="student_no" label="学号" width="130">
          <template #default="{ row }">{{ row.student_no || '—' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="130">
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column label="负责实验室" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ (row.managed_labs || []).map((item) => item.name).join('、') || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="160">
          <template #default="{ row }">{{ formatDateTime(row.last_login) }}</template>
        </el-table-column>
        <el-table-column v-if="userStore.isSysAdmin" label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="warning" size="small" @click="openReset(row)">重置密码</el-button>
            <el-button link :type="row.is_active ? 'danger' : 'success'" size="small"
                       :disabled="row.id === userStore.user?.id" @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无用户数据</div>
        </template>
      </el-table>

      <el-pagination class="mt-16" v-model:current-page="query.page" v-model:page-size="query.page_size"
                     :page-sizes="[10, 20, 50]" :total="total"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="load" @current-change="load" />
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑用户' : '新增用户'" width="700px"
               @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="登录账号" prop="username">
              <el-input v-model="form.username" :disabled="!!form.id" placeholder="登录用户名" />
            </el-form-item>
          </el-col>
          <el-col v-if="!form.id" :span="12">
            <el-form-item label="初始密码">
              <el-input v-model="form.password" show-password placeholder="留空默认 123456" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="real_name">
              <el-input v-model="form.real_name" placeholder="真实姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色" prop="role">
              <el-select v-model="form.role" style="width: 100%" @change="onRoleChange">
                <el-option v-for="item in ROLE_OPTIONS" :key="item.value" :label="item.label"
                           :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属学院" :prop="form.role === 'student' ? 'college' : ''">
              <el-select v-model="form.college" clearable filterable style="width: 100%"
                         @change="onCollegeChange">
                <el-option v-for="item in colleges" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="班级">
              <el-select v-model="form.class_group" clearable filterable style="width: 100%">
                <el-option v-for="item in classOptions" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.role === 'student'" :span="12">
            <el-form-item label="学号" prop="student_no">
              <el-input v-model="form.student_no" placeholder="学号" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.role === 'lab_admin'" :span="24">
            <el-form-item label="负责实验室" prop="lab_ids">
              <el-select v-model="form.lab_ids" multiple filterable style="width: 100%"
                         placeholder="请选择该管理员负责的实验室">
                <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="账号状态">
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="选填" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="440px">
      <el-alert v-if="currentRow" type="warning" :closable="false" class="mb-16">
        将重置账号「{{ currentRow.real_name }}（{{ currentRow.username }}）」的密码
      </el-alert>
      <el-input v-model="newPassword" show-password placeholder="请输入新密码（至少 6 位）" />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { classApi, collegeApi, labApi, userApi } from '@/api'
import { ROLE_OPTIONS, useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/dict'

const userStore = useUserStore()

const roleFilterOptions = ROLE_OPTIONS

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const total = ref(0)
const colleges = ref([])
const labs = ref([])
const classOptions = ref([])
const dialogVisible = ref(false)
const resetVisible = ref(false)
const formRef = ref()
const currentRow = ref(null)
const newPassword = ref('')

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  role: '',
  college: '',
  is_active: '',
  ordering: '-id'
})

const form = ref(emptyForm())

function emptyForm() {
  return {
    id: null,
    username: '',
    password: '',
    real_name: '',
    role: 'student',
    phone: '',
    email: '',
    college: '',
    class_group: '',
    student_no: '',
    is_active: true,
    remark: '',
    lab_ids: []
  }
}

const rules = {
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  student_no: [{ required: true, message: '学生必须填写学号', trigger: 'blur' }],
  college: [{ required: true, message: '学生必须选择所属学院', trigger: 'change' }],
  lab_ids: [
    {
      validator: (rule, value, callback) => {
        if (form.value.role === 'lab_admin' && (!value || !value.length)) {
          callback(new Error('实验室管理员必须至少负责一个实验室'))
        } else {
          callback()
        }
      },
      trigger: 'change'
    }
  ]
}

function roleTagType(role) {
  if (role === 'sys_admin') return 'danger'
  if (role === 'lab_admin') return 'warning'
  if (role === 'teacher') return 'success'
  return 'primary'
}

function buildParams() {
  const params = { page: query.page, page_size: query.page_size, ordering: query.ordering }
  if (query.keyword) params.keyword = query.keyword
  if (query.role) params.role = query.role
  if (query.college) params.college = query.college
  if (query.is_active !== '') params.is_active = query.is_active
  return params
}

async function load() {
  loading.value = true
  try {
    const res = await userApi.list(buildParams())
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

async function loadClasses(collegeId) {
  if (!collegeId) {
    classOptions.value = []
    return
  }
  const res = await classApi.list({ college_id: collegeId, page_size: 200 })
  classOptions.value = res.data.results
}

function reset() {
  query.keyword = ''
  query.role = ''
  query.college = ''
  query.is_active = ''
  query.page = 1
  load()
}

function resetForm() {
  form.value = emptyForm()
  formRef.value?.clearValidate()
}

function onRoleChange() {
  if (form.value.role !== 'lab_admin') form.value.lab_ids = []
  if (form.value.role !== 'student') form.value.student_no = ''
}

function onCollegeChange(collegeId) {
  form.value.class_group = ''
  loadClasses(collegeId)
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

async function openEdit(row) {
  resetForm()
  form.value = {
    id: row.id,
    username: row.username,
    password: '',
    real_name: row.real_name,
    role: row.role,
    phone: row.phone || '',
    email: row.email || '',
    college: row.college || '',
    class_group: row.class_group || '',
    student_no: row.student_no || '',
    is_active: row.is_active,
    remark: row.remark || '',
    lab_ids: (row.managed_labs || []).map((item) => item.id)
  }
  if (row.college) await loadClasses(row.college)
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      real_name: form.value.real_name,
      role: form.value.role,
      phone: form.value.phone,
      college: form.value.college || null,
      class_group: form.value.class_group || null,
      student_no: form.value.student_no,
      email: form.value.email,
      is_active: form.value.is_active,
      remark: form.value.remark,
      lab_ids: form.value.lab_ids
    }
    if (form.value.id) {
      await userApi.update(form.value.id, payload)
      ElMessage.success('用户信息已更新')
    } else {
      await userApi.create({
        ...payload,
        username: form.value.username,
        password: form.value.password || undefined
      })
      ElMessage.success('用户创建成功，默认密码 123456')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openReset(row) {
  currentRow.value = row
  newPassword.value = ''
  resetVisible.value = true
}

async function doReset() {
  if (!newPassword.value || newPassword.value.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  saving.value = true
  try {
    await userApi.resetPassword(currentRow.value.id, { new_password: newPassword.value })
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  const action = row.is_active ? '停用' : '启用'
  await ElMessageBox.confirm(`确认${action}账号「${row.username}」吗？`, `${action}确认`, {
    type: 'warning'
  })
  await userApi.toggleActive(row.id)
  ElMessage.success(`账号已${action}`)
  load()
}

onMounted(async () => {
  const [collegeRes, labRes] = await Promise.all([collegeApi.list(), labApi.simple()])
  colleges.value = collegeRes.data.results
  labs.value = labRes.data
  load()
})
</script>
