<template>
  <div class="operation-overview">
    <h2 class="page-title">业务运营监控 · 总览</h2>

    <!-- 总统计 -->
    <el-row :gutter="12" class="stats-row">
      <el-col :span="3">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value">{{ overall.total }}</div>
            <div class="stat-label">工单总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-pending">
          <div class="stat-item">
            <div class="stat-value">{{ overall.pending }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-processing">
          <div class="stat-item">
            <div class="stat-value">{{ overall.processing }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-verify">
          <div class="stat-item">
            <div class="stat-value">{{ overall.verify }}</div>
            <div class="stat-label">待验证</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-resolved">
          <div class="stat-item">
            <div class="stat-value">{{ overall.resolved }}</div>
            <div class="stat-label">已解决</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-overdue">
          <div class="stat-item">
            <div class="stat-value">{{ overall.overdue }}</div>
            <div class="stat-label">超期</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-loop">
          <div class="stat-item">
            <div class="stat-value">{{ overall.closed_loop_rate }}%</div>
            <div class="stat-label">闭环率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 五大类工单卡片 -->
    <h3 class="section-title">工单分类（点击进入独立管理）</h3>
    <el-row :gutter="16" class="cat-row">
      <el-col v-for="cat in categories" :key="cat.key" :span="24 / categories.length">
        <el-card
          shadow="hover"
          class="cat-card"
          :body-style="{ padding: '18px 20px' }"
          @click="goCategory(cat.key)"
        >
          <div class="cat-head">
            <span class="cat-name">{{ cat.label }}</span>
            <el-tag :type="cat.color" effect="light">{{ catStats[cat.key]?.total || 0 }}</el-tag>
          </div>
          <div class="cat-meta">
            <span>超期 <b :class="{ danger: (catStats[cat.key]?.overdue || 0) > 0 }">{{ catStats[cat.key]?.overdue || 0 }}</b></span>
            <span>闭环率 <b>{{ catStats[cat.key]?.closed_loop_rate || 0 }}%</b></span>
          </div>
          <div class="cat-foot">责任到人 · 跟踪闭环 →</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 近期工单 -->
    <h3 class="section-title">近期工单</h3>
    <el-card shadow="never">
      <el-table :data="recent" v-loading="loading" style="width: 100%">
        <el-table-column prop="issue_no" label="工单编号" width="160" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category" label="大类" width="120">
          <template #default="{ row }">
            <el-tag :type="categoryMeta[row.category]?.color || 'info'" size="small">
              {{ categoryMeta[row.category]?.label || row.category }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <StatusBadge :value="row.status" :options="statusBadgeOptions" />
          </template>
        </el-table-column>
        <el-table-column prop="handler" label="责任人" width="120" />
        <el-table-column prop="impact_level" label="影响等级" width="90" />
        <el-table-column prop="is_overdue" label="超期" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_overdue" type="danger" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="goCategory(row.category)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import { operationApi } from '@/api/operation'

const router = useRouter()

const categoryMeta = {
  bug: { label: 'BUG管理', color: 'danger', key: 'bug' },
  data: { label: '数据异常管理', color: 'warning', key: 'data' },
  prod: { label: '生产问题分析', color: 'primary', key: 'prod' },
  task: { label: '临时交办任务', color: 'success', key: 'task' },
  complaint: { label: '热点投诉', color: 'danger', key: 'complaint' },
}
const categories = Object.values(categoryMeta)

const statusBadgeOptions = {
  pending: { label: '待处理', type: 'danger' },
  processing: { label: '处理中', type: 'warning' },
  verify: { label: '待验证', type: 'primary' },
  resolved: { label: '已解决', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
  suspended: { label: '已挂起', type: 'info' },
}

const overall = reactive({
  total: 0,
  pending: 0,
  processing: 0,
  verify: 0,
  resolved: 0,
  closed: 0,
  suspended: 0,
  overdue: 0,
  closed_loop_rate: 0,
})

const catStats = reactive({})
const recent = ref([])
const loading = ref(false)

const loadOverall = async () => {
  try {
    const res = await operationApi.getStats()
    Object.assign(overall, res)
  } catch (e) {
    ElMessage.error('加载总统计失败')
  }
}

const loadCategoryStats = async () => {
  for (const cat of categories) {
    try {
      const res = await operationApi.getStats(cat.key)
      catStats[cat.key] = {
        total: res.total,
        overdue: res.overdue,
        closed_loop_rate: res.closed_loop_rate,
      }
    } catch (e) {
      catStats[cat.key] = { total: 0, overdue: 0, closed_loop_rate: 0 }
    }
  }
}

const loadRecent = async () => {
  loading.value = true
  try {
    const res = await operationApi.listIssues({ page: 1, page_size: 10 })
    recent.value = res.items || []
  } catch (e) {
    ElMessage.error('加载近期工单失败')
  } finally {
    loading.value = false
  }
}

const goCategory = (key) => {
  router.push(`/operation/${key}`)
}

onMounted(() => {
  loadOverall()
  loadCategoryStats()
  loadRecent()
})
</script>

<style scoped>
.operation-overview {
  padding: 20px;
}
.page-title {
  margin-bottom: 20px;
  font-size: 20px;
  font-weight: 600;
}
.section-title {
  margin: 24px 0 14px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.stats-row {
  margin-bottom: 8px;
}
.stat-item {
  text-align: center;
  padding: 10px 0;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #303133;
}
.stat-label {
  font-size: 13px;
  color: #606266;
  margin-top: 6px;
}
.cat-card {
  cursor: pointer;
  transition: transform 0.2s;
  border-top: 3px solid transparent;
}
.cat-card:hover {
  transform: translateY(-3px);
}
.cat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.cat-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.cat-meta {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #909399;
  margin-bottom: 12px;
}
.cat-meta b {
  color: #303133;
}
.cat-meta b.danger {
  color: #f56c6c;
}
.cat-foot {
  font-size: 12px;
  color: #409eff;
}
.status-pending .stat-value {
  color: #f56c6c;
}
.status-processing .stat-value {
  color: #e6a23c;
}
.status-verify .stat-value {
  color: #409eff;
}
.status-resolved .stat-value {
  color: #67c23a;
}
.status-overdue .stat-value {
  color: #f56c6c;
}
.status-loop .stat-value {
  color: #409eff;
}
</style>
