<template>
  <div class="page-container">
    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">
            站内提醒
            <el-tag type="danger" size="small" effect="dark">未读 {{ userStore.unreadCount }}</el-tag>
          </h3>
          <p class="page-subtitle">系统自动扫描待审批、待签到、待归还、即将到期、待评价等事项并在此提醒</p>
        </div>
        <div class="header-actions">
          <el-switch v-model="unreadOnly" active-text="仅看未读" @change="onFilterChange" />
          <el-button v-if="selectedIds.length" type="primary" :icon="Select" @click="batchRead">
            批量已读（{{ selectedIds.length }}）
          </el-button>
          <el-button :icon="Check" @click="readAll">全部已读</el-button>
          <el-button :icon="Delete" @click="clearRead">清除已读</el-button>
          <el-button :icon="Refresh" @click="load">刷新</el-button>
        </div>
      </div>

      <el-tabs v-model="activeType" @tab-change="onFilterChange">
        <el-tab-pane label="全部" name="" />
        <el-tab-pane v-for="item in summary" :key="item.notify_type"
                     :name="item.notify_type">
          <template #label>
            {{ item.notify_type_display }}
            <el-badge v-if="item.unread" :value="item.unread" class="tab-badge" />
          </template>
        </el-tab-pane>
      </el-tabs>

      <div v-loading="loading" class="notify-list">
        <div v-if="list.length" class="batch-bar" @click.stop>
          <el-checkbox :model-value="allSelected" :indeterminate="indeterminate" @change="toggleAll">
            全选本页
          </el-checkbox>
          <span class="batch-tip">{{ selectedIds.length ? `已选 ${selectedIds.length} 条` : '勾选后可批量标记已读' }}</span>
        </div>
        <div v-for="item in list" :key="item.id" class="notify-item"
             :class="{ unread: !item.is_read }" @click="openItem(item)">
          <div class="notify-check" @click.stop>
            <el-checkbox :model-value="selectedIds.includes(item.id)"
                         @change="(checked) => toggleSelect(item.id, checked)" />
          </div>
          <div class="notify-icon" :style="{ background: levelColor(item.level) }">
            <el-icon><component :is="levelIcon(item.level)" /></el-icon>
          </div>
          <div class="notify-main">
            <div class="notify-title">
              <el-tag :type="notifyTypeTag(item.notify_type)" size="small" effect="plain">
                {{ item.notify_type_display }}
              </el-tag>
              <span class="title-text">{{ item.title }}</span>
              <el-tag v-if="!item.is_read" type="danger" size="small" effect="plain">未读</el-tag>
            </div>
            <div class="notify-content">{{ item.content }}</div>
            <div class="notify-meta">
              <span>{{ formatDateTimeFull(item.created_at) }}</span>
              <el-link v-if="item.reservation" type="primary" :underline="false"
                       @click.stop="$router.push(`/reservations/${item.reservation}`)">
                查看预约 {{ item.reservation_no }}
              </el-link>
            </div>
          </div>
          <div class="notify-actions">
            <el-button v-if="!item.is_read" link type="primary" size="small"
                       @click.stop="markRead(item)">标为已读</el-button>
            <el-button v-else link type="info" size="small" @click.stop="markUnread(item)">标为未读</el-button>
          </div>
        </div>
        <div v-if="!list.length && !loading" class="empty-tip">暂无提醒消息</div>
      </div>

      <el-pagination class="mt-16" v-model:current-page="query.page" v-model:page-size="query.page_size"
                     :page-sizes="[10, 20, 50]" :total="total"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="load" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Delete, Refresh, Select } from '@element-plus/icons-vue'
import { notificationApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { formatDateTimeFull, notifyTypeTag } from '@/utils/dict'

const userStore = useUserStore()

const loading = ref(false)
const list = ref([])
const total = ref(0)
const summary = ref([])
const activeType = ref('')
const unreadOnly = ref(false)

const query = reactive({ page: 1, page_size: 10 })
const selectedIds = ref([])

const allSelected = computed(() => list.value.length > 0 && selectedIds.value.length === list.value.length)
const indeterminate = computed(() => selectedIds.value.length > 0 && !allSelected.value)

function toggleSelect(id, checked) {
  if (checked) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter((item) => item !== id)
  }
}

function toggleAll(checked) {
  selectedIds.value = checked ? list.value.map((item) => item.id) : []
}

async function batchRead() {
  if (!selectedIds.value.length) return
  const res = await notificationApi.batchRead(selectedIds.value)
  ElMessage.success(res.message || '已批量标记为已读')
  selectedIds.value = []
  load()
  loadSummary()
}

function levelColor(level) {
  if (level === 'danger') return '#e5484d'
  if (level === 'warning') return '#f5a524'
  if (level === 'success') return '#17a673'
  return '#2f6fed'
}

function levelIcon(level) {
  if (level === 'danger') return 'WarningFilled'
  if (level === 'warning') return 'Bell'
  if (level === 'success') return 'CircleCheckFilled'
  return 'InfoFilled'
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size, scan: 1 }
    if (activeType.value) params.notify_type = activeType.value
    if (unreadOnly.value) params.unread_only = 1
    const res = await notificationApi.list(params)
    list.value = res.data.results
    total.value = res.data.count
    selectedIds.value = []
    userStore.loadBadges()
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  const res = await notificationApi.summary()
  summary.value = res.data
}

function onFilterChange() {
  query.page = 1
  load()
  loadSummary()
}

function openItem(item) {
  if (!item.is_read) markRead(item, false)
}

async function markRead(item, notify = true) {
  await notificationApi.markRead(item.id)
  item.is_read = true
  userStore.loadBadges()
  if (notify) ElMessage.success('已标记为已读')
}

async function markUnread(item) {
  await notificationApi.markUnread(item.id)
  item.is_read = false
  userStore.loadBadges()
}

async function readAll() {
  const payload = activeType.value ? { notify_type: activeType.value } : {}
  await notificationApi.readAll(payload)
  ElMessage.success('已全部标记为已读')
  load()
  loadSummary()
}

async function clearRead() {
  await ElMessageBox.confirm('确认清除所有已读提醒吗？该操作不可恢复。', '清除已读', { type: 'warning' })
  await notificationApi.clear()
  ElMessage.success('已清除已读提醒')
  load()
  loadSummary()
}

onMounted(() => {
  load()
  loadSummary()
})
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.notify-list {
  min-height: 200px;
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #f7f9fc;
  border-radius: 8px;
  margin-bottom: 6px;
}

.batch-tip {
  font-size: 12px;
  color: var(--text-sub);
}

.notify-check {
  flex-shrink: 0;
  padding-top: 9px;
}

.notify-item {
  display: flex;
  gap: 14px;
  padding: 14px 12px;
  border-bottom: 1px solid var(--border-soft);
  transition: background 0.2s;
  align-items: flex-start;
}

.notify-item:hover {
  background: #f7f9fc;
}

.notify-item.unread {
  background: #f5f8ff;
}

.notify-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  flex-shrink: 0;
}

.notify-main {
  flex: 1;
  min-width: 0;
}

.notify-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.title-text {
  font-weight: 600;
  font-size: 14px;
}

.notify-content {
  color: var(--text-sub);
  font-size: 13px;
  margin-top: 4px;
  word-break: break-word;
}

.notify-meta {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 6px;
}

.notify-actions {
  flex-shrink: 0;
}

.tab-badge {
  margin-left: 6px;
}
</style>
