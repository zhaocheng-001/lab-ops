<template>
  <div class="page-container">
    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">操作日志</h3>
          <p class="page-subtitle">
            系统对预约、审批、设备、用户等关键操作自动留痕；系统管理员可见全部日志
          </p>
        </div>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <div v-if="actionStats.length" class="action-stats">
        <span class="action-stats-label">操作类型分布</span>
        <el-tag v-for="item in actionStats" :key="item.action" class="action-stat"
                :type="query.action === item.action ? 'primary' : 'info'"
                :effect="query.action === item.action ? 'dark' : 'plain'"
                @click="filterByAction(item.action)">
          {{ item.action_display || logActionLabel(item.action) }}
          <b>{{ item.count }}</b>
        </el-tag>
        <el-tag v-if="query.action" class="action-stat" type="danger" effect="plain"
                @click="filterByAction('')">
          清除筛选
        </el-tag>
      </div>

      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="操作对象 / 备注 / 操作人" clearable
                  style="width: 220px" @keyup.enter="load" @clear="load" />
        <el-select v-model="query.action" placeholder="操作类型" clearable style="width: 150px"
                   @change="load">
          <el-option v-for="item in LOG_ACTION_OPTIONS" :key="item.value" :label="item.label"
                     :value="item.value" />
        </el-select>
        <el-select v-model="query.target_type" placeholder="对象类型" clearable style="width: 140px"
                   @change="load">
          <el-option v-for="(label, value) in TARGET_TYPE_LABEL" :key="value" :label="label"
                     :value="value" />
        </el-select>
        <el-select v-if="userStore.isAdminRole" v-model="query.lab" placeholder="实验室" clearable
                   filterable style="width: 180px" @change="load">
          <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
                        start-placeholder="开始日期" end-placeholder="结束日期"
                        format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width: 250px"
                        @change="load" />
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="reset">重置</el-button>
          <el-button :icon="Search" type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatDateTimeFull(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作人" width="130">
          <template #default="{ row }">
            <div>{{ row.operator_name }}</div>
            <div class="text-muted" style="font-size: 12px">{{ roleLabel(row.operator_role) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-tag :type="logActionType(row.action)" size="small">
              {{ row.action_display || logActionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象类型" width="100">
          <template #default="{ row }">{{ targetTypeLabel(row.target_type) }}</template>
        </el-table-column>
        <el-table-column prop="target_repr" label="操作对象" min-width="180" show-overflow-tooltip />
        <el-table-column prop="lab_name" label="所属实验室" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.lab_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="change_summary" label="变更明细" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.change_summary || row.remark || '—' }}</template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130">
          <template #default="{ row }">{{ row.ip || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无操作日志</div>
        </template>
      </el-table>

      <el-pagination class="mt-16" v-model:current-page="query.page" v-model:page-size="query.page_size"
                     :page-sizes="[10, 20, 50]" :total="total"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="load" @current-change="load" />
    </div>

    <el-dialog v-model="detailVisible" title="日志详情" width="680px">
      <el-descriptions v-if="current" :column="2" border>
        <el-descriptions-item label="操作时间">
          {{ formatDateTimeFull(current.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="操作人">{{ current.operator_name }}</el-descriptions-item>
        <el-descriptions-item label="操作人角色">{{ roleLabel(current.operator_role) }}</el-descriptions-item>
        <el-descriptions-item label="操作类型">
          {{ current.action_display || logActionLabel(current.action) }}
        </el-descriptions-item>
        <el-descriptions-item label="对象类型">{{ targetTypeLabel(current.target_type) }}</el-descriptions-item>
        <el-descriptions-item label="对象 ID">{{ current.target_id || '—' }}</el-descriptions-item>
        <el-descriptions-item label="操作对象" :span="2">{{ current.target_repr || '—' }}</el-descriptions-item>
        <el-descriptions-item label="所属实验室">{{ current.lab_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="来源 IP">{{ current.ip || '—' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ current.remark || '—' }}</el-descriptions-item>
      </el-descriptions>

      <h4 class="section-title">变更明细</h4>
      <el-table v-if="detailRows.length" :data="detailRows" border size="small">
        <el-table-column prop="field" label="字段" width="160" />
        <el-table-column prop="old" label="变更前" min-width="140" />
        <el-table-column prop="new" label="变更后" min-width="140" />
      </el-table>
      <div v-else class="empty-tip">本次操作无字段级变更记录</div>

      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { labApi, logApi } from '@/api'
import { roleLabel, useUserStore } from '@/stores/user'
import {
  LOG_ACTION_OPTIONS,
  TARGET_TYPE_LABEL,
  formatDateTimeFull,
  logActionLabel,
  logActionType,
  targetTypeLabel
} from '@/utils/dict'

const userStore = useUserStore()

const loading = ref(false)
const list = ref([])
const total = ref(0)
const labs = ref([])
const dateRange = ref([])
const detailVisible = ref(false)
const current = ref(null)
const actionStats = ref([])

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  action: '',
  target_type: '',
  lab: '',
  ordering: '-created_at'
})

const detailRows = computed(() => {
  const detail = current.value?.detail
  if (!detail || typeof detail !== 'object') return []
  return Object.entries(detail).map(([field, values]) => {
    if (Array.isArray(values) && values.length === 2) {
      return { field, old: values[0] === '' || values[0] === null ? '空' : String(values[0]), new: values[1] === '' || values[1] === null ? '空' : String(values[1]) }
    }
    return { field, old: '—', new: String(values) }
  })
})

function buildParams() {
  const params = { page: query.page, page_size: query.page_size, ordering: query.ordering }
  if (query.keyword) params.keyword = query.keyword
  if (query.action) params.action = query.action
  if (query.target_type) params.target_type = query.target_type
  if (query.lab) params.lab = query.lab
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  return params
}

async function load() {
  loading.value = true
  try {
    const res = await logApi.list(buildParams())
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

/** 按操作类型统计（点击标签即按该类型筛选） */
async function loadSummary() {
  const res = await logApi.summary()
  actionStats.value = res.data || []
}

function filterByAction(action) {
  query.action = action || ''
  query.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.action = ''
  query.target_type = ''
  query.lab = ''
  dateRange.value = []
  query.page = 1
  load()
}

function openDetail(row) {
  current.value = row
  detailVisible.value = true
}

onMounted(async () => {
  if (userStore.isAdminRole) {
    const res = await labApi.simple(userStore.isLabAdmin ? { mine: 1 } : {})
    labs.value = res.data
  }
  loadSummary()
  load()
})
</script>

<style scoped>
.action-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
  background: #f7f9fc;
  border-radius: 8px;
}

.action-stats-label {
  font-size: 13px;
  color: var(--text-sub);
  margin-right: 4px;
}

.action-stat {
  cursor: pointer;
  user-select: none;
}

.action-stat b {
  margin-left: 4px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 20px 0 12px;
  padding-left: 10px;
  border-left: 3px solid var(--brand-primary);
}
</style>
