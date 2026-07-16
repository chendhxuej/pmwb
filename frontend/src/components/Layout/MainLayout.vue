<template>
  <el-container class="main-layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <span v-show="!collapsed">PMWB</span>
      </div>
        <el-menu
          :default-active="$route.path"
          :collapse="collapsed"
          :collapse-transition="false"
          router
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409eff"
        >
          <template v-for="item in menuItems" :key="item.path">
            <el-sub-menu v-if="item.children && item.children.length" :index="item.path">
              <template #title>
                <el-icon>
                  <component :is="item.icon" />
                </el-icon>
                <span>{{ item.title }}</span>
              </template>
              <el-menu-item
                v-for="sub in item.children"
                :key="sub.path"
                :index="sub.path"
              >
                <el-icon v-if="sub.icon">
                  <component :is="sub.icon" />
                </el-icon>
                <template #title>
                  <span>{{ sub.title }}</span>
                  <el-tag
                    v-if="sub.badge"
                    size="small"
                    type="info"
                    effect="plain"
                    class="menu-badge"
                  >{{ sub.badge }}</el-tag>
                </template>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.path">
              <el-icon>
                <component :is="item.icon" />
              </el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </template>
        </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-icon" @click="toggleCollapsed">
            <Fold v-if="!collapsed" />
            <Expand v-else />
          </el-icon>
          <span class="header-title">{{ appStore.title }}</span>
        </div>
        <div class="header-right">
          <span>产品经理</span>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores'

const route = useRoute()
const appStore = useAppStore()
const { collapsed, toggleCollapsed } = appStore

const menuItems = computed(() => {
  const top = route.matched[0]?.children || []
  return top.map((child) => {
    const base = {
      path: '/' + child.path,
      title: child.meta?.title || child.name,
      icon: child.meta?.icon,
    }
    if (child.children && child.children.length) {
      base.children = child.children
        .filter((c) => !c.meta?.hidden)
        .map((c) => ({
          path: '/' + child.path + '/' + c.path,
          title: c.meta?.title || c.name,
          icon: c.meta?.icon,
        }))
    }
    return base
  })
})
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
  transition: width 0.3s;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: bold;
  border-bottom: 1px solid #1f2d3d;
}

.header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
}

.collapse-icon {
  font-size: 20px;
  cursor: pointer;
  margin-right: 15px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
}

.main-content {
  background-color: #f5f7fa;
  padding: 0;
}

:deep(.el-menu) {
  border-right: none;
}

.menu-badge {
  margin-left: 8px;
  transform: scale(0.85);
}
</style>
