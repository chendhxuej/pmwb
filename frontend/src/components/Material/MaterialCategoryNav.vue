<template>
  <div class="material-cat-nav">
    <div class="mcn-head">
      <div class="mcn-head-left">
        <span class="mcn-title">材料分类</span>
        <span class="mcn-meta">{{ l1List.length }} 类 · 共 {{ totalAll }} 份</span>
      </div>
      <el-button link type="primary" size="small" @click="$emit('manage')">
        <el-icon><Setting /></el-icon> 管理分类
      </el-button>
    </div>

    <!-- 一级卡片行：自动换行，全部可见（超 ~3 行再考虑折叠，本期不做） -->
    <div class="mcn-l1">
      <div
        v-for="c in l1Cards"
        :key="c.key"
        class="cat-l1-card"
        :class="{ 'is-active': c.active, 'is-open': c.open, 'is-disabled': c.off }"
        :data-cat-key="c.key"
        @click="pick(c.id)"
      >
        <div class="cat-l1-name" :title="c.name">
          <span class="cat-l1-name-text">{{ c.name }}</span>
          <span v-if="c.off" class="cat-l1-off">停用</span>
        </div>
        <div class="cat-l1-num">
          {{ c.count }}<span class="cat-l1-unit">份</span><span v-if="c.kids" class="cat-l1-sub"> · {{ c.kids }} 子类</span>
        </div>
      </div>
    </div>

    <!-- 二级胶囊行：跟随选中一级联动，数量不定故单行横向滚动，高度固定 -->
    <div class="mcn-l2-row">
      <template v-if="l2Parent">
        <button class="mcn-crumb" type="button" @click="pick(l2Parent.id)">{{ l2Parent.name }} ›</button>
        <div v-if="l2Parent.children.length" ref="l2Ref" class="mcn-l2">
          <div
            class="cat-l2-chip"
            :class="{ 'is-active': categoryId === l2Parent.id }"
            @click="pick(l2Parent.id)"
          >
            不限<span class="cat-l2-count">{{ l2Parent.material_count }}</span>
          </div>
          <div
            v-for="k in l2Parent.children"
            :key="k.id"
            class="cat-l2-chip"
            :class="{ 'is-active': categoryId === k.id, 'is-disabled': !k.enabled }"
            @click="pick(k.id)"
          >
            <span>{{ k.name }}</span>
            <span v-if="!k.enabled" class="cat-l1-off">停用</span>
            <span class="cat-l2-count">{{ k.material_count }}</span>
          </div>
        </div>
        <span v-else class="mcn-l2-hint">该分类无子分类，直接展示其下材料</span>
      </template>
      <span v-else class="mcn-l2-hint">选择上方任一一级分类，此处联动展开其子分类</span>
    </div>
  </div>
</template>

<script setup>
/**
 * 材料分类顶部横向导航（受控组件，不发起任何请求）。
 * 口径：一级卡计数 = 后端 material_count（含子孙），与点击后列表查询同口径；
 *      「全部」= Σ一级 material_count + 未分类（前端派生，替换旧树里用 total 的不纯口径）。
 * 边界：只渲染两级（与 pmwb_material_category 两级设计一致）；选中态单一真相源为 categoryId
 *      （null=全部、-1=未分类、>0=分类 id），改名/排序/移动父级经 computed 派生自动同步。
 */
import { ref, computed, watch, nextTick } from 'vue'
import { Setting } from '@element-plus/icons-vue'

const props = defineProps({
  categories: { type: Array, default: () => [] },
  categoryId: { type: Number, default: null },
  uncategorizedCount: { type: Number, default: 0 },
})
const emit = defineEmits(['update:categoryId', 'manage'])

// 排序唯一规则：sort_order asc → id asc（管理弹窗改 sort_order 后经 computed 即时重排）
const byOrder = (a, b) => (a.sort_order - b.sort_order) || (a.id - b.id)

const l1List = computed(() => props.categories.filter((c) => !c.parent_id).slice().sort(byOrder))

const totalAll = computed(
  () => l1List.value.reduce((s, c) => s + (c.material_count || 0), 0) + props.uncategorizedCount
)

// 选中反查：categoryId 直指一级 → l1+child=null；指向二级 → l1=其父、child=该二级
const selectedInfo = computed(() => {
  const id = props.categoryId
  if (id == null || id === -1) return { l1: null, child: null }
  const direct = l1List.value.find((c) => c.id === id)
  if (direct) return { l1: direct, child: null }
  for (const c of l1List.value) {
    const k = props.categories.find((x) => x.id === id && x.parent_id === c.id)
    if (k) return { l1: c, child: k }
  }
  return { l1: null, child: null }
})

const l1Cards = computed(() => {
  const info = selectedInfo.value
  const cards = [
    { key: 'all', id: null, name: '全部', count: totalAll.value, kids: 0, active: props.categoryId == null, open: false, off: false },
    { key: 'unc', id: -1, name: '未分类', count: props.uncategorizedCount, kids: 0, active: props.categoryId === -1, open: false, off: false },
  ]
  l1List.value.forEach((c) => {
    cards.push({
      key: 'c' + c.id,
      id: c.id,
      name: c.name,
      count: c.material_count || 0,
      kids: c.children_count || 0,
      enabled: c.enabled !== false,
      active: props.categoryId === c.id,
      open: !!info.child && info.l1 && info.l1.id === c.id,
      off: c.enabled === false,
    })
  })
  return cards
})

const l2Parent = computed(() => {
  const l1 = selectedInfo.value.l1
  if (!l1) return null
  const children = props.categories.filter((c) => c.parent_id === l1.id).slice().sort(byOrder)
  return { ...l1, children }
})

function pick(id) {
  if (id === props.categoryId || (id == null && props.categoryId == null)) return
  emit('update:categoryId', id)
}

// 选中胶囊滚入可视区：只平移容器 scrollLeft，禁 scrollIntoView（避免带动整页滚动）
const l2Ref = ref(null)
watch(
  () => props.categoryId,
  async () => {
    await nextTick()
    const box = l2Ref.value
    if (!box) return
    const el = box.querySelector('.cat-l2-chip.is-active')
    if (!el) return
    const target = el.offsetLeft - box.clientWidth / 2 + el.offsetWidth / 2
    box.scrollTo({ left: Math.max(0, target), behavior: 'smooth' })
  }
)
</script>

<style scoped>
.material-cat-nav {
  background: var(--surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 12px 16px 10px;
  margin-bottom: 14px;
}
.mcn-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.mcn-head-left { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.mcn-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.mcn-meta { font-size: 11.5px; color: var(--text-muted); }

/* ── 一级卡片行 ── */
.mcn-l1 { display: flex; flex-wrap: wrap; gap: 8px; }
.cat-l1-card {
  min-width: 132px; max-width: 176px; padding: 8px 12px; cursor: pointer;
  background: var(--bg-app);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);
  transition: transform var(--transition-fast), border-color var(--transition-fast),
              box-shadow var(--transition-fast), background var(--transition-fast);
}
.cat-l1-card:hover { border-color: var(--accent); transform: translateY(-1px); }
.cat-l1-card.is-active {
  background: var(--accent-soft); border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.cat-l1-card.is-open { border-color: var(--accent); }
.cat-l1-card.is-disabled { opacity: .55; }
.cat-l1-name {
  display: flex; align-items: center; gap: 4px; min-width: 0;
  font-size: 12.5px; font-weight: 600; color: var(--text-primary);
}
.cat-l1-name-text { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-l1-card.is-active .cat-l1-name { color: var(--accent); }
.cat-l1-off {
  flex-shrink: 0; font-size: 11px; font-weight: 400; line-height: 1;
  padding: 2px 5px; border-radius: 999px;
  background: var(--border-subtle); color: var(--text-muted);
}
.cat-l1-num {
  margin-top: 3px; display: flex; align-items: baseline; gap: 3px;
  font-family: var(--font-mono); font-size: 15px; font-weight: 800;
  line-height: 1; color: var(--text-primary);
}
.cat-l1-card.is-active .cat-l1-num { color: var(--accent); }
.cat-l1-unit { font-family: var(--font-display); font-size: 11px; font-weight: 600; color: var(--text-muted); }
.cat-l1-sub { font-family: var(--font-display); font-size: 11px; font-weight: 400; color: var(--text-muted); }

/* ── 二级胶囊行 ── */
.mcn-l2-row {
  display: flex; align-items: center; gap: 10px;
  margin-top: 10px; padding-top: 9px; border-top: 1px solid var(--border-subtle);
  min-height: 34px;
}
.mcn-crumb {
  flex-shrink: 0; border: none; background: none; padding: 0; cursor: pointer;
  font-size: 12px; font-weight: 600; color: var(--text-secondary);
}
.mcn-crumb:hover { color: var(--accent); }
.mcn-l2 {
  display: flex; gap: 6px; overflow-x: auto; min-width: 0;
  padding-bottom: 2px; scrollbar-width: thin;
}
.mcn-l2::-webkit-scrollbar { height: 4px; }
.mcn-l2::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.cat-l2-chip {
  flex-shrink: 0; display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 12px; border-radius: 999px; cursor: pointer;
  font-size: 12px; color: var(--text-primary);
  background: transparent; border: 1px solid var(--border-subtle);
  transition: border-color var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}
.cat-l2-chip:hover { border-color: var(--accent); color: var(--accent); }
.cat-l2-chip.is-active {
  background: var(--accent-soft); border-color: var(--accent);
  color: var(--accent); font-weight: 600;
}
.cat-l2-chip.is-disabled { opacity: .55; }
.cat-l2-count { font-family: var(--font-mono); font-size: 11px; font-weight: 400; color: var(--text-muted); }
.cat-l2-chip.is-active .cat-l2-count { color: var(--accent); }
.mcn-l2-hint { font-size: 11.5px; color: var(--text-muted); }

/* ── 响应式：1400 / 1100 / 960 / 768 ── */
@media (max-width: 1400px) {
  .cat-l1-card { min-width: 120px; }
}
@media (max-width: 1100px) {
  .cat-l1-card { padding: 7px 10px; }
  .cat-l1-sub { display: none; }
}
@media (max-width: 960px) {
  .cat-l1-card { min-width: 96px; }
}
@media (max-width: 768px) {
  .mcn-l2 { flex-wrap: wrap; overflow-x: visible; }
}
</style>
