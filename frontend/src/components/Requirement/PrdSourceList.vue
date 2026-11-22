<script setup>
import { computed } from 'vue'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  conflicts: { type: Array, default: () => [] },
  assumptions: { type: Array, default: () => [] },
  openItems: { type: Array, default: () => [] },
})

const levelClass = (lv) => ({
  '致命': 'lv-fatal', '高': 'lv-high', '中': 'lv-mid', '低': 'lv-low', 'INFO': 'lv-info',
}[lv] || 'lv-low')

const hasData = computed(() =>
  (props.sources?.length || 0) + (props.conflicts?.length || 0) +
  (props.assumptions?.length || 0) + (props.openItems?.length || 0) > 0)
</script>

<template>
  <div class="prd-evidence">
    <el-empty v-if="!hasData" description="本次未产生冲突或引用来源" :image-size="56" />

    <template v-else>
      <div v-if="conflicts.length" class="ev-block">
        <div class="ev-hd">
          <span>冲突清单</span>
          <span class="pm-tag gray ml-8">{{ conflicts.length }} 条 · CL 定级</span>
        </div>
        <div class="conflict-list">
          <div v-for="(c, i) in conflicts" :key="'c' + i" class="conflict-item" :class="levelClass(c.level)">
            <div class="ci-hd">
              <span class="ci-level">{{ c.level || '未定级' }}</span>
              <span class="ci-type">{{ c.type || '未分类' }}</span>
            </div>
            <div class="ci-desc">{{ c.desc }}</div>
            <div v-if="c.evidence" class="ci-ev">依据：{{ c.evidence }}</div>
          </div>
        </div>
      </div>

      <div v-if="sources.length" class="ev-block">
        <div class="ev-hd">
          <span>知识引用来源</span>
          <span class="pm-tag gray ml-8">{{ sources.length }} 条 · 系统+仓库+SHA+路径+条款</span>
        </div>
        <el-table :data="sources" size="small" border stripe style="width: 100%">
          <el-table-column prop="sys_id" label="系统" width="110" />
          <el-table-column prop="repo_id" label="仓库" min-width="110" />
          <el-table-column prop="sha" label="SHA" width="100" show-overflow-tooltip />
          <el-table-column prop="path" label="相对路径" min-width="180" show-overflow-tooltip />
          <el-table-column prop="clause" label="条款" width="110" show-overflow-tooltip />
        </el-table>
      </div>

      <div v-if="assumptions.length" class="ev-block">
        <div class="ev-hd"><span>采用的假设</span><span class="pm-tag gray ml-8">未在问卷覆盖</span></div>
        <ul class="ev-list"><li v-for="(a, i) in assumptions" :key="'a' + i">{{ a }}</li></ul>
      </div>

      <div v-if="openItems.length" class="ev-block">
        <div class="ev-hd"><span>待确认事项</span><span class="pm-tag gray ml-8">写入 PRD 6.1</span></div>
        <ul class="ev-list"><li v-for="(o, i) in openItems" :key="'o' + i">{{ o }}</li></ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.prd-evidence { font-size: 12px; }
.ev-block { margin-bottom: 16px; }
.ev-hd { display: flex; align-items: center; font-weight: 600; font-size: 12.5px; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid var(--border-subtle); }
.conflict-list { display: flex; flex-direction: column; gap: 7px; }
.conflict-item { border: 1px solid var(--border); border-left-width: 3px; border-radius: 8px; padding: 8px 10px; background: var(--bg-app); }
.conflict-item.lv-fatal { border-left-color: var(--danger); }
.conflict-item.lv-high { border-left-color: var(--danger); }
.conflict-item.lv-mid { border-left-color: var(--warning); }
.conflict-item.lv-low { border-left-color: var(--success); }
.conflict-item.lv-info { border-left-color: var(--accent); }
.ci-hd { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.ci-level { font-weight: 700; }
.ci-type { color: var(--text-secondary); font-size: 11px; }
.ci-desc { line-height: 1.6; }
.ci-ev { color: var(--text-muted); font-size: 11px; margin-top: 4px; }
.ev-list { margin: 0; padding-left: 20px; line-height: 1.8; color: var(--text-secondary); }
.ml-8 { margin-left: 8px; }
</style>
