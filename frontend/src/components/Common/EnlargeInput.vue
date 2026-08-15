<template>
  <div class="enlarge-input-wrap" :class="{ 'is-textarea': isTextarea }">
    <ElInput
      v-bind="passAttrs"
      :model-value="model"
      @update:model-value="(v) => (model = v)"
    >
      <template v-for="(_, name) in forwardSlots" :key="name" #[name]="slotData">
        <slot :name="name" v-bind="slotData" />
      </template>
      <template v-if="!isTextarea" #suffix>
        <button class="enlarge-trigger" type="button" title="放大编辑" @click="onEnlarge">
          <FullScreen />
        </button>
      </template>
    </ElInput>
    <button
      v-if="isTextarea"
      class="enlarge-trigger enlarge-trigger--float"
      type="button"
      title="放大编辑"
      @click="onEnlarge"
    >
      <FullScreen />
    </button>
  </div>
</template>

<script setup>
import { useAttrs, useSlots, computed } from 'vue'
import { ElInput } from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
import { useEnlargeInput } from '@/composables/useEnlargeInput'

// 双向绑定：直接复用父级的 v-model（不递归，内部渲染的是 import 来的原始 ElInput）
const model = defineModel()

const attrs = useAttrs()
const slots = useSlots()
const isTextarea = computed(() => attrs.type === 'textarea')

// 透传给原始 ElInput 的属性；移除 update:modelValue 避免与下方手动绑定重复触发；
// 过滤掉 suffix 槽，避免与下面显式声明的放大按钮 suffix 冲突
const passAttrs = computed(() => {
  const { 'onUpdate:modelValue': _omit, ...rest } = attrs
  return rest
})
const forwardSlots = computed(() => {
  const out = {}
  for (const key in slots) {
    if (key !== 'suffix') out[key] = slots[key]
  }
  return out
})

function onEnlarge() {
  useEnlargeInput().open({
    value: model.value,
    type: attrs.type,
    rows: attrs.rows,
    onSave: (v) => {
      model.value = v
    },
  })
}
</script>

<style scoped>
.enlarge-input-wrap {
  position: relative;
  width: 100%;
}
.enlarge-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.enlarge-trigger:hover {
  background: var(--accent-soft);
  color: var(--accent);
}
/* 多行文本：按钮置于右上角浮层，避免遮挡正文 */
.enlarge-input-wrap.is-textarea .enlarge-trigger--float {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.enlarge-input-wrap.is-textarea .enlarge-trigger--float:hover {
  background: var(--accent-soft);
}
</style>
