<template>
  <router-view />
</template>

<script setup>
/**
 * 任务中心二级布局容器（2026-09-18）。
 *
 * 与 OperationLayout / MeetingLayout / AiCenterLayout 同构：仅承载 router-view，
 * 二级导航由 MainLayout 依据路由 children 自动渲染，无需在此重复实现。
 * 结构改造后 /task-center 重定向到 /task-center/overview。
 */
</script>
