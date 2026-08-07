<template>
  <div class="related-knowledge-panel" v-if="domainCode">
    <div class="rkp-header">
      <el-icon><Collection /></el-icon>
      <span>相关知识</span>
      <el-button v-if="showSediment" size="small" type="primary" link @click="onSediment">
        沉淀知识
      </el-button>
    </div>

    <div v-if="loading" class="rkp-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>

    <div v-else-if="notes.length === 0" class="rkp-empty">
      暂无该领域的知识笔记
    </div>

    <div v-else class="rkp-list">
      <div
        v-for="note in notes"
        :key="note.id"
        class="rkp-item"
        @click="onNoteClick(note)"
      >
        <el-tooltip :content="note.title" placement="top">
          <span class="rkp-title">{{ note.title }}</span>
        </el-tooltip>
        <el-tag size="small" type="info" v-if="note.sub_category">{{ note.sub_category }}</el-tag>
      </div>
    </div>

    <div v-if="!domainCode" class="rkp-empty">
      请先选择业务领域
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { knowledgeApi } from '@/api/knowledge.js'
import { obsidianApi } from '@/api/obsidian.js'

const props = defineProps({
  domainCode: { type: String, default: '' },
  showSediment: { type: Boolean, default: false },
  sedimentParams: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['sediment', 'note-click'])

const notes = ref([])
const loading = ref(false)

const fetchNotes = async () => {
  if (!props.domainCode) {
    notes.value = []
    return
  }
  loading.value = true
  try {
    const data = await knowledgeApi.listItems({
      domain_code: props.domainCode,
      page_size: 10,
    })
    notes.value = data?.items || []
  } catch {
    notes.value = []
  } finally {
    loading.value = false
  }
}

const onSediment = () => {
  emit('sediment', props.domainCode)
}

const onNoteClick = (note) => {
  emit('note-click', note)
}

watch(() => props.domainCode, fetchNotes, { immediate: true })
</script>

<style scoped>
.related-knowledge-panel {
  border: 1px solid var(--border-subtle, #e4e7ed);
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
  background: var(--bg-secondary, #fafafa);
}
.rkp-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}
.rkp-loading, .rkp-empty {
  text-align: center;
  padding: 20px 0;
  font-size: 12.5px;
  color: var(--text-secondary, #909399);
}
.rkp-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 260px;
  overflow-y: auto;
}
.rkp-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12.5px;
  transition: background var(--transition-fast, .2s);
}
.rkp-item:hover {
  background: var(--accent-soft, rgba(64,158,255,.08));
}
.rkp-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary, #303133);
}
</style>
