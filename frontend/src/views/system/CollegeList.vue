<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <div class="page-card">
          <div class="page-header">
            <div>
              <h3 class="page-title">学院管理</h3>
              <p class="page-subtitle">维护学院基础信息，学院下存在班级或用户时需先处理关联数据</p>
            </div>
            <el-button v-if="userStore.isSysAdmin" type="primary" :icon="Plus" @click="openCollege()">
              新增学院
            </el-button>
          </div>

          <el-table :data="colleges" v-loading="collegeLoading" border stripe
                    highlight-current-row @current-change="onSelectCollege">
            <el-table-column prop="name" label="学院名称" min-width="160" />
            <el-table-column prop="code" label="学院编码" width="120">
              <template #default="{ row }">{{ row.code || '—' }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.remark || '—' }}</template>
            </el-table-column>
            <el-table-column v-if="userStore.isSysAdmin" label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openCollege(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click.stop="removeCollege(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <div class="empty-tip">暂无学院数据</div>
            </template>
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="12">
        <div class="page-card">
          <div class="page-header">
            <div>
              <h3 class="page-title">
                班级管理
                <span v-if="currentCollege" class="text-muted" style="font-size: 13px">
                  · {{ currentCollege.name }}
                </span>
              </h3>
              <p class="page-subtitle">点击左侧学院筛选其下班级</p>
            </div>
            <el-button v-if="userStore.isSysAdmin" type="primary" :icon="Plus" @click="openClass()">
              新增班级
            </el-button>
          </div>

          <el-table :data="classes" v-loading="classLoading" border stripe>
            <el-table-column prop="name" label="班级名称" min-width="140" />
            <el-table-column prop="college_name" label="所属学院" min-width="140" show-overflow-tooltip />
            <el-table-column prop="grade" label="年级" width="100">
              <template #default="{ row }">{{ row.grade || '—' }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.remark || '—' }}</template>
            </el-table-column>
            <el-table-column v-if="userStore.isSysAdmin" label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openClass(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="removeClass(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <div class="empty-tip">请选择左侧学院查看班级</div>
            </template>
          </el-table>

          <el-pagination class="mt-16" v-model:current-page="classQuery.page"
                         v-model:page-size="classQuery.page_size" :page-sizes="[10, 20, 50]"
                         :total="classTotal" layout="total, prev, pager, next"
                         @size-change="loadClasses" @current-change="loadClasses" />
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="collegeVisible" :title="collegeForm.id ? '编辑学院' : '新增学院'" width="480px">
      <el-form ref="collegeFormRef" :model="collegeForm" :rules="collegeRules" label-width="90px">
        <el-form-item label="学院名称" prop="name">
          <el-input v-model="collegeForm.name" placeholder="如：计算机科学与技术学院" />
        </el-form-item>
        <el-form-item label="学院编码">
          <el-input v-model="collegeForm.code" placeholder="选填，如：CS" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="collegeForm.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="collegeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCollege">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="classVisible" :title="classForm.id ? '编辑班级' : '新增班级'" width="480px">
      <el-form ref="classFormRef" :model="classForm" :rules="classRules" label-width="90px">
        <el-form-item label="班级名称" prop="name">
          <el-input v-model="classForm.name" placeholder="如：计算机 2201 班" />
        </el-form-item>
        <el-form-item label="所属学院" prop="college">
          <el-select v-model="classForm.college" filterable style="width: 100%">
            <el-option v-for="item in colleges" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-input v-model="classForm.grade" placeholder="选填，如：2022" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="classForm.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="classVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitClass">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { classApi, collegeApi } from '@/api'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const collegeLoading = ref(false)
const classLoading = ref(false)
const saving = ref(false)
const colleges = ref([])
const classes = ref([])
const classTotal = ref(0)
const currentCollege = ref(null)

const collegeVisible = ref(false)
const classVisible = ref(false)
const collegeFormRef = ref()
const classFormRef = ref()

const collegeForm = ref({ id: null, name: '', code: '', remark: '' })
const classForm = ref({ id: null, name: '', college: '', grade: '', remark: '' })

const classQuery = reactive({ page: 1, page_size: 10 })

const collegeRules = {
  name: [{ required: true, message: '请输入学院名称', trigger: 'blur' }]
}

const classRules = {
  name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }],
  college: [{ required: true, message: '请选择所属学院', trigger: 'change' }]
}

async function loadColleges() {
  collegeLoading.value = true
  try {
    const res = await collegeApi.list()
    colleges.value = res.data.results
  } finally {
    collegeLoading.value = false
  }
}

async function loadClasses() {
  classLoading.value = true
  try {
    const params = { page: classQuery.page, page_size: classQuery.page_size }
    if (currentCollege.value) params.college_id = currentCollege.value.id
    const res = await classApi.list(params)
    classes.value = res.data.results
    classTotal.value = res.data.count
  } finally {
    classLoading.value = false
  }
}

function onSelectCollege(row) {
  if (!row) return
  currentCollege.value = row
  classQuery.page = 1
  loadClasses()
}

function openCollege(row) {
  collegeForm.value = row
    ? { id: row.id, name: row.name, code: row.code || '', remark: row.remark || '' }
    : { id: null, name: '', code: '', remark: '' }
  collegeVisible.value = true
}

async function submitCollege() {
  await collegeFormRef.value.validate()
  saving.value = true
  try {
    const payload = {
      name: collegeForm.value.name,
      code: collegeForm.value.code,
      remark: collegeForm.value.remark
    }
    if (collegeForm.value.id) {
      await collegeApi.update(collegeForm.value.id, payload)
      ElMessage.success('学院已更新')
    } else {
      await collegeApi.create(payload)
      ElMessage.success('学院创建成功')
    }
    collegeVisible.value = false
    loadColleges()
  } finally {
    saving.value = false
  }
}

async function removeCollege(row) {
  await ElMessageBox.confirm(`确认删除学院「${row.name}」吗？`, '删除确认', { type: 'warning' })
  await collegeApi.remove(row.id)
  ElMessage.success('学院已删除')
  if (currentCollege.value?.id === row.id) {
    currentCollege.value = null
    classes.value = []
    classTotal.value = 0
  }
  loadColleges()
}

function openClass(row) {
  classForm.value = row
    ? {
        id: row.id,
        name: row.name,
        college: row.college,
        grade: row.grade || '',
        remark: row.remark || ''
      }
    : {
        id: null,
        name: '',
        college: currentCollege.value?.id || '',
        grade: '',
        remark: ''
      }
  classVisible.value = true
}

async function submitClass() {
  await classFormRef.value.validate()
  saving.value = true
  try {
    const payload = {
      name: classForm.value.name,
      college: classForm.value.college,
      grade: classForm.value.grade,
      remark: classForm.value.remark
    }
    if (classForm.value.id) {
      await classApi.update(classForm.value.id, payload)
      ElMessage.success('班级已更新')
    } else {
      await classApi.create(payload)
      ElMessage.success('班级创建成功')
    }
    classVisible.value = false
    loadClasses()
  } finally {
    saving.value = false
  }
}

async function removeClass(row) {
  await ElMessageBox.confirm(`确认删除班级「${row.name}」吗？`, '删除确认', { type: 'warning' })
  await classApi.remove(row.id)
  ElMessage.success('班级已删除')
  loadClasses()
}

onMounted(async () => {
  await loadColleges()
  if (colleges.value.length) {
    currentCollege.value = colleges.value[0]
    await loadClasses()
  }
})
</script>
