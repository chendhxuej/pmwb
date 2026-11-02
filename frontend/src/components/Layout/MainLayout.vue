<template>
  <el-container class="main-layout">
    <el-aside
      :width="collapsed ? '64px' : '220px'"
      class="sidebar"
      :class="{ collapsed, 'mobile-open': mobileOpen }"
    >
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
              <el-icon class="nav-icon">
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
            <el-icon class="nav-icon">
              <component :is="item.icon" />
            </el-icon>
            <span class="nav-text">{{ item.title }}</span>
            <el-badge v-if="item.badge && !collapsed" :value="item.badge" class="nav-badge" type="primary" />
          </button>
        </template>
      </nav>
    </el-aside>

    <!-- 移动端抽屉遮罩（样式在 @media ≤768 内，桌面态不会渲染出有效样式） -->
    <div
      v-if="mobileOpen"
      class="mobile-mask"
      @click="mobileOpen = false"
    />

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-icon" @click="handleCollapse">
            <Fold v-if="!collapsed" />
            <Expand v-else />
          </el-icon>
          <span class="header-title">{{ appStore.title }}</span>
        </div>
        <div class="header-right">
          <span class="user-name">{{ authStore.username || '产品经理' }}</span>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>

    <StaffAdminDrawer />
    <EnlargeInputDialog />
  </el-container>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { Fold, Expand, ArrowDown } from '@element-plus/icons-vue'
import StaffAdminDrawer from '@/components/Common/StaffAdminDrawer.vue'
import EnlargeInputDialog from '@/components/Common/EnlargeInputDialog.vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()
const { collapsed, toggleCollapsed } = appStore

// ── 移动端适配（mb-3）：≤768 侧边栏变 fixed 抽屉，桌面逻辑零改动 ──
// 用 matchMedia 监听断点（resize 事件在部分场景不触发，如 CDP 视口模拟），
// matchMedia 的 change 事件由媒体查询求值驱动，覆盖面更全。
const mobileOpen = ref(false)
const _mq = window.matchMedia('(max-width: 768px)')
function onViewportChange() {
  if (!_mq.matches) mobileOpen.value = false
}
_mq.addEventListener('change', onViewportChange)
window.addEventListener('resize', onViewportChange)
onBeforeUnmount(() => {
  _mq.removeEventListener('change', onViewportChange)
  window.removeEventListener('resize', onViewportChange)
})

function handleCollapse() {
  // 点击瞬间实时判定（不依赖事件是否触发过），保证移动端首次点开抽屉必生效
  if (window.matchMedia('(max-width: 768px)').matches) mobileOpen.value = !mobileOpen.value
  else toggleCollapsed()
}

// 侧边栏图标统一中性灰，仅在选中/悬停时点亮为强调蓝（单一蓝系纪律）
const menuItems = computed(() => {
  const top = route.matched[0]?.children || []
  return top
    .filter((child) => !child.meta?.hidden)
    .map((child) => {
      const base = {
        path: '/' + child.path,
        title: child.meta?.title || child.name,
        icon: child.meta?.icon,
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
  const firstChild = item.children?.[0]?.path
  const isOpen = s.has(item.path)
  const onFirst = route.path === firstChild
  if (isOpen && onFirst) {
    // 已展开且正处于第一个子页面 → 收起（提供关闭入口）
    s.delete(item.path)
  } else {
    // 展开二级菜单并默认打开第一个子页面
    s.add(item.path)
    if (firstChild && route.path !== firstChild) go(firstChild)
  }
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
  // 移动端选中后收起抽屉（实时判定，不依赖事件是否触发过）
  if (window.matchMedia('(max-width: 768px)').matches) mobileOpen.value = false
}

// 移动端路由变化自动收起抽屉（含二级菜单展开后自动跳首子页的场景）
watch(() => route.path, () => {
  if (window.matchMedia('(max-width: 768px)').matches) mobileOpen.value = false
})
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
  color: #64748b;
  transition: color 0.15s ease;
}
.nav-parent:hover .nav-icon,
.nav-parent.active .nav-icon {
  color: #2f6fed;
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

/* ── 移动端第四档（mb-3）：≤768 侧边栏变 fixed 抽屉，遮罩交互 ── */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 2001;
    width: 240px !important;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: none;
  }
  .sidebar.mobile-open {
    transform: translateX(0);
    box-shadow: 0 0 24px rgba(31, 45, 61, 0.18);
  }
  .mobile-mask {
    position: fixed;
    inset: 0;
    background: rgba(31, 45, 61, 0.4);
    z-index: 2000;
  }
  .header {
    padding: 0 14px;
  }
  .header-title {
    font-size: 15px;
  }
}
</style>
