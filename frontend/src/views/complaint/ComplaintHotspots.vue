<template>
  <div class="complaint-hotspots">
    <PageHeader title="热点投诉" :subtitle="subTitle">
      <template #actions>
        <el-select v-model="selectedWeek" style="width: 168px" @change="load">
          <el-option v-for="w in weekOptions" :key="w" :label="w" :value="w" />
        </el-select>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </template>
    </PageHeader>

    <div v-if="data.week" class="hot-body">
      <div class="hot-summary">
        <span>{{ data.week }}</span>
        <span class="sep">｜</span>
        <span>本周新增投诉 <b class="total-num">{{ data.total }}</b> 单</span>
        <span class="sep">｜</span>
        <span>热点场景 <b>{{ data.items.length }}</b> 个</span>
        <span class="hint">（按二级场景统计，凸显当下投诉都集中在什么事）</span>
      </div>

      <section class="card">
        <div class="hot-list">
          <div v-for="(it, i) in data.items" :key="it.l2" class="hot-row">
            <div class="hot-rank" :class="`rank-${i + 1}`">{{ i + 1 }}</div>
            <div class="hot-main">
              <div class="hot-name">
                {{ it.l2 }}
                <el-tag size="small" :type="l1TagType(it.l1)">{{ it.l1 || '待分析' }}</el-tag>
                <el-tag v-if="it.rebound" size="small" type="danger" effect="plain">⚠ 已闭环场景反弹，建议复盘</el-tag>
              </div>
              <div class="hot-meta">
                占本周 {{ pct(it.cur) }}%
                <template v-if="it.open_problems.length">
                  ｜在办问题 <el-link type="primary" style="font-size:12px" @click="goProblem(it.open_problems[0].problem_no)">{{ it.open_problems[0].problem_no }}</el-link> 等 {{ it.open_problems.length }} 个
                </template>
                <template v-else-if="it.closed_problem_no">
                  ｜已闭环 <el-link type="primary" style="font-size:12px" @click="goProblem(it.closed_problem_no)">{{ it.closed_problem_no }}</el-link>
                </template>
                <template v-else>｜尚无关联问题</template>
                <template v-if="it.sample_tickets.length">｜代表工单 <span class="mono">{{ it.sample_tickets.join('、') }}</span></template>
              </div>
            </div>
            <div class="hot-cnt">
              <div class="n">{{ it.cur }}</div>
              <div class="d">
                <span class="badge" :class="flagClass(it)">{{ flagText(it) }}</span>
              </div>
            </div>
            <div class="hot-ops">
              <el-button size="small" @click="drillTickets(it)">工单明细</el-button>
              <el-button v-if="!it.open_problems.length" size="small" type="primary" plain @click="createProblem(it)">立问题入台账</el-button>
              <el-button v-else size="small" type="primary" plain @click="goProblem(it.open_problems[0].problem_no)">关联已有问题</el-button>
            </div>
          </div>
        </div>
        <el-empty v-if="!data.items.length" description="本周暂无带场景归类的工单（等待 AI 归类完成或导入数据）" :image-size="70" />
      </section>

      <div class="hot-note">
        💡 热点 → 问题的通路：热点行可直接「立问题入台账」（同场景已有在办问题则提示关联）；
        环比标注 <el-tag size="small" type="danger">↑ 上升</el-tag>
        <el-tag size="small" type="success">↓ 下降</el-tag>
        <el-tag size="small" type="info">→ 持平</el-tag>
        <el-tag size="small" type="warning">新进</el-tag>；
        已闭环场景出现反弹自动标红提示复盘。所有数量点击「工单明细」下钻到工单级。
      </div>
    </div>

    <el-empty v-else-if="!loading" description="暂无客诉数据" />

    <TicketDrillDrawer v-model="drillVisible" :filters="drillFilters" :title="drillTitle" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import TicketDrillDrawer from './components/TicketDrillDrawer.vue'
import { complaintApi } from '@/api/complaint'

const router = useRouter()
const loading = ref(false)
const data = ref({ week: '', items: [], total: 0, weeks: [] })
const selectedWeek = ref('')
const drillVisible = ref(false)
const drillFilters = ref({})
const drillTitle = ref('')

const subTitle = computed(() =>
  data.value.week
    ? `${data.value.week} 环比 ${data.value.prev_week} ｜按大模型归类结果统计`
    : '近一周投诉热点（按二级场景统计）'
)

const weekOptions = computed(() => data.value.weeks || [])

async function load() {
  loading.value = true
  try {
    const res = await complaintApi.getHotspots(
      selectedWeek.value ? { week: selectedWeek.value } : {})
    data.value = res || { week: '', items: [], total: 0, weeks: [] }
    if (!selectedWeek.value && data.value.week) selectedWeek.value = data.value.week
  } catch (e) {
    ElMessage.error('热点加载失败')
  } finally {
    loading.value = false
  }
}

function pct(cur) {
  return data.value.total ? Math.round((cur / data.value.total) * 1000) / 10 : 0
}

function flagText(it) {
  if (it.flag === 'new') return '新进'
  const arrow = it.flag === 'up' ? '↑' : (it.flag === 'down' ? '↓' : '→')
  return it.wow === null ? `${arrow} 上期${it.prev}` : `${arrow} ${Math.abs(it.wow)}%`
}

function flagClass(it) {
  return { new: 'new', up: 'up', down: 'down', flat: 'flat' }[it.flag] || 'flat'
}

function drillTickets(it) {
  drillFilters.value = { week: selectedWeek.value || data.value.week, l2: it.l2 }
  drillTitle.value = `热点「${it.l2}」工单`
  drillVisible.value = true
}

async function createProblem(it) {
  try {
    const { value } = await ElMessageBox.prompt(
      `为热点场景「${it.l2}」建立共性问题（本周 ${it.cur} 单），将进入问题台账跟踪闭环。`,
      '立问题入台账',
      {
        inputValue: `${it.l2}（${data.value.week} 热点，${it.cur} 单）`,
        inputPlaceholder: '问题标题',
        inputValidator: v => (v && v.trim() ? true : '请填写问题标题'),
        confirmButtonText: '确认立问题',
        cancelButtonText: '取消',
      })
    await complaintApi.createProblem({
      title: value.trim(),
      category_l1: it.l1 || undefined,
      category_l2: it.l2,
      owner: '',
    })
    ElMessage.success('问题已建立，已进入问题台账')
    load()
  } catch (e) {
    if (e === 'cancel') return
    const msg = e?.response?.data?.detail || e?.message || ''
    if (String(msg).includes('已存在')) {
      ElMessageBox.confirm(String(msg), '该场景已有在办问题', {
        confirmButtonText: '去问题台账',
        cancelButtonText: '取消',
        type: 'warning',
      }).then(() => router.push('/operation/complaint-center/problems')).catch(() => {})
    } else if (msg) {
      ElMessage.error(String(msg))
    }
  }
}

function goProblem(problemNo) {
  router.push({ path: '/operation/complaint-center/problems', query: { problem_no: problemNo } })
}

onMounted(load)
</script>

<style scoped>
.complaint-hotspots {
  display: flex;
  flex-direction: column;
}
.hot-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.hot-summary {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm, 8px);
}
.hot-summary .total-num {
  color: var(--accent);
  font-size: 16px;
}
.hot-summary .sep { color: var(--border-color); }
.hot-summary .hint { font-size: 12px; opacity: 0.8; }
.hot-list { display: flex; flex-direction: column; }
.hot-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 6px;
  border-bottom: 1px solid var(--border-color);
}
.hot-row:last-child { border-bottom: none; }
.hot-rank {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 700;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.hot-rank.rank-1 { background: var(--danger); color: #fff; }
.hot-rank.rank-2 { background: var(--warning, #f59e0b); color: #fff; }
.hot-rank.rank-3 { background: #f59e0b; color: #fff; }
.hot-main { flex: 1; min-width: 0; }
.hot-name {
  font-weight: 600;
  font-size: 13.5px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.hot-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 3px;
}
.mono {
  font-family: var(--font-mono, monospace);
  font-size: 11.5px;
}
.hot-cnt { text-align: right; flex-shrink: 0; width: 72px; }
.hot-cnt .n {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.hot-cnt .d { font-size: 11px; margin-top: 1px; }
.badge {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}
.badge.up { background: var(--danger-bg, #fef2f2); color: var(--danger); }
.badge.down { background: var(--success-bg, #f0fdf4); color: var(--success); }
.badge.flat { background: var(--bg-secondary); color: var(--text-secondary); }
.badge.new { background: var(--warning-bg, #fff7ed); color: var(--warning, #ea580c); }
.hot-ops { flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; }
.hot-note {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.8;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 10px 14px;
}
</style>
