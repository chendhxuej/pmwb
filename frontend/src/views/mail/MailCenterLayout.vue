<template>
  <div class="mail-center-layout">
    <div class="page-header">
      <h2>邮件中心</h2>
      <span class="link-hint">统一邮件中心管理</span>
    </div>
    <MailStatsOverview />
    <el-tabs :model-value="$route.path" @tab-click="onTabClick" class="mail-tabs">
      <el-tab-pane label="发送日志" name="/mail-center/logs" />
      <el-tab-pane label="邮件账号" name="/mail-center/accounts" />
      <el-tab-pane label="通讯录" name="/mail-center/contacts" />
      <el-tab-pane label="联系人分组" name="/mail-center/groups" />
      <el-tab-pane label="邮件模板" name="/mail-center/templates" />
    </el-tabs>
    <div class="tab-content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import MailStatsOverview from './MailStatsOverview.vue'

const router = useRouter()

function onTabClick(tab) {
  router.push(tab.props.name)
}
</script>

<style scoped>
.mail-center-layout {
  padding: 16px;
}
.page-header {
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 18px;
  color: var(--text-primary, #303133);
}
.link-hint {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
.mail-tabs {
  margin-bottom: 16px;
}
.tab-content {
  min-height: 400px;
}
</style>
