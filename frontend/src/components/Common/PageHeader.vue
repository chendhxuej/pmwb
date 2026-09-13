<template>
  <header class="pm-page-header">
    <div class="pm-page-header__main">
      <h1 class="pm-page-header__title">{{ title }}</h1>
      <p v-if="subtitle" class="pm-page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="pm-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' }
})
</script>

<style scoped>
.pm-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.pm-page-header__main {
  min-width: 0;
}

.pm-page-header__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text-primary, #1f2d3d);
}

.pm-page-header__subtitle {
  margin: 4px 0 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-secondary, #64748b);
}

.pm-page-header__actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}
</style>
