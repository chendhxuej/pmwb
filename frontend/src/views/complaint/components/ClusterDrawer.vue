<template>
  <el-drawer
    :model-value="modelValue"
    :title="cluster ? `批量异常簇：${cluster.l2}` : '批量异常簇'"
    size="620px"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template v-if="cluster">
      <el-descriptions :column="2" border size="small" class="cluster-meta">
        <el-descriptions-item label="场景">{{ cluster.l2 }}</el-descriptions-item>
        <el-descriptions-item label="发现日">{{ cluster.date }}</el-descriptions-item>
        <el-descriptions-item label="单量">
          <b class="cnt-danger">{{ cluster.cnt }}</b>
        </el-descriptions-item>
        <el-descriptions-item label="涉及地市">{{ cluster.cities || '—' }}</el-descriptions-item>
        <el-descriptions-item label="组织修复" :span="2">
          <el-tag :type="cluster.fixed ? 'success' : 'danger'" size="small">
            {{ cluster.fixed ? '已批量处置' : '逐单兜底（未组织批量修复）' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div class="cluster-tip">
        处置建议：单日同场景 ≥ 阈值即属批量异常，应升级为故障处置（批量修复 + 主动通知），
        而非逐单兜底；「批量转派」属逐单流转，不计为修复。
      </div>

      <h4 class="sub-title">簇内工单明细</h4>
      <el-table v-loading="loading" :data="tickets" size="small" border>
        <el-table-column prop="ticket_no" label="BOMC 流水号" width="150" show-overflow-tooltip />
        <el-table-column prop="created_time" label="创建时间" width="150">
          <template #default="{ row }">{{ (row.created_time || '').replace('T', ' ').slice(0, 16) }}</template>
        </el-table-column>
        <el-table-column prop="city" label="地市" width="76" />
        <el-table-column prop="handler" label="处理人" width="90" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="84" />
        <el-table-column prop="content_preview" label="工单内容" min-width="180" show-overflow-tooltip />
      </el-table>
    </template>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { complaintApi } from '@/api/complaint'

const props = defineProps({
  modelValue: Boolean,
  cluster: { type: Object, default: null },
  week: { type: String, default: '' },
})
defineEmits(['update:modelValue'])

const loading = ref(false)
const tickets = ref([])

watch(() => props.modelValue, async (open) => {
  if (!open || !props.cluster) return
  loading.value = true
  try {
    // 簇内明细按「同场景 + 同发现日」过滤（cluster_key = 场景@日期）
    const [l2, d] = String(props.cluster.key || '').split('@')
    const data = await complaintApi.listTickets({ l2, week: props.week, page_size: 200 })
    tickets.value = (data.items || []).filter(t =>
      (t.created_time || '').slice(0, 10) === d
    )
  } catch (e) {
    tickets.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.cluster-meta {
  margin-bottom: 12px;
}
.cnt-danger {
  color: var(--danger);
}
.cluster-tip {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border-left: 3px solid var(--warning);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  margin-bottom: 14px;
  line-height: 1.7;
}
.sub-title {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 8px;
}
</style>
