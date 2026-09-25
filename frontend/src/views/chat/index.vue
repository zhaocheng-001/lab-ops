<template>
  <div class="page-container">
    <div class="chat-wrap">
      <!-- 会话列表 -->
      <div class="page-card thread-panel">
        <div class="page-header" style="margin-bottom: 10px">
          <h3 class="page-title">
            沟通会话
            <el-tag v-if="totalUnread" type="danger" size="small" effect="dark">
              {{ totalUnread }} 条未读
            </el-tag>
          </h3>
          <el-badge v-if="unanswered" :value="unanswered" type="danger" />
        </div>
        <el-input v-model="query.keyword" placeholder="预约编号 / 申请人 / 设备" clearable
                  :prefix-icon="Search" @keyup.enter="loadThreads" @clear="loadThreads" />
        <el-radio-group v-model="query.status" size="small" class="mt-8" @change="loadThreads">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending_reply">待回复</el-radio-button>
          <el-radio-button value="closed">已结束</el-radio-button>
        </el-radio-group>

        <div class="thread-list" v-loading="threadLoading">
          <div v-for="item in threads" :key="item.id" class="thread-item"
               :class="{ active: selected && selected.id === item.id, unread: item.unread_count > 0 }"
               @click="selectThread(item)">
            <div class="thread-top">
              <span class="thread-no">{{ item.reservation_no }}</span>
              <span class="thread-tags">
                <el-tag v-if="item.unread_count" type="danger" size="small" effect="dark">
                  {{ item.unread_count }} 条未读
                </el-tag>
                <el-tag :type="chatStatusType(item.status)" size="small">{{ item.status_display }}</el-tag>
              </span>
            </div>
            <div class="thread-sub">{{ item.device_name }} · {{ item.laboratory_name }}</div>
            <div class="thread-bottom">
              <span class="thread-applicant">{{ item.applicant_name }}</span>
              <span class="text-muted">{{ formatDateTime(item.last_message_time) }}</span>
            </div>
          </div>
          <div v-if="!threads.length" class="empty-tip">暂无沟通会话</div>
        </div>
      </div>

      <!-- 消息面板 -->
      <div class="page-card message-panel">
        <template v-if="selected">
          <div class="page-header" style="margin-bottom: 10px">
            <div>
              <h3 class="page-title">
                {{ selected.reservation_no }}
                <el-tag :type="chatStatusType(selected.status)" size="small">{{ selected.status_display }}</el-tag>
              </h3>
              <p class="page-subtitle">
                {{ selected.device_name }} · {{ selected.laboratory_name }} · 申请人 {{ selected.applicant_name }}
              </p>
            </div>
            <div class="panel-actions">
              <el-button :icon="Refresh" size="small" @click="loadMessages">刷新</el-button>
              <el-button v-if="selected.status !== 'closed'" size="small" @click="closeThread">结束会话</el-button>
              <el-button size="small" @click="$router.push(`/reservations/${selected.reservation}`)">
                预约详情
              </el-button>
            </div>
          </div>

          <div ref="messageBox" class="message-box" v-loading="messageLoading">
            <div v-for="msg in messages" :key="msg.id" class="chat-bubble"
                 :class="{ mine: msg.sender === userStore.user?.id }">
              <el-avatar :size="36" :style="{ background: msg.is_admin_side ? '#f5a524' : '#2f6fed' }">
                {{ (msg.sender_name || '')[0] }}
              </el-avatar>
              <div class="bubble-main">
                <div class="bubble-meta">
                  {{ msg.sender_name }}
                  <el-tag v-if="msg.is_admin_side" size="small" type="warning" effect="plain"
                          style="margin-left: 6px">管理员</el-tag>
                  <span style="margin-left: 8px">{{ formatDateTimeFull(msg.created_at) }}</span>
                </div>
                <div v-if="msg.content" class="bubble-content">{{ msg.content }}</div>
                <el-image v-if="msg.image_url" class="bubble-image" :src="msg.image_url"
                          :preview-src-list="[msg.image_url]" fit="cover" preview-teleported />
              </div>
            </div>
            <div v-if="!messages.length" class="empty-tip">暂无沟通消息，发送第一条消息开始交流吧</div>
          </div>

          <div class="input-area">
            <el-upload :auto-upload="false" :show-file-list="false" accept="image/*"
                       :on-change="onPickImage">
              <el-button :icon="Picture">图片</el-button>
            </el-upload>
            <div v-if="imagePreview" class="image-chip">
              <el-image :src="imagePreview" class="image-chip-img" fit="cover" />
              <el-icon class="image-chip-close" @click="clearImage"><Close /></el-icon>
            </div>
            <el-input v-model="content" type="textarea" :rows="2" resize="none"
                      placeholder="输入沟通内容，Ctrl + Enter 发送"
                      @keydown.ctrl.enter.prevent="send" />
            <el-button type="primary" :loading="sending" @click="send">发送</el-button>
          </div>
        </template>
        <div v-else class="empty-panel">
          <el-empty description="请从左侧选择一个会话开始沟通" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, Picture, Refresh, Search } from '@element-plus/icons-vue'
import { chatApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { chatStatusType, formatDateTime, formatDateTimeFull } from '@/utils/dict'

const route = useRoute()
const userStore = useUserStore()

const threadLoading = ref(false)
const messageLoading = ref(false)
const sending = ref(false)
const threads = ref([])
const messages = ref([])
const selected = ref(null)
const unanswered = ref(0)
const content = ref('')
const imageFile = ref(null)
const imagePreview = ref('')
const messageBox = ref()

const query = reactive({ keyword: '', status: '' })

/** 会话列表中未读消息总数 */
const totalUnread = computed(() => threads.value.reduce((sum, item) => sum + (item.unread_count || 0), 0))

async function loadThreads() {
  threadLoading.value = true
  try {
    const params = { page_size: 50 }
    if (query.keyword) params.keyword = query.keyword
    if (query.status) params.status = query.status
    const res = await chatApi.list(params)
    threads.value = res.data.results
  } finally {
    threadLoading.value = false
  }
}

async function loadUnanswered() {
  try {
    const res = await chatApi.unansweredCount()
    unanswered.value = res.data.count
  } catch (error) {
    unanswered.value = 0
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messageBox.value) messageBox.value.scrollTop = messageBox.value.scrollHeight
  })
}

async function loadMessages() {
  if (!selected.value) return
  messageLoading.value = true
  try {
    const res = await chatApi.messages(selected.value.id)
    messages.value = res.data
    scrollToBottom()
  } finally {
    messageLoading.value = false
  }
}

async function selectThread(thread) {
  selected.value = thread
  if (thread.messages && thread.messages.length && !messages.value.length) {
    messages.value = thread.messages
  }
  await loadMessages()
  await markThreadRead(thread)
}

/** 打开会话即把对方发来的消息标记为已读，用于清除未读提示 */
async function markThreadRead(thread) {
  if (!thread || !thread.unread_count) return
  try {
    const res = await chatApi.markRead(thread.id)
    thread.unread_count = 0
    if (res.data && res.data.count) loadUnanswered()
  } catch (error) {
    /* 标记已读失败不影响会话浏览 */
  }
}

async function openByReservation(reservationId) {
  const res = await chatApi.byReservation({ reservation: reservationId })
  selected.value = res.data
  messages.value = res.data.messages || []
  scrollToBottom()
}

function onPickImage(uploadFile) {
  const raw = uploadFile.raw
  if (!raw) return
  if (raw.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 5MB')
    return
  }
  imageFile.value = raw
  imagePreview.value = URL.createObjectURL(raw)
}

function clearImage() {
  imageFile.value = null
  imagePreview.value = ''
}

async function send() {
  if (!selected.value) return
  if (!content.value.trim() && !imageFile.value) {
    ElMessage.warning('请输入内容或上传图片')
    return
  }
  const formData = new FormData()
  formData.append('reservation', selected.value.reservation)
  formData.append('content', content.value.trim())
  if (imageFile.value) formData.append('image', imageFile.value)

  sending.value = true
  try {
    await chatApi.send(formData)
    content.value = ''
    clearImage()
    await loadMessages()
    loadThreads()
    loadUnanswered()
  } finally {
    sending.value = false
  }
}

async function closeThread() {
  await ElMessageBox.confirm('确认结束该会话吗？结束后将不再计入待回复。', '结束会话', { type: 'warning' })
  await chatApi.close(selected.value.id)
  ElMessage.success('会话已结束')
  await loadThreads()
  const res = await chatApi.messages(selected.value.id)
  messages.value = res.data
  selected.value.status = 'closed'
  loadUnanswered()
}

onMounted(async () => {
  await loadThreads()
  loadUnanswered()
  if (route.query.reservation) {
    await openByReservation(route.query.reservation)
  }
})
</script>

<style scoped>
.chat-wrap {
  display: flex;
  gap: 16px;
  height: calc(100vh - 130px);
}

.thread-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.thread-list {
  flex: 1;
  overflow-y: auto;
  margin-top: 12px;
}

.thread-item {
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.2s;
}

.thread-item:hover {
  background: #f5f8ff;
}

.thread-item.active {
  background: var(--brand-primary-light);
  border-color: #cfe0ff;
}

.thread-item.unread .thread-no {
  color: #e5484d;
}

.thread-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.thread-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.thread-no {
  font-weight: 600;
  font-size: 13px;
}

.thread-sub {
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thread-bottom {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-top: 6px;
  color: var(--text-sub);
}

.thread-applicant {
  color: var(--text-main);
}

.message-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

.message-box {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  background: #f7f9fc;
  border-radius: 10px;
}

.input-area {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  margin-top: 12px;
}

.input-area .el-textarea {
  flex: 1;
}

.image-chip {
  position: relative;
  width: 54px;
  height: 54px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
}

.image-chip-img {
  width: 100%;
  height: 100%;
}

.image-chip-close {
  position: absolute;
  top: 2px;
  right: 2px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  cursor: pointer;
  padding: 2px;
}

.empty-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
