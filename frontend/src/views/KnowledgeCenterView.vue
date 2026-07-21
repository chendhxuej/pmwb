<template>
  <div class="knowledge-center">
    <!-- 顶部 Tab 条：四个知识子模块快捷切换 -->
    <div class="kc-tabs">
      <div
        v-for="tab in tabs"
        :key="tab.path"
        class="kc-tab"
        :class="{ active: activePath === tab.path }"
        @click="go(tab.path)"
      >
        <el-icon class="kc-tab-ico"><component :is="tab.icon" /></el-icon>
        <span>{{ tab.label }}</span>
      </div>
    </div>

    <!-- 子模块内容 -->
    <div class="kc-body">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/knowledge-center/knowledge', label: '知识库', icon: 'Collection' },
  { path: '/knowledge-center/product-bible', label: '产品圣经', icon: 'Notebook' },
  { path: '/knowledge-center/notes', label: '知识沉淀', icon: 'Files' },
  { path: '/knowledge-center/sql-scripts', label: 'SQL脚本库', icon: 'Document' },
]

const activePath = computed(() => '/' + (route.path.split('/').slice(1, 3).join('/')))

const go = (path) => {
  if (activePath.value !== path) router.push(path)
}
</script>

<style scoped>
.knowledge-center {
  height: 100%;
}
.kc-tabs {
  display: flex;
  gap: 6px;
  padding: 0 24px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.kc-tab {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13.5px;
  font-weight: 600;
  padding: 9px 16px;
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
  height: calc(100% - 46px);
  overflow: auto;
}
</style>
