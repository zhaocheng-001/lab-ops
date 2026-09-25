<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <div class="page-card">
          <div class="profile-head">
            <el-avatar :size="76" :src="userStore.user?.avatar || ''">
              {{ (userStore.displayName || '')[0] }}
            </el-avatar>
            <h3 class="profile-name">{{ userStore.displayName }}</h3>
            <el-tag :type="roleTagType" effect="plain">{{ userStore.user?.role_display }}</el-tag>
            <p class="text-muted" style="margin-top: 8px">账号：{{ userStore.user?.username }}</p>
          </div>

          <el-divider />

          <el-descriptions :column="1" border>
            <el-descriptions-item label="所属学院">
              {{ userStore.user?.college_name || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="班级">
              {{ userStore.user?.class_group_name || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="学号">
              {{ userStore.user?.student_no || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="单次预约上限">
              {{ userStore.maxReserveHours }} 小时
            </el-descriptions-item>
            <el-descriptions-item label="最近登录">
              {{ formatDateTime(userStore.user?.last_login) }}
            </el-descriptions-item>
            <el-descriptions-item label="最近登录 IP">
              {{ userStore.user?.last_login_ip || '—' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="managedLabs.length" label="负责实验室">
              <el-tag v-for="lab in managedLabs" :key="lab.id" size="small" style="margin: 2px 4px 2px 0">
                {{ lab.name }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>

      <el-col :xs="24" :lg="16">
        <div class="page-card mb-16">
          <div class="page-header">
            <div>
              <h3 class="page-title">基本资料</h3>
              <p class="page-subtitle">更新联系方式等信息，账号与角色需联系系统管理员调整</p>
            </div>
          </div>
          <el-form ref="profileFormRef" :model="profileForm" :rules="profileRules" label-width="90px"
                   style="max-width: 560px">
            <el-form-item label="姓名" prop="real_name">
              <el-input v-model="profileForm.real_name" placeholder="请输入真实姓名" />
            </el-form-item>
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
              <el-button @click="resetProfile">重置</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="page-card">
          <div class="page-header">
            <div>
              <h3 class="page-title">修改密码</h3>
              <p class="page-subtitle">修改成功后需使用新密码重新登录</p>
            </div>
          </div>
          <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="110px"
                   style="max-width: 560px">
            <el-form-item label="原密码" prop="old_password">
              <el-input v-model="pwdForm.old_password" show-password placeholder="请输入原密码" />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="pwdForm.new_password" show-password placeholder="至少 6 位" />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input v-model="pwdForm.confirm_password" show-password placeholder="请再次输入新密码" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingPwd" @click="changePassword">修改密码</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/dict'

const router = useRouter()
const userStore = useUserStore()

const savingProfile = ref(false)
const savingPwd = ref(false)
const profileFormRef = ref()
const pwdFormRef = ref()

const profileForm = ref({ real_name: '', phone: '', email: '' })
const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })

const roleTagType = computed(() => {
  const role = userStore.role
  if (role === 'sys_admin') return 'danger'
  if (role === 'lab_admin') return 'warning'
  if (role === 'teacher') return 'success'
  return 'primary'
})

const managedLabs = computed(() => userStore.user?.managed_labs || [])

const profileRules = {
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }]
}

const pwdRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少 6 位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== pwdForm.value.new_password) callback(new Error('两次输入的新密码不一致'))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

function resetProfile() {
  profileForm.value = {
    real_name: userStore.user?.real_name || '',
    phone: userStore.user?.phone || '',
    email: userStore.user?.email || ''
  }
}

async function saveProfile() {
  await profileFormRef.value.validate()
  savingProfile.value = true
  try {
    await authApi.updateProfile(profileForm.value)
    await userStore.fetchProfile()
    ElMessage.success('资料已更新')
  } finally {
    savingProfile.value = false
  }
}

async function changePassword() {
  await pwdFormRef.value.validate()
  savingPwd.value = true
  try {
    await authApi.changePassword(pwdForm.value)
    ElMessage.success('密码修改成功，请使用新密码重新登录')
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
    setTimeout(() => {
      userStore.logout()
      router.push('/login')
    }, 800)
  } finally {
    savingPwd.value = false
  }
}

onMounted(async () => {
  await userStore.fetchProfile()
  resetProfile()
})
</script>

<style scoped>
.profile-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 8px;
}

.profile-name {
  margin: 12px 0 8px;
  font-size: 18px;
  font-weight: 700;
}
</style>
