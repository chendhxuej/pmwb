<template>
  <div class="hub-panel">
    <!-- 领域卡片网格 -->
    <div class="hub-header">
      <div class="hub-header-titles">
        <h3 class="hub-title">业务领域</h3>
        <span class="hub-subtitle">选择领域查看其知识全景（标准结构 + 全过程时间线）</span>
      </div>
      <el-button type="primary" :loading="syncLoading" @click="syncAll">
        <el-icon><Refresh /></el-icon>
        <span>一键同步全部主笔记</span>
      </el-button>
    </div>

    <div v-loading="loading" class="hub-cards">
      <button
        v-for="d in domains"
        :key="d.domain_code"
        class="dk-card"
        :class="{ active: selectedDomain?.domain_code === d.domain_code }"
        @click="selectDomain(d)"
      >
        <span class="dk-avatar">{{ d.domain_name.slice(0, 1) }}</span>
        <span class="dk-card-body">
          <span class="dk-card-name">{{ d.domain_name }}</span>
          <span class="dk-card-code">{{ d.domain_code }}</span>
        </span>
        <span v-if="d.domain_group" class="dk-card-tag">{{ d.domain_group }}</span>
      </button>
      <el-empty v-if="!loading && !domains.length" description="暂无业务领域" />
    </div>

    <!-- 选中领域详情：左知识标准化管理 / 右时间线 -->
    <div v-if="selectedDomain" class="hub-detail">
      <div class="hub-detail-head">
        <div class="hub-detail-title">
          <el-icon class="hub-detail-ico"><DataBoard /></el-icon>
          <span>{{ selectedDomain.domain_name }} · 业务全景</span>
        </div>
        <div class="hub-detail-actions">
          <el-button plain :loading="syncOneLoading" @click="syncOne">
            <el-icon><Refresh /></el-icon>
            <span>同步此领域</span>
          </el-button>
          <el-button
            v-if="mainNotePath"
            plain
            type="primary"
            @click="$emit('open-note', mainNotePath)"
          >
            <el-icon><FolderOpened /></el-icon>
            <span>打开主笔记</span>
          </el-button>
        </div>
      </div>

      <!-- 主笔记说明条 -->
      <div v-if="mainNoteTitle" class="hub-note-bar">
        <el-icon class="hub-note-ico"><Notebook /></el-icon>
        <span class="hub-note-text">
          主笔记：<strong>{{ mainNoteTitle }}</strong>
          <span class="hub-note-hint">展示主笔记标准结构（业务概述 / 产商品 / 场景 SOP / 规则 / 时间线等）；编辑后点「同步此领域」自动回流。</span>
        </span>
      </div>

      <!-- 左右分栏 -->
      <div class="hub-split">
        <!-- 左：知识标准化管理 -->
        <section class="hub-col">
          <div class="hub-col-label">
            <el-icon><Notebook /></el-icon>
            <span>知识标准化管理（主笔记标准结构）</span>
          </div>
          <div v-loading="bibleLoading" class="hub-bible">
            <template v-if="bibleSections.length">
              <article v-for="sec in bibleSections" :key="sec.key" class="hub-sec">
                <header class="hub-sec-head">
                  <span class="hub-sec-badge" :class="'badge-' + sec.kind">{{ sec.kind_label }}</span>
                  <h4 class="hub-sec-title">{{ sec.title }}</h4>
                </header>
                <div class="hub-sec-body" v-if="sec.markdown && sec.markdown !== '_暂无数据_'">
                  <MarkdownRender :content="sec.markdown" />
                </div>
                <div class="hub-sec-empty" v-else>暂无内容</div>
              </article>
            </template>
            <el-empty v-else-if="!bibleLoading" description="暂无主笔记内容（同步后自动生成）" :image-size="80" />
          </div>
        </section>

        <!-- 右：时间线 -->
        <section class="hub-col">
          <div class="hub-col-label">
            <el-icon><Clock /></el-icon>
            <span>业务全过程时间线</span>
          </div>
          <div class="hub-timeline-wrap">
            <BusinessTimeline
              :domain-code="selectedDomain.domain_code"
              @open-note="$emit('open-note', $event)"
            />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Notebook, FolderOpened, DataBoard, Clock } from '@element-plus/icons-vue'
import { basicDataApi } from '@/api/basicData.js'
import { knowledgeApi } from '@/api/knowledge.js'
import BusinessTimeline from '@/components/Common/BusinessTimeline.vue'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import { productBibleApi } from '@/api/productBible.js'
import { bus, EVT_DOMAINS_CHANGED } from '@/utils/bus'

const emit = defineEmits(['open-note'])

const loading = ref(false)
const domains = ref([])
const selectedDomain = ref(null)
const syncLoading = ref(false)
const syncOneLoading = ref(false)
const mainNoteTitle = ref('')
const mainNotePath = ref('')
const bibleSections = ref([])
const bibleLoading = ref(false)

const loadDomains = async () => {
  loading.value = true
  try {
    const res = await basicDataApi.getBusinessDomains()
    domains.value = (res || []).map((d) => ({ ...d }))
    // 自动选第一个有数据的领域
    if (domains.value.length && !selectedDomain.value) {
      selectDomain(domains.value[0])
    }
  } finally {
    loading.value = false
  }
}

const selectDomain = async (d) => {
  if (selectedDomain.value?.domain_code === d.domain_code) return
  selectedDomain.value = d
  mainNoteTitle.value = ''
  mainNotePath.value = ''
  // 预取知识标准化管理标准结构（切到主笔记 Tab 时直接渲染）
  loadBible(d.domain_code)

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

const syncAll = async () => {
  syncLoading.value = true
  try {
    await knowledgeApi.ensureMainNotes()
    ElMessage.success('已确保所有领域主笔记')
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
    // 同步后知识标准化管理内容可能更新，刷新
    loadBible(selectedDomain.value.domain_code)
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncOneLoading.value = false
  }
}

onMounted(loadDomains)
// 领域增删改后全局通知刷新（kc-5：跨模块联动）
bus.on(EVT_DOMAINS_CHANGED, loadDomains)
onBeforeUnmount(() => bus.off(EVT_DOMAINS_CHANGED, loadDomains))
defineExpose({ reload: loadDomains })
</script>

<style scoped>
.hub-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100%;
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
  gap: 3px;
}
.hub-title {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 700;
  letter-spacing: .3px;
}
.hub-subtitle {
  font-size: var(--fs-sm);
  color: var(--text-muted);
}
.hub-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.dk-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: all var(--transition-fast);
}
.dk-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}
.dk-card.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.dk-avatar {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--fs-md);
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, var(--accent), #5b8af1);
}
.dk-card.active .dk-avatar {
  background: linear-gradient(135deg, var(--accent-hover), var(--accent));
}
.dk-card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.dk-card-name {
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-card-code {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}
.dk-card-tag {
  flex-shrink: 0;
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hub-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 16px;
  border-top: 1px solid var(--border-subtle);
}
.hub-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.hub-detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-md);
  font-weight: 700;
  color: var(--text-primary);
}
.hub-detail-ico {
  color: var(--accent);
  font-size: var(--fs-lg);
}
.hub-detail-actions {
  display: flex;
  gap: 10px;
}
.hub-note-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  flex-wrap: wrap;
}
.hub-note-ico {
  color: var(--accent);
  flex-shrink: 0;
}
.hub-note-text {
  line-height: 1.5;
}
.hub-note-text strong {
  color: var(--text-primary);
}
.hub-note-hint {
  color: var(--text-muted);
}
.hub-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  min-height: 420px;
}
.hub-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.hub-col-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-bottom: none;
}
.hub-col-label .el-icon {
  color: var(--accent);
}
.hub-bible {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  min-height: 220px;
}
.hub-timeline-wrap {
  flex: 1;
  overflow: hidden;
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  min-height: 220px;
}
.hub-sec {
  padding: 14px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.hub-sec:first-child {
  padding-top: 0;
}
.hub-sec:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.hub-sec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.hub-sec-badge {
  font-size: var(--fs-xs);
  padding: 2px 9px;
  border-radius: 999px;
  font-weight: 600;
  flex-shrink: 0;
}
.badge-baseline { background: #ecf5ff; color: #409eff; }
.badge-auto { background: #f0f9eb; color: #67c23a; }
.badge-system { background: #f4f4f5; color: #909399; }
.hub-sec-title {
  margin: 0;
  font-size: var(--fs-base);
  font-weight: 700;
  color: var(--text-primary);
}
.hub-sec-body {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  line-height: 1.65;
}
.hub-sec-empty {
  font-size: var(--fs-sm);
  color: var(--text-muted);
  padding: 4px 0;
}
</style>
