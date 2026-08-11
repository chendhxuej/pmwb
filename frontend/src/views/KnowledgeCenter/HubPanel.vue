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

    <!-- 选中领域详情：主笔记预览 + 时间线 -->
    <div v-if="selectedDomain" class="hub-detail">
      <div class="hub-detail-head">
        <span class="hub-detail-title">{{ selectedDomain.domain_name }} — 全景</span>
        <el-button size="small" @click="syncOne" :loading="syncOneLoading">
          同步此领域
        </el-button>
      </div>

      <!-- 业务时间线 -->
      <div class="hub-section">
        <div class="hub-section-title">业务时间线</div>
        <BusinessTimeline
          :domain-code="selectedDomain.domain_code"
          @open-note="$emit('open-note', $event)"
        />
      </div>

      <!-- 主笔记快速预览（有主笔记时显示） -->
      <div v-if="mainNoteTitle" class="hub-section">
        <div class="hub-section-title">
          主笔记：{{ mainNoteTitle }}
          <el-button link type="primary" size="small" @click="$emit('open-note', mainNotePath)">打开</el-button>
        </div>
        <div class="hub-note-hint">在 Obsidian 中编辑主笔记后点「同步」可自动回流关联事件到时间线。</div>
      </div>

      <!-- 产品圣经：读主笔记 §2 产商品章节 -->
      <div class="hub-section">
        <div class="hub-section-title">产品圣经（产商品与资费）</div>
        <el-button size="small" type="primary" plain @click="openBible">
          <el-icon><Notebook /></el-icon> 查看「{{ selectedDomain.domain_name }}」产商品体系
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Notebook } from '@element-plus/icons-vue'
import { basicDataApi } from '@/api/basicData.js'
import { knowledgeApi } from '@/api/knowledge.js'
import BusinessTimeline from '@/components/Common/BusinessTimeline.vue'

const emit = defineEmits(['open-note'])
const router = useRouter()

const loading = ref(false)
const domains = ref([])
const selectedDomain = ref(null)
const syncLoading = ref(false)
const syncOneLoading = ref(false)
const mainNoteTitle = ref('')
const mainNotePath = ref('')

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
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncOneLoading.value = false
  }
}

const openBible = () => {
  if (!selectedDomain.value) return
  router.push({
    name: 'KcProductBible',
    query: { domain: selectedDomain.value.domain_code },
  })
}

onMounted(loadDomains)
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
.hub-section {
  /* 容器 */
}
.hub-section-title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.hub-note-hint {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  line-height: 1.5;
}
</style>
