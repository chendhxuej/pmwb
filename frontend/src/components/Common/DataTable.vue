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
      <slot name="columns" />
      <el-table-column v-if="showAction" label="操作" width="150" fixed="right">
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
import { ref, watch } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  showPagination: { type: Boolean, default: true },
  showAction: { type: Boolean, default: true },
})

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
