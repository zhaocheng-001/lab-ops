<template>
  <div class="login-page">
    <div class="login-bg">
      <span class="blob blob-1"></span>
      <span class="blob blob-2"></span>
      <span class="blob blob-3"></span>
    </div>

    <div class="login-content">
      <div class="intro">
        <div class="greeting">
          <el-icon class="greeting-icon"><component :is="greetIcon" /></el-icon>
          <span>{{ greeting }}，很高兴见到你</span>
        </div>

        <h1>高校实验室设备<br />预约运维系统</h1>
        <p class="intro-desc">
          预约设备、提交审批、报修故障、查看统计——实验室里的大小事，在这里一次办妥。
        </p>

        <div class="today-card">
          <div class="today-item">
            <el-icon><Calendar /></el-icon>
            <div class="today-text">
              <strong>{{ dateText }}</strong>
              <span>{{ weekText }}</span>
            </div>
          </div>
          <span class="today-split"></span>
          <div class="today-item">
            <el-icon><Clock /></el-icon>
            <div class="today-text">
              <strong>{{ timeText }}</strong>
              <span>{{ dayPart }}</span>
            </div>
          </div>
        </div>

        <ul class="feature-list">
          <li v-for="item in features" :key="item.title">
            <el-icon><component :is="item.icon" /></el-icon>
            <div>
              <strong>{{ item.title }}</strong>
              <span>{{ item.desc }}</span>
            </div>
          </li>
        </ul>
      </div>

      <div class="login-card">
        <h2>账号登录</h2>
        <p class="card-sub">使用学校统一分配的账号，随时查看你的预约与工单</p>

        <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="submit">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="请输入登录账号" clearable
                      autocomplete="username">
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password
                      autocomplete="current-password" @keyup="checkCapsLock" @keydown="checkCapsLock">
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
            <transition name="fade">
              <p v-if="capsOn" class="caps-tip">
                <el-icon><WarningFilled /></el-icon>大写锁定已开启，请注意密码大小写
              </p>
            </transition>
          </el-form-item>

          <div class="form-extra">
            <el-checkbox v-model="remember">记住账号</el-checkbox>
            <span class="extra-link" @click="onForget">忘记密码？</span>
          </div>

          <el-form-item class="submit-item">
            <el-button type="primary" class="login-btn" :loading="loading" @click="submit">
              {{ loading ? '正在进入系统…' : '登录系统' }}
            </el-button>
          </el-form-item>
        </el-form>

        <el-divider class="demo-divider">
          <span class="demo-divider-text">演示账号</span>
        </el-divider>

        <div class="demo-accounts">
          <el-tooltip v-for="item in demoAccounts" :key="item.username" placement="top"
                      :content="`点击填充「${item.role}」演示账号`">
            <div class="demo-item" @click="fillAccount(item)">
              <span class="demo-tag" :style="{ background: item.color }">{{ item.short }}</span>
              <span class="demo-name">{{ item.username }}</span>
              <span class="demo-desc">{{ item.role }}</span>
            </div>
          </el-tooltip>
        </div>
        <p class="demo-hint">初始密码请查看项目根目录 <code>README.md</code></p>

        <p class="card-foot">
          <el-icon><Service /></el-icon>
          登录遇到问题？请联系实验室管理员协助处理
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const REMEMBER_KEY = 'lab_remember_username'

const formRef = ref()
const loading = ref(false)
const remember = ref(false)
const capsOn = ref(false)
const form = ref({ username: '', password: '' })
const now = ref(new Date())

const rules = {
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const HOUR_GREETINGS = [
  { max: 5, text: '夜深了', icon: 'MoonNight', part: '早点休息，注意身体' },
  { max: 9, text: '早上好', icon: 'Sunrise', part: '新的一天开始啦' },
  { max: 12, text: '上午好', icon: 'Sunny', part: '上午的实验顺利吗' },
  { max: 14, text: '中午好', icon: 'Sunny', part: '记得按时吃午饭' },
  { max: 18, text: '下午好', icon: 'Cloudy', part: '下午继续加油' },
  { max: 24, text: '晚上好', icon: 'Moon', part: '忙完记得早点回去' }
]

const greetInfo = computed(() => {
  const hour = now.value.getHours()
  return HOUR_GREETINGS.find((item) => hour < item.max) || HOUR_GREETINGS[1]
})
const greeting = computed(() => greetInfo.value.text)
const greetIcon = computed(() => greetInfo.value.icon)
const dayPart = computed(() => greetInfo.value.part)

const WEEK_TEXT = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const dateText = computed(
  () => `${now.value.getFullYear()} 年 ${now.value.getMonth() + 1} 月 ${now.value.getDate()} 日`
)
const weekText = computed(() => WEEK_TEXT[now.value.getDay()])
const timeText = computed(() => {
  const pad = (value) => String(value).padStart(2, '0')
  const date = now.value
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
})

const features = [
  { icon: 'Calendar', title: '在线预约', desc: '挑好时间就能约，时段冲突自动帮你避开' },
  { icon: 'CircleCheck', title: '审批流转', desc: '提交后实时看到进度，谁在处理一目了然' },
  { icon: 'WarningFilled', title: '故障报修', desc: '设备出问题一键报修，自动派单到管理员' },
  { icon: 'DataAnalysis', title: '运维统计', desc: '使用率、故障率、维修时效，图表一眼看懂' }
]

const demoAccounts = [
  { username: 'admin',     short: '管', role: '系统管理员',   color: '#8b5cf6' },
  { username: 'labadmin1', short: '室', role: '实验室管理员', color: '#f5a524' },
  { username: 'teacher1',  short: '教', role: '教师',         color: '#17a673' },
  { username: 'student1',  short: '学', role: '学生',         color: '#2f6fed' }
]

function fillAccount(item) {
  form.value.username = item.username
  form.value.password = ''
  capsOn.value = false
  formRef.value?.clearValidate()
  ElMessage.info(`已填入「${item.role}」账号，请输入密码后登录`)
}

function checkCapsLock(event) {
  if (typeof event.getModifierState === 'function') {
    capsOn.value = event.getModifierState('CapsLock')
  }
}

function onForget() {
  ElMessageBox.alert(
    '账号由学校统一分配，忘记密码请携带校园卡前往实验室管理办公室重置，或联系实验室管理员协助。',
    '忘记密码',
    { type: 'info', confirmButtonText: '我知道了' }
  ).catch(() => {})
}

async function submit() {
  try {
    await formRef.value.validate()
  } catch (error) {
    return
  }
  loading.value = true
  try {
    const user = await userStore.login(form.value)
    if (remember.value) {
      localStorage.setItem(REMEMBER_KEY, form.value.username)
    } else {
      localStorage.removeItem(REMEMBER_KEY)
    }
    ElMessage.success(`${greeting.value}，${user.real_name || user.username}，欢迎回来`)
    const redirect = route.query.redirect
    router.replace(redirect ? String(redirect) : '/dashboard')
  } catch (error) {
    form.value.password = ''
  } finally {
    loading.value = false
  }
}

let timer = null

onMounted(() => {
  const saved = localStorage.getItem(REMEMBER_KEY)
  if (saved) {
    form.value.username = saved
    remember.value = true
  }
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.login-page {
  position: relative;
  min-height: 100vh;
  background: linear-gradient(135deg, #eef3ff 0%, #f7f9fd 45%, #eaf1ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 24px;
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.55;
}

.blob-1 {
  width: 380px;
  height: 380px;
  background: #a8c4ff;
  top: -80px;
  left: -60px;
  animation: float-a 14s ease-in-out infinite;
}

.blob-2 {
  width: 300px;
  height: 300px;
  background: #b8ecd8;
  bottom: -60px;
  right: 12%;
  animation: float-b 18s ease-in-out infinite;
}

.blob-3 {
  width: 260px;
  height: 260px;
  background: #ffd9b8;
  top: 30%;
  right: -60px;
  animation: float-a 16s ease-in-out infinite reverse;
}

@keyframes float-a {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(24px, 18px);
  }
}

@keyframes float-b {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(-20px, -24px);
  }
}

.login-content {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 56px;
  max-width: 1160px;
  width: 100%;
  align-items: center;
}

.intro {
  flex: 1.15;
  color: #1f2a44;
  animation: rise 0.5s ease both;
}

.greeting {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(47, 111, 237, 0.1);
  color: var(--brand-primary);
  font-size: 13px;
  margin-bottom: 18px;
}

.greeting-icon {
  font-size: 16px;
}

.intro h1 {
  font-size: 38px;
  line-height: 1.3;
  margin: 0 0 16px;
  letter-spacing: 1px;
}

.intro-desc {
  color: #5a6478;
  line-height: 1.9;
  font-size: 14px;
  margin-bottom: 22px;
}

.today-card {
  display: flex;
  align-items: center;
  gap: 20px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(47, 111, 237, 0.12);
  border-radius: 14px;
  padding: 14px 20px;
  margin-bottom: 22px;
  box-shadow: 0 6px 20px rgba(47, 111, 237, 0.06);
}

.today-item {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.today-item .el-icon {
  font-size: 20px;
  color: var(--brand-primary);
}

.today-text strong {
  display: block;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.today-text span {
  font-size: 12px;
  color: #8a93a5;
}

.today-split {
  width: 1px;
  height: 30px;
  background: rgba(47, 111, 237, 0.15);
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.feature-list li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(47, 111, 237, 0.1);
  border-radius: 10px;
  padding: 12px 14px;
  transition: transform 0.2s, box-shadow 0.2s;
}

.feature-list li:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(47, 111, 237, 0.1);
}

.feature-list .el-icon {
  color: var(--brand-primary);
  font-size: 18px;
  margin-top: 2px;
}

.feature-list strong {
  display: block;
  font-size: 14px;
  margin-bottom: 3px;
}

.feature-list span {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}

.login-card {
  width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 32px 30px 24px;
  box-shadow: 0 18px 48px rgba(31, 42, 68, 0.13);
  flex-shrink: 0;
  animation: rise 0.5s ease 0.08s both;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-card h2 {
  margin: 0 0 6px;
  font-size: 22px;
}

.card-sub {
  margin: 0 0 22px;
  font-size: 13px;
  color: #8a93a5;
  line-height: 1.6;
}

.caps-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--brand-warning);
  line-height: 1.4;
}

.form-extra {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -6px 0 12px;
}

.extra-link {
  font-size: 13px;
  color: var(--brand-primary);
  cursor: pointer;
}

.extra-link:hover {
  text-decoration: underline;
}

.submit-item {
  margin-bottom: 6px;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  letter-spacing: 2px;
}

.demo-divider {
  margin: 18px 0 12px;
}

.demo-divider-text {
  font-size: 12px;
  color: #9aa3b5;
  letter-spacing: 1px;
}

.demo-accounts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.demo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-soft);
  background: #fafbff;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s, transform 0.2s;
}

.demo-item:hover {
  background: #f1f5ff;
  border-color: rgba(47, 111, 237, 0.35);
  transform: translateY(-1px);
}

.demo-tag {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.demo-name {
  font-size: 13px;
  font-weight: 600;
  color: #2f6fed;
  font-variant-numeric: tabular-nums;
}

.demo-desc {
  font-size: 12px;
  color: #8a93a5;
  margin-left: auto;
}

.demo-hint {
  margin: 10px 0 0;
  text-align: center;
  font-size: 12px;
  color: #9aa3b5;
}

.demo-hint code {
  padding: 1px 6px;
  margin-left: 2px;
  background: #f4f7ff;
  color: #2f6fed;
  border-radius: 4px;
  font-size: 12px;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 18px 0 0;
  padding-top: 14px;
  border-top: 1px dashed var(--border-soft);
  font-size: 12px;
  color: #9aa3b5;
}

@media (max-width: 1000px) {
  .intro {
    display: none;
  }

  .login-content {
    justify-content: center;
  }
}
</style>
