<template>
  <div class="hub-panel">
    <!-- 领域卡片网格 -->
    <div class="hub-header">
      <h3 class="hub-title">业务领域</h3>
      <el-button size="small" type="primary" :loading="syncLoading" @click="syncAll">
        <el-icon><Refresh /></el-icon> 一键同步全部主笔记
      </el-button>
    </div>

    <div v-loading="loading" class="hub-cards">
      <div
        v-for="d in domains"
        :key="d.domain_code"
        class="dk-card"
        :class="{ active: selectedDomain?.domain_code === d.domain_code }"
        @click="selectDomain(d)"
      >
        <div class="dk-card-name">{{ d.domain_name }}</div>
        <div class="dk-card-code">{{ d.domain_code }}</div>
        <div class="dk-card-group">{{ d.domain_group }}</div>
        <div class="dk-card-stats">
          <span v-if="d._reqs" class="dk-stat">{{ d._reqs }} 需求</span>
          <span v-if="d._meetings" class="dk-stat">{{ d._meetings }} 会议</span>
        </div>
      </div>
      <el-empty v-if="!loading && !domains.length" description="暂无业务领域" />
    </div>

    <!-- 选中领域详情：左产品圣经 / 右时间线 -->
    <div v-if="selectedDomain" class="hub-detail">
      <div class="hub-detail-head">
        <span class="hub-detail-title">{{ selectedDomain.domain_name }} — 全景</span>
        <el-button size="small" @click="syncOne" :loading="syncOneLoading">
          同步此领域
        </el-button>
      </div>

      <!-- 主笔记说明条 -->
      <div v-if="mainNoteTitle" class="hub-note-bar">
        <span>📓 主笔记：<strong>{{ mainNoteTitle }}</strong></span>
        <span class="hub-note-hint">产品圣经为主笔记 §2 产商品章节的结构化展示；编辑主笔记后点「同步」自动回流。</span>
        <el-button link type="primary" size="small" @click="$emit('open-note', mainNotePath)">打开主笔记</el-button>
      </div>

      <!-- 左右分栏 -->
      <div class="hub-split">
        <!-- 左：产品圣经 -->
        <div class="hub-split-left">
          <div class="hub-split-label">📖 产品圣经（产商品与资费体系）</div>
          <div v-loading="bibleLoading" class="hub-bible">
            <MarkdownRender v-if="bibleMarkdown" :content="bibleMarkdown" />
            <el-empty v-else-if="!bibleLoading" description="暂无产商品体系内容（同步主笔记后自动生成）" :image-size="80" />
          </div>
        </div>

        <!-- 右：时间线 -->
        <div class="hub-split-right">
          <div class="hub-split-label">📅 业务时间线</div>
          <BusinessTimeline
            :domain-code="selectedDomain.domain_code"
            @open-note="$emit('open-note', $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Notebook } from '@element-plus/icons-vue'
import { basicDataApi } from '@/api/basicData.js'
import { knowledgeApi } from '@/api/knowledge.js'
import BusinessTimeline from '@/components/Common/BusinessTimeline.vue'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import { productBibleApi } from '@/api/productBible.js'
import { bus, EVT_DOMAINS_CHANGED } from '@/utils/bus'

const emit = defineEmits(['open-note'])
const router = useRouter()

const loading = ref(false)
const domains = ref([])
const selectedDomain = ref(null)
const syncLoading = ref(false)
const syncOneLoading = ref(false)
const mainNoteTitle = ref('')
const mainNotePath = ref('')
const bibleMarkdown = ref('')
const bibleLoading = ref(false)

const loadDomains = async () => {
  loading.value = true
  try {
    const res = await basicDataApi.getBusinessDomains()
    domains.value = (res || []).map((d) => ({ ...d, _reqs: 0, _meetings: 0 }))
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
  // 预取产品圣经 §2 产商品章节（切到产品圣经 Tab 时直接渲染）
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
    const res = await productBibleApi.getBible(code)
    bibleMarkdown.value = res?.markdown || ''
  } catch {
    bibleMarkdown.value = ''
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
    // 同步后产品圣经内容可能更新，刷新
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
  gap: 16px;
  height: 100%;
}
.hub-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.hub-title {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 700;
}
.hub-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.dk-card {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.dk-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-card);
}
.dk-card.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.dk-card-name {
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--text-primary);
}
.dk-card-code {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-top: 2px;
}
.dk-card-group {
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  margin-top: 4px;
}
.dk-card-stats {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.dk-stat {
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-secondary);
}
.hub-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
}
.hub-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.hub-detail-title {
  font-size: var(--fs-md);
  font-weight: 700;
}
/* 主笔记说明条 */
.hub-note-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  flex-wrap: wrap;
}
.hub-note-bar strong {
  color: var(--text-primary);
}
/* 左右分栏 */
.hub-split {
  display: flex;
  gap: 16px;
  min-height: 400px;
}
.hub-split-left,
.hub-split-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.hub-split-left {
  border-right: 1px solid var(--border-subtle);
  padding-right: 16px;
}
.hub-split-label {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  flex-shrink: 0;
}
.hub-bible {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  min-height: 200px;
}
</style>
