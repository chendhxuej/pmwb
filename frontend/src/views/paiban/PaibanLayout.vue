<template>
  <router-view />
</template>

<script setup>
/**
 * 排版管理二级布局容器（2026-11-19，pb-1）。
 *
 * 与 TaskCenterLayout / OperationLayout 同构：仅承载 router-view，
 * 5 个二级页由 MainLayout 依据路由 children 自动渲染，此处不重复实现导航。
 * 默认落地 /paiban/track（排版跟踪）。
 */
</script>
