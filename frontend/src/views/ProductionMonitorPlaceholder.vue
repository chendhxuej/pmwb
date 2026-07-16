<template>
  <div class="monitor-placeholder">
    <el-empty description="生产监控模块建设中">
      <template #description>
        <div class="ph-title">生产监控</div>
        <div class="ph-desc">
          实时指标、告警、链路监控等能力后续单独规划与开发，<br />
          当前运营监控的「生产问题分析」工单已承接生产运营问题的发现与闭环跟踪。
        </div>
      </template>
      <el-button type="primary" @click="goOperation">前往「生产问题分析」工单</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
const goOperation = () => router.push('/operation/prod')
</script>

<style scoped>
.monitor-placeholder {
  padding: 60px 20px;
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ph-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}
.ph-desc {
  font-size: 14px;
  color: #909399;
  line-height: 1.8;
}
</style>
