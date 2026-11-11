<template>
  <section v-if="d.scope && d.scope.total" class="card ov-card">
    <div class="card-header">
      <h3>整体投诉全貌<span class="ov-tag">全量 · 跨周期</span></h3>
      <span class="hint">{{ scopeHint }}</span>
      <div class="ov-actions">
        <el-button size="small" text type="primary" :icon="Download" :loading="exporting"
          @click="exportAll()">导出全量明细</el-button>
        <el-button size="small" text @click="collapsed = !collapsed">
          {{ collapsed ? '展开' : '收起' }}
        </el-button>
      </div>
    </div>

    <div v-show="!collapsed" class="card-body">
      <!-- 一、全貌 KPI：全部为全表口径，与下方周维度区块互不混用 -->
      <div class="pm-stat-grid pm-stat-grid--6">
        <div class="pm-stat is-clickable" title="点击查看全部工单" @click="emitDrill({}, '整体·全部投诉工单')">
          <div class="pm-stat__top"><span class="pm-stat__label">累计工单</span></div>
          <div class="pm-stat__val is-accent">{{ d.scope.total }}<span class="pm-stat__unit">单</span></div>
          <div class="pm-stat__sub">库中全部，不带周筛选</div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">覆盖周期</span></div>
          <div class="pm-stat__val">{{ d.scope.weeks }}<span class="pm-stat__unit">周</span></div>
          <div class="pm-stat__sub">{{ d.scope.first_date }} ~ {{ d.scope.last_date }}</div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">完整周周均</span></div>
          <div class="pm-stat__val">{{ ts.avg_week }}<span class="pm-stat__unit">单</span></div>
          <div class="pm-stat__sub">{{ ts.complete_week_cnt }} 个有效天数≥{{ d.scope.min_effective_days }} 的完整周</div>
        </div>
        <div class="pm-stat is-clickable" title="点击下钻峰值周工单"
          @click="emitDrill({ week: ts.peak_week }, `整体·峰值周 ${ts.peak_week}`)">
          <div class="pm-stat__top"><span class="pm-stat__label">峰值周单量</span></div>
          <div class="pm-stat__val is-warning">{{ ts.peak_total }}<span class="pm-stat__unit">单</span></div>
          <div class="pm-stat__sub">{{ ts.peak_week }}（周均 {{ peakRatio }} 倍）</div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">累计闭环率</span></div>
          <div class="pm-stat__val" :class="cl.closed_pct >= 80 ? 'is-success' : 'is-warning'">
            {{ cl.closed_pct }}<span class="pm-stat__unit">%</span>
          </div>
          <div class="pm-stat__sub">{{ cl.closed }} / {{ d.scope.total }} 单（已回复≠结单）</div>
        </div>
        <div class="pm-stat is-clickable" title="点击下钻未闭环工单"
          @click="emitDrill({ unclosed: 1 }, '整体·未闭环工单')">
          <div class="pm-stat__top"><span class="pm-stat__label">未闭环存量</span></div>
          <div class="pm-stat__val is-danger">{{ cl.open }}<span class="pm-stat__unit">单</span></div>
          <div class="pm-stat__sub">其中已回复 {{ cl.replied_not_closed }} 单</div>
        </div>
      </div>

      <!-- 二、关键结论摘要：后端规则生成，点任意一条按对应条件下钻 -->
      <div class="sub-h">关键结论摘要<span class="hint">（规则自动生成，点击按对应口径下钻）</span></div>
      <div class="ov-conclusions">
        <div v-for="(c, i) in d.conclusions || []" :key="i"
          class="ov-conclusion" :class="`is-${c.level}`"
          @click="emitDrill(c.filters || {}, `整体结论·${c.text.slice(0, 20)}`)" >
          <span class="ov-conclusion__text">{{ c.text }}</span>
          <span v-if="c.note" class="ov-conclusion__note">{{ c.note }}</span>
          <span class="ov-conclusion__go">下钻 →</span>
        </div>
      </div>

      <!-- 三、总量趋势：全周期折线 + 周均基线；异常/不完整周用标签显式标出 -->
      <div class="sub-h">投诉总量变化趋势（{{ d.scope.weeks }} 个自然周）</div>
      <div class="ov-chips">
        <span v-for="a in ts.anomaly_weeks || []" :key="a.week" class="ov-chip is-clickable"
          :class="a.type === 'spike' ? 'is-danger' : 'is-success'"
          :title="`偏离周均 ${a.vs_avg_pct}%，z=${a.z}，点击下钻该周`"
          @click="emitDrill({ week: a.week }, `整体·异常波动周 ${a.week}`)">
          {{ a.type === 'spike' ? '▲ 突增' : '▼ 骤降' }} {{ a.week }} · {{ a.total }} 单
        </span>
        <span v-for="w in d.scope.incomplete_weeks || []" :key="w" class="ov-chip is-muted"
          :title="`有效天数 < ${d.scope.min_effective_days}，仅计入总量，不参与周均/异常判定`">
          ○ {{ w }} 不完整周
        </span>
        <span class="ov-chip is-plain">周均基线 {{ ts.avg_week }} 单 · 判定阈值 ±{{ ts.sigma_threshold }}σ / 环比 ±{{ ts.wow_threshold }}%</span>
      </div>
      <ChartLine :x-data="trendX" :series="trendSeries" height="250px" />
      <div class="hint ov-foot">首尾不完整周仍画在趋势里，但已在上方标注；异常判定只基于完整周（{{ ts.complete_week_cnt }} 个）。</div>

      <!-- 四、三栏：分类占比 / 高频问题 / 处理状态与闭环 -->
      <div class="ov-panels">
        <div class="ov-panel">
          <div class="ov-panel__title">问题分类占比（L1 五类 · 全周期）</div>
          <ChartPie :data="pieData" height="210px" @item-click="onPieClick" />
          <div class="ov-drift">
            <div v-for="c in d.categories || []" :key="c.name" class="ov-drift__row is-clickable"
              :title="`点击下钻「${c.name}」全部工单`"
              @click="emitDrill({ l1: c.name }, `整体·分类「${c.name}」`)">
              <span class="ov-drift__name">{{ c.name }}</span>
              <span class="ov-drift__val">{{ c.cnt }} 单 / {{ c.pct }}%</span>
              <span class="ov-drift__pp" :class="c.drift_pp > 0 ? 'is-up' : c.drift_pp < 0 ? 'is-down' : ''">
                近4周 {{ c.drift_pp > 0 ? '+' : '' }}{{ c.drift_pp }}pp
              </span>
            </div>
          </div>
        </div>

        <div class="ov-panel">
          <div class="ov-panel__title">高频问题 TOP{{ (d.top_problems || []).length }}（L2 闭集缺陷类 · 全周期累计）</div>
          <div class="hint ov-panel__hint">按累计单量，非本周单量；使用咨询 {{ pc.consult_cnt }} 单（{{ pc.consult_pct }}%）属非缺陷，另计不入榜</div>
          <div class="ov-top">
            <div v-for="(p, i) in d.top_problems || []" :key="p.module_problem_id"
              class="ov-top__item is-clickable" :title="`点击下钻「${p.name}」全部工单`"
              @click="emitDrill({ module_problem_id: p.module_problem_id }, `整体·高频问题「${p.name}」`)">
              <span class="ov-rank">{{ i + 1 }}</span>
              <span class="ov-top__main">
                <span class="ov-top__name">{{ p.name }}</span>
                <span class="ov-top__meta">
                  首现 {{ p.first_week }} · 持续 {{ p.active_weeks }} 周 · 近4周 {{ p.recent4_cnt }} 单
                  <b v-if="p.still_active && p.active_weeks >= 8" class="ov-flag">久拖不决</b>
                  <b v-else-if="!p.still_active" class="ov-flag is-quiet">近期静默</b>
                </span>
              </span>
              <span class="ov-top__cnt">{{ p.cnt }}<small> 单</small></span>
            </div>
          </div>
        </div>

        <div class="ov-panel">
          <div class="ov-panel__title">处理状态 / 闭环情况（全周期）</div>
          <div class="ov-status">
            <div v-for="s in cl.status_breakdown || []" :key="s.name"
              class="ov-status__row is-clickable" :title="`点击下钻状态「${s.name}」工单`"
              @click="emitDrill({ status: s.name }, `整体·处理状态「${s.name}」`)">
              <span class="ov-status__name">{{ s.name }}</span>
              <span class="ov-status__bar">
                <i :style="{ width: s.pct + '%' }" :class="s.closed ? 'is-closed' : 'is-open'" />
              </span>
              <span class="ov-status__val">{{ s.cnt }} / {{ s.pct }}%</span>
            </div>
          </div>
          <div class="ov-mini">
            <div class="ov-mini__item is-clickable" @click="emitDrill({ unclosed: 1 }, '整体·未闭环工单')">
              <span>未闭环</span><b>{{ cl.open }} 单</b>
            </div>
            <div class="ov-mini__item is-clickable" @click="emitDrill({ retention: 1 }, '整体·超期滞留工单')">
              <span>超 {{ cl.retention_days }} 天滞留</span><b>{{ cl.retention }} 单</b>
            </div>
            <div class="ov-mini__item is-clickable" @click="emitDrill({ is_batch: 1 }, '整体·批量投诉工单')">
              <span>批量投诉</span><b>{{ cl.batch }} 单</b>
            </div>
            <div class="ov-mini__item is-clickable" @click="emitDrill({ unclassified: 1 }, '整体·未归类工单')">
              <span>待自动补跑</span><b>{{ pc.unclassified }} 单</b>
            </div>
          </div>
          <div class="ov-ledger">
            问题台账在册 <b>{{ (cl.problem_ledger || {}).live ?? 0 }}</b> 条（open {{ (cl.problem_ledger || {}).open ?? 0 }} / resolving {{ (cl.problem_ledger || {}).resolving ?? 0 }}）；
            措施 <b>{{ actionTotal }}</b> 条，已生效 <b>{{ cl.actions.effective ?? 0 }}</b> 条。
            <el-link type="primary" :underline="false" @click="goActions">去措施跟踪 →</el-link>
          </div>
          <div class="hint ov-foot">分类占比按 L1 五类、高频问题按 L2 闭集，两套分类体系不同源，不互相加总。</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import ChartLine from '@/components/Charts/ChartLine.vue'
import ChartPie from '@/components/Charts/ChartPie.vue'
import { complaintApi } from '@/api/complaint'
import { downloadWithAuth } from '@/utils/download.js'

// 整体视图是独立组件：数据由父页统一取（刷新按钮自然同步），
// 下钻/抽屉复用父页唯一的 TicketDrillDrawer，避免第二个抽屉实例。
const props = defineProps({
  data: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['drill'])
const router = useRouter()
const collapsed = ref(false)
const exporting = ref(false)

const d = computed(() => props.data || {})
const ts = computed(() => d.value.trend_summary || {})
const cl = computed(() => d.value.closure || {})
const pc = computed(() => d.value.problem_coverage || {})

const scopeHint = computed(() => {
  const s = d.value.scope || {}
  return `范围 ${s.first_date} ~ ${s.last_date}｜${s.weeks} 个自然周｜数据截至 ${s.data_until || '—'}` +
    (s.in_progress_week ? `｜${s.in_progress_week} 进行中（仅 ${s.in_progress_days} 天）` : '')
})
const peakRatio = computed(() => ts.value.avg_week
  ? Math.round((ts.value.peak_total / ts.value.avg_week) * 10) / 10 : 0)
const actionTotal = computed(() => Object.values(cl.value.actions || {})
  .reduce((s, v) => s + (Number(v) || 0), 0))

const pieData = computed(() => (d.value.categories || [])
  .map(c => ({ value: c.cnt, name: c.name })))
const trendX = computed(() => (d.value.trend || []).map(t => t.week.replace(/^\d{4}-/, '')))
const trendSeries = computed(() => {
  const rows = d.value.trend || []
  return [
    { name: '周单量', data: rows.map(t => t.total), width: 2.5, area: true },
    // 周均基线用虚线常量序列，让偏离一眼可见；颜色走图表默认色板，禁硬编码
    { name: '完整周周均', data: rows.map(() => ts.value.avg_week), dash: true,
      width: 1.5, area: false },
  ]
})

function emitDrill(filters, title) {
  emit('drill', { ...filters }, title)
}
function onPieClick(p) {
  if (p?.name) emitDrill({ l1: p.name }, `整体·分类「${p.name}」`)
}
function goActions() {
  router.push('/complaint-center/actions')
}
async function exportAll() {
  exporting.value = true
  try {
    const name = await downloadWithAuth(complaintApi.ticketExportUrl({}))
    ElMessage.success(`已导出全量 ${d.value.scope.total} 单明细：${name}`)
  } catch (e) {
    ElMessage.error('导出失败：' + (e?.message || e))
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.ov-card { margin-bottom: 4px; }
/* .hint / .sub-h / 结论卡在看板页是 scoped 样式，独立组件内需自带同款视觉 */
.hint { font-size: 12px; color: var(--text-muted); }
.sub-h { font-size: 13px; font-weight: 700; color: var(--text-primary); margin: 18px 0 8px; }
.sub-h .hint { font-weight: 400; margin-left: 8px; }
.ov-tag {
  margin-left: 10px; padding: 2px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 600; color: var(--accent); background: var(--accent-soft);
  vertical-align: middle;
}
.ov-actions { margin-left: auto; display: flex; align-items: center; gap: 4px; }
.ov-conclusions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 14px; }
.ov-conclusion {
  margin: 0; padding: 10px 14px; border-radius: var(--radius-sm);
  border-left: 3px solid var(--accent); background: var(--accent-soft);
  font-size: 12.5px; line-height: 1.8; color: var(--text-secondary);
  cursor: pointer; display: flex; flex-direction: column; gap: 3px;
  transition: filter .15s;
}
.ov-conclusion:hover { filter: brightness(.97); }
.ov-conclusion.is-danger { background: var(--danger-soft); border-left-color: var(--danger); }
.ov-conclusion.is-success { background: var(--success-soft); border-left-color: var(--success); }
.ov-conclusion__text { color: var(--text-primary); }
.ov-conclusion__note { font-size: 11.5px; color: var(--text-muted); }
.ov-conclusion__go { font-size: 11px; color: var(--accent); align-self: flex-end; }
.ov-chips { display: flex; flex-wrap: wrap; gap: 6px 8px; margin: 0 0 8px; }
.ov-chip {
  padding: 4px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 600;
  border: 1px solid var(--border); color: var(--text-secondary);
  background: var(--surface);
}
.ov-chip.is-danger { color: var(--danger); background: var(--danger-soft); border-color: var(--danger); }
.ov-chip.is-success { color: var(--success); background: var(--success-soft); border-color: var(--success); }
.ov-chip.is-muted { color: var(--text-muted); }
.ov-chip.is-plain { font-weight: 400; color: var(--text-muted); }
.is-clickable { cursor: pointer; }
.ov-foot { margin-top: 8px; line-height: 1.7; }
.ov-panels {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px; margin-top: 18px;
}
.ov-panel {
  min-width: 0; padding: 12px 14px; border: 1px solid var(--border);
  border-radius: var(--radius-md); background: var(--surface);
}
.ov-panel__title { font-size: 12.5px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
.ov-panel__hint { display: block; line-height: 1.6; margin-bottom: 8px; }
.ov-drift { margin-top: 6px; }
.ov-drift__row {
  display: grid; grid-template-columns: 1fr auto auto; gap: 8px; align-items: center;
  padding: 5px 0; border-bottom: 1px dashed var(--border); font-size: 12px;
}
.ov-drift__name { color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ov-drift__val { color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.ov-drift__pp { min-width: 82px; text-align: right; color: var(--text-muted); font-size: 11.5px; }
.ov-drift__pp.is-up { color: var(--danger); }
.ov-drift__pp.is-down { color: var(--success); }
.ov-top { display: flex; flex-direction: column; gap: 5px; max-height: 320px; overflow-y: auto; }
.ov-top__item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border-radius: 8px; background: var(--bg-app); transition: background .15s;
}
.ov-top__item:hover { background: var(--accent-soft); }
.ov-rank {
  width: 20px; height: 20px; flex: none; border-radius: 6px; font-size: 11px; font-weight: 700;
  color: var(--surface); background: var(--accent); display: flex; align-items: center; justify-content: center;
}
.ov-top__main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ov-top__name { font-size: 12px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ov-top__meta { font-size: 11px; color: var(--text-muted); }
.ov-flag { margin-left: 5px; color: var(--danger); font-weight: 600; }
.ov-flag.is-quiet { color: var(--text-muted); font-weight: 400; }
.ov-top__cnt { flex: none; font-size: 13px; font-weight: 700; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.ov-top__cnt small { font-size: 10.5px; font-weight: 400; color: var(--text-muted); }
.ov-status { display: flex; flex-direction: column; gap: 7px; }
.ov-status__row {
  display: grid; grid-template-columns: 82px 1fr 82px; gap: 8px; align-items: center; font-size: 12px;
}
.ov-status__name { color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ov-status__bar { height: 7px; border-radius: 4px; background: var(--bg-app); overflow: hidden; }
.ov-status__bar i { display: block; height: 100%; border-radius: 4px; }
.ov-status__bar i.is-closed { background: var(--success); }
.ov-status__bar i.is-open { background: var(--warning); }
.ov-status__val { text-align: right; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.ov-mini { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; margin-top: 12px; }
.ov-mini__item {
  display: flex; justify-content: space-between; gap: 6px; padding: 6px 9px;
  border-radius: 8px; background: var(--bg-app); font-size: 11.5px; color: var(--text-secondary);
}
.ov-mini__item b { color: var(--text-primary); font-variant-numeric: tabular-nums; }
.ov-ledger { margin-top: 10px; font-size: 12px; line-height: 1.8; color: var(--text-secondary); }
@media (max-width: 1400px) {
  .ov-panels { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  .ov-conclusions, .ov-panels { grid-template-columns: 1fr; }
  .pm-stat-grid--6 { --pm-stat-cols: 3; }
}
@media (max-width: 768px) {
  .pm-stat-grid--6 { --pm-stat-cols: 2; }
  .ov-status__row { grid-template-columns: 68px 1fr 72px; }
}
</style>
