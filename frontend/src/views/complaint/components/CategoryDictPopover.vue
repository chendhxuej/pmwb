<template>
  <el-popover v-model:visible="visible" width="640" trigger="click" placement="bottom-end">
    <template #reference>
      <el-button :icon="Collection">分类字典</el-button>
    </template>
    <div class="dict-panel">
      <div class="dict-head">
        <span class="dict-title">两级分类字典（keywords 正则即口径）</span>
        <el-button size="small" text :icon="Refresh" @click="load">刷新</el-button>
      </div>
      <el-table ref="pmTbl1" v-loading="loading" :data="rows" size="small" max-height="420">
        <el-table-column prop="level" label="级" width="44" align="center">
          <template #default="{ row }">
            <el-tag :type="row.level === 1 ? 'primary' : 'info'" size="small">L{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'l1-name': row.level === 1 }">{{ row.parent_name ? `${row.parent_name} / ${row.name}` : row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="keywords" label="关键词正则" min-width="180" show-overflow-tooltip />
        <el-table-column label="启用" width="70" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="!!row.enabled"
              size="small"
              @change="v => toggle(row, v)"
            />
          </template>
        </el-table-column>
      </el-table>
      <div class="dict-tip">停用后新导入工单不再命中该场景；「按字典重跑分类」可用脚本执行（不影响人工校正记录）。</div>
    </div>
  </el-popover>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, Refresh } from '@element-plus/icons-vue'
import { complaintApi } from '@/api/complaint'

const visible = ref(false)
const loading = ref(false)
const rows = ref([])

watch(visible, (v) => { if (v) load() })

async function load() {
  loading.value = true
  try {
    rows.value = await complaintApi.listCategories()
  } catch (e) {
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function toggle(row, v) {
  try {
    await complaintApi.toggleCategory(row.id, v ? 1 : 0)
    row.enabled = v ? 1 : 0
    ElMessage.success(`${row.name} 已${v ? '启用' : '停用'}（分类缓存已刷新）`)
  } catch (e) { /* request 已提示 */ }
}
</script>

<style scoped>
.dict-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.dict-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.l1-name {
  font-weight: 600;
  color: var(--text-primary);
}
.dict-tip {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--text-secondary);
  line-height: 1.6;
}
</style>
