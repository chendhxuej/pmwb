<template>
  <div class="knowledge-center">
    <router-view />
  </div>
</template>

<script setup>
// 知识中心作为聚合壳层，只负责渲染子模块。
// 历史保留：之前用顶部 Tab 切换多个知识子页面；现在只保留「业务全景」(HubPanel) 作为唯一入口，
// 其他子模块路由仍可深链访问（meta.hidden=true），但不再于菜单/外露入口出现。
</script>

<style scoped>
.knowledge-center {
  height: 100%;
}
</style>
