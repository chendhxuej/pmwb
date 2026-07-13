<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-title">运营监控</div>
      <el-button type="primary" @click="handleAdd">新增问题</el-button>
    </div>
    <div class="table-card">
      <el-empty description="暂无数据" />
    </div>
  </div>
</template>

<script setup>
const handleAdd = () => {
  console.log('新增问题')
}
</script>
