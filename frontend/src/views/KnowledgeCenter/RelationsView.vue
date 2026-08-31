<template>
  <div class="relations-view">
    <div class="relations-header">
      <div class="relations-titles">
        <h3 class="relations-title">智能关联</h3>
        <span class="relations-subtitle">各模块录入即关联 · 便捷性优化</span>
      </div>
    </div>

    <div class="relations-grid">
      <div class="relations-card">
        <div class="card-head">
          <el-icon><EditPen /></el-icon>
          <span>录工单 / 需求时：智能推荐领域</span>
        </div>
        <div class="field">
          <label>标题（随手输入，无需先想领域）</label>
          <el-input v-model="smartTitle" placeholder="例如：一网通宽带融合开通流程优化需求" clearable @input="onTitleChange" />
        </div>
        <div v-if="suggestions.length" class="rec-box">
          <div class="rec-title">实时推荐（关键词匹配 + 名称 + 编码 + 首字母）· 点击即选用</div>
          <div class="chip-list">
            <div
              v-for="s in suggestions"
              :key="s.domain_code"
              class="chip"
              :class="{ active: selectedDomain === s.domain_code }"
              @click="pickSuggestion(s)"
            >
              <span class="chip-name">{{ s.domain_name }}</span>
              <span class="chip-group" :style="tagStyle(s.domain_group)">{{ s.domain_group }}</span>
              <span class="chip-why">{{ s.reason }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="smartTitle.trim()" class="rec-empty">未匹配到推荐领域，可换关键词试试</div>
        <div v-if="selectedDomain" class="picked-bar">
          已选用目标领域：<b>{{ selectedDomainName }}</b>
          <span class="picked-tip">已同步到右侧「选择目标领域」，勾选记录后可直接批量应用</span>
        </div>
        <div class="relations-note">支持关键词、名称包含、编码匹配、首字母匹配；点击芯片即选中目标 domain_code。</div>
      </div>

      <div class="relations-card">
        <div class="card-head">
          <el-icon><Finished /></el-icon>
          <span>批量关联（列表多选 → 一键设领域）</span>
        </div>
        <div class="batch-toolbar">
          <el-radio-group v-model="onlyUnlinked" size="small" @change="loadBatch">
            <el-radio-button :value="true">仅未关联</el-radio-button>
            <el-radio-button :value="false">全部工单</el-radio-button>
          </el-radio-group>
          <el-button size="small" :loading="batchLoading" @click="loadBatch">
            <el-icon><Refresh /></el-icon>
            <span>刷新</span>
          </el-button>
        </div>
        <div class="batch-table-wrap">
          <el-table
            v-loading="batchLoading"
            :data="batchRows"
            size="small"
            height="320"
            @selection-change="onSelectionChange"
          >
            <el-table-column type="selection" width="40" />
            <el-table-column prop="source_type" label="类型" width="70">
              <template #default="{ row }">
                <span class="tag type">{{ typeLabel(row.source_type) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" show-overflow-tooltip />
            <el-table-column prop="domain_code" label="当前领域" width="120">
              <template #default="{ row }">
                <span v-if="row.domain_code" class="tag">{{ domainName(row.domain_code) }}</span>
                <span v-else class="tag empty">未关联</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="batch-bar">
          <span>已选 {{ selectedRows.length }} 条</span>
          <BusinessDomainSelect v-model="batchDomainCode" clearable placeholder="选择目标领域" style="width: 180px" />
          <el-button type="primary" :disabled="!batchDomainCode || !selectedRows.length" :loading="applying" @click="applyBatch">
            批量应用
          </el-button>
        </div>
        <div v-if="lastResult" class="result-box" :class="{ warn: lastResult.errors.length }">
          <span v-if="lastResult.errors.length">
            成功 {{ lastResult.updated }} 条，失败 {{ lastResult.errors.length }} 条：
            {{ lastResult.errors.slice(0, 3).map((e) => e.source_id).join('、') }}
          </span>
          <span v-else>成功更新 {{ lastResult.updated }} 条，跳过 {{ lastResult.skipped }} 条</span>
        </div>
        <div class="relations-note">数据源：运营工单（operation）。勾选后选目标领域即可批量回填 domain_code。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { EditPen, Finished, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { basicDataApi, loadBusinessDomains } from '@/api/basicData'
import { operationApi } from '@/api/operation'
import BusinessDomainSelect from '@/components/Common/BusinessDomainSelect.vue'

const smartTitle = ref('')
const suggestions = ref([])
const selectedDomain = ref('')
const batchDomainCode = ref('')
const selectedRows = ref([])

const batchRows = ref([])
const batchLoading = ref(false)
const applying = ref(false)
const onlyUnlinked = ref(true)
const lastResult = ref(null)

// code -> name 映射：表格「当前领域」需要显示中文名而非编码
const domainOptions = ref([])
const domainNameMap = computed(() => {
  const m = {}
  for (const d of domainOptions.value) m[d.domain_code] = d.domain_name
  return m
})
const domainName = (code) => domainNameMap.value[code] || code
const selectedDomainName = computed(() => domainName(selectedDomain.value))

const groupColor = (g) => {
  const map = { '商客业务': '#165dff', '系统平台': '#36c5d0', '公共能力': '#3fb950', '通用': '#9da7b3' }
  return map[g] || '#165dff'
}
const tagStyle = (g) => ({ background: groupColor(g) + '15', color: groupColor(g) })

function typeLabel(s) {
  return { operation: '工单', requirement: '需求', ticket: '开发', meeting: '会议' }[s] || s || '工单'
}

async function loadDomainOptions() {
  try {
    const data = await loadBusinessDomains({}, false)
    domainOptions.value = Array.isArray(data) ? data : []
  } catch {
    domainOptions.value = []
  }
}

let suggestTimer = null
function onTitleChange() {
  clearTimeout(suggestTimer)
  suggestTimer = setTimeout(async () => {
    const t = smartTitle.value.trim()
    if (!t) { suggestions.value = []; return }
    try {
      const data = await basicDataApi.suggestDomains(t, 5)
      suggestions.value = Array.isArray(data) ? data : []
    } catch (e) {
      ElMessage.error(e.message || '推荐失败')
    }
  }, 300)
}

// 点击推荐芯片：除了高亮，还要联动填充批量关联的目标领域，否则用户看不到任何反馈
function pickSuggestion(s) {
  selectedDomain.value = s.domain_code
  batchDomainCode.value = s.domain_code
  ElMessage.success(`已选用「${s.domain_name}」，可在右侧勾选记录后批量应用`)
}

function onSelectionChange(rows) {
  selectedRows.value = rows
}

async function loadBatch() {
  batchLoading.value = true
  try {
    const res = await operationApi.listIssues({ page: 1, page_size: 100 })
    const items = res?.items || []
    const rows = items.map((it) => ({
      // source_id 必须是 issue_no：后端 batch_set_domain 用它作为 PmwbOperationIssue 的主键
      source_id: it.issue_no,
      source_type: 'operation',
      title: it.title || it.issue_no,
      domain_code: it.domain_code || '',
    }))
    batchRows.value = onlyUnlinked.value ? rows.filter((r) => !r.domain_code) : rows
    selectedRows.value = []
    lastResult.value = null
  } catch (e) {
    batchRows.value = []
    ElMessage.error(e?.message || '加载工单失败')
  } finally {
    batchLoading.value = false
  }
}

async function applyBatch() {
  if (!batchDomainCode.value || !selectedRows.value.length) return
  applying.value = true
  try {
    const items = selectedRows.value.map((r) => ({
      source_type: r.source_type,
      source_id: String(r.source_id),
      domain_code: batchDomainCode.value,
    }))
    const data = await basicDataApi.batchSetDomain({ items, overwrite: true })
    const result = {
      updated: data?.updated ?? 0,
      skipped: data?.skipped ?? 0,
      errors: Array.isArray(data?.errors) ? data.errors : [],
    }
    lastResult.value = result

    if (result.errors.length) {
      ElMessage.warning(`成功 ${result.updated} 条，失败 ${result.errors.length} 条`)
    } else {
      ElMessage.success(`已更新 ${result.updated} 条`)
    }
    // 重新拉取列表，确保「当前领域」显示的是中文名而不是刚写入的 code
    await loadBatch()
  } catch (e) {
    ElMessage.error(e?.message || '批量设置失败')
  } finally {
    applying.value = false
  }
}

onMounted(() => {
  loadDomainOptions()
  loadBatch()
})
</script>

<style scoped>
.relations-view { padding: 16px 20px; height: 100%; overflow: auto; background: #f5f7fa; }
.relations-header { margin-bottom: 16px; }
.relations-titles { display: flex; flex-direction: column; gap: 4px; }
.relations-title { font-size: 18px; font-weight: 700; margin: 0; color: #1d2129; }
.relations-subtitle { font-size: 13px; color: #86909c; }
.relations-grid {
  display: grid; grid-template-columns: 1.1fr .9fr; gap: 16px;
}
.relations-card {
  background: #fff; border: 1px solid #e5e6eb; border-radius: 12px;
  padding: 18px; box-shadow: 0 2px 12px rgba(0,0,0,.04);
}
.card-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 700; color: #1d2129;
  margin-bottom: 16px;
}
.field { margin-bottom: 14px; }
.field label {
  display: block; font-size: 12.5px; color: #606266;
  margin-bottom: 6px;
}
.rec-box { margin-top: 10px; }
.rec-title {
  font-size: 11.5px; color: #86909c; margin-bottom: 8px;
}
.chip-list { display: flex; flex-direction: column; gap: 8px; }
.chip {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 12px; background: #f5f7fa;
  border: 1px solid #e5e6eb; border-radius: 10px;
  cursor: pointer; font-size: 13px; transition: .12s;
}
.chip:hover, .chip.active {
  border-color: #2f6fed; background: #2f6fed10;
}
.chip-name { flex: 1; font-weight: 600; }
.chip-group {
  font-size: 11px; padding: 1px 6px; border-radius: 8px;
}
.chip-why {
  font-size: 11px; color: #86909c;
}
.rec-empty {
  padding: 12px; color: #86909c; font-size: 13px; background: #f5f7fa; border-radius: 8px;
}
.picked-bar {
  margin-top: 12px; padding: 9px 12px; font-size: 13px;
  background: #eaf3ff; border: 1px solid #bcdaff; border-radius: 10px; color: #1d4ed8;
}
.picked-tip {
  display: block; margin-top: 3px; font-size: 11.5px; color: #6080a8; font-weight: 400;
}
.batch-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.batch-table-wrap { margin-bottom: 12px; }
.batch-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; background: #f2f5ff; border-radius: 10px;
  font-size: 13px;
}
.result-box {
  margin-top: 10px; padding: 8px 12px; border-radius: 8px; font-size: 12.5px;
  background: #eaf7ee; color: #217a3c; border: 1px solid #b7e3c4;
}
.result-box.warn {
  background: #fdf3e7; color: #a15c00; border-color: #f5d3a1;
}
.relations-note {
  margin-top: 12px; font-size: 12px; color: #86909c; line-height: 1.6;
}
.tag { font-size: 11px; padding: 1px 6px; border-radius: 6px; background: #e5e6eb; color: #4e5969; }
.tag.empty { background: #fdf2e8; color: #f0a64a; }
.tag.type { background: #eaf3ff; color: #2f6fed; }
</style>
