<template>
  <div class="domain-knowledge">
    <div class="dk-header">
      <h2>按业务领域浏览</h2>
      <span class="dk-sub">按政企业务线聚合关联的知识条目、需求、会议和运营工单</span>
      <el-button size="small" text type="primary" @click="$router.push('/business-domains')" style="margin-left: auto;">
        管理业务领域
      </el-button>
    </div>

    <el-row v-loading="loading" :gutter="16" class="dk-grid">
      <el-col v-for="d in domains" :key="d.domain_code" :xs="24" :sm="12" :lg="8" class="dk-col">
        <div class="dk-card" @click="selectDomain(d)">
          <div class="dk-card-head">
            <span class="dk-card-name">{{ d.domain_name }}</span>
            <el-tag size="small" type="info">{{ d.domain_group }}</el-tag>
          </div>
          <div class="dk-card-desc" v-if="d.description">{{ d.description }}</div>
          <el-divider style="margin: 12px 0" />
          <div class="dk-stats">
            <div class="dk-stat">
              <span class="dk-stat-num">{{ d.knowledge_count || 0 }}</span>
              <span class="dk-stat-label">知识条目</span>
            </div>
            <div class="dk-stat">
              <span class="dk-stat-num">{{ d.req_count || 0 }}</span>
              <span class="dk-stat-label">需求</span>
            </div>
            <div class="dk-stat">
              <span class="dk-stat-num">{{ d.issue_count || 0 }}</span>
              <span class="dk-stat-label">运营工单</span>
            </div>
            <div class="dk-stat">
              <span class="dk-stat-num">{{ d.meeting_count || 0 }}</span>
              <span class="dk-stat-label">会议</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 领域详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="`${selectedDomain?.domain_name} - 关联内容`" width="860px">
      <div class="dk-dialog-bar">
        <span class="dk-dialog-hint">主笔记为该领域知识总入口，子笔记按下分类分组展示</span>
        <el-button size="small" type="primary" :loading="ensureLoading" @click="ensureMainNotes">
          确保主笔记
        </el-button>
      </div>
      <el-tabs v-model="detailTab">
        <el-tab-pane label="知识主笔记" name="knowledge">
          <!-- 主笔记概述 -->
          <div v-if="related.main_note" class="dk-main-note">
            <div class="dk-main-note-head">
              <el-icon><Star /></el-icon>
              <span class="dk-main-note-title">{{ related.main_note.title }}</span>
              <el-button link type="primary" size="small" @click="openNote(related.main_note.obsidian_path)">打开主笔记</el-button>
            </div>
            <div class="dk-main-note-sub" v-if="related.main_note.sub_title">{{ related.main_note.sub_title }}</div>
          </div>
          <el-empty v-else description="该领域暂无主笔记，点击右上角「确保主笔记」自动生成" />

          <!-- 子笔记按分类分组 -->
          <div v-for="g in groupedSubNotes" :key="g.category" class="dk-sub-group">
            <div class="dk-sub-group-head">
              <span class="dk-sub-group-label">{{ g.label }}</span>
              <span class="dk-sub-group-count">{{ g.items.length }}</span>
            </div>
            <div class="dk-sub-list">
              <div
                v-for="n in g.items"
                :key="n.id"
                class="dk-sub-item"
                @click="n.obsidian_path && openNote(n.obsidian_path)"
              >
                <span class="dk-sub-title">{{ n.title }}</span>
                <span class="dk-sub-cat" v-if="n.sub_title">{{ n.sub_title }}</span>
                <el-button link type="primary" size="small" @click.stop="openNote(n.obsidian_path)">查看</el-button>
              </div>
            </div>
          </div>
          <el-empty v-if="!relLoading && !related.sub_notes.length" description="暂无子笔记" />
        </el-tab-pane>
        <el-tab-pane label="需求" name="requirements">
          <el-table :data="related.requirements" size="small" max-height="420" v-loading="relLoading" @row-click="(row) => goTo('requirement', row.code)">
            <el-table-column prop="code" label="需求编号" width="160" />
            <el-table-column prop="title" label="需求名称" min-width="220" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100" />
          </el-table>
          <el-empty v-if="!relLoading && !related.requirements.length" description="暂无关联需求" />
        </el-tab-pane>
        <el-tab-pane label="会议" name="meetings">
          <el-table :data="related.meetings" size="small" max-height="420" v-loading="relLoading" @row-click="(row) => row.obsidian_path ? openNote(row.obsidian_path) : goTo('meeting', row.code)">
            <el-table-column prop="code" label="会议编号" width="160" />
            <el-table-column prop="title" label="会议主题" min-width="220" show-overflow-tooltip />
            <el-table-column prop="sub_title" label="时间" width="120" />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="row.obsidian_path ? openNote(row.obsidian_path) : goTo('meeting', row.code)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!relLoading && !related.meetings.length" description="暂无关联会议" />
        </el-tab-pane>
        <el-tab-pane label="运营工单" name="issues">
          <el-table :data="related.issues" size="small" max-height="420" v-loading="relLoading" @row-click="(row) => goTo('issue', row.code)">
            <el-table-column prop="code" label="工单编号" width="150" />
            <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
            <el-table-column prop="category" label="大类" width="100" />
            <el-table-column prop="status" label="状态" width="100" />
          </el-table>
          <el-empty v-if="!relLoading && !related.issues.length" description="暂无关联运营工单" />
        </el-tab-pane>
        <el-tab-pane label="关联时间线" name="timeline">
          <el-table :data="related.timeline" size="small" max-height="420" v-loading="relLoading">
            <el-table-column label="来源" width="110">
              <template #default="{ row }">
                <el-tag size="small">{{ sourceLabel(row.source_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="source_id" label="来源ID" width="170" show-overflow-tooltip />
            <el-table-column prop="note_title" label="关联知识笔记" min-width="200" show-overflow-tooltip />
            <el-table-column prop="link_note" label="关联说明" min-width="160" show-overflow-tooltip />
            <el-table-column prop="created_at" label="关联时间" width="140" />
          </el-table>
          <el-empty v-if="!relLoading && !related.timeline.length" description="暂无通过关联建立的跨对象关联" />
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { basicDataApi } from '@/api/basicData.js'
import { knowledgeApi } from '@/api/knowledge.js'
import { Star } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const domains = ref([])
const detailVisible = ref(false)
const detailTab = ref('knowledge')
const selectedDomain = ref(null)
const relLoading = ref(false)
const ensureLoading = ref(false)
const related = ref({
  knowledge_items: [],
  main_note: null,
  sub_notes: [],
  requirements: [],
  meetings: [],
  issues: [],
  timeline: [],
})

const SOURCE_LABELS = {
  requirement: '需求',
  ticket: '开发工单',
  operation: '运营工单',
  meeting: '会议',
  deliverable: '交付物',
  key_work: '重点工作',
}
const sourceLabel = (t) => SOURCE_LABELS[t] || t

const CATEGORY_LABELS = {
  product: '产品知识',
  operation: '运营知识',
  requirement: '需求沉淀',
  meeting: '会议沉淀',
  personal: '个人笔记',
  study: '学习沉淀',
}
const categoryLabel = (c) => CATEGORY_LABELS[c] || (c || '其他')

// 子笔记按分类分组（树形展示）
const groupedSubNotes = computed(() => {
  const map = {}
  for (const n of related.value.sub_notes || []) {
    const c = n.category || 'other'
    if (!map[c]) map[c] = []
    map[c].push(n)
  }
  return Object.keys(map).map((c) => ({
    category: c,
    label: categoryLabel(c),
    items: map[c],
  }))
})

const ensureMainNotes = async () => {
  ensureLoading.value = true
  try {
    const res = await knowledgeApi.ensureMainNotes()
    ElMessage.success(res?.message || '主笔记已保活')
    if (selectedDomain.value) {
      const r = await basicDataApi.getDomainRelated(selectedDomain.value.domain_code)
      related.value = r || related.value
    }
  } catch {
    ElMessage.error('保活失败')
  } finally {
    ensureLoading.value = false
  }
}

const goTo = (type, code) => {
  const map = {
    requirement: '/requirement-delivery',
    meeting: '/meeting',
    issue: '/operation',
    operation: '/operation',
    ticket: '/dev-ticket',
  }
  const target = map[type] || '/knowledge'
  router.push({ path: target, query: code ? { q: code } : {} })
}

const loadDomains = async () => {
  loading.value = true
  try {
    domains.value = await basicDataApi.getBusinessDomains()
  } catch {
    // 静默
  } finally {
    loading.value = false
  }
}

const selectDomain = async (d) => {
  selectedDomain.value = d
  detailVisible.value = true
  detailTab.value = 'knowledge'
  related.value = { knowledge_items: [], requirements: [], meetings: [], issues: [] }
  relLoading.value = true
  try {
    const res = await basicDataApi.getDomainRelated(d.domain_code)
    related.value = res || related.value
  } catch {
    // 静默
  } finally {
    relLoading.value = false
  }
}

const openNote = (path) => {
  if (!path) return
  window.open(`obsidian://open?vault=知识图谱&file=${encodeURIComponent(path)}`, '_blank')
}

onMounted(loadDomains)
</script>

<style scoped>
.domain-knowledge {
  padding: 16px;
}
.dk-header {
  margin-bottom: 20px;
}
.dk-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
  color: #e0e0e0;
}
.dk-sub {
  font-size: 13px;
  color: #888;
}
.dk-grid {
  margin: 0 !important;
}
.dk-col {
  margin-bottom: 16px;
}
.dk-card {
  background: #1e1e2e;
  border: 1px solid #2a2a3e;
  border-radius: 10px;
  padding: 18px;
  cursor: pointer;
  transition: all .2s;
}
.dk-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, .15);
}
.dk-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.dk-card-name {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
}
.dk-card-desc {
  margin-top: 8px;
  font-size: 13px;
  color: #999;
}
.dk-stats {
  display: flex;
  gap: 20px;
}
.dk-stat {
  text-align: center;
  flex: 1;
}
.dk-stat-num {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
}
.dk-stat-label {
  font-size: 12px;
  color: #888;
}
.dk-dialog-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.dk-dialog-hint {
  font-size: 12px;
  color: #888;
}
.dk-main-note {
  background: rgba(64, 158, 255, .08);
  border: 1px solid #2a3a55;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.dk-main-note-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dk-main-note-title {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
  flex: 1;
}
.dk-main-note-sub {
  margin-top: 6px;
  font-size: 13px;
  color: #999;
}
.dk-sub-group {
  margin-bottom: 14px;
}
.dk-sub-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}
.dk-sub-group-label {
  font-size: 14px;
  font-weight: 600;
  color: #cfcfcf;
}
.dk-sub-group-count {
  font-size: 12px;
  color: #888;
  background: #2a2a3e;
  border-radius: 10px;
  padding: 0 8px;
}
.dk-sub-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.dk-sub-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #1e1e2e;
  border: 1px solid #2a2a3e;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all .15s;
}
.dk-sub-item:hover {
  border-color: #409eff;
}
.dk-sub-title {
  flex: 1;
  font-size: 13px;
  color: #dcdcdc;
}
.dk-sub-cat {
  font-size: 12px;
  color: #888;
}
</style>
