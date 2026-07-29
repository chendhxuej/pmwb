<template>
  <div class="stats-overview">
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in cards" :key="card.key">
        <div class="stat-card" @mouseenter="card.hover = true" @mouseleave="card.hover = false"
             :class="{ 'stat-card--hover': card.hover }">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-trend" v-if="card.trend != null">
            <span :class="card.trend >= 0 ? 'trend-up' : 'trend-down'">
              {{ card.trend >= 0 ? '↑' : '↓' }} {{ Math.abs(card.trend) }}%
            </span>
            <span class="trend-period">较昨日</span>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { getStats } from '@/api/mailCenter.js'

const stats = ref({
  todaySent: 0,
  weekSent: 0,
  successRate: 0,
  accountCount: 0,
  contactCount: 0,
  templateCount: 0,
  pendingAlerts: 0,
})

// 生成 KPI 卡
const cards = computed(() => [
  { key: 'todaySent', label: '今日发送', value: stats.value.todaySent, trend: null, hover: false },
  { key: 'weekSent', label: '本周发送', value: stats.value.weekSent, trend: null, hover: false },
  { key: 'successRate', label: '成功率', value: stats.value.successRate + '%', trend: null, hover: false },
  { key: 'accountCount', label: '邮件账号', value: stats.value.accountCount, trend: null, hover: false },
  { key: 'contactCount', label: '联系人', value: stats.value.contactCount, trend: null, hover: false },
  { key: 'templateCount', label: '邮件模板', value: stats.value.templateCount, trend: null, hover: false },
  { key: 'pendingAlerts', label: '待处理异常', value: stats.value.pendingAlerts, trend: null, hover: false },
])

async function fetchStats() {
  try {
    const resp = await getStats()
    const payload = resp.data?.data || resp.data || resp
    if (payload.todaySent !== undefined) {
      stats.value = payload
    }
  } catch (err) {
    console.error('获取统计失败', err)
  }
}

onMounted(fetchStats)
</script>

<style scoped>
.stats-overview {
  margin-bottom: 16px;
}
.stat-card {
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 8px;
  padding: 16px 20px;
  transition: all 0.25s ease;
  cursor: default;
}
.stat-card--hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--el-text-color-primary, #303133);
  line-height: 1.3;
}
.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 4px;
}
.stat-trend {
  margin-top: 6px;
  font-size: 12px;
}
.trend-up {
  color: #67c23a;
}
.trend-down {
  color: #f56c6c;
}
.trend-period {
  color: var(--el-text-color-placeholder, #c0c4cc);
  margin-left: 4px;
}
</style>
