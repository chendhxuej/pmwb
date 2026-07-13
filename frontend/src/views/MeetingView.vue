<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-title">会议管理</div>
      <el-button type="primary" @click="handleAdd">新增会议</el-button>
    </div>
    <div class="table-card">
      <el-empty description="暂无数据" />
    </div>
  </div>
</template>

<script setup>
const handleAdd = () => {
  console.log('新增会议')
}
</script>
