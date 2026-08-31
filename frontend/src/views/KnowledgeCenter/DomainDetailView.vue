<template>
  <div class="domain-detail-view">
    <!-- 顶部栏 -->
    <div class="detail-topbar">
      <div class="detail-title">
        <span class="gtag" :style="groupStyle(detail.domain_group)">{{ detail.domain_group }}</span>
        <span>{{ detail.domain_name }}</span>
      </div>
      <div class="detail-breadcrumb">
        <router-link to="/knowledge-center/hub" class="bc-link">知识中心</router-link>
        <span class="bc-sep">/</span>
        <span class="bc-current">{{ detail.domain_name }} · 领域详情</span>
      </div>
      <div class="detail-actions">
        <el-button plain :loading="syncing" @click="syncMainNote">
          <el-icon><Refresh /></el-icon>
          <span>同步主笔记</span>
        </el-button>
        <el-button v-if="detail.obsidian_path" plain type="primary" @click="openObsidian">
          <el-icon><FolderOpened /></el-icon>
          <span>打开 Obsidian</span>
        </el-button>
      </div>
    </div>

    <!-- 详情区：左 300px + 右自适应 -->
    <div class="detail-body" v-loading="loading">
      <!-- 左侧：主笔记结构 + 全景指标 -->
      <div class="detail-left">
        <!-- 主笔记结构卡片 -->
        <div class="dcard">
          <div class="dcard-head">
            <span>主笔记结构（§3.8 三类模板）</span>
            <span v-if="bibleTitle" class="dcard-sub">{{ bibleTitle }}</span>
          </div>
          <div class="bible-list">
            <div v-for="sec in bibleSections" :key="sec.key" class="bible-item">
              <span class="bible-badge" :class="'kind-' + sec.kind">{{ sec.kind_label }}</span>
              <span class="bible-title">{{ sec.title }}</span>
            </div>
            <el-empty v-if="!bibleSections.length && !bibleLoading" description="暂无主笔记内容" :image-size="60" />
          </div>
        </div>

        <!-- 全景指标卡片 -->
        <div class="dcard">
          <div class="dcard-head"><span>📊 全景指标</span></div>
          <div class="mini-list">
            <div class="mini-item">
              <span>知识条目</span>
              <b>{{ stats.knowledge_count || 0 }}</b>
            </div>
            <div class="mini-item">
              <span>关联需求</span>
              <b>{{ stats.requirement_count || 0 }}</b>
            </div>
            <div class="mini-item">
              <span>关联工单</span>
              <b>{{ stats.issue_count || 0 }}</b>
            </div>
            <div class="mini-item">
              <span>时间线事件</span>
              <b>{{ stats.timeline_count || 0 }}</b>
            </div>
          </div>
          <div class="health-note" v-if="!detail.has_main_note">
            ⚠️ 该领域尚无主笔记，点击「同步主笔记」一键创建。
          </div>
        </div>
      </div>

      <!-- 右侧：tab 切换 + 内容 -->
      <div class="detail-right">
        <div class="dtabs" id="dTabs">
          <div class="dtab" :class="{ on: activeTab === 'bible' }" @click="activeTab = 'bible'">产品圣经</div>
          <div class="dtab" :class="{ on: activeTab === 'rel' }" @click="activeTab = 'rel'">关联对象</div>
          <div class="dtab" :class="{ on: activeTab === 'tl' }" @click="activeTab = 'tl'">时间线</div>
          <div class="dtab" :class="{ on: activeTab === 'auto' }" @click="activeTab = 'auto'">自动区状态</div>
        </div>
        <div class="dbody">
          <!-- 产品圣经 tab -->
          <div v-if="activeTab === 'bible'" class="tab-content">
            <div v-if="bibleContent" class="markdown-body" v-html="renderedBible"></div>
            <el-empty v-else :description="bibleLoading ? '加载中...' : '暂无主笔记内容'" />
          </div>

          <!-- 关联对象 tab -->
          <div v-if="activeTab === 'rel'" class="tab-content">
            <div class="filt">
              <span class="f" :class="{ on: relFilter === 'all' }" @click="relFilter = 'all'">全部</span>
              <span class="f" :class="{ on: relFilter === 'req' }" @click="relFilter = 'req'">需求</span>
              <span class="f" :class="{ on: relFilter === 'issue' }" @click="relFilter = 'issue'">工单</span>
              <span class="f" :class="{ on: relFilter === 'meeting' }" @click="relFilter = 'meeting'">会议</span>
            </div>
            <table class="rel-table">
              <thead>
                <tr>
                  <th style="width:80px">类型</th>
                  <th>标题</th>
                  <th style="width:100px">状态</th>
                  <th style="width:80px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredRelations" :key="item.code">
                  <td><span class="ptag">{{ typeLabel(item.status || item.category || '知识') }}</span></td>
                  <td>{{ item.title }}</td>
                  <td>{{ item.sub_title || '-' }}</td>
                  <td><a href="#" @click.prevent="viewItem(item)" class="link-btn">查看</a></td>
                </tr>
                <tr v-if="!filteredRelations.length"><td colspan="4" class="empty-row">暂无关联对象</td></tr>
              </tbody>
            </table>
          </div>

          <!-- 时间线 tab -->
          <div v-if="activeTab === 'tl'" class="tab-content">
            <BusinessTimeline :domain-code="detail.domain_code" :limit="20" />
          </div>

          <!-- 自动区状态 tab -->
          <div v-if="activeTab === 'auto'" class="tab-content">
            <div class="auto-status">
              <div class="auto-item">
                <span class="auto-label">主笔记已建</span>
                <span :class="['auto-val', detail.has_main_note ? 'ok' : 'warn']">{{ detail.has_main_note ? '✅ 是' : '❌ 否' }}</span>
              </div>
              <div class="auto-item">
                <span class="auto-label">结构完整性</span>
                <span :class="['auto-val', detail.structure_ok ? 'ok' : 'warn']">{{ detail.structure_ok ? '✅ 完整' : '⚠️ 残缺' }}</span>
              </div>
              <div class="auto-item">
                <span class="auto-label">最后同步</span>
                <span class="auto-val">{{ detail.updated_at || '未知' }}</span>
              </div>
            </div>
            <div class="note">自动区由系统维护，无需手动操作。</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, FolderOpened } from '@element-plus/icons-vue'
import { basicDataApi } from '@/api/basicData'
import { knowledgeApi } from '@/api/knowledge'
import { productBibleApi } from '@/api/productBible'
import BusinessTimeline from '@/components/Common/BusinessTimeline.vue'
import { openObsidianNote } from '@/utils/obsidian'
import { marked } from 'marked'

const route = useRoute()
const code = route.params.code

const loading = ref(false)
const detail = ref({})
const bibleSections = ref([])
const bibleContent = ref('')
const bibleTitle = ref('')
const bibleLoading = ref(false)
const relations = ref([])
const timelineEvents = ref([])
const relFilter = ref('all')
const activeTab = ref('bible')

const GROUP_META = {
  '商客业务': { color: '#2f6fed', bg: 'rgba(47,111,237,.10)' },
  '系统平台': { color: '#06b6d4', bg: 'rgba(6,182,212,.10)' },
  '公共能力': { color: '#10b981', bg: 'rgba(16,185,129,.10)' },
  '通用': { color: '#8b5cf6', bg: 'rgba(139,92,246,.10)' },
}

const groupStyle = (g) => {
  const m = GROUP_META[g] || GROUP_META.通用
  return { color: m.color, background: m.bg }
}

const stats = computed(() => ({
  knowledge_count: detail.value.knowledge_count || 0,
  requirement_count: detail.value.requirement_count || 0,
  issue_count: detail.value.issue_count || 0,
  timeline_count: timelineEvents.value.length,
}))

const filteredRelations = computed(() => {
  if (relFilter.value === 'all') return relations.value
  const map = { req: 'requirement', issue: 'operation', meeting: 'meeting' }
  return relations.value.filter(r => r.status === map[relFilter.value])
})

const renderedBible = computed(() => {
  if (!bibleContent.value) return ''
  return marked.parse(bibleContent.value)
})

async function loadDetail() {
  loading.value = true
  try {
    const res = await basicDataApi.getDomainRelated(code)
    detail.value = res || {}
    // 合并 stats
    relations.value = [
      ...(res.requirements || []).map(r => ({ ...r, status: 'requirement' })),
      ...(res.issues || []).map(r => ({ ...r, status: 'operation' })),
      ...(res.meetings || []).map(r => ({ ...r, status: 'meeting' })),
      ...(res.knowledge_items || []).map(r => ({ ...r, status: 'knowledge' })),
    ]
  } catch (e) {
    ElMessage.error('加载领域详情失败')
  } finally {
    loading.value = false
  }
}

async function loadBible() {
  bibleLoading.value = true
  try {
    const res = await productBibleApi.getMainNote(code)
    bibleSections.value = res?.sections || []
    bibleContent.value = res?.content || ''
    bibleTitle.value = res?.title || ''
  } catch {
    bibleSections.value = []
    bibleContent.value = ''
  } finally {
    bibleLoading.value = false
  }
}

const syncing = ref(false)

async function syncMainNote() {
  // 原实现只是跳转到管理页，用户点「同步主笔记」却没执行任何同步；改为直接调用同步接口
  syncing.value = true
  try {
    const res = await knowledgeApi.syncMainNote(code)
    const blocks = res?.blocks_written || []
    if (res?.changed) {
      ElMessage.success(`主笔记已同步，写入 ${blocks.length} 个自动区章节`)
    } else {
      ElMessage.info('主笔记无变更（关联数据未发生变化）')
    }
    await loadBible()
  } catch (e) {
    ElMessage.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

function openObsidian() {
  if (detail.value.obsidian_path) {
    openObsidianNote(detail.value.obsidian_path)
  }
}

function typeLabel(s) {
  const map = { requirement: '需求', operation: '工单', meeting: '会议', knowledge: '知识' }
  return map[s] || s || '知识'
}

function viewItem(item) {
  // TODO: 根据类型跳转到对应页面
  ElMessage.info(`查看 ${item.title}`)
}

onMounted(() => {
  loadDetail()
  loadBible()
})
</script>

<style scoped>
.domain-detail-view {
  padding: 16px 20px;
  background: #f5f7fa;
  min-height: 100%;
}
.detail-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}
.gtag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 600;
}
.detail-breadcrumb {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}
.bc-link { color: #2f6fed; text-decoration: none; }
.bc-sep { margin: 0 6px; }
.bc-current { color: #64748b; }
.detail-actions { display: flex; gap: 10px; }

.detail-body {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  align-items: start;
}
.detail-left, .detail-right { display: flex; flex-direction: column; gap: 14px; }

.dcard {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 14px 16px;
}
.dcard-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: #1f2d3d;
  margin-bottom: 12px;
}
.dcard-sub {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}
.bible-list { display: flex; flex-direction: column; gap: 8px; }
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
.mini-list { display: flex; flex-direction: column; gap: 8px; }
.mini-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #1f2d3d;
}
.mini-item b { font-family: 'JetBrains Mono', monospace; color: #1f2d3d; }
.health-note {
  margin-top: 10px;
  padding: 8px 10px;
  background: #fdf2e8;
  border-radius: 8px;
  font-size: 12px;
  color: #f0a64a;
}

/* 右侧 tab */
.dtabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 14px;
}
.dtab {
  padding: 9px 14px;
  cursor: pointer;
  color: #64748b;
  font-size: 13px;
  border-bottom: 2px solid transparent;
}
.dtab.on { color: #2f6fed; border-color: #2f6fed; }
.dbody { min-height: 300px; }
.tab-content { padding: 4px 0; }

/* 关联表格 */
.filt { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.f {
  padding: 4px 10px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
}
.f.on { border-color: #2f6fed; color: #2f6fed; }
.rel-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.rel-table th {
  text-align: left;
  color: #64748b;
  font-weight: 600;
  font-size: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid #e4e7ed;
}
.rel-table td {
  padding: 9px 10px;
  border-bottom: 1px solid #ebeef5;
}
.ptag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  background: #ecf5ff;
  color: #409eff;
}
.link-btn {
  font-size: 12px;
  color: #2f6fed;
  text-decoration: none;
}
.empty-row { text-align: center; color: #909399; }

/* 自动区 */
.auto-status { display: flex; flex-direction: column; gap: 10px; }
.auto-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 8px;
}
.auto-label { color: #64748b; font-size: 13px; }
.auto-val { font-size: 13px; font-weight: 600; }
.auto-val.ok { color: #10b981; }
.auto-val.warn { color: #f0a64a; }
.note {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

/* markdown body */
.markdown-body {
  font-size: 13px;
  line-height: 1.7;
  color: #1f2d3d;
}
.markdown-body h1, .markdown-body h2, .markdown-body h3 {
  margin: 16px 0 8px;
  color: #1f2d3d;
}
.markdown-body p { margin: 8px 0; }
.markdown-body ul { padding-left: 20px; }

@media (max-width: 1200px) {
  .detail-body { grid-template-columns: 1fr; }
}
</style>
