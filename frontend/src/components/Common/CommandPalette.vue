<template>
  <Teleport to="body">
    <Transition name="cp-fade">
      <div v-if="modelValue" class="cp-overlay" @click="close">
        <div class="cp-panel" @click.stop>
          <div class="cp-head">
            <el-icon class="cp-search-icon"><Search /></el-icon>
            <input
              ref="inputRef"
              v-model="query"
              class="cp-input"
              type="text"
              placeholder="搜索页面 / 功能 / 路由…"
              @keydown.esc="close"
              @keydown.enter="selectActive"
              @keydown.down.prevent="move(1)"
              @keydown.up.prevent="move(-1)"
            />
            <div class="cp-kbd-hint">
              <span class="cp-kbd">ESC</span>关闭
            </div>
          </div>
          <div v-if="results.length" ref="listRef" class="cp-list">
            <div
              v-for="(item, i) in results"
              :key="item.path"
              class="cp-item"
              :class="{ active: activeIdx === i }"
              @click="go(item.path)"
              @mouseenter="activeIdx = i"
            >
              <el-icon class="cp-icon"><component :is="item.icon" /></el-icon>
              <div class="cp-meta">
                <div class="cp-title">{{ item.title }}</div>
                <div class="cp-path">{{ item.path }}</div>
              </div>
              <el-icon v-if="activeIdx === i" class="cp-enter"><ArrowRight /></el-icon>
            </div>
          </div>
          <div v-else class="cp-empty">
            未找到匹配页面，试试其他关键词
          </div>
          <div class="cp-foot">
            <span><span class="cp-kbd">↑</span><span class="cp-kbd">↓</span>选择</span>
            <span><span class="cp-kbd">↵</span>跳转</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'select'])

const router = useRouter()
const route = useRoute()
const query = ref('')
const activeIdx = ref(0)
const inputRef = ref(null)
const listRef = ref(null)

function close() {
  emit('update:modelValue', false)
}

// 聚合所有可见路由：meta.title 非空，非 hidden，去重 path
const commands = computed(() => {
  const seen = new Set()
  const out = []
  const walk = (list) => {
    if (!Array.isArray(list)) return
    for (const r of list) {
      if (r.meta?.hidden || !r.meta?.title || !r.path) {
        // 如果有 children 仍继续下探
        if (r.children) walk(r.children)
        continue
      }
      const path = r.path.startsWith('/') ? r.path : '/' + r.path
      if (!seen.has(path)) {
        seen.add(path)
        out.push({
          path,
          title: r.meta.title,
          icon: r.meta.icon || 'Link',
        })
      }
      if (r.children) walk(r.children)
    }
  }
  // route.matched[0] 为根，children 为一级菜单
  const root = router.options.routes.find((r) => r.path === '/') || router.options.routes[0]
  walk(root?.children || router.options.routes)
  return out
})

const results = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return commands.value
  return commands.value.filter((c) =>
    c.title.toLowerCase().includes(q) || c.path.toLowerCase().includes(q)
  )
})

watch(() => props.modelValue, async (open) => {
  if (open) {
    query.value = ''
    activeIdx.value = 0
    await nextTick()
    inputRef.value?.focus()
  }
})

watch(query, () => { activeIdx.value = 0 })

function move(dir) {
  const n = results.value.length
  if (!n) return
  activeIdx.value = (activeIdx.value + dir + n) % n
}

function go(path) {
  if (path && route.path !== path) router.push(path)
  emit('select', path)
  close()
}

function selectActive() {
  const item = results.value[activeIdx.value]
  if (item) go(item.path)
}
</script>

<style scoped>
.cp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(4px);
  z-index: 3000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 140px;
}
.cp-panel {
  width: 560px;
  max-width: calc(100vw - 32px);
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.cp-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-subtle);
}
.cp-search-icon {
  font-size: 18px;
  color: var(--text-muted);
}
.cp-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--text-primary);
  font-family: var(--font-display);
}
.cp-input::placeholder {
  color: var(--text-muted);
}
.cp-kbd-hint {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
.cp-kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  padding: 2px 6px;
  border-radius: 5px;
  background: var(--border-subtle);
  color: var(--text-secondary);
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
}
.cp-list {
  max-height: 320px;
  overflow-y: auto;
  padding: 6px;
}
.cp-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.12s ease;
}
.cp-item:hover,
.cp-item.active {
  background: var(--accent-soft);
}
.cp-icon {
  font-size: 18px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.cp-item.active .cp-icon {
  color: var(--accent);
}
.cp-meta {
  flex: 1;
  min-width: 0;
}
.cp-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.cp-path {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-top: 2px;
}
.cp-enter {
  font-size: 16px;
  color: var(--accent);
}
.cp-empty {
  padding: 32px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--text-muted);
}
.cp-foot {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 10px 14px;
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-app);
  font-size: 12px;
  color: var(--text-muted);
}
.cp-fade-enter-active,
.cp-fade-leave-active {
  transition: opacity 0.18s ease;
}
.cp-fade-enter-from,
.cp-fade-leave-to {
  opacity: 0;
}
</style>
