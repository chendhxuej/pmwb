<template>
  <el-container class="main-layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar" :class="{ collapsed }">
      <div class="logo">
        <span v-show="!collapsed" class="logo-mark">PMWB</span>
        <span v-show="collapsed" class="logo-dot">P</span>
      </div>

      <nav class="side-nav">
        <template v-for="item in menuItems" :key="item.path">
          <!-- 一级父菜单（含子菜单）：可点击展开/收起 -->
          <div v-if="item.children && item.children.length" class="nav-block">
            <button
              class="nav-parent"
              :class="{ active: isParentActive(item) }"
              @click="toggleParent(item)"
              :title="collapsed ? item.title : ''"
            >
              <span class="nav-bar" v-show="isParentActive(item)" />
              <el-icon class="nav-icon" :style="{ color: item.color }">
                <component :is="item.icon" />
              </el-icon>
              <span class="nav-text">{{ item.title }}</span>
              <el-badge v-if="item.badge && !collapsed" :value="item.badge" class="nav-badge" type="primary" />
              <el-icon v-if="!collapsed" class="nav-caret" :class="{ open: isExpanded(item.path) }">
                <ArrowDown />
              </el-icon>
            </button>

            <!-- 二级菜单：缩进 + 圆点，弱化处理，与一级明显区分 -->
            <transition name="nav-expand">
              <div v-show="isExpanded(item.path) && !collapsed" class="nav-children">
                <button
                  v-for="sub in item.children"
                  :key="sub.path"
                  class="nav-child"
                  :class="{ active: isActive(sub.path) }"
                  @click="go(sub.path)"
                  :title="collapsed ? sub.title : ''"
                >
                  <span class="nav-dot" />
                  <span class="nav-text">{{ sub.title }}</span>
                  <el-badge v-if="sub.badge" :value="sub.badge" class="nav-badge" type="primary" />
                </button>
              </div>
            </transition>
          </div>

          <!-- 单级菜单项（无子菜单）：与一级父项同款卡片样式 -->
          <button
            v-else
            class="nav-parent"
            :class="{ active: isActive(item.path) }"
            @click="go(item.path)"
            :title="collapsed ? item.title : ''"
          >
            <span class="nav-bar" v-show="isActive(item.path)" />
            <el-icon class="nav-icon" :style="{ color: item.color }">
              <component :is="item.icon" />
            </el-icon>
            <span class="nav-text">{{ item.title }}</span>
            <el-badge v-if="item.badge && !collapsed" :value="item.badge" class="nav-badge" type="primary" />
          </button>
        </template>
      </nav>
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
          <span class="user-name">产品经理</span>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>

    <StaffAdminDrawer />
  </el-container>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores'
import { Fold, Expand, ArrowDown } from '@element-plus/icons-vue'
import StaffAdminDrawer from '@/components/Common/StaffAdminDrawer.vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const { collapsed, toggleCollapsed } = appStore

// 彩色图标调色板（按菜单顺序循环分配，保证视觉一致性）
const iconPalette = [
  '#2f6fed', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#ec4899', '#64748b',
]

const menuItems = computed(() => {
  const top = route.matched[0]?.children || []
  return top
    .filter((child) => !child.meta?.hidden)
    .map((child, idx) => {
      const color = iconPalette[idx % iconPalette.length]
      const base = {
        path: '/' + child.path,
        title: child.meta?.title || child.name,
        icon: child.meta?.icon,
        color,
        badge: child.meta?.badge,
      }
      if (child.children && child.children.length) {
        base.children = child.children
          .filter((c) => !c.meta?.hidden)
          .map((c) => ({
            path: '/' + child.path + '/' + c.path,
            title: c.meta?.title || c.name,
            badge: c.meta?.badge,
          }))
      }
      return base
    })
})

// —— 二级菜单展开状态（手动控制）——
const expanded = ref(new Set())

function isExpanded(path) {
  return expanded.value.has(path)
}

function toggleParent(item) {
  // 折叠态下点击父图标 → 直接进入第一个子页面
  if (collapsed.value) {
    if (item.children && item.children.length) go(item.children[0].path)
    else go(item.path)
    return
  }
  const s = new Set(expanded.value)
  if (s.has(item.path)) s.delete(item.path)
  else s.add(item.path)
  expanded.value = s
}

function isActive(path) {
  return route.path === path || route.path.startsWith(path + '/')
}

function isParentActive(item) {
  if (isActive(item.path)) return true
  return (item.children || []).some((c) => isActive(c.path))
}

// 进入子页面时自动展开其所属父菜单（保证上下文可见）
function ensureActiveExpanded() {
  for (const item of menuItems.value) {
    if (item.children && item.children.some((c) => isActive(c.path)) && !expanded.value.has(item.path)) {
      const s = new Set(expanded.value)
      s.add(item.path)
      expanded.value = s
    }
  }
}
watch(() => route.path, ensureActiveExpanded, { immediate: true })

function go(path) {
  if (route.path !== path) router.push(path)
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

/* —— 浅色极简侧边栏 —— */
.sidebar {
  background-color: #ffffff;
  border-right: 1px solid #eef0f4;
  transition: width 0.3s;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid #f1f3f7;
  flex-shrink: 0;
}
.logo-mark {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #2f6fed, #06b6d4);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.logo-dot {
  font-size: 18px;
  font-weight: 800;
  color: #2f6fed;
  margin: 0 auto;
}

.side-nav {
  flex: 1;
  overflow-y: auto;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
}

.nav-block {
  margin-bottom: 2px;
}

/* —— 一级菜单项（父节点 / 单级项 共用）—— */
.nav-parent {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: #1f2d3d;
  font-size: 14px;
  font-weight: 600; /* 一级加粗，层级感强 */
  font-family: inherit;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.nav-parent:hover {
  background: #f4f7fc;
  color: #1f2d3d;
}
.nav-parent.active {
  background: #eaf1ff;
  border-color: #d4e2ff;
  color: #2f6fed;
}

/* 选中态左侧蓝色彩条 */
.nav-bar {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 58%;
  border-radius: 0 3px 3px 0;
  background: #2f6fed;
}

.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
}
.nav-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-badge {
  flex-shrink: 0;
  margin-left: 2px;
}

/* 展开/收起箭头 */
.nav-caret {
  font-size: 14px;
  color: #94a3b8;
  flex-shrink: 0;
  transition: transform 0.2s ease, color 0.2s ease;
}
.nav-caret.open {
  transform: rotate(180deg);
  color: #2f6fed;
}

/* —— 二级菜单项（子节点，明显弱于一级）—— */
.nav-children {
  padding: 2px 0 4px;
}
.nav-child {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px 8px 40px; /* 大缩进，体现从属关系 */
  margin-bottom: 2px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b; /* 浅灰，弱化 */
  font-size: 13px;
  font-weight: 400; /* 小一号、非粗体 */
  font-family: inherit;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease, color 0.15s ease;
}
.nav-child:hover {
  background: #f4f7fc;
  color: #1f2d3d;
}
.nav-child.active {
  background: #eaf1ff;
  color: #2f6fed;
  font-weight: 500;
}

/* 子项层级圆点（替代彩色图标，弱化视觉） */
.nav-dot {
  position: absolute;
  left: 26px;
  top: 50%;
  transform: translateY(-50%);
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #cbd5e1;
  flex-shrink: 0;
}
.nav-child.active .nav-dot {
  background: #2f6fed;
}

/* 展开过渡：淡入 + 轻微上移 */
.nav-expand-enter-active,
.nav-expand-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.nav-expand-enter-from,
.nav-expand-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 折叠态：仅图标居中，隐藏文字/箭头/二级 */
.sidebar.collapsed .nav-children {
  display: none;
}
.sidebar.collapsed .nav-caret {
  display: none;
}
.sidebar.collapsed .nav-parent {
  justify-content: center;
  padding: 10px 0;
}
.sidebar.collapsed .nav-text,
.sidebar.collapsed .nav-badge,
.sidebar.collapsed .nav-dot {
  display: none;
}

/* —— 顶栏 —— */
.header {
  background-color: #ffffff;
  border-bottom: 1px solid #eef0f4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.header-left {
  display: flex;
  align-items: center;
}
.collapse-icon {
  font-size: 20px;
  cursor: pointer;
  margin-right: 15px;
  color: #64748b;
  transition: color 0.15s ease;
}
.collapse-icon:hover {
  color: #2f6fed;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2d3d;
}
.header-right {
  color: #64748b;
  font-size: 14px;
}
.user-name {
  font-weight: 500;
  color: #475569;
}

.main-content {
  background-color: #f5f7fa;
  padding: 0;
}
</style>
