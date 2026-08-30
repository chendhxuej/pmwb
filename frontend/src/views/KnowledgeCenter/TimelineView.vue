<template>
  <div class="timeline-view">
    <div class="timeline-header">
      <div class="timeline-titles">
        <h3 class="timeline-title">全局时间线 Feed</h3>
        <span class="timeline-subtitle">跨领域事件流 · 倒序</span>
      </div>
      <div class="timeline-actions">
        <el-select v-model="filterGroup" clearable placeholder="全部分组" style="width: 130px">
          <el-option label="商客业务" value="商客业务" />
          <el-option label="系统平台" value="系统平台" />
          <el-option label="公共能力" value="公共能力" />
          <el-option label="通用" value="通用" />
        </el-select>
        <el-select v-model="filterType" clearable placeholder="全部类型" style="width: 130px; margin-left: 8px">
          <el-option v-for="t in eventTypes" :key="t.value" :label="t.label + ' (' + t.count + ')'" :value="t.value" />
        </el-select>
        <el-button type="primary" style="margin-left: 8px" @click="refresh">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
    </div>

    <div class="timeline-body">
      <div v-loading="loading" class="timeline-card">
        <div v-if="events.length" class="timeline-list">
          <div v-for="(ev, idx) in events" :key="idx" class="timeline-event">
            <div class="timeline-dot" :style="{ background: groupColor(ev.domain_group) }" />
            <div class="timeline-content">
              <div class="timeline-event-title">{{ ev.domain_name }} · {{ ev.source_title || ev.knowledge_title || ev.event_label }}</div>
              <div class="timeline-event-meta">
                <span class="timeline-tag" :style="tagStyle(ev.domain_group)">{{ ev.domain_group }}</span>
                <span class="timeline-type">{{ ev.event_label }}</span>
                <span v-if="ev.event_date" class="timeline-date">{{ ev.event_date }}</span>
              </div>
              <div v-if="ev.summary" class="timeline-summary">{{ ev.summary }}</div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无事件" :image-size="80" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api/knowledge'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const events = ref([])
const eventTypes = ref([])
const filterGroup = ref('')
const filterType = ref('')

const groupColor = (g) => {
  const map = {
    '商客业务': '#165dff',
    '系统平台': '#36c5d0',
    '公共能力': '#3fb950',
    '通用': '#9da7b3',
  }
  return map[g] || '#165dff'
}

const tagStyle = (g) => ({
  background: groupColor(g) + '15',
  color: groupColor(g),
})

async function refresh() {
  loading.value = true
  try {
    const params = {}
    if (filterGroup.value) params.group = filterGroup.value
    if (filterType.value) params.event_type = filterType.value
    const res = await knowledgeApi.getGlobalTimeline(params)
    if (res.data && res.data.code === 0) {
      events.value = res.data.data.events || []
      eventTypes.value = res.data.data.event_types || []
    } else {
      ElMessage.error(res.data?.message || '加载失败')
    }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

watch([filterGroup, filterType], refresh)
onMounted(refresh)
</script>

<style scoped>
.timeline-view { padding: 16px 20px; height: 100%; overflow: auto; background: #f5f7fa; }
.timeline-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.timeline-titles { display: flex; flex-direction: column; gap: 4px; }
.timeline-title { font-size: 18px; font-weight: 700; margin: 0; color: #1d2129; }
.timeline-subtitle { font-size: 13px; color: #86909c; }
.timeline-actions { display: flex; align-items: center; }
.timeline-body { min-height: 400px; }
.timeline-card {
  background: #fff; border-radius: 12px; border: 1px solid #e5e6eb;
  padding: 20px 24px; box-shadow: 0 2px 12px rgba(0,0,0,.04);
}
.timeline-list { position: relative; padding-left: 8px; }
.timeline-list::before {
  content: ''; position: absolute; left: 14px; top: 8px; bottom: 8px;
  width: 2px; background: #e5e6eb; border-radius: 1px;
}
.timeline-event {
  position: relative; padding: 0 0 18px 28px; display: flex; gap: 12px;
}
.timeline-dot {
  position: absolute; left: 9px; top: 6px;
  width: 12px; height: 12px; border-radius: 50%;
  border: 2px solid #fff; box-shadow: 0 0 0 1px #e5e6eb;
}
.timeline-content { flex: 1; min-width: 0; }
.timeline-event-title { font-size: 14px; font-weight: 600; color: #1d2129; line-height: 1.4; }
.timeline-event-meta { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.timeline-tag, .timeline-type, .timeline-date { font-size: 12px; }
.timeline-tag {
  padding: 1px 7px; border-radius: 10px; font-weight: 500;
}
.timeline-type { color: #165dff; background: #165dff10; padding: 1px 7px; border-radius: 10px; }
.timeline-date { color: #86909c; }
.timeline-summary { margin-top: 6px; font-size: 12.5px; color: #4e5969; line-height: 1.5; }
</style>
