<template>
  <div class="pb-placeholder">
    <div class="pb-placeholder-card">
      <div class="pb-placeholder-icon">
        <el-icon :size="28"><Calendar /></el-icon>
      </div>
      <h2>{{ title }}</h2>
      <p class="pb-placeholder-lead">此页由后续子任务交付，当前为结构占位，不影响版本计划功能使用。</p>
      <div class="pb-placeholder-meta">
        <span class="pm-tag">待交付 {{ taskId }}</span>
        <span>方案 v1.2 · 5 页结构已定稿</span>
      </div>
      <el-alert type="info" :closable="false" show-icon class="pb-placeholder-alert">
        <template #title>交互原型可直接预览</template>
        <template #default>
          完整交互见 <code>docs/排版管理_页面Demo.html</code>（准入模拟器 / 自动顺延 / 手工例外放行 / 批量督办 / 反馈同步均已可点）。
        </template>
      </el-alert>
      <el-button type="primary" plain @click="goVersions">去看已交付的「版本计划」</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Calendar } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const title = computed(() => route.meta?.title || '排版管理')
const taskId = computed(() => route.meta?.pb || 'pb-2 ~ pb-8')
const goVersions = () => router.push('/paiban/versions')
</script>

<style scoped>
.pb-placeholder { padding: 24px; }
.pb-placeholder-card {
  max-width: 720px;
  margin: 0 auto;
  padding: 40px 36px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  text-align: center;
}
.pb-placeholder-icon {
  width: 56px; height: 56px; margin: 0 auto 16px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--accent-soft); color: var(--accent);
}
.pb-placeholder-card h2 { margin: 0 0 10px; font-size: 20px; color: var(--text-primary); }
.pb-placeholder-lead { margin: 0 0 16px; color: var(--text-secondary); line-height: 1.7; }
.pb-placeholder-meta {
  display: flex; gap: 12px; justify-content: center; align-items: center;
  margin-bottom: 20px; font-size: 13px; color: var(--text-muted);
}
.pm-tag {
  padding: 3px 10px; border-radius: 999px;
  background: var(--warning-soft); color: var(--warning);
}
.pb-placeholder-alert { margin-bottom: 20px; text-align: left; }
code { font-family: var(--font-mono); font-size: 12px; }
</style>
