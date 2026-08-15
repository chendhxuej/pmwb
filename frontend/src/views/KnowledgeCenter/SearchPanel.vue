<template>
  <div class="search-panel">
    <!-- 统一搜索栏 -->
    <div class="sp-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索知识笔记、SQL脚本、产品文档…"
        clearable
        size="default"
        @keyup.enter="doSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
        <template #append>
          <el-button :icon="Search" @click="doSearch" />
        </template>
      </el-input>
      <BusinessDomainSelect v-model="filterDomain" class="sp-domain" @change="doSearch" />
    </div>

    <!-- 结果 Tab：知识库 / SQL脚本 / 全部 -->
    <el-tabs v-model="resultTab">
      <el-tab-pane label="全部" name="all">
        <div v-loading="loading" class="sp-results">
          <div v-for="item in allResults" :key="item._id" class="sp-item" @click="openItem(item)">
            <span class="sp-type-tag" :class="'type-' + item._type">{{ typeLabel(item._type) }}</span>
            <span class="sp-title">{{ item.title || item.name || '(无标题)' }}</span>
            <span v-if="item.domain_code" class="sp-domain">{{ item.domain_code }}</span>
          </div>
          <el-empty v-if="!loading && !allResults.length && keyword" :description="`未找到「${keyword}」相关内容`" />
          <el-empty v-if="!loading && !keyword" description="输入关键字开始搜索" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="知识笔记" name="knowledge">
        <div v-loading="loading">
          <div v-for="item in knowledgeResults" :key="item.id" class="sp-item" @click="$emit('open-note', item.obsidian_path)">
            <span class="sp-type-tag type-knowledge">笔记</span>
            <span class="sp-title">{{ item.title }}</span>
            <span v-if="item.category" class="sp-cat">{{ item.category }}</span>
          </div>
          <el-empty v-if="!loading && !knowledgeResults.length" description="暂无知识笔记" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="SQL 脚本" name="sql">
        <div v-loading="loading">
          <div v-for="item in sqlResults" :key="item.id" class="sp-item">
            <span class="sp-type-tag type-sql">SQL</span>
            <span class="sp-title">{{ item.title }}</span>
            <span v-if="item.category" class="sp-cat">{{ item.category }}</span>
          </div>
          <el-empty v-if="!loading && !sqlResults.length" description="暂无 SQL 脚本" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import BusinessDomainSelect from '@/components/Common/BusinessDomainSelect.vue'
import { knowledgeApi } from '@/api/knowledge.js'
import { sqlScriptApi } from '@/api/sqlScript.js'

const emit = defineEmits(['open-note'])
const keyword = ref('')
const filterDomain = ref('')
const loading = ref(false)
const resultTab = ref('all')
const knowledgeResults = ref([])
const sqlResults = ref([])
const allResults = ref([])

const TYPE_MAP = {
  knowledge: '笔记',
  sql: 'SQL',
  product: '产品',
}
const typeLabel = (t) => TYPE_MAP[t] || t

const doSearch = async () => {
  loading.value = true
  try {
    const params = { keyword: keyword.value || undefined }
    if (filterDomain.value) params.domain_code = filterDomain.value

    const [kRes, sRes] = await Promise.allSettled([
      knowledgeApi.listItems(params).catch(() => ({ data: [] })),
      sqlScriptApi.listSqlScripts(params).catch(() => ({ data: [] })),
    ])

    knowledgeResults.value = kRes.status === 'fulfilled' ? (kRes.value?.data || []) : []
    sqlResults.value = sRes.status === 'fulfilled' ? (sRes.value?.data || []) : []

    // 合并全部结果
    allResults.value = [
      ...knowledgeResults.value.map((i) => ({ ...i, _id: `k-${i.id}`, _type: 'knowledge' })),
      ...sqlResults.value.map((i) => ({ ...i, _id: `s-${i.id}`, _type: 'sql' })),
    ]
  } finally {
    loading.value = false
  }
}

const openItem = (item) => {
  if (item._type === 'knowledge' && item.obsidian_path) {
    emit('open-note', item.obsidian_path)
  }
}

onMounted(doSearch)
watch([keyword, filterDomain], () => { if (resultTab.value !== 'all') resultTab.value = 'all'; doSearch() })
</script>

<style scoped>
.search-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.sp-bar {
  display: flex;
  gap: 10px;
  align-items: center;
}
.sp-bar .el-input {
  flex: 1;
  max-width: 480px;
}
.sp-domain {
  width: 180px;
  flex-shrink: 0;
}
.sp-results {
  min-height: 200px;
}
.sp-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}
.sp-item:hover {
  background: var(--surface-soft);
}
.sp-type-tag {
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--surface-soft);
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}
.sp-type-tag.type-knowledge { background: #eaf1fe; color: var(--accent); }
.sp-type-tag.type-sql { background: #fef7ed; color: var(--warning); }
.sp-title {
  font-size: var(--fs-base);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 400px;
}
.sp-domain, .sp-cat {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  margin-left: auto;
}
</style>
