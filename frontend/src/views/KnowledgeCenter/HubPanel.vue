<template>
  <div class="hub-panel">
    <!-- 顶部：标题 + 搜索 + 操作（原「首页/知识中心」面包屑已按需求移除） -->
    <div class="hub-header">
      <div class="hub-header-titles">
        <h3 class="hub-title">知识中心 · 总览驾驶舱</h3>
        <span class="hub-subtitle">业务领域全景 · 主笔记人工维护 · 场景规则自动沉淀</span>
      </div>

      <!-- 全局搜索（智能推荐领域） -->
      <div class="hub-search-wrap">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索知识 / 输入领域名（如「一网通」）看智能推荐…"
          clearable
          prefix-icon="Search"
          style="width: 320px"
          @input="onSearchInput"
          @focus="showSearchHint = true"
          @blur="hideSearchHint"
          @select="onSearchSelect"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
          <template #suffix>
            <span v-if="searchKeyword" class="search-hint-count">{{ suggestCount }} 个相关领域</span>
          </template>
        </el-input>
        <div v-if="showSearchHint && searchSuggestions.length" class="search-hint">
          <div class="hint-title">智能推荐领域（关键词 + 名称 + 编码 + 首字母）</div>
          <div
            v-for="s in searchSuggestions"
            :key="s.domain_code"
            class="hint-row"
            @click="onSearchSelect(s)"
          >
            <span class="hint-name">{{ s.domain_name }}</span>
            <span class="hint-group" :style="tagStyle(s.domain_group)">{{ s.domain_group }}</span>
            <span class="hint-why">{{ s.reason || '匹配' }}</span>
          </div>
          <div v-if="!searchSuggestions.length && searchKeyword" class="hint-empty">未匹配到相关领域</div>
        </div>
      </div>

      <div class="hub-header-actions">
        <el-button plain @click="goManage">
          <el-icon><SetUp /></el-icon>
          <span>业务领域管理</span>
        </el-button>
        <el-button plain type="success" :loading="sedimentLoading" @click="sedimentAllRules">
          <el-icon><MagicStick /></el-icon>
          <span>规则沉淀</span>
        </el-button>
        <el-button type="primary" :loading="syncLoading" @click="syncAll">
          <el-icon><Refresh /></el-icon>
          <span>一键同步全部主笔记</span>
        </el-button>
      </div>
    </div>

    <!-- 子导航 -->
    <div class="hub-subnav">
      <router-link to="/knowledge-center/hub" class="subnav-link" :class="{ active: $route.path === '/knowledge-center/hub' }">总览驾驶舱</router-link>
      <router-link to="/knowledge-center/timeline" class="subnav-link" :class="{ active: $route.path === '/knowledge-center/timeline' }">全局时间线</router-link>
      <router-link to="/knowledge-center/relations" class="subnav-link" :class="{ active: $route.path === '/knowledge-center/relations' }">智能关联</router-link>
      <router-link to="/knowledge-center/manage" class="subnav-link" :class="{ active: $route.path === '/knowledge-center/manage' }">领域管理</router-link>
    </div>

    <!-- 主体：左主区（领域全景）+ 右信息栏（动态 / 待补 / 规则沉淀） -->
    <div class="hub-main" :class="{ 'detail-open': selectedDomain }">
      <!-- ========== 左：主区 ========== -->
      <div class="hub-col hub-col-main">
        <!-- KPI 条 -->
        <div class="kpi-strip">
          <div class="kpi-card">
            <div class="kpi-value">{{ stats.total }}</div>
            <div class="kpi-label">业务领域总数</div>
            <div class="kpi-delta">{{ groupNames.length }} 个分组</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value">{{ stats.coveragePercent }}%</div>
            <div class="kpi-label">领域覆盖率</div>
            <div class="kpi-delta">主笔记 {{ stats.withMainNote }}/{{ stats.total }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value rule">{{ ruleStats.total }}</div>
            <div class="kpi-label">已识别规则</div>
            <div class="kpi-delta" :class="{ warn: ruleStats.pending > 0 }">
              {{ ruleStats.pending > 0 ? `待沉淀 ${ruleStats.pending}` : '全部已沉淀' }}
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value warn">{{ incompleteDomains.length }}</div>
            <div class="kpi-label">需补领域</div>
            <div class="kpi-delta warn">缺笔记 / 结构不全</div>
          </div>
        </div>

        <!-- 分组 tab -->
        <div class="grp-tabs">
          <button
            v-for="g in groupTabs"
            :key="g.code"
            class="grp-tab"
            :class="{ on: activeGroup === g.code }"
            @click="activeGroup = g.code"
          >
            {{ g.name }}
            <span class="grp-count">{{ g.count }}</span>
          </button>
        </div>

        <!-- 领域网格（两级分节：每组带色条头 + 二级卡片网格） -->
        <div v-loading="loading" class="domain-grid-wrap">
          <div v-for="sec in groupedSections" :key="sec.code" class="grid-section">
            <div class="grid-section-head">
              <span class="grid-section-dot" :style="{ background: sec.color }"></span>
              <span class="grid-title">{{ sec.name }}</span>
              <span class="grid-count">{{ sec.domains.length }} 个领域</span>
            </div>
            <div class="domain-grid">
              <div
                v-for="d in sec.domains"
                :key="d.domain_code"
                class="domain-card"
                :class="{ active: selectedDomain?.domain_code === d.domain_code, alert: isIncomplete(d.domain_code) }"
                role="button"
                tabindex="0"
                :title="`${d.domain_name} · 点击查看领域详情`"
                @click="selectDomain(d)"
                @keydown.enter="selectDomain(d)"
              >
                <div class="domain-card-top">
                  <span class="domain-avatar" :style="{ background: groupGradient(d.domain_group) }">{{ d.domain_name.slice(0, 1) }}</span>
                  <span class="domain-name">{{ d.domain_name }}</span>
                  <span class="domain-tag" :style="tagStyle(d.domain_group)">{{ d.domain_group }}</span>
                </div>
                <div class="domain-code">{{ d.domain_code }}</div>
                <div class="domain-meta">
                  <span>知识 {{ d.knowledge_count || 0 }}</span>
                  <span>需求 {{ d.requirement_count || 0 }}</span>
                  <span>工单 {{ d.issue_count || 0 }}</span>
                  <span>会议 {{ d.meeting_count || 0 }}</span>
                </div>
                <div class="domain-bar">
                  <i class="bar-seg b1" :style="{ width: barSeg(d.knowledge_count || 0) }"></i>
                  <i class="bar-seg b2" :style="{ width: barSeg(d.requirement_count || 0) }"></i>
                  <i class="bar-seg b3" :style="{ width: barSeg(d.issue_count || 0) }"></i>
                </div>
                <div class="domain-barlbl">
                  <span><b>{{ (d.knowledge_count || 0) + (d.requirement_count || 0) + (d.issue_count || 0) + (d.meeting_count || 0) }}</b> 关联对象</span>
                  <span v-if="healthMap[d.domain_code]?.has_main_note"><b>主笔记已建</b></span>
                  <span v-else class="text-warn"><b>缺主笔记</b></span>
                </div>
                <!-- 规则沉淀标记 -->
                <div v-if="ruleMap[d.domain_code]?.total" class="domain-rule-flag">
                  <el-icon><MagicStick /></el-icon>
                  <span>规则 {{ ruleMap[d.domain_code].total }}</span>
                  <em v-if="ruleMap[d.domain_code].pending">待沉淀 {{ ruleMap[d.domain_code].pending }}</em>
                </div>
                <!-- 一键同步按钮 -->
                <div v-if="!healthMap[d.domain_code]?.has_main_note" class="domain-sync-btn">
                  <el-button size="small" type="primary" plain @click.stop="syncOneMainNote(d.domain_code)">
                    一键同步
                  </el-button>
                </div>
              </div>
            </div>
            <el-empty v-if="!loading && !sec.domains.length" description="该分组暂无领域" />
          </div>
          <el-empty v-if="!loading && !groupedSections.length" description="暂无业务领域" />
        </div>

        <!-- 领域详情（点击领域卡片后平滑滚动到这里） -->
        <div v-if="selectedDomain" id="domainDetail" class="domain-detail-embed">
          <div class="embed-head">
            <div class="detail-title">
              <span class="detail-tag" :style="groupStyle(selectedDomain.domain_group)">{{ selectedDomain.domain_group }}</span>
              <span>{{ selectedDomain.domain_name }} · 领域详情</span>
            </div>
            <div class="detail-actions">
              <el-button plain :loading="syncOneLoading" @click="syncOne">
                <el-icon><Refresh /></el-icon>
                <span>同步此领域</span>
              </el-button>
              <el-button plain type="success" @click="openDetailPage">
                <el-icon><View /></el-icon>
                <span>领域详情 Dashboard</span>
              </el-button>
            </div>
          </div>
          <DomainDetailPanel :key="selectedDomain.domain_code" :code="selectedDomain.domain_code" />
        </div>
      </div>

      <!-- ========== 右：信息栏（领域详情展开时隐藏，详情全屏展示）========== -->
      <aside class="hub-col hub-col-side" :class="{ hidden: selectedDomain }">
        <!-- 规则沉淀 -->
        <div class="action-card">
          <div class="action-head">
            <el-icon><MagicStick /></el-icon>
            <span>规则沉淀</span>
            <el-button size="small" type="primary" :loading="sedimentLoading" @click="sedimentAllRules">
              一键沉淀
            </el-button>
          </div>
          <div class="rule-stat">
            <div class="rs-item">
              <b>{{ ruleStats.pending }}</b>
              <span>待沉淀</span>
            </div>
            <div class="rs-item">
              <b>{{ ruleStats.total }}</b>
              <span>已识别</span>
            </div>
            <div class="rs-item">
              <b>{{ ruleStats.domains }}</b>
              <span>覆盖领域</span>
            </div>
          </div>
          <div class="mini-list">
            <div
              v-for="d in ruleDomains.slice(0, 6)"
              :key="d.domain_code"
              class="mini-item clickable"
              @click="jumpToDomain(d.domain_code)"
            >
              <span class="mini-dot" :style="{ background: groupColor(d.domain_group) }"></span>
              <span class="mini-name">{{ d.domain_name }}</span>
              <span class="mini-badge" :class="{ ok: !d.pending }">
                {{ d.pending ? `待沉淀 ${d.pending}` : `已沉淀 ${d.total}` }}
              </span>
            </div>
            <el-empty v-if="!ruleDomains.length" description="暂无识别到的规则" :image-size="50" />
          </div>
          <div class="action-note">
            规则来源：需求用户故事的业务规则；系统按关键词智能归类后写入对应主笔记「场景规则（自动区）」。
          </div>
        </div>

        <!-- 需补领域 -->
        <div class="action-card">
          <div class="action-head">
            <el-icon><FirstAidKit /></el-icon>
            <span>需补领域</span>
            <span class="head-count">{{ incompleteDomains.length }}</span>
          </div>
          <div class="todo-tabs">
            <span
              v-for="lv in todoLevels"
              :key="lv.key"
              class="todo-tab"
              :class="{ on: activeTodoLevel === lv.key }"
              @click="activeTodoLevel = lv.key"
            >
              {{ lv.name }} {{ lv.count }}
            </span>
          </div>
          <div class="mini-list">
            <div
              v-for="d in filteredIncomplete"
              :key="d.domain_code"
              class="mini-item clickable"
              @click="jumpToDomain(d.domain_code)"
            >
              <span class="mini-dot" :style="{ background: groupColor(d.domain_group) }"></span>
              <span class="mini-name">{{ d.domain_name }}</span>
              <span class="mini-badge" :class="'lv' + d.level">{{ d.reason }}</span>
            </div>
            <el-empty v-if="!filteredIncomplete.length" description="该分类暂无待补领域" :image-size="50" />
          </div>
          <div class="action-note">
            <el-button size="small" plain :loading="repairLoading" @click="repairDamaged">
              一键修复结构
            </el-button>
            <span>「缺主笔记」请用顶部一键同步创建；其余可一键修复补索引。</span>
          </div>
        </div>

        <!-- 领域动态 -->
        <div class="action-card">
          <div class="action-head">
            <el-icon><Lightning /></el-icon>
            <span>本周新增 · 领域动态</span>
          </div>
          <div class="feed">
            <div v-for="(ev, idx) in recentFeed" :key="idx" class="feed-item">
              <span class="feed-dot" :style="{ background: groupColor(ev.domain_group) }"></span>
              <span class="feed-text">{{ ev.text }}</span>
              <span class="feed-time">{{ ev.time }}</span>
            </div>
            <el-empty v-if="!recentFeed.length" description="暂无领域动态" :image-size="50" />
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, SetUp, Lightning, FirstAidKit, Search, View, MagicStick
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { basicDataApi, loadBusinessDomains } from '@/api/basicData.js'
import { knowledgeApi } from '@/api/knowledge.js'
import { bus, EVT_DOMAINS_CHANGED } from '@/utils/bus'
import DomainDetailPanel from './DomainDetailPanel.vue'

const router = useRouter()
const goManage = () => router.push('/knowledge-center/business-domains')

const loading = ref(false)
const domainTree = ref([])
const allDomains = ref([])
const healthMap = ref({})
const activeGroup = ref('all')
const selectedDomain = ref(null)
const syncLoading = ref(false)
const syncOneLoading = ref(false)
const recentFeed = ref([])

// 规则沉淀
const ruleCandidates = ref({ domains: [], total_rules: 0, total_pending: 0, domain_count: 0 })
const ruleMap = ref({})
const sedimentLoading = ref(false)

// 需补领域
const damageReport = ref({ damaged_notes: [], damaged_count: 0, total_scanned: 0 })
const activeTodoLevel = ref('all')
const repairLoading = ref(false)

// 全局搜索智能推荐
const searchKeyword = ref('')
const searchSuggestions = ref([])
const showSearchHint = ref(false)
let searchTimer = null

const suggestCount = computed(() => searchSuggestions.value.length)

const GROUP_META = {
  商客业务: { color: '#2f6fed', bg: 'rgba(47,111,237,.10)', grad: 'linear-gradient(135deg,#2f6fed,#5b8af1)' },
  系统平台: { color: '#06b6d4', bg: 'rgba(6,182,212,.10)', grad: 'linear-gradient(135deg,#06b6d4,#22d3ee)' },
  公共能力: { color: '#10b981', bg: 'rgba(16,185,129,.10)', grad: 'linear-gradient(135deg,#10b981,#34d399)' },
  通用: { color: '#8b5cf6', bg: 'rgba(139,92,246,.10)', grad: 'linear-gradient(135deg,#8b5cf6,#a78bfa)' },
}

const tagStyle = (g) => {
  const m = GROUP_META[g] || GROUP_META.通用
  return { color: m.color, background: m.bg }
}
const groupColor = (g) => GROUP_META[g]?.color || '#64748b'
const groupGradient = (g) => GROUP_META[g]?.grad || 'linear-gradient(135deg,#64748b,#94a3b8)'
const groupStyle = (g) => {
  const m = GROUP_META[g] || GROUP_META.通用
  return { color: m.color, background: m.bg }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    const t = searchKeyword.value.trim()
    if (!t) { searchSuggestions.value = []; return }
    try {
      const data = await basicDataApi.suggestDomains(t, 6)
      searchSuggestions.value = Array.isArray(data) ? data : []
    } catch {
      searchSuggestions.value = []
    }
  }, 300)
}

function hideSearchHint() {
  setTimeout(() => { showSearchHint.value = false }, 200)
}

function onSearchSelect(s) {
  searchSuggestions.value = []
  searchKeyword.value = ''
  showSearchHint.value = false
  if (s?.domain_code) jumpToDomain(s.domain_code)
}

const groupNames = computed(() => domainTree.value.map((g) => g.domain_name))

const groupTabs = computed(() => {
  const tabs = [{ code: 'all', name: '全部', count: allDomains.value.length }]
  const groupMap = new Map()
  for (const d of allDomains.value) {
    const g = d.domain_group
    if (!groupMap.has(g)) groupMap.set(g, { code: g, name: g, count: 0 })
    groupMap.get(g).count++
  }
  for (const g of groupMap.values()) tabs.push(g)
  return tabs
})

const filteredDomains = computed(() => {
  if (activeGroup.value === 'all') return allDomains.value
  return allDomains.value.filter((d) => d.domain_group === activeGroup.value)
})

// 驾驶舱按一级分组分节展示
const groupedSections = computed(() => {
  const sections = []
  if (activeGroup.value === 'all') {
    for (const g of groupTabs.value) {
      if (g.code === 'all') continue
      const domains = allDomains.value.filter((d) => d.domain_group === g.code)
      if (!domains.length) continue
      sections.push({ code: g.code, name: g.name, color: groupColor(g.name), domains })
    }
  } else {
    sections.push({
      code: activeGroup.value,
      name: activeGroup.value,
      color: groupColor(activeGroup.value),
      domains: filteredDomains.value,
    })
  }
  return sections
})

const stats = computed(() => {
  const total = allDomains.value.length
  // 必须以 allDomains 为分母口径统计，避免 healthMap 含额外条目算出 >100%
  const withMainNote = allDomains.value.filter(
    (d) => healthMap.value[d.domain_code]?.has_main_note,
  ).length
  const firstHealth = Object.values(healthMap.value)[0] || {}
  const weeklyNew = firstHealth.weekly_new_count || 0
  const zombieCount = firstHealth.zombie_count || 0
  const coveragePercent = total > 0 ? Math.round((withMainNote / total) * 100) : 0
  return { total, withMainNote, weeklyNew, zombieCount, coveragePercent }
})

const ruleStats = computed(() => ({
  total: ruleCandidates.value.total_rules || 0,
  pending: ruleCandidates.value.total_pending || 0,
  domains: ruleCandidates.value.domain_count || 0,
}))

const ruleDomains = computed(() => ruleCandidates.value.domains || [])

// ── 需补领域：三级触发逻辑（优先级从高到低，一个领域只落一档）──
// L3 结构受损：scan-damage 命中的 missing_file / structure_incomplete
// L1 缺主笔记：DB 无记录且 Obsidian 文件不存在
// L2 待补索引：文件存在但 DB 未索引
// L3 结构不全：有主笔记但 §7 关联索引缺失
const TODO_LEVELS = [
  { key: 'all', name: '全部' },
  { key: '1', name: '缺主笔记' },
  { key: '2', name: '待补索引' },
  { key: '3', name: '结构不全' },
]

function classifyDomain(d) {
  const h = healthMap.value[d.domain_code]
  const dmg = damageMap.value[d.domain_code]
  if (dmg) {
    if (dmg.damage_type === 'missing_file') {
      return { level: 3, reason: h?.has_main_note ? '笔记文件缺失' : '缺主笔记', fixable: !h?.has_main_note ? 'sync' : 'repair' }
    }
    return { level: 3, reason: '结构不全', fixable: 'repair' }
  }
  if (!h || !h.has_main_note) return { level: 1, reason: '缺主笔记', fixable: 'sync' }
  if (h.needs_db_index) return { level: 2, reason: '待补索引', fixable: 'sync' }
  if (!h.structure_ok) return { level: 3, reason: '结构不全', fixable: 'repair' }
  return null
}

const damageMap = computed(() => {
  const m = {}
  for (const n of damageReport.value.damaged_notes || []) m[n.domain_code] = n
  return m
})

const incompleteDomains = computed(() =>
  allDomains.value
    .map((d) => {
      const c = classifyDomain(d)
      return c ? { ...d, ...c } : null
    })
    .filter(Boolean)
    .sort((a, b) => a.level - b.level || a.domain_name.localeCompare(b.domain_name, 'zh')),
)

const todoLevels = computed(() =>
  TODO_LEVELS.map((lv) => ({
    ...lv,
    count: lv.key === 'all'
      ? incompleteDomains.value.length
      : incompleteDomains.value.filter((d) => String(d.level) === lv.key).length,
  })),
)

const filteredIncomplete = computed(() => {
  if (activeTodoLevel.value === 'all') return incompleteDomains.value
  return incompleteDomains.value.filter((d) => String(d.level) === activeTodoLevel.value)
})

const isIncomplete = (code) => incompleteDomains.value.some((d) => d.domain_code === code)

function barSeg(n) {
  return Math.min(100, Math.max(6, n * 8)) + 'px'
}

// ── 领域卡片交互：选中 + 平滑滚动到「领域详情」区 ──
function scrollToDetail() {
  nextTick(() => {
    const el = document.getElementById('domainDetail')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

const selectDomain = (d) => {
  selectedDomain.value = d
  scrollToDetail()
}

function jumpToDomain(code) {
  const d = allDomains.value.find((x) => x.domain_code === code)
  if (!d) {
    ElMessage.warning('未找到该业务领域')
    return
  }
  // 若被分组 tab 过滤掉，先切回全部，确保卡片可见
  if (activeGroup.value !== 'all' && d.domain_group !== activeGroup.value) {
    activeGroup.value = 'all'
  }
  selectDomain(d)
}

const loadDomains = async () => {
  loading.value = true
  try {
    const tree = await loadBusinessDomains({ tree: true }, true)
    domainTree.value = tree || []
    const flat = []
    for (const g of domainTree.value) {
      for (const d of g.children || []) flat.push(d)
    }
    allDomains.value = flat
    if (!selectedDomain.value && flat.length) selectedDomain.value = flat[0]
    await Promise.all([scanHealth(), loadDamage(), loadRuleCandidates()])
  } finally {
    loading.value = false
  }
}

const scanHealth = async () => {
  try {
    const data = await knowledgeApi.getMainNoteHealth()
    if (Array.isArray(data)) {
      const m = {}
      for (const r of data) m[r.domain_code] = r
      healthMap.value = m
    }
  } catch {
    // fallback 静默
  }
}

const loadDamage = async () => {
  try {
    const data = await knowledgeApi.scanDamage()
    damageReport.value = data || { damaged_notes: [], damaged_count: 0 }
  } catch {
    damageReport.value = { damaged_notes: [], damaged_count: 0 }
  }
}

const loadRuleCandidates = async () => {
  try {
    const data = await knowledgeApi.getRuleCandidates()
    ruleCandidates.value = data || { domains: [], total_rules: 0, total_pending: 0, domain_count: 0 }
    const m = {}
    for (const d of ruleCandidates.value.domains || []) {
      m[d.domain_code] = { total: d.total, pending: d.pending }
    }
    ruleMap.value = m
  } catch {
    ruleCandidates.value = { domains: [], total_rules: 0, total_pending: 0, domain_count: 0 }
    ruleMap.value = {}
  }
}

const sedimentAllRules = async () => {
  sedimentLoading.value = true
  try {
    const res = await knowledgeApi.sedimentRules([])
    const written = (res?.results || []).filter((r) => r.action === 'written').length
    const failed = (res?.results || []).filter((r) => !r.success)
    if (failed.length) {
      ElMessage.warning(
        `规则沉淀完成：写入 ${written} 个领域；${failed.length} 个领域无主笔记，请先一键同步`,
      )
    } else if (written) {
      ElMessage.success(`规则沉淀完成：写入 ${written} 个领域的场景规则（自动区）`)
    } else {
      ElMessage.info('场景规则已是最新，无需重复沉淀')
    }
    await loadRuleCandidates()
  } catch (e) {
    ElMessage.error(e?.message || '规则沉淀失败')
  } finally {
    sedimentLoading.value = false
  }
}

const repairDamaged = async () => {
  repairLoading.value = true
  try {
    const res = await knowledgeApi.repairSections([])
    const ok = res?.success_count ?? 0
    const total = res?.total ?? 0
    if (total === 0) {
      ElMessage.info('未发现需要修复的主笔记')
    } else {
      ElMessage.success(`修复完成：${ok}/${total} 个领域`)
    }
    await Promise.all([loadDamage(), scanHealth()])
  } catch (e) {
    ElMessage.error(e?.message || '修复失败')
  } finally {
    repairLoading.value = false
  }
}

const syncOneMainNote = async (code) => {
  try {
    await knowledgeApi.syncMainNote(code)
    ElMessage.success('主笔记已同步')
    await loadDomains()
  } catch {
    ElMessage.error('同步失败')
  }
}

// 跳转到领域详情 Dashboard（路由需真实领域编码，不能从侧边栏菜单直接进）
const openDetailPage = () => {
  const code = selectedDomain.value?.domain_code
  if (!code) {
    ElMessage.warning('请先选择一个业务领域')
    return
  }
  router.push({ name: 'KcDomainDetail', params: { code } })
}

const loadGlobalFeed = async () => {
  try {
    const res = await knowledgeApi.getGlobalTimeline({ days: 7, limit: 8 })
    const list = Array.isArray(res) ? res : (res?.events || [])
    recentFeed.value = list.slice(0, 8).map((ev) => ({
      text: `${ev.domain_name || '未知领域'} · ${ev.event_label || ''} ${ev.source_title || ev.summary || '事件'}`,
      time: ev.event_date || '',
      domain_group: ev.domain_group || '通用',
    }))
  } catch {
    recentFeed.value = []
  }
}

const syncAll = async () => {
  syncLoading.value = true
  try {
    const res = await knowledgeApi.ensureMainNotes()
    const scanned = res?.domains_scanned ?? 0
    const created = res?.main_notes_created ?? 0
    const ensured = res?.main_notes_ensured ?? 0
    const indexed = res?.db_indexed_from_obsidian ?? 0
    const errors = Array.isArray(res?.errors) ? res.errors : []

    if (errors.length) {
      ElMessage.warning(
        `同步完成但有 ${errors.length} 个领域失败：${errors.map((e) => e.domain_code).join('、')}`,
      )
    } else if (created || indexed) {
      ElMessage.success(`同步完成：扫描 ${scanned} 个领域，新建 ${created} 个，补索引 ${indexed} 个`)
    } else {
      ElMessage.success(`同步完成：扫描 ${scanned} 个领域，${ensured} 个主笔记已是最新`)
    }
    await loadDomains()
  } catch (e) {
    ElMessage.error(e?.message || '同步失败，请查看后端日志')
  } finally {
    syncLoading.value = false
  }
}

const syncOne = async () => {
  if (!selectedDomain.value) return
  syncOneLoading.value = true
  try {
    await knowledgeApi.syncMainNote(selectedDomain.value.domain_code)
    ElMessage.success(`${selectedDomain.value.domain_name} 主笔记已同步`)
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncOneLoading.value = false
  }
}

onMounted(() => {
  loadDomains()
  loadGlobalFeed()
})
bus.on(EVT_DOMAINS_CHANGED, () => {
  loadDomains()
  loadGlobalFeed()
})
</script>

<style scoped>
.hub-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 18px 24px;
  background: #f5f7fa;
  min-height: 100%;
}

.hub-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.hub-header-titles {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hub-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1f2d3d;
  letter-spacing: .3px;
}
.hub-subtitle {
  font-size: 13px;
  color: #64748b;
}
.hub-header-actions {
  display: flex;
  gap: 10px;
}

/* 子导航 */
.hub-subnav {
  display: flex; align-items: center; gap: 8px;
  padding: 6px; background: #f5f7fa; border-radius: 10px;
  border: 1px solid #e4e7ed; width: fit-content;
}
.subnav-link {
  padding: 6px 14px; border-radius: 8px;
  font-size: 13px; color: #606266; text-decoration: none;
  transition: .15s;
}
.subnav-link:hover { color: #2f6fed; background: #fff; }
.subnav-link.active { background: #2f6fed; color: #fff; }

/* ── 主体双栏 ── */
.hub-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 336px;
  gap: 14px;
  align-items: start;
  transition: grid-template-columns .2s;
}
.hub-main.detail-open {
  grid-template-columns: minmax(0, 1fr);
}
.hub-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.hub-col-side {
  position: sticky;
  top: 8px;
  transition: opacity .18s, transform .18s, max-height .22s;
  overflow: hidden;
  max-height: 2000px;
}
.hub-col-side.hidden {
  opacity: 0;
  max-height: 0;
  pointer-events: none;
  margin: 0;
  border: none;
}
@media (min-width: 1400px) {
  /* 大屏保持双栏，右侧动态隐藏 */
  .hub-main.detail-open {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* KPI 条 */
.kpi-strip {
  display: flex;
  gap: 10px;
  align-items: stretch;
}
.kpi-card {
  flex: 1;
  min-width: 0;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 10px 13px;
  box-shadow: 0 2px 6px rgba(0,0,0,.04);
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.kpi-value {
  font-size: 21px;
  font-weight: 800;
  color: #1f2d3d;
  letter-spacing: -.5px;
  line-height: 1.1;
}
.kpi-value.warn { color: #f0a64a; }
.kpi-value.rule { color: #10b981; }
.kpi-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 3px;
}
.kpi-delta {
  font-size: 11px;
  color: #10b981;
  margin-top: 3px;
}
.kpi-delta.warn { color: #f0a64a; }

/* 分组 tab */
.grp-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.grp-tab {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid #e4e7ed;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  font-size: 13px;
  transition: .15s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.grp-tab:hover { border-color: #2f6fed; color: #2f6fed; }
.grp-tab.on { background: #2f6fed; color: #fff; border-color: #2f6fed; }
.grp-count {
  font-size: 11px;
  background: rgba(255,255,255,.2);
  padding: 1px 6px;
  border-radius: 999px;
}

/* 信息栏卡片 */
.action-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 13px 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.action-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #1f2d3d;
  margin-bottom: 10px;
}
.action-head > span:nth-child(2) { flex: 1; }
.action-head .el-icon { color: #2f6fed; }
.head-count {
  font-size: 11px;
  font-weight: 700;
  background: #fdf2e8;
  color: #f0a64a;
  padding: 1px 8px;
  border-radius: 999px;
}
.feed {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.feed-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  background: #f5f7fa;
  border-radius: 8px;
  font-size: 12.5px;
}
.feed-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.feed-text {
  flex: 1;
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feed-time { font-size: 11.5px; color: #909399; flex-shrink: 0; }

/* 需补领域分级 tab */
.todo-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.todo-tab {
  padding: 3px 9px;
  border-radius: 7px;
  background: #f5f7fa;
  border: 1px solid transparent;
  font-size: 11.5px;
  color: #64748b;
  cursor: pointer;
  transition: .15s;
}
.todo-tab:hover { color: #2f6fed; }
.todo-tab.on { border-color: #2f6fed; color: #2f6fed; background: #fff; }

.mini-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.mini-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}
.mini-item.clickable {
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 7px;
  transition: .15s;
}
.mini-item.clickable:hover { background: #f0f5ff; }
.mini-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.mini-name { flex: 1; color: #1f2d3d; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mini-badge {
  font-size: 11px;
  background: #fdf2e8;
  color: #f0a64a;
  padding: 1px 7px;
  border-radius: 6px;
  flex-shrink: 0;
}
.mini-badge.ok { background: #eafaf3; color: #10b981; }
.mini-badge.lv1 { background: #fdecec; color: #e47470; }
.mini-badge.lv2 { background: #fdf2e8; color: #f0a64a; }
.mini-badge.lv3 { background: #eef4ff; color: #2f6fed; }

/* 规则沉淀统计 */
.rule-stat {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.rs-item {
  flex: 1;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 7px 6px;
  text-align: center;
}
.rs-item b {
  display: block;
  font-size: 16px;
  color: #1f2d3d;
  line-height: 1.2;
}
.rs-item span { font-size: 11px; color: #909399; }

.action-note {
  font-size: 11.5px;
  color: #909399;
  margin-top: 9px;
  line-height: 1.6;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 领域网格 */
.domain-grid-wrap {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 14px 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.grid-section + .grid-section { margin-top: 18px; }
.grid-section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.grid-section-dot { width: 4px; height: 15px; border-radius: 2px; }
.grid-title { font-size: 15px; font-weight: 700; color: #1f2d3d; }
.grid-count { font-size: 12px; color: #909399; }
.domain-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(232px, 1fr));
  gap: 12px;
}
.domain-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 13px 14px;
  cursor: pointer;
  text-align: left;
  transition: .16s;
  position: relative;
  overflow: hidden;
}
.domain-card:hover {
  transform: translateY(-2px);
  border-color: #2f6fed;
  box-shadow: 0 6px 18px rgba(47,111,237,.12);
}
.domain-card.active {
  border-color: #2f6fed;
  background: rgba(47,111,237,.04);
  box-shadow: 0 0 0 2px rgba(47,111,237,.10);
}
.domain-card.alert::after {
  content: '';
  position: absolute;
  top: 0; right: 0;
  border: 7px solid #f0a64a;
  border-left-color: transparent;
  border-bottom-color: transparent;
}
.domain-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 7px;
}
.domain-avatar {
  width: 30px; height: 30px;
  border-radius: 9px;
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; flex-shrink: 0;
}
.domain-name {
  flex: 1;
  font-size: 14.5px;
  font-weight: 700;
  color: #1f2d3d;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.domain-tag {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 6px;
  font-weight: 600;
  flex-shrink: 0;
}
.domain-code {
  font-size: 11.5px;
  color: #909399;
  font-family: 'JetBrains Mono', monospace;
  margin-bottom: 8px;
}
.domain-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  color: #909399;
  margin-bottom: 8px;
}
.domain-bar {
  height: 5px;
  border-radius: 4px;
  background: #ebeef5;
  overflow: hidden;
  display: flex;
  gap: 2px;
}
.bar-seg { height: 100%; display: block; min-width: 4px; }
.bar-seg.b1 { background: #2f6fed; }
.bar-seg.b2 { background: #06b6d4; }
.bar-seg.b3 { background: #10b981; }
.domain-barlbl {
  font-size: 11px;
  color: #909399;
  margin-top: 7px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.domain-barlbl b { color: #1f2d3d; }
.text-warn { color: #f0a64a !important; }
.domain-rule-flag {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #10b981;
  background: #eafaf3;
  border-radius: 6px;
  padding: 3px 8px;
}
.domain-rule-flag em { font-style: normal; color: #f0a64a; margin-left: auto; }
.domain-sync-btn { margin-top: 9px; }

/* 领域详情内嵌面板 */
.domain-detail-embed {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  scroll-margin-top: 12px;
  min-width: 0;
  max-width: 100%;
  overflow-x: auto;
}
.embed-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
}
.detail-tag {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 6px;
  font-weight: 600;
}
.detail-actions { display: flex; gap: 10px; }

/* 搜索提示 */
.hub-search-wrap { position: relative; }
.search-hint {
  position: absolute;
  top: 42px; left: 0; right: 0;
  z-index: 20;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,.10);
  padding: 8px;
  max-height: 320px;
  overflow-y: auto;
}
.hint-title { font-size: 11.5px; color: #909399; padding: 4px 6px; }
.hint-row {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 8px; border-radius: 7px; cursor: pointer; font-size: 13px;
}
.hint-row:hover { background: #f0f5ff; }
.hint-name { font-weight: 600; color: #1f2d3d; }
.hint-group { font-size: 11px; padding: 1px 7px; border-radius: 6px; }
.hint-why { margin-left: auto; font-size: 11px; color: #909399; }
.hint-empty { padding: 10px; text-align: center; color: #909399; font-size: 12px; }
.search-hint-count { font-size: 11px; color: #909399; }

@media (max-width: 1400px) {
  .hub-main { grid-template-columns: minmax(0, 1fr); }
  .hub-col-side { position: static; }
  .hub-col-side {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    align-items: start;
  }
}
@media (max-width: 768px) {
  .kpi-strip { flex-wrap: wrap; }
  .kpi-card { min-width: 45%; }
  .domain-grid { grid-template-columns: 1fr; }
}
</style>
