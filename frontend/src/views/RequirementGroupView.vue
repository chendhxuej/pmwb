<template>
  <div class="group-req">
    <div class="page-header">
      <div class="page-title">集团需求</div>
      <div class="page-actions">
        <el-button :loading="loading" @click="loadData">刷新</el-button>
        <el-button type="success" :loading="exporting" @click="handleExport">导出 xlsx</el-button>
      </div>
    </div>

    <div class="table-hint">
      集团需求（个人优先级标记为「集团需求」）。点击「导出 xlsx」可导出当前全部集团需求台账。
    </div>

    <el-table v-loading="loading" :data="tableData" border stripe style="width: 100%">
      <el-table-column prop="req_id" label="需求编号" width="180" show-overflow-tooltip />
      <el-table-column prop="req_name" label="需求名称" min-width="220" show-overflow-tooltip />
      <el-table-column prop="proposer" label="提出人" width="90" />
      <el-table-column prop="system_name" label="负责系统" width="130" show-overflow-tooltip />
      <el-table-column prop="sa_name" label="评估SA" width="100" />
      <el-table-column label="个人状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.ext?.status)">{{ statusLabel(row.ext?.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="eval_count" label="团队评估" width="90" align="center" />
      <el-table-column prop="ext.version_required_date" label="版本要求" width="130" align="center" />
      <el-table-column label="跟踪状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="trackingType(row.tracking_status)">{{ trackingLabel(row.tracking_status) }}</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > 0"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      class="pagination"
      @size-change="loadData"
      @current-change="loadData"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import { getRequirements } from '@/api/requirement.js'

const loading = ref(false)
const exporting = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const statusMap = {
  proposed: { label: '已提出', type: 'info' },
  accepted: { label: '已受理', type: 'primary' },
  dev: { label: '开发中', type: 'warning' },
  closed: { label: '已关闭', type: 'success' },
  paused: { label: '已暂停', type: 'danger' },
}
const statusLabel = (s) => (statusMap[s] || { label: s || '未设置' }).label
const statusType = (s) => (statusMap[s] || { type: 'info' }).type

const trackingMap = {
  none: { label: '无工单', type: 'info' },
  on_time: { label: '按时', type: 'success' },
  on_track: { label: '进行中', type: 'primary' },
  warning: { label: '预警', type: 'warning' },
  overdue: { label: '超期', type: 'danger' },
}
const trackingLabel = (s) => (trackingMap[s] || trackingMap.none).label
const trackingType = (s) => (trackingMap[s] || trackingMap.none).type

async function loadData() {
  loading.value = true
  try {
    const res = await getRequirements({
      priority: '集团需求',
      page: page.value,
      page_size: pageSize.value,
    })
    tableData.value = (res.items || []).map((r) => ({ ...r, ext: r.ext || {} }))
    total.value = res.total || 0
  } catch (err) {
    ElMessage.error(err.message || '获取集团需求失败')
  } finally {
    loading.value = false
  }
}

async function fetchAll() {
  // 后端 page_size 上限为 100，导出前分批拉取全部集团需求
  const all = []
  let page = 1
  const pageSize = 100
  while (true) {
    const res = await getRequirements({ priority: '集团需求', page, page_size: pageSize })
    const items = res.items || []
    all.push(...items.map((r) => ({ ...r, ext: r.ext || {} })))
    const total = res.total || 0
    if (all.length >= total || items.length < pageSize) break
    page += 1
  }
  return all
}

function handleExport() {
  exporting.value = true
  fetchAll()
    .then((rows) => {
      if (!rows.length) {
        ElMessage.warning('暂无集团需求可导出')
        return
      }
      const data = rows.map((r) => ({
        需求编号: r.req_id,
        需求名称: r.req_name,
        提出人: r.proposer,
        负责系统: r.system_name,
        评估SA: r.sa_name,
        个人状态: statusLabel(r.ext?.status),
        优先级: r.ext?.priority || '',
        团队评估数: r.eval_count || 0,
        版本要求: r.ext?.version_required_date || '',
        跟踪状态: trackingLabel(r.tracking_status),
      }))
      const ws = XLSX.utils.json_to_sheet(data)
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, '集团需求')
      const stamp = new Date().toISOString().slice(0, 10)
      XLSX.writeFile(wb, `集团需求_${stamp}.xlsx`)
      ElMessage.success(`已导出 ${rows.length} 条集团需求`)
    })
    .catch((err) => {
      ElMessage.error(err.message || '导出失败')
    })
    .finally(() => {
      exporting.value = false
    })
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.group-req {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
}
.table-hint {
  font-size: 13px;
  color: #909399;
  margin: 4px 2px 16px;
  line-height: 1.6;
}
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
</style>
