<template>
  <div class="page-container">
    <div v-if="userStore.isAdminRole" class="stat-grid mb-16">
      <StatCard icon="ChatLineSquare" color="#2f6fed" :value="stats.count" label="评价总数" />
      <StatCard icon="Star" color="#f5a524" :value="stats.overall_avg" label="综合平均分" unit="分"
                :value-color="'#f5a524'" />
      <StatCard icon="Monitor" color="#17a673" :value="stats.device_avg" label="设备状态均分" unit="分" />
      <StatCard icon="Timer" color="#00b4d8" :value="stats.speed_avg" label="响应速度均分" unit="分" />
      <StatCard icon="Service" color="#8b5cf6" :value="stats.service_avg" label="管理服务均分" unit="分" />
    </div>

    <div class="page-card">
      <div class="page-header">
        <div>
          <h3 class="page-title">{{ userStore.isAdminRole ? '完工评价管理' : '我的评价记录' }}</h3>
          <p class="page-subtitle">
            {{ userStore.isAdminRole
              ? '查看申请人对设备与服务的评价，可回复说明以提升服务质量'
              : '预约完工后可对设备状态、响应速度与管理服务进行评价' }}
          </p>
        </div>
      </div>

      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="预约编号 / 申请人 / 评价内容" clearable
                  style="width: 240px" @keyup.enter="load" @clear="load" />
        <el-select v-if="userStore.isAdminRole" v-model="query.laboratory" placeholder="实验室" clearable
                   filterable style="width: 190px" @change="load">
          <el-option v-for="lab in labs" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-select v-model="query.score" placeholder="最低综合分" clearable style="width: 150px"
                   @change="load">
          <el-option v-for="score in [5, 4, 3, 2, 1]" :key="score" :label="`${score} 分及以上`"
                     :value="score" />
        </el-select>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="reset">重置</el-button>
          <el-button :icon="Search" type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="reservation_no" label="预约编号" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/reservations/${row.reservation}`)">
              {{ row.reservation_no }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="设备 / 实验室" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.device_name }}</div>
            <div class="text-muted" style="font-size: 12px">{{ row.laboratory_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="评分明细" width="230">
          <template #default="{ row }">
            <div class="score-row"><span>设备状态</span><el-rate :model-value="row.device_score" disabled
                                      size="small" /></div>
            <div class="score-row"><span>响应速度</span><el-rate :model-value="row.speed_score" disabled
                                      size="small" /></div>
            <div class="score-row"><span>管理服务</span><el-rate :model-value="row.service_score" disabled
                                      size="small" /></div>
          </template>
        </el-table-column>
        <el-table-column label="综合分" width="90">
          <template #default="{ row }">
            <span class="avg-score">{{ row.average_score }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="评价内容" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.content || '—' }}</template>
        </el-table-column>
        <el-table-column label="评价人" width="110">
          <template #default="{ row }">{{ row.evaluator_display || row.evaluator_name }}</template>
        </el-table-column>
        <el-table-column label="评价时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="管理员回复" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.reply_content">{{ row.reply_content }}</span>
            <span v-else class="text-muted">待回复</span>
          </template>
        </el-table-column>
        <el-table-column v-if="userStore.isAdminRole" label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openReply(row)">
              {{ row.reply_content ? '修改回复' : '回复' }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-tip">暂无评价记录</div>
        </template>
      </el-table>

      <el-pagination class="mt-16" v-model:current-page="query.page" v-model:page-size="query.page_size"
                     :page-sizes="[10, 20, 50]" :total="total"
                     layout="total, sizes, prev, pager, next, jumper"
                     @size-change="load" @current-change="load" />
    </div>

    <el-dialog v-model="replyVisible" title="回复评价" width="520px">
      <el-alert v-if="currentRow" type="info" :closable="false" class="mb-16">
        {{ currentRow.reservation_no }} · 申请人评价：{{ currentRow.content || '（无文字评价）' }}
      </el-alert>
      <el-input v-model="replyContent" type="textarea" :rows="4" maxlength="200" show-word-limit
                placeholder="请输入回复内容，例如改进措施或说明" />
      <template #footer>
        <el-button @click="replyVisible = false">取消</el-button>
        <el-button type="primary" :loading="replyLoading" @click="doReply">提交回复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import StatCard from '@/components/StatCard.vue'
import { evaluationApi, labApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/dict'

const userStore = useUserStore()

const loading = ref(false)
const list = ref([])
const total = ref(0)
const labs = ref([])
const stats = ref({
  count: 0,
  device_avg: 0,
  speed_avg: 0,
  service_avg: 0,
  overall_avg: 0,
  by_laboratory: []
})

const replyVisible = ref(false)
const replyLoading = ref(false)
const replyContent = ref('')
const currentRow = ref(null)

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  laboratory: '',
  score: '',
  ordering: '-created_at'
})

function buildParams() {
  const params = { page: query.page, page_size: query.page_size, ordering: query.ordering }
  if (query.keyword) params.keyword = query.keyword
  if (query.laboratory) params.laboratory = query.laboratory
  if (query.score) params.score = query.score
  return params
}

async function load() {
  loading.value = true
  try {
    const res = await evaluationApi.list(buildParams())
    list.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  const res = await evaluationApi.statistics()
  stats.value = res.data
}

function reset() {
  query.keyword = ''
  query.laboratory = ''
  query.score = ''
  query.page = 1
  load()
}

function openReply(row) {
  currentRow.value = row
  replyContent.value = row.reply_content || ''
  replyVisible.value = true
}

async function doReply() {
  if (!replyContent.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  replyLoading.value = true
  try {
    await evaluationApi.reply(currentRow.value.id, { reply_content: replyContent.value.trim() })
    ElMessage.success('回复成功')
    replyVisible.value = false
    load()
  } finally {
    replyLoading.value = false
  }
}

onMounted(async () => {
  if (userStore.isAdminRole) {
    const res = await labApi.simple({ mine: 1 })
    labs.value = res.data
    loadStats()
  }
  load()
})
</script>

<style scoped>
.score-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-sub);
}

.score-row .el-rate {
  height: 18px;
}

.avg-score {
  font-size: 18px;
  font-weight: 700;
  color: var(--brand-warning);
}
</style>
