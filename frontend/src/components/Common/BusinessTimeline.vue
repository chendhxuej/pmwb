<template>
  <div class="biz-timeline" v-loading="loading">
    <!-- 顶部：统计 + 类型筛选 -->
    <div class="bt-bar">
      <div class="bt-summary">
        <span class="bt-domain">{{ data.domain_name || domainCode }}</span>
        <span class="bt-count">{{ data.total }} 个事件</span>
        <span class="bt-span" v-if="rangeText">{{ rangeText }}</span>
      </div>
      <div class="bt-filters">
        <span
          class="bt-chip"
          :class="{ active: !activeType }"
          @click="setType('')"
        >全部</span>
        <span
          v-for="t in data.event_types"
          :key="t.value"
          class="bt-chip"
          :class="{ active: activeType === t.value }"
          @click="setType(t.value)"
        >{{ t.label }} {{ t.count }}</span>
      </div>
    </div>

    <!-- 时间轴 -->
    <div class="bt-scroll">
      <template v-if="grouped.length">
        <div v-for="g in grouped" :key="g.month" class="bt-group">
          <div
            class="bt-month"
            :class="{ 'is-current': g.month === nowMonth, 'is-collapsed': !expandedMonths.has(g.month) }"
            @click="toggleMonth(g.month)"
          >
            <span class="bt-caret">{{ expandedMonths.has(g.month) ? '▾' : '▸' }}</span>
            <span class="bt-month-label">{{ g.month === nowMonth ? g.month + '（当前月）' : g.month }}</span>
            <span class="bt-month-count">{{ g.events.length }}</span>
          </div>
          <div v-show="expandedMonths.has(g.month)" class="bt-items">
            <div
              v-for="e in g.events"
              :key="e.link_id"
              class="bt-item"
              :class="`kind-${e.event_type}`"
            >
              <span class="bt-dot"></span>
              <div class="bt-content">
                <div class="bt-line1">
                  <span class="bt-date">{{ e.event_date || '未记日期' }}</span>
                  <span class="bt-kind" :class="`kind-${e.event_type}`">{{ e.event_label }}</span>
                  <span class="bt-title" :title="e.source_title || e.source_id">
                    {{ e.source_title || e.source_id }}
                  </span>
                </div>
                <div class="bt-line2" v-if="e.summary">{{ e.summary }}</div>
                <div class="bt-line3">
                  <span class="bt-src" v-if="e.source_id">{{ e.source_id }}</span>
                  <el-button
                    v-if="e.source_route"
                    plain
                    size="small"
                    @click="goSource(e)"
                  ><el-icon><Position /></el-icon>查看源记录</el-button>
                  <el-button
                    v-if="e.obsidian_path"
                    plain
                    type="primary"
                    size="small"
                    @click="openNote(e)"
                  ><el-icon><FolderOpened /></el-icon>打开笔记</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <el-empty
        v-else-if="!loading"
        :description="activeType ? '该类型暂无事件' : '该业务暂无关联事件，去需求/会议/运营工单沉淀后自动出现'"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Position, FolderOpened } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api/knowledge.js'

const props = defineProps({
  domainCode: { type: String, default: '' },
  limit: { type: Number, default: 200 },
})
const emit = defineEmits(['open-note'])

const router = useRouter()
const loading = ref(false)
const activeType = ref('')
const data = ref({ domain_name: '', total: 0, returned: 0, event_types: [], events: [] })

// 当前月（用于时间线默认展开）
const nowMonth = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
})
// 已展开的年月集合（默认仅当前月，其余折叠，手工展开）
const expandedMonths = ref(new Set())

const load = async () => {
  if (!props.domainCode) {
    data.value = { domain_name: '', total: 0, returned: 0, event_types: [], events: [] }
    return
  }
  loading.value = true
  try {
    const res = await knowledgeApi.getBusinessTimeline({
      domain_code: props.domainCode,
      limit: props.limit,
      event_type: activeType.value || undefined,
    })
    data.value = res || { domain_name: '', total: 0, returned: 0, event_types: [], events: [] }
  } catch (e) {
    ElMessage.error('加载业务时间线失败')
  } finally {
    loading.value = false
  }
}

const setType = (t) => {
  if (activeType.value === t) return
  activeType.value = t
  load()
}

// 按月分组（后端已按时间倒序返回，这里保持顺序）
const grouped = computed(() => {
  const out = []
  let cur = null
  for (const e of data.value.events || []) {
    const m = e.month || '未记日期'
    if (!cur || cur.month !== m) {
      cur = { month: m, events: [] }
      out.push(cur)
    }
    cur.events.push(e)
  }
  return out
})

// 数据加载后默认仅展开当前月（若当月无事件则展开最新月）；其余年月折叠，手工展开
watch(grouped, (g) => {
  if (expandedMonths.value.size === 0 && g.length) {
    const hasCurrent = g.some((x) => x.month === nowMonth.value)
    expandedMonths.value = new Set([hasCurrent ? nowMonth.value : g[0].month])
  }
}, { immediate: true })

const toggleMonth = (m) => {
  const s = new Set(expandedMonths.value)
  if (s.has(m)) s.delete(m)
  else s.add(m)
  expandedMonths.value = s
}

const rangeText = computed(() => {
  const dates = (data.value.events || []).map((e) => e.event_date).filter(Boolean)
  if (!dates.length) return ''
  return dates.length === 1 ? dates[0] : `${dates[dates.length - 1]} ~ ${dates[0]}`
})

const goSource = (e) => {
  if (!e.source_route) return
  router.push({ path: e.source_route, query: { keyword: e.source_id } })
}

const openNote = (e) => {
  if (!e.obsidian_path) return
  emit('open-note', e.obsidian_path)
}

watch(() => props.domainCode, () => {
  activeType.value = ''
  expandedMonths.value = new Set()
  load()
})

onMounted(load)

defineExpose({ reload: load })
</script>

<style scoped>
.biz-timeline {
  display: flex;
  flex-direction: column;
  min-height: 200px;
}
.bt-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 12px;
}
.bt-summary {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.bt-domain {
  font-size: var(--fs-md);
  font-weight: 700;
  color: var(--text-primary);
}
.bt-count {
  font-size: var(--fs-sm);
  color: var(--accent);
  font-weight: 600;
}
.bt-span {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}
.bt-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.bt-chip {
  font-size: var(--fs-xs);
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: all var(--transition-fast);
  user-select: none;
}
.bt-chip:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.bt-chip.active {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: var(--accent);
  font-weight: 600;
}
.bt-scroll {
  flex: 1;
  overflow: auto;
  max-height: 460px;
  padding-right: 4px;
}
.bt-group {
  margin-bottom: 6px;
}
.bt-month {
  display: flex;
  align-items: center;
  gap: 8px;
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--surface);
  padding: 6px 0 6px 2px;
  cursor: pointer;
  user-select: none;
  border-radius: 6px;
  transition: background 0.15s;
}
.bt-month:hover {
  background: var(--surface-soft);
}
.bt-month.is-current .bt-month-label {
  color: var(--accent);
}
.bt-month.is-collapsed {
  opacity: 0.78;
}
.bt-caret {
  font-size: 12px;
  color: var(--text-muted);
  width: 14px;
  display: inline-block;
  transition: transform 0.15s;
}
.bt-month-label {
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--text-primary);
  font-family: var(--font-mono);
}
.bt-month-count {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  background: var(--surface-soft);
  border-radius: 999px;
  padding: 1px 7px;
}
.bt-items {
  position: relative;
  padding-left: 16px;
}
.bt-items::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: var(--border);
  border-radius: 1px;
}
.bt-item {
  position: relative;
  padding: 7px 0 9px 10px;
}
.bt-dot {
  position: absolute;
  left: -16px;
  top: 13px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--text-muted);
  border: 2px solid var(--surface);
  box-shadow: 0 0 0 1px var(--border);
}
.bt-item.kind-requirement .bt-dot { background: var(--accent); }
.bt-item.kind-meeting .bt-dot { background: #8b5cf6; }
.bt-item.kind-operation .bt-dot { background: var(--warning); }
.bt-item.kind-deliverable .bt-dot,
.bt-item.kind-delivery .bt-dot { background: var(--success); }
.bt-item.kind-rule .bt-dot,
.bt-item.kind-manual .bt-dot { background: #0ea5e9; }

.bt-line1 {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.bt-date {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}
.bt-kind {
  font-size: var(--fs-xs);
  padding: 1px 8px;
  border-radius: 6px;
  background: var(--surface-soft);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  white-space: nowrap;
}
.bt-kind.kind-requirement { background: var(--accent-soft); color: var(--accent); border-color: transparent; }
.bt-kind.kind-meeting { background: #f3edff; color: #7c3aed; border-color: transparent; }
.bt-kind.kind-operation { background: var(--warning-soft); color: var(--warning); border-color: transparent; }
.bt-kind.kind-deliverable,
.bt-kind.kind-delivery { background: var(--success-soft); color: var(--success); border-color: transparent; }
.bt-title {
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 420px;
}
.bt-line2 {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin-top: 3px;
  line-height: 1.5;
}
.bt-line3 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 2px;
}
.bt-src {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}
</style>
