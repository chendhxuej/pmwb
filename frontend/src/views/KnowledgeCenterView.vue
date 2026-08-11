<template>
  <div class="knowledge-center">
    <!-- 子路由视图（产品圣经等） -->
    <template v-if="isChildRoute">
      <router-view />
    </template>

    <!-- 默认三视图（无子路由时） -->
    <template v-else>
      <!-- 三视图 Tab 条 -->
      <div class="kc-tabs">
        <div
          v-for="tab in tabs"
          :key="tab.key"
          class="kc-tab"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <el-icon class="kc-tab-ico"><component :is="tab.icon" /></el-icon>
          <span>{{ tab.label }}</span>
        </div>
      </div>

      <!-- 视图内容 -->
      <div class="kc-body">
        <!-- ── 视图1: 业务全景 HUB ── -->
        <div v-show="activeTab === 'hub'" class="kc-panel">
          <HubPanel @open-note="openObsidianNote" />
        </div>

        <!-- ── 视图2: 知识检索 ── -->
        <div v-show="activeTab === 'search'" class="kc-panel">
          <SearchPanel />
        </div>

        <!-- ── 视图3: 沉淀向导 ── -->
        <div v-show="activeTab === 'sediment'" class="kc-panel">
          <SedimentPanel />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isChildRoute = computed(() => route.path !== '/knowledge-center' && route.path !== '/knowledge-center/')
import { ElMessage } from 'element-plus'
import HubPanel from './KnowledgeCenter/HubPanel.vue'
import SearchPanel from './KnowledgeCenter/SearchPanel.vue'
import SedimentPanel from './KnowledgeCenter/SedimentPanel.vue'

const activeTab = ref('hub')

const tabs = [
  { key: 'hub', label: '业务全景', icon: 'DataBoard' },
  { key: 'search', label: '知识检索', icon: 'Search' },
  { key: 'sediment', label: '沉淀向导', icon: 'Upload' },
]

const openObsidianNote = (path) => {
  if (!path) return
  window.open(`obsidian://open?vault=知识图谱&file=${encodeURIComponent(path)}`, '_blank')
}
</script>

<style scoped>
.knowledge-center {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.kc-tabs {
  display: flex;
  gap: 6px;
  padding: 0 24px;
  margin-bottom: 4px;
  flex-shrink: 0;
}
.kc-tab {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13.5px;
  font-weight: 600;
  padding: 9px 20px;
  border-radius: 11px 11px 0 0;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
}
.kc-tab:hover {
  color: var(--accent);
  background: var(--border-subtle);
}
.kc-tab.active {
  color: var(--accent);
  background: var(--accent-soft);
  border-bottom-color: var(--accent);
}
.kc-tab-ico {
  font-size: 15px;
}
.kc-body {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}
.kc-panel {
  height: 100%;
  overflow: auto;
  padding: 16px 24px;
}
</style>
