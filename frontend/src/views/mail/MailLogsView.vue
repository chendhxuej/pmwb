<template>
  <div class="mail-logs-view">
    <!-- 筛选区 -->
    <el-form :model="filters" inline class="filter-bar" @keyup.enter="onSearch">
      <el-form-item label="关键词">
        <el-input
          v-model="filters.search"
          placeholder="搜索主题/收件人/需求编号..."
          clearable
          style="width: 240px"
          @clear="onSearch"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px" @change="onSearch">
          <el-option label="发送成功" value="sent" />
          <el-option label="发送失败" value="failed" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="filters.logType" placeholder="全部类型" clearable style="width: 120px" @change="onSearch">
          <el-option label="催办通知" value="reminder" />
          <el-option label="需求通知" value="requirement" />
          <el-option label="系统通知" value="system" />
        </el-select>
      </el-form-item>
      <el-form-item label="来源">
        <el-select v-model="filters.sourceFilter" placeholder="全部来源" clearable style="width: 120px" @change="onSearch">
          <el-option label="邮件中心" value="mail-center" />
          <el-option label="PMWB" value="pmwb" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期范围">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          @change="onSearch"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSearch">查询</el-button>
        <el-button @click="onReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 表格 -->
    <el-table :data="tableData" v-loading="loading" stripe border style="width: 100%">
      <el-table-column label="时间" prop="sentAt" width="160" />
      <el-table-column label="来源" width="90">
        <template #default="{ row }">
          <el-tag :type="row.source === 'mail-center' ? '' : 'success'" size="small">
            {{ row.source === 'mail-center' ? '邮件中心' : 'PMWB' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="类型" prop="type" width="100" />
      <el-table-column label="主题" prop="subject" min-width="200" show-overflow-tooltip />
      <el-table-column label="收件人" prop="to" width="180" show-overflow-tooltip />
      <el-table-column label="发件人" prop="fromEmail" width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'sent' ? 'success' : 'danger'" size="small">
            {{ row.status === 'sent' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="onViewDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="邮件详情" width="720px" top="5vh">
      <el-descriptions :column="1" border v-if="detailRow">
        <el-descriptions-item label="发送时间">{{ detailRow.sentAt }}</el-descriptions-item>
        <el-descriptions-item label="来源">
          {{ detailRow.source === 'mail-center' ? '邮件中心' : 'PMWB' }}
        </el-descriptions-item>
        <el-descriptions-item label="类型">{{ detailRow.type }}</el-descriptions-item>
        <el-descriptions-item label="主题">{{ detailRow.subject }}</el-descriptions-item>
        <el-descriptions-item label="收件人">{{ detailRow.to }}</el-descriptions-item>
        <el-descriptions-item label="发件人">{{ detailRow.fromEmail }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="detailRow.status === 'sent' ? 'success' : 'danger'" size="small">
            {{ detailRow.status === 'sent' ? '发送成功' : '发送失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" v-if="detailRow.error">{{ detailRow.error }}</el-descriptions-item>
        <el-descriptions-item label="原文">
          <div class="mail-body-preview" v-html="sanitizedBody" v-if="detailRow.body"></div>
          <span v-else class="text-muted">（无内容）</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getMergedLogs } from '@/api/mailCenter.js'

// 筛选条件
const filters = reactive({
  search: '',
  status: '',
  logType: '',
  sourceFilter: '',
})
const dateRange = ref(null)

// 分页
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 表格
const tableData = ref([])
const loading = ref(false)

// 详情弹窗
const detailVisible = ref(false)
const detailRow = ref(null)

// 简单清理 HTML — 仅保留安全标签防止 XSS
const sanitizedBody = computed(() => {
  if (!detailRow.value?.body) return ''
  const div = document.createElement('div')
  div.textContent = detailRow.value.body
  return div.innerHTML
})

// 查询
async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      pageSize: pageSize.value,
    }
    if (filters.search) params.search = filters.search
    if (filters.status) params.status = filters.status
    if (filters.logType) params.logType = filters.logType
    if (dateRange.value) {
      params.startDate = dateRange.value[0]
      params.endDate = dateRange.value[1]
    }

    const resp = await getMergedLogs(params)
    const payload = resp.data?.data || resp.data || resp

    // 后端返回的 items 已经是合并过的，前端仅作来源补充过滤
    if (filters.sourceFilter) {
      tableData.value = (payload.items || []).filter(i => i.source === filters.sourceFilter)
    } else {
      tableData.value = payload.items || []
    }

    total.value = payload.total || 0
  } catch (err) {
    console.error('获取发送日志失败', err)
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  fetchData()
}

function onReset() {
  filters.search = ''
  filters.status = ''
  filters.logType = ''
  filters.sourceFilter = ''
  dateRange.value = null
  page.value = 1
  fetchData()
}

function onViewDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.mail-logs-view {
  padding: 0;
}
.filter-bar {
  margin-bottom: 16px;
  background: var(--el-fill-color-lighter, #f5f7fa);
  padding: 12px 16px;
  border-radius: 6px;
}
.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.mail-body-preview {
  max-height: 400px;
  overflow-y: auto;
  background: var(--el-fill-color, #f0f2f5);
  padding: 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.7;
}
.text-muted {
  color: var(--el-text-color-secondary, #909399);
}
</style>
