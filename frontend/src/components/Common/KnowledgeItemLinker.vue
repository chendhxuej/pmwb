<template>
  <div class="knowledge-item-linker">
    <!-- 头部：条目维度关联管理 -->
    <div class="kil-header">
      <span class="kil-title">
        <el-icon><Link /></el-icon>
        过程性对象关联
        <el-tag v-if="links.length" size="small" type="success">{{ links.length }}</el-tag>
      </span>
      <div class="kil-ops">
        <el-button size="small" type="primary" link @click="openPicker">＋ 关联对象</el-button>
      </div>
    </div>

    <div v-if="loading" class="kil-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>

    <div v-else-if="links.length === 0" class="kil-empty">
      <div>尚未关联需求 / 工单 / 会议 / 运营对象</div>
      <el-button size="small" type="primary" plain @click="openPicker">＋ 关联过程性对象</el-button>
    </div>

    <div v-else class="kil-list">
      <div v-for="lk in links" :key="lk.link_id" class="kil-item">
        <span class="kil-ico" :style="{ background: sourceColor(lk.source_type), color: '#fff' }">
          {{ sourceAbbr(lk.source_type) }}
        </span>
        <div class="kil-main">
          <div class="kil-name" :title="lk.source_id">{{ sourceLabelFull(lk.source_type) }} · {{ lk.source_id }}</div>
          <div class="kil-sub" v-if="lk.note">{{ lk.note }}</div>
        </div>
        <el-tag v-if="lk.link_type !== 'main'" size="small" type="info">{{ linkTypeLabel(lk.link_type) }}</el-tag>
        <el-button size="small" link type="danger" @click="removeLink(lk)">移除</el-button>
      </div>
    </div>

    <!-- 领域知识展示（保留 RelatedKnowledgePanel 能力） -->
    <div class="kil-domain" v-if="domainCode">
      <div class="kil-domain-head">
        <el-icon><Collection /></el-icon>
        <span>同领域知识（{{ domainCode }}）</span>
      </div>
      <div v-if="domainLoading" class="kil-loading"><el-icon class="is-loading"><Loading /></el-icon></div>
      <div v-else-if="domainNotes.length === 0" class="kil-empty small">暂无该领域其他知识笔记</div>
      <div v-else class="kil-domain-list">
        <div
          v-for="note in domainNotes"
          :key="note.id"
          class="kil-domain-item"
          :class="{ active: note.id === activeItemId }"
          @click="$emit('note-click', note)"
        >
          <span class="kil-domain-name">{{ note.title }}</span>
          <el-tag v-if="note.sub_category" size="small" type="info">{{ note.sub_category }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 关联选择弹窗 -->
    <el-dialog v-model="pickerVisible" title="关联过程性对象" width="620px" append-to-body>
      <el-form label-width="88px" class="kil-form">
        <el-form-item label="对象类型">
          <el-select v-model="pickerForm.source_type" style="width: 100%">
            <el-option v-for="opt in SOURCE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象ID">
          <el-input v-model="pickerForm.source_id" placeholder="如 REQ-2025-001 / 工单id / 会议id" clearable />
        </el-form-item>
        <el-form-item label="链接类型">
          <el-radio-group v-model="pickerForm.link_type">
            <el-radio value="main">主笔记</el-radio>
            <el-radio value="sub">子笔记</el-radio>
            <el-radio value="deliverable">交付物</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="关联说明">
          <el-input v-model="pickerForm.note" type="textarea" :rows="2" placeholder="可选：描述该对象与本笔记的关系" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pickerVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!pickerForm.source_id" @click="confirmLink">
          建立关联
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { knowledgeApi } from '@/api/knowledge.js'

const props = defineProps({
  // 知识条目 ID（条目维度关联管理的锚点）
  itemId: { type: [Number, String], default: null },
  // 领域编码（保留「同领域知识展示」能力）
  domainCode: { type: String, default: '' },
  // 当前激活的条目 id（高亮用）
  activeItemId: { type: [Number, String], default: null },
})

const emit = defineEmits(['note-click', 'changed'])

const SOURCE_OPTIONS = [
  { value: 'requirement', label: '需求' },
  { value: 'ticket', label: '开发工单' },
  { value: 'operation', label: '运营问题' },
  { value: 'meeting', label: '会议' },
  { value: 'deliverable', label: '交付物' },
  { value: 'key_work', label: '重点工作' },
]
const SOURCE_LABEL = Object.fromEntries(SOURCE_OPTIONS.map((o) => [o.value, o.label]))
const SOURCE_ABBR = { requirement: 'R', ticket: 'T', operation: 'O', meeting: 'M', deliverable: 'D', key_work: 'K' }
const SOURCE_COLOR = {
  requirement: 'var(--accent)', ticket: 'var(--success)', operation: 'var(--warning)',
  meeting: 'var(--accent)', deliverable: 'var(--danger)', key_work: 'var(--text-muted)',
}
const sourceLabelFull = (st) => SOURCE_LABEL[st] || st || '未知'
const sourceAbbr = (st) => SOURCE_ABBR[st] || '·'
const sourceColor = (st) => SOURCE_COLOR[st] || 'var(--text-muted)'
const linkTypeLabel = (lt) => ({ main: '主笔记', sub: '子笔记', deliverable: '交付物' }[lt] || lt)

const links = ref([])
const loading = ref(false)
const pickerVisible = ref(false)
const pickerForm = ref({ source_type: 'requirement', source_id: '', link_type: 'main', note: '' })

const domainNotes = ref([])
const domainLoading = ref(false)

const fetchLinks = async () => {
  if (!props.itemId) {
    links.value = []
    return
  }
  loading.value = true
  try {
    const data = await knowledgeApi.listByItem(props.itemId)
    links.value = data || []
  } catch (e) {
    links.value = []
  } finally {
    loading.value = false
  }
}

const fetchDomainNotes = async () => {
  if (!props.domainCode) {
    domainNotes.value = []
    return
  }
  domainLoading.value = true
  try {
    const data = await knowledgeApi.listItems({ domain_code: props.domainCode, page_size: 10 })
    domainNotes.value = (data?.items || []).filter((i) => String(i.id) !== String(props.itemId))
  } catch {
    domainNotes.value = []
  } finally {
    domainLoading.value = false
  }
}

const openPicker = () => {
  pickerForm.value = { source_type: 'requirement', source_id: '', link_type: 'main', note: '' }
  pickerVisible.value = true
}

const confirmLink = async () => {
  if (!pickerForm.value.source_id.trim()) return
  try {
    const payload = {
      source_type: pickerForm.value.source_type,
      source_id: pickerForm.value.source_id.trim(),
      link_type: pickerForm.value.link_type,
      note: pickerForm.value.note || null,
    }
    if (props.domainCode) payload.domain_code = props.domainCode
    await knowledgeApi.createItemLink(props.itemId, payload)
    ElMessage.success('关联已建立')
    pickerVisible.value = false
    await fetchLinks()
    emit('changed')
  } catch (e) {
    ElMessage.error('关联失败：' + (e.message || '未知错误'))
  }
}

const removeLink = async (lk) => {
  try {
    await knowledgeApi.deleteItemLink(props.itemId, lk.source_type, lk.source_id)
    ElMessage.success('已移除关联')
    await fetchLinks()
    emit('changed')
  } catch (e) {
    ElMessage.error('移除失败：' + (e.message || '未知错误'))
  }
}

watch(() => props.itemId, fetchLinks, { immediate: true })
watch(() => props.domainCode, fetchDomainNotes, { immediate: true })
onMounted(() => {
  fetchLinks()
  fetchDomainNotes()
})
</script>

<style scoped>
.knowledge-item-linker {
  border: 1px solid var(--border-subtle, #e4e7ed);
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
  background: var(--bg-secondary, #fafafa);
}
.kil-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}
.kil-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.kil-ops {
  display: flex;
  gap: 4px;
}
.kil-loading,
.kil-empty {
  text-align: center;
  padding: 16px 0;
  font-size: 12.5px;
  color: var(--text-secondary, #909399);
}
.kil-empty.small {
  padding: 8px 0;
  font-size: 12px;
}
.kil-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
  margin-bottom: 6px;
}
.kil-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fff;
  font-size: 12.5px;
}
.kil-ico {
  width: 20px;
  height: 20px;
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.kil-main {
  flex: 1;
  min-width: 0;
}
.kil-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary, #303133);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 12px;
}
.kil-sub {
  font-size: 11.5px;
  color: var(--text-secondary, #909399);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kil-domain {
  border-top: 1px dashed var(--border-subtle, #e4e7ed);
  padding-top: 10px;
  margin-top: 4px;
}
.kil-domain-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-secondary, #909399);
  margin-bottom: 8px;
}
.kil-domain-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
}
.kil-domain-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12.5px;
  transition: background var(--transition-fast, .2s);
}
.kil-domain-item:hover {
  background: var(--accent-soft, rgba(64, 158, 255, .08));
}
.kil-domain-item.active {
  background: var(--accent-soft, rgba(64, 158, 255, .08));
}
.kil-domain-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary, #303133);
}
.kil-form {
  padding-top: 6px;
}
</style>
