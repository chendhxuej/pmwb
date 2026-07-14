<template>
  <div class="data-table">
    <el-table
      v-loading="loading"
      :data="data"
      stripe
      border
      style="width: 100%"
      @sort-change="handleSortChange"
    >
      <!-- 根据 columns prop 动态渲染列 -->
      <template v-for="(col, index) in columns" :key="index">
        <!-- 插槽列（如 status、priority、actions） -->
        <el-table-column
          v-if="col.slot"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :fixed="col.fixed"
          :show-overflow-tooltip="col.showOverflowTooltip !== false"
        >
          <template #default="{ row }">
            <slot :name="col.slot" :row="row" />
          </template>
        </el-table-column>
        <!-- 普通数据列（有 prop） -->
        <el-table-column
          v-else-if="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :fixed="col.fixed"
          :sortable="col.sortable || false"
          :show-overflow-tooltip="col.showOverflowTooltip !== false"
        />
      </template>

      <!-- 默认操作列（当 showAction 且未在 columns 中定义 actions 时显示） -->
      <el-table-column v-if="showAction && !hasActionsSlot" label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <slot name="actions" :row="row">
            <el-button link type="primary" @click="$emit('edit', row)">编辑</el-button>
            <el-button link type="danger" @click="$emit('delete', row)">删除</el-button>
          </slot>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-if="showPagination"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      class="pagination"
      @size-change="handlePageChange"
      @current-change="handlePageChange"
    />
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  columns: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  showPagination: { type: Boolean, default: true },
  showAction: { type: Boolean, default: true },
})

// 检查 columns 中是否已定义了 actions 插槽列（避免重复渲染操作列）
const hasActionsSlot = computed(() =>
  props.columns.some(col => col.slot === 'actions')
)

const emit = defineEmits(['update:page', 'update:pageSize', 'change', 'edit', 'delete'])

const currentPage = ref(props.page)
const pageSize = ref(props.pageSize)

watch(() => props.page, (val) => { currentPage.value = val })
watch(() => props.pageSize, (val) => { pageSize.value = val })

const handlePageChange = () => {
  emit('update:page', currentPage.value)
  emit('update:pageSize', pageSize.value)
  emit('change')
}

const handleSortChange = ({ prop, order }) => {
  emit('sort-change', { field: prop, order: order === 'ascending' ? 'asc' : 'desc' })
}
</script>

<style scoped>
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
</style>
