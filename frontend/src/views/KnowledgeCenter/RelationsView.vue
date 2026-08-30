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
          <div class="rec-title">实时推荐（关键词匹配 + 名称 + 编码 + 首字母）</div>
          <div class="chip-list">
            <div
              v-for="s in suggestions"
              :key="s.domain_code"
              class="chip"
              :class="{ active: selectedDomain === s.domain_code }"
              @click="selectedDomain = s.domain_code"
            >
              <span class="chip-name">{{ s.domain_name }}</span>
              <span class="chip-group" :style="tagStyle(s.domain_group)">{{ s.domain_group }}</span>
              <span class="chip-why">{{ s.reason }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="smartTitle.trim()" class="rec-empty">未匹配到推荐领域，可换关键词试试</div>
        <div class="relations-note">支持关键词、名称包含、编码匹配、首字母匹配；点击芯片即选中目标 domain_code。</div>
      </div>

      <div class="relations-card">
        <div class="card-head">
          <el-icon><Finished /></el-icon>
          <span>批量关联（列表多选 → 一键设领域）</span>
        </div>
        <div class="batch-table-wrap">
          <el-table :data="mockBatch" size="small" @selection-change="onSelectionChange">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="title" label="工单" show-overflow-tooltip />
            <el-table-column prop="domain_name" label="当前领域" width="120">
              <template #default="{ row }">
                <span v-if="row.domain_name" class="tag">{{ row.domain_name }}</span>
                <span v-else class="tag empty">未关联</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="batch-bar">
          <span>已选 {{ selectedRows.length }} 条</span>
          <BusinessDomainSelect v-model="batchDomainCode" clearable placeholder="选择目标领域" style="width: 180px" />
          <el-button type="primary" :disabled="!batchDomainCode || !selectedRows.length" @click="applyBatch">
            批量应用
          </el-button>
        </div>
        <div class="relations-note">演示数据：实际可接入 operationApi / requirementApi 拉取未关联记录。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { EditPen, Finished } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { basicDataApi } from '@/api/basicData'
import BusinessDomainSelect from '@/components/Common/BusinessDomainSelect.vue'

const smartTitle = ref('')
const suggestions = ref([])
const selectedDomain = ref('')
const batchDomainCode = ref('')
const selectedRows = ref([])

const mockBatch = ref([
  { id: 1, title: '订单中心短信接口异常', domain_name: '', source_type: 'operation', source_id: 'O-001' },
  { id: 2, title: '政企工作台待办同步延迟', domain_name: '', source_type: 'operation', source_id: 'O-002' },
  { id: 3, title: '一网通宽带资费导出需求', domain_name: '一网通宽带', source_type: 'requirement', source_id: 'R-003' },
  { id: 4, title: '电子协议签署回调失败', domain_name: '', source_type: 'operation', source_id: 'O-004' },
])

const groupColor = (g) => {
  const map = { '商客业务': '#165dff', '系统平台': '#36c5d0', '公共能力': '#3fb950', '通用': '#9da7b3' }
  return map[g] || '#165dff'
}
const tagStyle = (g) => ({ background: groupColor(g) + '15', color: groupColor(g) })

let suggestTimer = null
function onTitleChange() {
  clearTimeout(suggestTimer)
  suggestTimer = setTimeout(async () => {
    const t = smartTitle.value.trim()
    if (!t) { suggestions.value = []; return }
    try {
      const res = await basicDataApi.suggestDomains(t, 5)
      if (res.data && res.data.code === 0) {
        suggestions.value = res.data.data || []
      }
    } catch (e) {
      ElMessage.error(e.message || '推荐失败')
    }
  }, 300)
}

function onSelectionChange(rows) {
  selectedRows.value = rows
}

async function applyBatch() {
  if (!batchDomainCode.value || !selectedRows.value.length) return
  try {
    const items = selectedRows.value.map(r => ({
      source_type: r.source_type,
      source_id: String(r.source_id),
      domain_code: batchDomainCode.value,
    }))
    const res = await basicDataApi.batchSetDomain({ items, overwrite: true })
    if (res.data && res.data.code === 0) {
      ElMessage.success(`已更新 ${res.data.data.updated} 条`)
      selectedRows.value.forEach(r => { r.domain_name = batchDomainCode.value })
    } else {
      ElMessage.error(res.data?.message || '批量设置失败')
    }
  } catch (e) {
    ElMessage.error(e.message || '批量设置失败')
  }
}
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
.batch-table-wrap { margin-bottom: 12px; }
.batch-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; background: #f2f5ff; border-radius: 10px;
  font-size: 13px;
}
.relations-note {
  margin-top: 12px; font-size: 12px; color: #86909c; line-height: 1.6;
}
.tag { font-size: 11px; padding: 1px 6px; border-radius: 6px; background: #e5e6eb; color: #4e5969; }
.tag.empty { background: #fdf2e8; color: #f0a64a; }
</style>
