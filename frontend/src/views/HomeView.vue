<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-title">首页看板</div>
    </div>
    <el-row :gutter="20">
      <el-col :span="6" v-for="(item, index) in stats" :key="index">
        <el-card shadow="hover">
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const stats = ref([
  { label: '需求总数', value: 0 },
  { label: '在途工单', value: 0 },
  { label: '未闭环问题', value: 0 },
  { label: '本周会议', value: 0 },
])
</script>

<style scoped>
.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}
.stat-label {
  margin-top: 10px;
  color: #606266;
}
</style>
