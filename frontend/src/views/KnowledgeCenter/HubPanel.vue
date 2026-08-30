<template>
  <div class="hub-panel">
    <!-- 顶部 -->
    <div class="hub-header">
      <div class="hub-header-titles">
        <div class="hub-breadcrumb">
          <router-link to="/" class="bc-link">首页</router-link>
          <span class="bc-sep">/</span>
          <router-link to="/knowledge-center/hub" class="bc-link bc-active">知识中心</router-link>
        </div>
        <h3 class="hub-title">知识中心 · 总览驾驶舱</h3>
        <span class="hub-subtitle">业务领域全景、主笔记标准化、关联事件时间线</span>
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

    <!-- KPI 条 -->
    <div class="kpi-strip">
      <div class="kpi-card">
        <div class="kpi-value">{{ stats.total }}</div>
        <div class="kpi-label">业务领域总数</div>
        <div class="kpi-delta">{{ groupNames.length }} 个分组</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value">{{ stats.withMainNote }}</div>
        <div class="kpi-label">主笔记已建</div>
        <div class="kpi-delta" :class="{ warn: stats.withMainNote < stats.total }">覆盖率 {{ coverageText }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value">{{ stats.recentEvents }}</div>
        <div class="kpi-label">本周动态</div>
        <div class="kpi-delta">关联事件</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value warn">{{ stats.incomplete }}</div>
        <div class="kpi-label">待完善领域</div>
        <div class="kpi-delta warn">缺主笔记或结构不全</div>
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

    <!-- 快捷卡片行 -->
    <div class="action-row">
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
          <el-empty v-if="!recentFeed.length" description="暂无领域动态" :image-size="60" />
        </div>
      </div>

      <div class="action-card">
        <div class="action-head">
          <el-icon><FirstAidKit /></el-icon>
          <span>需补领域（无主笔记 / 结构不全）</span>
        </div>
        <div class="mini-list">
          <div v-for="d in incompleteDomains.slice(0, 6)" :key="d.domain_code" class="mini-item">
            <span class="mini-dot" :style="{ background: groupColor(d.domain_group) }"></span>
            <span class="mini-name">{{ d.domain_name }}</span>
            <span class="mini-badge">{{ d.reason }}</span>
          </div>
          <el-empty v-if="!incompleteDomains.length" description="暂无待补领域" :image-size="60" />
        </div>
        <div class="action-note">点击「一键同步全部主笔记」可批量补齐缺失主笔记。</div>
      </div>
    </div>

    <!-- 领域网格 -->
    <div v-loading="loading" class="domain-grid-wrap">
      <div class="grid-head">
        <span class="grid-title">领域驾驶舱</span>
        <span class="grid-count">{{ filteredDomains.length }} 个领域</span>
      </div>
      <div class="domain-grid">
        <button
          v-for="d in filteredDomains"
          :key="d.domain_code"
          class="domain-card"
          :class="{ active: selectedDomain?.domain_code === d.domain_code }"
          @click="selectDomain(d)"
        >
          <div class="domain-card-top">
            <span class="domain-avatar">{{ d.domain_name.slice(0, 1) }}</span>
            <span class="domain-name">{{ d.domain_name }}</span>
            <span class="domain-tag">{{ d.domain_group }}</span>
          </div>
          <div class="domain-code">{{ d.domain_code }}</div>
          <div class="domain-meta">
            <span>知识 {{ d.knowledge_count || 0 }}</span>
            <span>需求 {{ d.req_count || 0 }}</span>
            <span>工单 {{ d.issue_count || 0 }}</span>
            <span>会议 {{ d.meeting_count || 0 }}</span>
          </div>
          <div class="domain-bar">
            <i class="bar-seg b1" :style="{ width: barSeg(d.knowledge_count || 0) }"></i>
            <i class="bar-seg b2" :style="{ width: barSeg(d.req_count || 0) }"></i>
            <i class="bar-seg b3" :style="{ width: barSeg(d.issue_count || 0) }"></i>
          </div>
          <div class="domain-barlbl">
            <span><b>{{ (d.knowledge_count || 0) + (d.req_count || 0) + (d.issue_count || 0) + (d.meeting_count || 0) }}</b> 关联对象</span>
            <span v-if="healthMap[d.domain_code]?.hasMainNote"><b>主笔记已建</b></span>
            <span v-else class="text-warn"><b>缺主笔记</b></span>
          </div>
        </button>
      </div>
      <el-empty v-if="!loading && !filteredDomains.length" description="该分组暂无领域" />
    </div>

    <!-- 领域详情 -->
    <div v-if="selectedDomain" v-loading="detailLoading" class="domain-detail">
      <div class="detail-head">
        <div class="detail-title">
          <span class="detail-tag" :style="groupStyle(selectedDomain.domain_group)">{{ selectedDomain.domain_group }}</span>
          <span>{{ selectedDomain.domain_name }} · 业务全景</span>
        </div>
        <div class="detail-actions">
          <el-button plain :loading="syncOneLoading" @click="syncOne">
            <el-icon><Refresh /></el-icon>
            <span>同步此领域</span>
          </el-button>
          <el-button v-if="mainNotePath" plain type="primary" @click="openObsidianNote(mainNotePath)">
            <el-icon><FolderOpened /></el-icon>
            <span>打开主笔记</span>
          </el-button>
        </div>
      </div>

      <div class="detail-grid">
        <!-- 左侧：概览 + 结构 -->
        <div class="detail-col">
          <div class="detail-card">
            <div class="detail-card-head">
              <span>主笔记标准结构</span>
              <span v-if="mainNoteTitle" class="detail-sub">{{ mainNoteTitle }}</span>
            </div>
            <div class="bible-list">
              <div v-for="sec in bibleSections" :key="sec.key" class="bible-item">
                <span class="bible-badge" :class="'kind-' + sec.kind">{{ sec.kind_label }}</span>
                <span class="bible-title">{{ sec.title }}</span>
              </div>
              <el-empty v-if="!bibleSections.length && !bibleLoading" description="暂无主笔记内容" :image-size="60" />
            </div>
          </div>

          <div class="detail-card">
            <div class="detail-card-head">全景指标</div>
            <div class="mini-list">
              <div class="mini-item"><span>知识条目</span><b>{{ selectedDomain.knowledge_count || 0 }}</b></div>
              <div class="mini-item"><span>关联需求</span><b>{{ selectedDomain.req_count || 0 }}</b></div>
              <div class="mini-item"><span>运营工单</span><b>{{ selectedDomain.issue_count || 0 }}</b></div>
              <div class="mini-item"><span>会议</span><b>{{ selectedDomain.meeting_count || 0 }}</b></div>
            </div>
          </div>
        </div>

        <!-- 右侧：时间线 -->
        <div class="detail-card detail-timeline">
          <div class="detail-card-head">
            <el-icon><Clock /></el-icon>
            <span>业务全过程时间线</span>
          </div>
          <BusinessTimeline :domain-code="selectedDomain.domain_code" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, Notebook, FolderOpened, SetUp, Clock, Lightning, FirstAidKit, Search
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { basicDataApi, loadBusinessDomains } from '@/api/basicData.js'
import { knowledgeApi } from '@/api/knowledge.js'
import { obsidianApi } from '@/api/obsidian.js'
import BusinessTimeline from '@/components/Common/BusinessTimeline.vue'
import { productBibleApi } from '@/api/productBible.js'
import { bus, EVT_DOMAINS_CHANGED } from '@/utils/bus'
import { openObsidianNote } from '@/utils/obsidian.js'

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
const mainNoteTitle = ref('')
const mainNotePath = ref('')
const bibleSections = ref([])
const bibleLoading = ref(false)
const detailLoading = ref(false)
const recentFeed = ref([])

// 全局搜索智能推荐
const searchKeyword = ref('')
const searchSuggestions = ref([])
const showSearchHint = ref(false)
let searchTimer = null

const suggestCount = computed(() => searchSuggestions.value.length)

const tagStyle = (g) => {
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
  if (s?.domain_code) {
    const d = allDomains.value.find(x => x.domain_code === s.domain_code)
    if (d) selectDomain(d)
  }
}

async function ensureMainNote(code) {
  try {
    await knowledgeApi.createMainNote(code)
    ElMessage.success('主笔记已创建')
    await scanHealth()
    loadDomains()
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  }
}

const GROUP_META = {
  商客业务: { color: '#2f6fed', bg: 'rgba(47,111,237,.10)' },
  系统平台: { color: '#06b6d4', bg: 'rgba(6,182,212,.10)' },
  公共能力: { color: '#10b981', bg: 'rgba(16,185,129,.10)' },
  通用: { color: '#8b5cf6', bg: 'rgba(139,92,246,.10)' },
}

const groupColor = (g) => GROUP_META[g]?.color || '#64748b'
const groupStyle = (g) => {
  const m = GROUP_META[g] || GROUP_META.通用
  return { color: m.color, background: m.bg }
}

const groupNames = computed(() => domainTree.value.map((g) => g.domain_name))

const groupTabs = computed(() => {
  const tabs = [{ code: 'all', name: '全部', count: allDomains.value.length }]
  for (const g of domainTree.value) {
    tabs.push({
      code: g.domain_code,
      name: g.domain_name,
      count: (g.children || []).length,
    })
  }
  return tabs
})

const filteredDomains = computed(() => {
  if (activeGroup.value === 'all') return allDomains.value
  const g = domainTree.value.find((x) => x.domain_code === activeGroup.value)
  return g?.children || []
})

const stats = computed(() => {
  const total = allDomains.value.length
  const withMainNote = Object.values(healthMap.value).filter((h) => h.hasMainNote).length
  const incomplete = total - withMainNote
  const recentEvents = recentFeed.value.length
  return { total, withMainNote, incomplete, recentEvents }
})

const coverageText = computed(() => {
  if (!stats.value.total) return '-'
  return Math.round((stats.value.withMainNote / stats.value.total) * 100) + '%'
})

const incompleteDomains = computed(() => {
  return allDomains.value
    .filter((d) => {
      const h = healthMap.value[d.domain_code]
      return !h || !h.hasMainNote
    })
    .map((d) => ({ ...d, reason: '缺主笔记' }))
})

function barSeg(n) {
  // 占位进度条，按最大值归一
  return Math.min(100, Math.max(6, n * 8)) + 'px'
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
    if (!selectedDomain.value && flat.length) {
      selectDomain(flat[0])
    }
    await scanHealth()
  } finally {
    loading.value = false
  }
}

const scanHealth = async () => {
  try {
    const data = await knowledgeApi.getMainNoteHealth()
    if (Array.isArray(data)) {
      for (const r of data) {
        healthMap.value[r.domain_code] = r
      }
    }
  } catch {
    // fallback 静默
  }
}

const selectDomain = async (d) => {
  if (selectedDomain.value?.domain_code === d.domain_code) return
  selectedDomain.value = d
  mainNoteTitle.value = ''
  mainNotePath.value = ''
  bibleSections.value = []
  detailLoading.value = true
  try {
    await Promise.all([loadBible(d.domain_code), loadDomainMeta(d)])
    await loadTimelineFeed(d.domain_code)
  } finally {
    detailLoading.value = false
  }
}

const loadBible = async (code) => {
  bibleLoading.value = true
  try {
    const res = await productBibleApi.getMainNote(code)
    bibleSections.value = res?.sections || []
  } catch {
    bibleSections.value = []
  } finally {
    bibleLoading.value = false
  }
}

const loadDomainMeta = async (d) => {
  try {
    const res = await basicDataApi.getDomainRelated(d.domain_code)
    if (res?.main_note) {
      mainNoteTitle.value = res.main_note.title || ''
      mainNotePath.value = res.main_note.obsidian_path || ''
    }
  } catch {
    // 静默
  }
}

const loadTimelineFeed = async (code) => {
  try {
    const res = await knowledgeApi.getBusinessTimeline({ domain_code: code, limit: 4 })
    const list = Array.isArray(res) ? res : (res?.data || [])
    recentFeed.value = list.slice(0, 4).map((ev) => ({
      text: `${ev.domain_name || code} · ${ev.event_title || ev.title || '事件'}`,
      time: ev.event_date || ev.created_at || '',
      domain_group: selectedDomain.value?.domain_group || '通用',
    }))
  } catch {
    recentFeed.value = []
  }
}

const syncAll = async () => {
  syncLoading.value = true
  try {
    const res = await knowledgeApi.ensureMainNotes()
    ElMessage.success(res?.message || '已确保所有领域主笔记')
    await loadDomains()
  } catch {
    ElMessage.error('同步失败')
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
    await loadBible(selectedDomain.value.domain_code)
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncOneLoading.value = false
  }
}

onMounted(loadDomains)
bus.on(EVT_DOMAINS_CHANGED, loadDomains)
</script>

<style scoped>
.hub-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 16px 18px 24px;
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

/* KPI 条 */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.kpi-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.kpi-value {
  font-size: 28px;
  font-weight: 800;
  color: #1f2d3d;
  letter-spacing: -.5px;
  line-height: 1.1;
}
.kpi-value.warn { color: #f0a64a; }
.kpi-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 6px;
}
.kpi-delta {
  font-size: 12px;
  color: #10b981;
  margin-top: 8px;
}
.kpi-delta.warn { color: #f0a64a; }

/* 分组 tab */
.grp-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.grp-tab {
  padding: 7px 14px;
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
.grp-tab:hover {
  border-color: #2f6fed;
  color: #2f6fed;
}
.grp-tab.on {
  background: #2f6fed;
  color: #fff;
  border-color: #2f6fed;
}
.grp-count {
  font-size: 11px;
  background: rgba(255,255,255,.2);
  padding: 1px 6px;
  border-radius: 999px;
}

/* 快捷卡片行 */
.action-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 14px;
}
.action-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.action-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #1f2d3d;
  margin-bottom: 12px;
}
.action-head .el-icon { color: #2f6fed; }
.feed {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.feed-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  background: #f5f7fa;
  border-radius: 8px;
  font-size: 13px;
}
.feed-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.feed-text {
  flex: 1;
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feed-time {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}
.mini-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mini-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.mini-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.mini-name {
  flex: 1;
  color: #1f2d3d;
}
.mini-badge {
  font-size: 11px;
  background: #fdf2e8;
  color: #f0a64a;
  padding: 2px 7px;
  border-radius: 6px;
}
.action-note {
  font-size: 12px;
  color: #909399;
  margin-top: 10px;
  line-height: 1.5;
}

/* 领域网格 */
.domain-grid-wrap {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 14px 16px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.grid-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.grid-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2d3d;
}
.grid-count {
  font-size: 12px;
  color: #909399;
}
.domain-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(248px, 1fr));
  gap: 14px;
}
.domain-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 14px 15px;
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
}
.domain-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.domain-avatar {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: linear-gradient(135deg, #2f6fed, #5b8af1);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.domain-name {
  flex: 1;
  font-size: 15px;
  font-weight: 700;
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.domain-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  background: #f5f7fa;
  color: #64748b;
  font-weight: 600;
  flex-shrink: 0;
}
.domain-code {
  font-size: 12px;
  color: #909399;
  font-family: 'JetBrains Mono', monospace;
  margin-bottom: 10px;
}
.domain-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
  margin-bottom: 10px;
}
.domain-bar {
  height: 6px;
  border-radius: 4px;
  background: #ebeef5;
  overflow: hidden;
  display: flex;
  gap: 2px;
}
.bar-seg {
  height: 100%;
  display: block;
  min-width: 4px;
}
.bar-seg.b1 { background: #2f6fed; }
.bar-seg.b2 { background: #06b6d4; }
.bar-seg.b3 { background: #10b981; }
.domain-barlbl {
  font-size: 11px;
  color: #909399;
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.domain-barlbl b { color: #1f2d3d; }
.text-warn { color: #f0a64a !important; }

/* 领域详情 */
.domain-detail {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
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

.detail-grid {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 16px;
}
.detail-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.detail-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 14px 16px;
}
.detail-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: #1f2d3d;
  margin-bottom: 12px;
}
.detail-sub {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}
.bible-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bible-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 7px 10px;
  background: #f5f7fa;
  border-radius: 8px;
}
.bible-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  font-weight: 600;
  flex-shrink: 0;
}
.bible-badge.kind-baseline { background: #ecf5ff; color: #409eff; }
.bible-badge.kind-auto { background: #f0f9eb; color: #67c23a; }
.bible-badge.kind-system { background: #f4f4f5; color: #909399; }
.bible-title {
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-timeline {
  min-height: 320px;
}

@media (max-width: 1200px) {
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
  .action-row, .detail-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .kpi-strip { grid-template-columns: 1fr; }
  .domain-grid { grid-template-columns: 1fr; }
}
</style>
