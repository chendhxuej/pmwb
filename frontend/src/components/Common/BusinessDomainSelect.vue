<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    clearable
    filterable
    :filter-method="onFilter"
    :loading="loading"
    :disabled="disabled"
    style="width: 100%"
    @update:model-value="onSelect"
  >
    <!-- 智能推荐（输入/外部 query 驱动：名称/编码/关键词/拼音首字母） -->
    <el-option-group v-if="recommended.length" label="智能推荐">
      <el-option
        v-for="d in recommended"
        :key="d.domain_code"
        :value="d.domain_code"
        :label="d.domain_name"
      />
    </el-option-group>
    <!-- 最近使用 -->
    <el-option-group v-if="recent.length" label="最近使用">
      <el-option
        v-for="d in recent"
        :key="d.domain_code"
        :value="d.domain_code"
        :label="d.domain_name"
      />
    </el-option-group>
    <!-- 全部分组（按查询过滤） -->
    <el-option-group
      v-for="group in displayGroups"
      :key="group.domain_code"
      :label="`${group.domain_name}（${group.children?.length || 0}个子类）`"
    >
      <el-option
        v-for="child in group.children"
        :key="child.domain_code"
        :value="child.domain_code"
        :label="child.domain_name"
      />
    </el-option-group>
  </el-select>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { loadBusinessDomains, subscribeBusinessDomains } from '@/api/basicData.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '选择业务领域' },
  // 录单标题等外部上下文，驱动智能推荐（关联便捷性优化 §3.11）
  query: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'change'])

const groups = ref([])
const flat = ref([])
const loading = ref(false)
const filterQuery = ref('')
const recentCodes = ref(loadRecent())

const RECENT_KEY = 'pmwb_recent_domains'

// 常见商客领域首字 -> 拼音首字母（覆盖绝大多数业务，其余返回空，不阻断）
const PINYIN_MAP = {
  '一': 'y', '网': 'w', '通': 't', '宽': 'k', '带': 'd', '安': 'a', '防': 'f',
  '商': 's', '客': 'k', '订': 'd', '单': 'd', '会': 'h', '议': 'y', '运': 'y',
  '营': 'y', '交': 'j', '付': 'f', '平': 'p', '台': 't', '工': 'g', '作': 'z',
  '协': 'x', '议': 'y', '调': 'd', '研': 'y', '知': 'z', '识': 's', '需': 'x',
  '求': 'q', '邮': 'y', '件': 'j', '系': 'x', '统': 't', '电': 'd', '子': 'z',
  '政': 'z', '企': 'q', '微': 'w', '智': 'z', '能': 'n', '组': 'z', '融': 'r',
  '合': 'h', '专': 'z', '线': 'x', '短': 'd', '信': 'x', '卫': 'w', '星': 'x',
  '国': 'g', '铁': 't', '际': 'j', '客': 'k', '户': 'h', '产': 'c', '品': 'p',
  '市': 's', '场': 'c', '区': 'q', '力': 'l', '销': 'x', '售': 's', '充': 'c',
  '值': 'z', '购': 'g', '景': 'j', '小': 'x', '企': 'q',
}

function pinyinInitials(name) {
  let s = ''
  for (const ch of (name || '')) s += PINYIN_MAP[ch] || ''
  return s.toLowerCase()
}

function loadRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
}
function saveRecent(codes) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(codes.slice(0, 5))) } catch { /* ignore */ }
}

function flatten(tree) {
  const out = []
  for (const g of (tree || [])) {
    out.push(g)
    if (g.children) out.push(...g.children)
  }
  return out
}

const DOMAIN_PARAMS = { tree: true }
const DOMAIN_KEY = JSON.stringify(DOMAIN_PARAMS)

const loadDomains = async (force = false) => {
  loading.value = true
  try {
    const tree = await loadBusinessDomains(DOMAIN_PARAMS, force)
    groups.value = tree
    flat.value = flatten(tree)
  } catch { /* 静默失败 */ } finally { loading.value = false }
}

const effectiveQuery = computed(() => (filterQuery.value || props.query || '').trim().toLowerCase())

function matchDomain(d, q) {
  if (!q) return true
  return (
    (d.domain_name || '').toLowerCase().includes(q) ||
    (d.domain_code || '').toLowerCase().includes(q) ||
    (d.match_keywords || '').toLowerCase().split(/[,，\s]+/).some((k) => k && q.includes(k.toLowerCase())) ||
    pinyinInitials(d.domain_name || '').includes(q)
  )
}

const recommended = computed(() =>
  effectiveQuery.value
    ? flat.value.filter((d) => matchDomain(d, effectiveQuery.value)).slice(0, 8)
    : []
)
const recent = computed(() =>
  recentCodes.value.map((c) => flat.value.find((d) => d.domain_code === c)).filter(Boolean)
)
const displayGroups = computed(() => {
  if (!effectiveQuery.value) return groups.value
  return groups.value
    .map((g) => ({ ...g, children: (g.children || []).filter((c) => matchDomain(c, effectiveQuery.value)) }))
    .filter((g) => matchDomain(g, effectiveQuery.value) || (g.children && g.children.length))
})

function onFilter(val) {
  filterQuery.value = val || ''
}

const onSelect = (val) => {
  if (val) {
    recentCodes.value = [val, ...recentCodes.value.filter((c) => c !== val)].slice(0, 5)
    saveRecent(recentCodes.value)
  }
  emit('update:modelValue', val)
  emit('change', val)
}

let unsub = null
onMounted(() => {
  loadDomains()
  unsub = subscribeBusinessDomains((key, data) => {
    if (key === DOMAIN_KEY) {
      groups.value = data
      flat.value = flatten(data)
    }
  })
})
onUnmounted(() => { if (unsub) unsub() })
</script>
