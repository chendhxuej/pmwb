<template>
  <div class="home-view">
    <h2 class="page-title">首页看板</h2>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card" @click="goTo('/todo')">
          <div class="stat-item">
            <div class="stat-value">{{ stats.todo_total }}</div>
            <div class="stat-label">待办总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-warning" @click="goTo('/todo')">
          <div class="stat-item">
            <div class="stat-value">{{ stats.todo_today }}</div>
            <div class="stat-label">今日待办</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-danger" @click="goTo('/todo')">
          <div class="stat-item">
            <div class="stat-value">{{ stats.todo_overdue }}</div>
            <div class="stat-label">超期待办</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card" @click="goTo('/meeting')">
          <div class="stat-item">
            <div class="stat-value">{{ stats.meeting_this_week }}</div>
            <div class="stat-label">本周会议</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-danger" @click="goTo('/operation')">
          <div class="stat-item">
            <div class="stat-value">{{ stats.issue_pending }}</div>
            <div class="stat-label">待处理问题</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card" @click="goTo('/knowledge')">
          <div class="stat-item">
            <div class="stat-value">{{ stats.knowledge_total }}</div>
            <div class="stat-label">知识条目</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 -->
    <el-card class="quick-actions" shadow="never">
      <el-button type="primary" @click="goTo('/operation')">新增运营问题</el-button>
      <el-button type="success" @click="goTo('/meeting')">新增会议</el-button>
      <el-button type="warning" @click="goTo('/knowledge')">新增知识条目</el-button>
      <el-button @click="goTo('/todo')">查看待办</el-button>
    </el-card>

    <!-- 中间运营问题分布 -->
    <el-row :gutter="16" class="middle-row">
      <el-col :span="12">
        <el-card shadow="never" class="issue-progress-card">
          <template #header>
            <div class="card-header-title">运营问题处理进度</div>
          </template>
          <div class="issue-progress">
            <div class="progress-item">
              <span class="progress-label">待处理</span>
              <el-progress :percentage="issuePercent(stats.issue_pending, stats.issue_total)" status="exception" />
              <span class="progress-value">{{ stats.issue_pending }}</span>
            </div>
            <div class="progress-item">
              <span class="progress-label">处理中</span>
              <el-progress :percentage="issuePercent(stats.issue_processing, stats.issue_total)" status="warning" />
              <span class="progress-value">{{ stats.issue_processing }}</span>
            </div>
            <div class="progress-item">
              <span class="progress-label">已解决</span>
              <el-progress :percentage="issuePercent(stats.issue_resolved, stats.issue_total)" status="success" />
              <span class="progress-value">{{ stats.issue_resolved }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="summary-card">
          <template #header>
            <div class="card-header-title">工作概览</div>
          </template>
          <div class="summary-list">
            <div class="summary-item">
              <span>今日会议</span>
              <span class="summary-value">{{ stats.meeting_today }} 场</span>
            </div>
            <div class="summary-item">
              <span>运营问题总数</span>
              <span class="summary-value">{{ stats.issue_total }} 个</span>
            </div>
            <div class="summary-item">
              <span>超期运营问题</span>
              <span class="summary-value danger">{{ stats.issue_overdue }} 个</span>
            </div>
            <div class="summary-item">
              <span>知识库条目</span>
              <span class="summary-value">{{ stats.knowledge_total }} 条</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 下方列表 -->
    <el-row :gutter="16" class="list-row">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-header-title">
              <span>今日/近期待办</span>
              <el-button link type="primary" @click="goTo('/todo')">更多</el-button>
            </div>
          </template>
          <div v-if="recentTodos.length" class="list-items">
            <div
              v-for="item in recentTodos"
              :key="item.id"
              class="list-item"
              :class="{ overdue: item.is_overdue }"
            >
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <el-tag size="small" :type="priorityType(item.priority)">{{ item.priority }}</el-tag>
                <span>{{ item.due_date || '无截止日期' }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无待办" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-header-title">
              <span>近期会议</span>
              <el-button link type="primary" @click="goTo('/meeting')">更多</el-button>
            </div>
          </template>
          <div v-if="recentMeetings.length" class="list-items">
            <div v-for="item in recentMeetings" :key="item.id" class="list-item">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <el-tag size="small" type="info">{{ meetingTypeText(item.meeting_type) }}</el-tag>
                <span>{{ formatDateTime(item.start_time) || '时间待定' }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无会议" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-header-title">
              <span>待处理运营问题</span>
              <el-button link type="primary" @click="goTo('/operation')">更多</el-button>
            </div>
          </template>
          <div v-if="recentIssues.length" class="list-items">
            <div v-for="item in recentIssues" :key="item.id" class="list-item">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <el-tag size="small" :type="issueStatusType(item.status)">{{ issueStatusText(item.status) }}</el-tag>
                <el-tag size="small" :type="impactType(item.impact_level)">{{ item.impact_level }}</el-tag>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无运营问题" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dashboardApi } from '@/api/dashboard'
import { formatDateTime } from '@/utils/format'

const router = useRouter()
const loading = ref(false)

const stats = reactive({
  todo_total: 0,
  todo_today: 0,
  todo_overdue: 0,
  meeting_this_week: 0,
  meeting_today: 0,
  issue_total: 0,
  issue_pending: 0,
  issue_processing: 0,
  issue_resolved: 0,
  issue_overdue: 0,
  knowledge_total: 0,
})

const recentTodos = ref([])
const recentMeetings = ref([])
const recentIssues = ref([])

const loadData = async () => {
  loading.value = true
  try {
    const res = await dashboardApi.getDashboard()
    Object.assign(stats, res.stats)
    recentTodos.value = res.recent_todos || []
    recentMeetings.value = res.recent_meetings || []
    recentIssues.value = res.recent_issues || []
  } catch (error) {
    ElMessage.error('加载看板数据失败')
  } finally {
    loading.value = false
  }
}

const goTo = (path) => {
  router.push(path)
}

const issuePercent = (value, total) => {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

const priorityType = (priority) => {
  const map = { P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' }
  return map[priority] || 'info'
}

const meetingTypeText = (type) => {
  const map = {
    requirement_review: '需求评审',
    project_weekly: '项目周报',
    troubleshooting: '问题排查',
    training: '培训',
    other: '其他',
  }
  return map[type] || type
}

const issueStatusType = (status) => {
  const map = {
    pending: 'danger',
    processing: 'warning',
    verify: 'primary',
    resolved: 'success',
    closed: 'info',
    suspended: 'info',
  }
  return map[status] || 'info'
}

const issueStatusText = (status) => {
  const map = {
    pending: '待处理',
    processing: '处理中',
    verify: '待验证',
    resolved: '已解决',
    closed: '已关闭',
    suspended: '已挂起',
  }
  return map[status] || status
}

const impactType = (level) => {
  const map = { P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' }
  return map[level] || 'info'
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.home-view {
  padding: 20px;
}

.page-title {
  margin-bottom: 20px;
  font-size: 20px;
  font-weight: 600;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.stat-item {
  text-align: center;
  padding: 10px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #409eff;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-top: 6px;
}

.stat-warning .stat-value {
  color: #e6a23c;
}

.stat-danger .stat-value {
  color: #f56c6c;
}

.quick-actions {
  margin-bottom: 16px;
}

.middle-row {
  margin-bottom: 16px;
}

.card-header-title {
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.issue-progress {
  padding: 10px 0;
}

.progress-item {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
}

.progress-label {
  width: 60px;
  font-size: 14px;
  color: #606266;
}

.progress-value {
  width: 40px;
  text-align: right;
  font-weight: 600;
  color: #303133;
}

.summary-list {
  padding: 10px 0;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid #ebeef5;
  font-size: 14px;
}

.summary-item:last-child {
  border-bottom: none;
}

.summary-value {
  font-weight: 600;
  color: #409eff;
}

.summary-value.danger {
  color: #f56c6c;
}

.list-row {
  margin-bottom: 16px;
}

.list-items {
  max-height: 320px;
  overflow-y: auto;
}

.list-item {
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.list-item:last-child {
  border-bottom: none;
}

.list-item.overdue {
  background-color: #fff5f5;
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: #909399;
}
</style>
