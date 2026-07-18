<template>
  <section class="card" :class="{ 'card-flat': flat }" :style="cardStyle">
    <header v-if="title || $slots.head" class="card-header">
      <slot name="head">
        <span class="card-label">{{ title }}</span>
      </slot>
      <slot name="action" />
    </header>
    <div class="card-body" :style="{ padding: bodyPadding }">
      <slot />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  // 网格跨列，如 span 8 / span 4 / span 12
  span: { type: [Number, String], default: 12 },
  flat: { type: Boolean, default: false },
  bodyPadding: { type: String, default: '16px 22px 20px' },
  hover: { type: Boolean, default: true },
})

const cardStyle = computed(() => ({
  gridColumn: `span ${props.span}`,
  cursor: 'default',
}))
</script>

<style scoped>
.card {
  /* 复用全局 design.css 的 .card 视觉；此处仅补充 scoped 需要的覆盖 */
}
.card-flat:hover {
  transform: none;
  box-shadow: var(--shadow-card);
}
</style>
