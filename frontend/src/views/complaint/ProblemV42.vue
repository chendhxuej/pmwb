<template>
  <div class="problem-v42">
    <PageHeader title="客诉问题点类 · v4.2 自动化" :subtitle="subTitle">
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" :icon="VideoPlay" :loading="running" @click="runAnalysis(false)">
          重新分析（只读演练）
        </el-button>
        <el-button type="warning" :icon="Upload" :loading="running" @click="confirmApply">
          落库并自动补跑
        </el-button>
      </template>
    </PageHeader>

    <!-- 验收状态卡 -->
    <section class="card status-card">
      <div class="status-head">
        <div class="status-title">最近一次验收结论</div>
        <el-tag v-if="status.last_run" :type="status.last_run.publish ? 'success' : 'danger'" effect="dark">
          {{ status.last_run.publish ? '已发布' : '未发布（自动拦截）' }}
        </el-tag>
        <el-tag v-else type="info" effect="plain">尚未运行</el-tag>
        <span v-if="status.last_run" class="status-time">{{ status.last_run.created_at }}</span>
      </div>

      <div class="pm-stat-grid pm-stat-grid--5 status-kpis">
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">工单总数</span></div>
          <div class="pm-stat__val">{{ counts.points }}<span class="pm-stat__unit">单</span></div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">已生成问题点</span></div>
          <div class="pm-stat__val is-accent">{{ counts.point_ok }}<span class="pm-stat__unit">单</span></div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">问题点类</span></div>
          <div class="pm-stat__val">{{ counts.classes }}<span class="pm-stat__unit">个</span></div>
          <div class="pm-stat__sub">已发布 {{ counts.published_classes }}</div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">未归类</span></div>
          <div class="pm-stat__val" :class="counts.unclassified ? 'is-warning' : 'is-success'">
            {{ counts.unclassified }}<span class="pm-stat__unit">单</span>
          </div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">待自动补跑</span></div>
          <div class="pm-stat__val" :class="counts.pending_auto_rerun ? 'is-warning' : 'is-muted'">
            {{ counts.pending_auto_rerun }}<span class="pm-stat__unit">单</span>
          </div>
        </div>
      </div>

      <div v-if="status.last_run" class="metrics-row">
        <div v-for="m in metricList" :key="m.key" class="metric-chip" :class="m.tone">
          <span class="metric-label">{{ m.label }}</span>
          <span class="metric-val">{{ m.value }}%</span>
        </div>
      </div>

      <el-alert
        v-if="status.last_run && status.last_run.veto && status.last_run.veto.length"
        type="error" :closable="false" show-icon
        :title="'一票否决未通过：' + status.last_run.veto.join('、')" />

      <el-alert
        v-if="status.warnings && status.warnings.length"
        type="warning" :closable="false" show-icon
        :title="'观测项需关注：' + status.warnings.join('；')" />

      <div v-if="status.last_run" class="channel-line">
        <el-tag size="small" :type="status.last_run.channel_available ? 'success' : 'info'" effect="plain">
          语义通道 {{ status.last_run.channel_available ? '可用' : '不可用' }}
        </el-tag>
        <span v-if="status.last_run.channel_notice" class="channel-notice">{{ status.last_run.channel_notice }}</span>
      </div>
    </section>

    <!-- 问题点类列表 -->
    <section class="card">
      <div class="block-head">
        <span class="block-title">问题点类（一句话具体投诉问题点）</span>
        <span class="block-sub">按工单量降序 · 共 {{ classTotal }} 个</span>
      </div>
      <el-table :data="classItems" v-loading="loading" size="small" stripe>
        <el-table-column prop="class_no" label="类编号" width="120" />
        <el-table-column label="投诉问题点（一句具体描述）" min-width="320">
          <template #default="{ row }">
            <div class="cls-desc">{{ row.description }}</div>
            <div v-if="row.fix_point" class="cls-fix">改进措施：{{ row.fix_point }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="ticket_cnt" label="工单量" width="90" align="center" sortable />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="classStatusType(row.status)">{{ classStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column type="expand" label="判定卡" width="80">
          <template #default="{ row }">
            <div class="card-detail" v-if="row.card && Object.keys(row.card).length">
              <div v-for="(v, k) in row.card" :key="k" class="card-line">
                <span class="card-k">{{ cardKeyText(k) }}</span>
                <span class="card-v">{{ formatVal(v) }}</span>
              </div>
            </div>
            <div v-if="row.reasons && row.reasons.length" class="card-reasons">
              未发布原因：{{ row.reasons.join('；') }}
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="classTotal > classPageSize" class="pg" layout="prev,pager,next"
        :total="classTotal" :page-size="classPageSize" v-model:current-page="classPage"
        @current-change="loadClasses" />
    </section>

    <!-- 未归类清单 -->
    <section class="card">
      <div class="block-head">
        <span class="block-title">未归类清单（逐单写明缺哪项证据）</span>
        <span class="block-sub">共 {{ unclsTotal }} 单</span>
      </div>
      <el-table :data="unclsItems" v-loading="loading" size="small" stripe max-height="420">
        <el-table-column prop="ticket_no" label="工单号" width="150" />
        <el-table-column label="状态" width="130" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'pending_auto_rerun' ? 'warning' : 'info'" effect="plain">
              {{ row.status === 'pending_auto_rerun' ? '待自动补跑' : '自动拒识' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="缺口原因" min-width="380" />
      </el-table>
      <el-pagination
        v-if="unclsTotal > unclsPageSize" class="pg" layout="prev,pager,next"
        :total="unclsTotal" :page-size="unclsPageSize" v-model:current-page="unclsPage"
        @current-change="loadUnclassified" />
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, VideoPlay, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/Common/PageHeader.vue'
import { complaintApi as api } from '@/api/complaint'

const loading = ref(false)
const running = ref(false)

const status = ref({ counts: {} })
const counts = computed(() => status.value.counts || {})

const classItems = ref([])
const classTotal = ref(0)
const classPage = ref(1)
const classPageSize = 20

const unclsItems = ref([])
const unclsTotal = ref(0)
const unclsPage = ref(1)
const unclsPageSize = 20

const subTitle = computed(() =>
  '逐单投诉问题点由系统自动生成与确定性判定，分析过程不依赖人（v4.2 ' +
  (status.value.policy_version || '') + '）')

const METRIC_LABELS = {
  no_human_touch: '无人工触点率',
  point_pass_rate: '逐单合格率',
  analysis_coverage: '分析完成率',
  gate_coverage: '门禁覆盖率',
  card_complete: '判定卡完备率',
  evidence_anchor: '证据锚点覆盖率',
  separation: '生成判定分离率',
  count_closure: '数量闭合率',
  content_closure: '内容闭合率',
  one_ticket_one_class: '一单一类率',
}
const metricList = computed(() => {
  const m = status.value.last_run?.metrics || {}
  return Object.keys(METRIC_LABELS)
    .filter((k) => m[k] != null)
    .map((k) => {
      const v = Number(m[k])
      return {
        key: k,
        label: METRIC_LABELS[k],
        value: v.toFixed(0),
        tone: v >= 100 ? 'is-success' : v >= 90 ? 'is-warning' : 'is-danger',
      }
    })
})

function classStatusType(s) {
  return { published: 'success', blocked: 'danger', draft: 'warning', changed: 'info', voided: 'info' }[s] || 'info'
}
function classStatusText(s) {
  return { published: '已发布', blocked: '已拦截', draft: '草稿', changed: '口径变更', voided: '已作废' }[s] || s
}
function cardKeyText(k) {
  return {
    problem_point: '共性问题点', appeal: '客户诉求', failure: '可观察失败',
    trigger: '触发场景', object: '具体对象', fix_point: '改进措施',
  }[k] || k
}
function formatVal(v) {
  if (Array.isArray(v)) return v.join('、')
  if (typeof v === 'object' && v) return JSON.stringify(v)
  return String(v ?? '')
}

async function loadStatus() {
  // request.js 响应拦截器已在 code===0 时解出 data.data，api.* 直接返回真实载荷
  const r = await api.problemV42Status()
  status.value = r || {}
}
async function loadClasses() {
  const r = await api.problemV42Classes({ page: classPage.value, page_size: classPageSize })
  const d = r || {}
  classItems.value = d.items || []
  classTotal.value = d.total || 0
}
async function loadUnclassified() {
  const r = await api.problemV42Unclassified({ page: unclsPage.value, page_size: unclsPageSize })
  const d = r || {}
  unclsItems.value = d.items || []
  unclsTotal.value = d.total || 0
}
async function loadAll() {
  loading.value = true
  try {
    await loadStatus()
    await Promise.all([loadClasses(), loadUnclassified()])
  } finally {
    loading.value = false
  }
}

async function runAnalysis(apply) {
  running.value = true
  try {
    const r = await api.problemV42Run({ dry_run: !apply, force: true, limit: 0, allow_semantic: true, max_semantic_batches: 0 })
    const d = r || {}
    ElMessage.success(`分析完成：${d.point_ok ?? 0} 单通过、` +
      `${d.published_classes ?? 0} 个类发布、` +
      `${d.pending_auto_rerun ?? 0} 单待自动补跑` + (apply ? '（已落库）' : '（只读演练）'))
    await loadAll()
  } catch (e) {
    ElMessage.error('分析失败：' + (e?.response?.data?.message || e.message))
  } finally {
    running.value = false
  }
}
async function confirmApply() {
  try {
    await ElMessageBox.confirm(
      '将按 v4.2 口径全量重写历史逐单问题点与问题点类并落库，语义通道不可用的单会标「待自动补跑」自动续跑。确定执行？',
      '落库并自动补跑', { type: 'warning', confirmButtonText: '确定落库', cancelButtonText: '取消' })
  } catch { return }
  await runAnalysis(true)
}

onMounted(loadAll)
</script>

<style scoped>
.problem-v42 { padding: 4px 2px 24px; }
.status-card { margin-bottom: 16px; }
.status-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.status-title { font-size: 15px; font-weight: 600; color: var(--text-primary, #1f2d3d); }
.status-time { margin-left: auto; font-size: 12px; color: var(--text-muted, #94a3b8); }
.status-kpis { margin-bottom: 12px; }
.metrics-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 12px; }
.metric-chip {
  display: inline-flex; align-items: baseline; gap: 6px;
  padding: 5px 10px; border-radius: 8px; background: var(--bg-soft, #f1f5f9);
  border: 1px solid var(--border-soft, #e2e8f0); font-size: 12px;
}
.metric-label { color: var(--text-secondary, #64748b); }
.metric-val { font-weight: 700; font-size: 13px; }
.metric-chip.is-success .metric-val { color: var(--success, #16a34a); }
.metric-chip.is-warning .metric-val { color: var(--warning, #d97706); }
.metric-chip.is-danger .metric-val { color: var(--danger, #dc2626); }
.channel-line { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.channel-notice { font-size: 12px; color: var(--text-muted, #94a3b8); }
.block-head { display: flex; align-items: baseline; gap: 10px; margin: 4px 2px 12px; }
.block-title { font-size: 14.5px; font-weight: 600; color: var(--text-primary, #1f2d3d); }
.block-sub { font-size: 12px; color: var(--text-muted, #94a3b8); }
.cls-desc { font-weight: 600; line-height: 1.5; color: var(--text-primary, #1f2d3d); }
.cls-fix { margin-top: 3px; font-size: 12px; color: var(--text-secondary, #64748b); }
.card-detail { padding: 6px 4px; }
.card-line { display: flex; gap: 10px; padding: 3px 0; font-size: 13px; }
.card-k { width: 96px; flex-shrink: 0; color: var(--text-secondary, #64748b); }
.card-v { color: var(--text-primary, #1f2d3d); flex: 1; }
.card-reasons { margin-top: 6px; font-size: 12.5px; color: var(--danger, #dc2626); }
.pg { margin-top: 12px; justify-content: flex-end; }
</style>
