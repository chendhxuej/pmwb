<template>
  <div class="rlt">
    <el-tag
      v-for="rid in displayed"
      :key="rid"
      size="small"
      :type="isInvalid(rid) ? 'danger' : 'info'"
      effect="plain"
      class="rlt-tag"
      :title="titleOf(rid)"
      @click.stop="$emit('open', rid)"
    >
      {{ rid }}
    </el-tag>
    <el-tooltip v-if="collapsedCount" placement="top" :content="restText">
      <span class="rlt-more">+{{ collapsedCount }}</span>
    </el-tooltip>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * 关联需求文号标签组（列表列 / 详情抽屉共用，避免两处各写一份）。
 * 最多展示 maxVisible 个，其余折叠为 +N（悬浮显示全部文号）。
 * 失效文号（不在需求宇宙）标红并给出提示。
 */
const props = defineProps({
  reqIds: { type: Array, default: () => [] },
  /** 文号 → 需求名称 映射（可选，仅用于 tooltip） */
  nameMap: { type: Object, default: () => ({}) },
  /** 文号 → 是否存在于需求宇宙 映射（可选，缺省视为有效） */
  reqExists: { type: Object, default: () => ({}) },
  maxVisible: { type: Number, default: 2 },
})
defineEmits(['open'])

const list = computed(() => (Array.isArray(props.reqIds) ? props.reqIds : []))
const displayed = computed(() => list.value.slice(0, props.maxVisible))
const collapsedCount = computed(() => Math.max(0, list.value.length - props.maxVisible))
const restText = computed(() => list.value.slice(props.maxVisible).join('、'))

const isInvalid = (rid) => props.reqExists && props.reqExists[rid] === false
const titleOf = (rid) => {
  const nm = props.nameMap && props.nameMap[rid]
  const base = nm ? `${nm}（${rid}）` : rid
  return isInvalid(rid) ? `${base} · 该文号已不在需求宇宙` : `${base} · 点击打开需求`
}
</script>

<style scoped>
.rlt {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.rlt-tag {
  cursor: pointer;
}
.rlt-more {
  color: var(--text-secondary);
  font-size: 12px;
  cursor: default;
}
</style>
