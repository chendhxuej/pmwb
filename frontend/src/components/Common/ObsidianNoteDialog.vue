<template>
  <el-dialog
    :model-value="modelValue"
    title="Obsidian 笔记预览"
    width="820px"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="obsidian-note">
      <template v-if="loadedPath">
        <div v-if="exists" class="note-body">
          <MarkdownRender :content="content" />
        </div>
        <el-empty v-else description="笔记文件不存在">
          <template #description>
            <span>未找到笔记文件：<code>{{ loadedPath }}</code></span>
          </template>
        </el-empty>
      </template>
      <el-empty v-else description="未关联 Obsidian 笔记" />
    </div>
    <template #footer>
      <div class="note-footer">
        <span class="note-path" :title="loadedPath">{{ loadedPath || '—' }}</span>
        <div>
          <el-button
            v-if="exists && absolutePath"
            type="primary"
            tag="a"
            :href="obsidianUri"
            target="_blank"
          >
            在 Obsidian 打开
          </el-button>
          <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import { obsidianApi } from '@/api/obsidian'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  path: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const loadedPath = ref('')
const exists = ref(false)
const content = ref('')
const absolutePath = ref('')

const obsidianUri = computed(() =>
  absolutePath.value
    ? `obsidian://open?path=${encodeURIComponent(absolutePath.value)}`
    : ''
)

const load = async (relPath) => {
  if (!relPath) {
    loadedPath.value = ''
    return
  }
  loading.value = true
  try {
    const res = await obsidianApi.getContent(relPath)
    loadedPath.value = relPath
    exists.value = res.exists
    content.value = res.content || ''
    absolutePath.value = res.absolute_path || ''
  } catch (e) {
    ElMessage.error('读取笔记失败')
    loadedPath.value = relPath
    exists.value = false
    content.value = ''
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.path],
  ([visible, p]) => {
    if (visible && p) {
      load(p)
    } else if (!visible) {
      // 关闭时清空，避免下次打开残留旧内容
      loadedPath.value = ''
      exists.value = false
      content.value = ''
      absolutePath.value = ''
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.obsidian-note {
  min-height: 240px;
  max-height: 60vh;
  overflow: auto;
}
.note-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.note-path {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}
</style>
