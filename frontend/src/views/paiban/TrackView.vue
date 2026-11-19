<template>
  <div class="pb-page">
    <PageHeader title="排版跟踪" :subtitle="subtitle">
      <template #actions>
        <el-select v-model="planId" filterable clearable placeholder="选择版本计划" style="width: 240px" @change="loadAll">
          <el-option v-for="p in plans" :key="p.id" :label="p.version_no" :value="p.id" />
        </el-select>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" @click="openCandidates">从候选池纳入</el-button>
      </template>
    </PageHeader>

    <el-alert type="info" show-icon :closable="false" class="pb-alert">
      <template #title>按计划上线，跟踪到成功为止</template>
      <template #default>
        候选规则跑出「未闭环、未纳入」的需求与 BUG → 人工确认纳入 → 四环节推进 → 准入判定 → 登记结果。
        未准入 / 未排进版本 / 上线失败<b>默认自动顺延下一版</b>，主行不关闭；确需留本版走单据级「手工处理」，原因必填且不计按计划上线率分子。
      </template>
    </el-alert>

    <div v-if="ov" class="pm-stat-grid pm-stat-grid--4">
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">本版在跟（主行）</span></div>
        <div class="pm-stat__val is-accent">{{ ov.kpi.should_go_live }}<span class="pm-stat__unit">单</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">已准入 / 待判定</span></div>
        <div class="pm-stat__val">{{ ov.kpi.admitted }} / {{ ov.kpi.pending }}</div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">人工例外</span></div>
        <div class="pm-stat__val">{{ ov.kpi.exception }}<span class="pm-stat__unit">单</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">未消除硬门禁风险</span></div>
        <div class="pm-stat__val">{{ ov.kpi.blocking_risks }}<span class="pm-stat__unit">条</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">已上线</span></div>
        <div class="pm-stat__val">{{ ov.kpi.live }}<span class="pm-stat__unit">单</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">未排进 / 上线失败</span></div>
        <div class="pm-stat__val">{{ ov.kpi.not_scheduled }} / {{ ov.kpi.failed }}</div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">顺延进入本版</span></div>
        <div class="pm-stat__val">{{ ov.kpi.deferred_in }}<span class="pm-stat__unit">单</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">按计划上线率</span></div>
        <div class="pm-stat__val">{{ rateText }}<span class="pm-stat__unit">%</span></div></div>
    </div>

    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">四环节泳道</span>
          <div class="pb-filters">
            <el-select v-model="filters.ticket_type" clearable placeholder="类型" style="width: 110px" @change="loadTracks">
              <el-option v-for="o in meta.ticket_types || []" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="filters.stage" clearable placeholder="环节" style="width: 130px" @change="loadTracks">
              <el-option v-for="o in meta.stages || []" :key="o.key" :label="o.label" :value="o.key" />
            </el-select>
            <el-select v-model="filters.admit_status" clearable placeholder="准入" style="width: 150px" @change="loadTracks">
              <el-option v-for="o in meta.admit_statuses || []" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-model="filters.keyword" clearable placeholder="工单号 / 标题" style="width: 180px" @keyup.enter="loadTracks" />
          </div>
        </div>
      </template>
      <div class="pb-lanes">
        <div v-for="s in meta.stages || []" :key="s.key" class="pb-lane">
          <div class="pb-lane-head">{{ s.label }} <span>{{ laneCount(s.key) }}</span></div>
          <div class="pb-lane-body">
            <div v-for="t in laneTracks(s.key)" :key="t.id" class="pb-ticket" @click="openTrack(t)">
              <div class="pb-ticket-top">
                <el-tag size="small" effect="plain">{{ t.ticket_type_label }}</el-tag>
                <span class="pb-ticket-no">{{ t.ticket_no }}</span>
                <el-tag v-if="t.exception_flag" size="small" type="warning" effect="dark">例外</el-tag>
                <el-tag v-if="t.focus_flag" size="small" type="danger" effect="plain">重点</el-tag>
              </div>
              <div class="pb-ticket-title">{{ t.title }}</div>
              <div class="pb-ticket-meta">
                <span>{{ t.system_name || '待补全系统' }}</span>
                <span>{{ t.admit_status_label }}</span>
                <span v-if="t.metrics?.overdue" class="pb-danger">已超期</span>
                <span v-else-if="t.metrics?.near_due" class="pb-warn">临期</span>
                <span v-if="t.blocking_risk_count" class="pb-danger">{{ t.blocking_risk_count }} 风险</span>
              </div>
              <div v-if="t.defer_count" class="pb-ticket-defer">顺延 {{ t.defer_count }} 次 · {{ t.plan?.version_no || '待补版本计划' }}</div>
            </div>
            <div v-if="!laneTracks(s.key).length" class="pb-empty-lane">暂无</div>
          </div>
        </div>
      </div>
      <div class="pb-footnote">{{ tracks.scope_note || '版本统计按主行；团队视图按团队子行，两处不可加总' }}</div>
    </el-card>

    <!-- 候选池 -->
    <el-drawer v-model="candVisible" title="从候选池纳入" size="60%">
      <el-alert type="info" :closable="false" show-icon class="pb-alert">
        <template #default>规则自动出候选、人工一次性确认；候选页只读，不做后台静默纳入。排除原因逐条可见。</template>
      </el-alert>
      <div class="pb-toolbar">
        <el-input v-model="candKeyword" clearable placeholder="工单号 / 标题" style="width: 240px" @keyup.enter="loadCandidates" />
        <el-button @click="loadCandidates">查询</el-button>
        <el-button type="primary" :disabled="!selected.length" @click="doInclude">纳入选中（{{ selected.length }}）</el-button>
        <el-button @click="doSync">幂等同步源快照</el-button>
      </div>
      <el-table :data="cands.items || []" height="52vh" @selection-change="v => selected = v.map(x => ({ ticket_type: x.ticket_type, ticket_no: x.ticket_no }))">
        <el-table-column type="selection" width="46" />
        <el-table-column prop="ticket_no" label="工单号" width="130" />
        <el-table-column label="类型" width="80"><template #default="{ row }">{{ row.ticket_type === 'req' ? '需求' : 'BUG' }}</template></el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="system_name" label="系统" width="120" />
        <el-table-column prop="expected_date" label="期望上线" width="110" />
        <el-table-column prop="admit_status" label="源状态" width="100" />
      </el-table>
      <div class="pb-footnote">排除 {{ cands.summary?.excluded_count || 0 }} 条：
        <span v-for="r in cands.summary?.by_reason || []" :key="r.reason" class="pb-chip">{{ r.label }} {{ r.count }}</span>
      </div>
    </el-drawer>

    <!-- 工单抽屉 -->
    <el-drawer v-model="trackVisible" size="62%" :title="detail.ticket_no || '工单详情'">
      <template v-if="detail.id">
        <div class="pb-detail-head">
          <div><b>{{ detail.title }}</b></div>
          <div class="pb-ticket-meta">
            <span>{{ detail.system_name || '待补全系统' }}</span><span>{{ detail.stage_label }}</span>
            <span>{{ detail.admit_status_label }}</span><span>{{ detail.plan?.version_no || '待补版本计划' }}</span>
          </div>
        </div>
        <el-tabs v-model="detailTab">
          <el-tab-pane label="团队环节" name="teams">
            <el-table :data="detail.teams || []" size="small">
              <el-table-column prop="team_name" label="团队" min-width="140" />
              <el-table-column prop="owner" label="对接人" min-width="130" />
              <el-table-column prop="stage_label" label="环节" width="110" />
              <el-table-column label="改环节" width="180">
                <template #default="{ row }">
                  <el-select :model-value="row.stage" size="small" placeholder="选择环节" @change="v => changeTeamStage(row, v)">
                    <el-option v-for="o in meta.stages || []" :key="o.key" :label="o.label" :value="o.key" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column prop="last_feedback_at" label="最近反馈" width="160" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="登记结果" name="result">
            <el-form label-width="100px" class="pb-form">
              <el-form-item label="上线结果">
                <el-select v-model="resultForm.result" style="width: 220px">
                  <el-option v-for="o in meta.results || []" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="resultForm.result !== 'live'" label="原因" required>
                <el-input v-model="resultForm.reason" type="textarea" :rows="2" placeholder="未排进版本 / 上线失败 / 取消必填" />
              </el-form-item>
              <el-form-item label="结果日期"><el-date-picker v-model="resultForm.result_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
              <el-form-item><el-button type="primary" @click="doResult">登记（失败/未排进默认顺延）</el-button></el-form-item>
            </el-form>
            <el-alert v-if="detail.blocking_risk_count" type="error" :closable="false" show-icon class="pb-alert">
              <template #default>存在 {{ detail.blocking_risk_count }} 条影响上线且未消除的风险，登记「已上线」会被硬门禁拦截；先在「风险」页消除。</template>
            </el-alert>
          </el-tab-pane>
          <el-tab-pane label="手工处理" name="manual">
            <el-alert type="warning" :closable="false" show-icon class="pb-alert">
              <template #default>默认动作 = 自动顺延。仅确需留本版时使用「例外放行」，须选闭集原因并留操作人与原判定事实；例外单不计按计划上线率分子。</template>
            </el-alert>
            <el-form label-width="100px" class="pb-form">
              <el-form-item label="动作">
                <el-radio-group v-model="manualForm.action">
                  <el-radio value="defer">确认顺延（默认）</el-radio>
                  <el-radio value="allow">例外放行留本版</el-radio>
                  <el-radio v-if="detail.exception_flag" value="revoke">撤销例外</el-radio>
                </el-radio-group>
              </el-form-item>
              <template v-if="manualForm.action === 'allow'">
                <el-form-item label="例外原因" required>
                  <el-select v-model="manualForm.reason" style="width: 280px">
                    <el-option v-for="o in meta.exception_reasons || []" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="manualForm.reason === 'other'" label="说明" required>
                  <el-input v-model="manualForm.reason_note" type="textarea" :rows="2" />
                </el-form-item>
              </template>
              <el-form-item label="操作人"><el-input v-model="manualForm.operator" style="width: 220px" /></el-form-item>
              <el-form-item><el-button type="primary" @click="doManual">提交处理</el-button></el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="风险与轨迹" name="timeline">
            <el-form inline class="pb-form">
              <el-form-item label="风险类型">
                <el-select v-model="riskForm.risk_type" style="width: 180px">
                  <el-option v-for="o in meta.risk_types || []" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="说明"><el-input v-model="riskForm.description" style="width: 260px" /></el-form-item>
              <el-form-item><el-checkbox v-model="riskForm.affect_release">影响本版上线</el-checkbox></el-form-item>
              <el-form-item><el-button type="primary" @click="doRisk">登记风险</el-button></el-form-item>
            </el-form>
            <el-timeline>
              <el-timeline-item v-for="l in timeline.stage_logs || []" :key="l.id" :timestamp="l.changed_at">
                {{ l.from_stage ? stageLabel(l.from_stage) + ' → ' : '' }}{{ stageLabel(l.to_stage) }}
                <span v-if="l.is_rollback" class="pb-danger">（回退）</span>
                <div class="pb-hint">{{ l.source }} · {{ l.operator }} · {{ l.reason }}</div>
              </el-timeline-item>
            </el-timeline>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/Common/PageHeader.vue'
import {
  getPaibanMeta, listVersionPlans, getPbOverview, listPbTracks, listCandidates,
  includeCandidates, syncTracks, getTrackTimeline, setTrackResult, manualHandle,
  setTeamStage, createPbRisk,
} from '@/api/paiban.js'

const meta = ref({}), plans = ref([]), planId = ref(null)
const ov = ref(null), tracks = ref({ items: [] }), loading = ref(false)
const filters = reactive({ ticket_type: '', stage: '', admit_status: '', keyword: '' })
const candVisible = ref(false), cands = ref({ items: [] }), candKeyword = ref(''), selected = ref([])
const trackVisible = ref(false), detail = ref({}), timeline = ref({}), detailTab = ref('teams')
const resultForm = reactive({ result: '', reason: '', result_date: '' })
const manualForm = reactive({ action: 'defer', reason: '', reason_note: '', operator: '' })
const riskForm = reactive({ risk_type: 'other', description: '', affect_release: false })

const subtitle = computed(() => '围绕版本计划跟踪需求与运营 BUG，直到成功上线')
const rateText = computed(() => ov.value?.rates?.planned_rate == null ? '—' : Math.round(ov.value.rates.planned_rate * 100))
const stageLabel = key => (meta.value.stages || []).find(s => s.key === key)?.label || key

async function loadAll() {
  loading.value = true
  try {
    meta.value = await getPaibanMeta()
    meta.value = await getPaibanMeta()
    const p = await listVersionPlans({ status: 'confirmed' })
    plans.value = p.items || []
    if (!planId.value && plans.value.length) planId.value = plans.value[0].id
    await Promise.all([loadOverview(), loadTracks()])
  } finally { loading.value = false }
}
async function loadOverview() {
  if (!planId.value) { ov.value = null; return }
  ov.value = await getPbOverview(planId.value)
}
async function loadTracks() {
  tracks.value = await listPbTracks({ plan_id: planId.value || undefined, ...filters })
}
const laneTracks = key => (tracks.value.items || []).filter(t => t.stage === key)
const laneCount = key => laneTracks(key).length

async function openCandidates() { candVisible.value = true; await loadCandidates() }
async function loadCandidates() {
  cands.value = await listCandidates({ keyword: candKeyword.value, limit: 200 })
  selected.value = []
}
async function doInclude() {
  if (!selected.value.length) return
  const out = await includeCandidates({ items: selected.value, operator: '页面' })
  ElMessage.success(`纳入 ${out.created_count} 条，跳过 ${out.skipped_count} 条`)
  await loadAll(); await loadCandidates()
}
async function doSync() {
  const out = await syncTracks({ operator: '页面' })
  ElMessage.success(`同步完成：更新 ${out.updated.length}，墓碑 ${out.missing.length}`)
  await loadAll()
}
async function openTrack(t) {
  detail.value = t
  trackVisible.value = true
  detailTab.value = 'teams'
  Object.assign(resultForm, { result: '', reason: '', result_date: '' })
  Object.assign(manualForm, { action: 'defer', reason: '', reason_note: '', operator: '' })
  timeline.value = await getTrackTimeline(t.id)
}
async function changeTeamStage(row, stage) {
  await setTeamStage(row.id, { stage, reason: '', operator: '页面' })
  ElMessage.success('团队环节已更新，主行按最慢子行重算')
  await refreshDetail(); await loadAll()
}
async function refreshDetail() {
  if (!detail.value?.id) return
  timeline.value = await getTrackTimeline(detail.value.id)
  detail.value = timeline.value.track
}
async function doResult() {
  await setTrackResult(detail.value.id, { ...resultForm, operator: '页面' })
  ElMessage.success('结果已登记')
  trackVisible.value = false
  await loadAll()
}
async function doManual() {
  await manualHandle(detail.value.id, { ...manualForm, operator: manualForm.operator || '页面' })
  ElMessage.success('手工处理完成')
  await refreshDetail(); await loadAll()
}
async function doRisk() {
  await createPbRisk(detail.value.id, { ...riskForm, affect_release: riskForm.affect_release ? 1 : 0, operator: '页面' })
  ElMessage.success('风险已登记')
  await refreshDetail()
}
onMounted(loadAll)
</script>

<style scoped>
.pb-page { padding: 4px 2px 24px; }
.pb-alert { margin-bottom: 14px; }
.pb-card { margin-bottom: 16px; }
.pb-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.pb-card-title { font-weight: 600; }
.pb-filters, .pb-toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pb-toolbar { margin-bottom: 12px; }
.pb-lanes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.pb-lane { background: var(--bg-app); border-radius: var(--radius-sm); padding: 10px; min-height: 260px; }
.pb-lane-head { display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 10px; }
.pb-lane-head span { color: var(--text-secondary); }
.pb-lane-body { display: flex; flex-direction: column; gap: 8px; }
.pb-ticket { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px; cursor: pointer; transition: var(--transition-fast); }
.pb-ticket:hover { border-color: var(--accent); box-shadow: var(--shadow-card); }
.pb-ticket-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pb-ticket-no { font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); }
.pb-ticket-title { font-size: 13px; margin: 8px 0 6px; line-height: 1.45; }
.pb-ticket-meta { display: flex; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--text-secondary); }
.pb-ticket-defer { margin-top: 6px; font-size: 12px; color: var(--warning); }
.pb-empty-lane { color: var(--text-muted); font-size: 12px; text-align: center; padding: 18px 0; }
.pb-footnote { margin-top: 12px; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.pb-chip { display: inline-block; margin: 0 6px 4px 0; padding: 2px 8px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); }
.pb-danger { color: var(--danger); }
.pb-warn { color: var(--warning); }
.pb-detail-head { margin-bottom: 14px; }
.pb-form { padding: 8px 0; }
.pb-hint { color: var(--text-muted); font-size: 12px; }
@media (max-width: 1100px) { .pb-lanes { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
