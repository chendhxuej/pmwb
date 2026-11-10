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

    <!-- 主要投诉点速览（新闭集 · 与「主要投诉点」页同源，定位系统改造落点） -->
    <section class="card mp-overview">
      <div class="card-header">
        <h3>主要投诉点（功能模块问题 · 闭集）</h3>
        <span class="hint">上方 KPI 为全周期累计；下方 TOP 为所选周单量（vL2 闭集字典）</span>
        <el-button class="ml-auto" size="small" type="primary" plain @click="goModuleProblemPage">查看完整主要投诉点 →</el-button>
      </div>
      <div class="card-body">
        <div class="pm-stat-grid pm-stat-grid--5">
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">总工单</span></div>
            <div class="pm-stat__val">{{ mpSummary.total_tickets ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">缺陷已归集</span></div>
            <div class="pm-stat__val is-accent">{{ mpSummary.defect_classified ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">缺陷类数</span></div>
            <div class="pm-stat__val">{{ mpSummary.defect_classes ?? 0 }}<span class="pm-stat__unit">个</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">未归类</span></div>
            <div class="pm-stat__val" :class="(mpSummary.unclassified || 0) ? 'is-warning' : 'is-success'">{{ mpSummary.unclassified ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">咨询类（隔离）</span></div>
            <div class="pm-stat__val is-muted">{{ mpSummary.consult ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
        </div>
        <div class="mp-top">
          <div class="mp-top__title">TOP 缺陷类（{{ data.week || '所选周' }} 单量，点击下钻该周工单）</div>
          <div class="mp-top__list">
            <div v-for="(c, i) in mpTop" :key="c.module_problem_id" class="mp-top__item"
                 @click="drill({ week: data.week, module_problem_id: c.module_problem_id }, '主要投诉点·' + c.name)">
              <span class="mp-rank">{{ i + 1 }}</span>
              <span class="mp-name" :title="c.name">{{ c.name }}</span>
              <span class="mp-cnt">{{ c.week_cnt ?? 0 }} 单</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div v-if="data.week" class="hot-body">
      <div class="pm-stat-grid pm-stat-grid--2 hot-kpis">
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">本周新增投诉</span></div>
          <div class="pm-stat__val is-accent">{{ data.total }}<span class="pm-stat__unit">单</span></div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">热点场景</span></div>
          <div class="pm-stat__val">{{ data.items.length }}<span class="pm-stat__unit">个</span></div>
          <div class="pm-stat__sub">按二级场景统计</div>
        </div>
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

// 主要投诉点速览（新闭集，与「主要投诉点」页同源）
const mpSummary = ref({})
const mpTop = ref([])
function goModuleProblemPage() {
  router.push({ path: '/complaint-center/module-problem' })
}
async function loadMp(week) {
  try {
    const [s, c] = await Promise.all([
      complaintApi.moduleProblemSummary(),
      // 必须与热点主表同一周：后端不传 week 会取库内最新周（进行中周）
      complaintApi.moduleProblemClasses({ include_consult: false, week: week || undefined }),
    ])
    mpSummary.value = s || {}
    // 排序由后端按 week_cnt 降序（与展示字段同源）；0 单的类不占 TOP 位
    mpTop.value = ((c && c.items) || []).filter(x => (x.week_cnt || 0) > 0).slice(0, 6)
  } catch (e) { /* 不影响热点主表 */ }
}

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
  // TOP 速览与主表共用最终生效周，避免两处周次不一致
  loadMp(selectedWeek.value || data.value.week)
}

function pct(cur) {
  return data.value.total ? Math.round((cur / data.value.total) * 1000) / 10 : 0
}

// 一级 4 类问题性质 → tag 颜色（整改归口视觉区分）
const L1_TAG = {
  系统问题: 'danger',
  流程优化: 'warning',
  投诉咨询: 'info',
  数据问题: 'success',
}

function l1TagType(l1) {
  return L1_TAG[l1] || 'info'
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

// 通用下钻（主要投诉点速览用：按闭集模块问题过滤）
function drill(filters, title) {
  drillFilters.value = { ...filters }
  drillTitle.value = title || '投诉工单下钻'
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

onMounted(() => {
  // load() 内部按最终生效周刷新 TOP 速览
  load()
})
</script>

<style scoped>
.complaint-hotspots {
  display: flex;
  flex-direction: column;
}
.mp-overview { margin-bottom: 4px; }
.hint { font-size: 12px; color: var(--text-muted); }
.ml-auto { margin-left: auto; }
.mp-top { margin-top: 14px; }
.mp-top__title { font-size: 12.5px; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; }
.mp-top__list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 18px; }
.mp-top__item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border: 1px solid var(--border-light, #eef0f4); border-radius: 8px;
  background: var(--bg-soft, #fafbfc); cursor: pointer; transition: all .15s;
}
.mp-top__item:hover { border-color: var(--brand, #3b6cff); background: var(--brand-soft, #eef4ff); }
.mp-rank {
  width: 20px; height: 20px; flex: none; border-radius: 6px;
  font-size: 12px; font-weight: 700; color: #fff; background: var(--brand, #3b6cff);
  display: flex; align-items: center; justify-content: center;
}
.mp-name { flex: 1; font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mp-cnt { flex: none; font-size: 12.5px; font-weight: 600; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.hot-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.hot-kpis { max-width: 880px; }
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
