<template>
  <div class="pb-page">
    <PageHeader title="团队跟踪" :subtitle="subtitle">
      <template #actions>
        <el-select v-model="planId" filterable clearable placeholder="选择版本计划" style="width: 240px" @change="loadAll">
          <el-option v-for="p in plans" :key="p.id" :label="p.version_no" :value="p.id" />
        </el-select>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <el-alert type="info" show-icon :closable="false" class="pb-alert">
      <template #title>主行与团队子行，两套口径不可加总</template>
      <template #default>版本统计按主行计数，本页矩阵按下钻到团队的<b>工单×团队子行</b>计数。一个工单跨团队会被拆成多行，因此两处数字天然不同，禁止互相校验。团队/收件人解析失败进「未分配团队」可见兜底，不静默丢弃。</template>
    </el-alert>

    <div class="pm-stat-grid pm-stat-grid--4">
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">主行数</span></div>
        <div class="pm-stat__val is-accent">{{ matrix.main_row_count || 0 }}<span class="pm-stat__unit">单</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">团队子行数</span></div>
        <div class="pm-stat__val">{{ matrix.team_row_count || 0 }}<span class="pm-stat__unit">行</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">解析失败待补全</span></div>
        <div class="pm-stat__val">{{ (matrix.unresolved || []).length }}<span class="pm-stat__unit">行</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">超期子行</span></div>
        <div class="pm-stat__val">{{ overdueCount }}<span class="pm-stat__unit">行</span></div></div>
    </div>

    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">团队 × 四环节矩阵</span>
          <div class="pb-filters">
            <el-select v-model="filters.team_name" filterable clearable placeholder="全部团队" style="width: 180px" @change="loadMatrix">
              <el-option v-for="n in teamNames" :key="n" :label="n" :value="n" />
            </el-select>
            <el-select v-model="filters.stage" clearable placeholder="环节" style="width: 130px" @change="loadMatrix">
              <el-option v-for="s in matrix.stages || []" :key="s.key" :label="s.label" :value="s.key" />
            </el-select>
            <el-select v-model="filters.overdue" clearable placeholder="超期" style="width: 110px" @change="loadMatrix">
              <el-option label="仅超期" value="1" /><el-option label="仅未超期" value="0" />
            </el-select>
          </div>
        </div>
      </template>
      <!-- 主行 0 = 该版本还没纳入任何工单，显式引导，避免误以为系统没关联 -->
      <el-alert v-if="!loading && !(matrix.main_row_count > 0)" type="warning" show-icon :closable="false" class="pb-empty-hint">
        <template #title>该版本尚未纳入任何工单</template>
        <template #default>
          版本计划只是发布日基准，<b>不会自动抓取需求和 BUG</b>（避免把未确认的工单塞进跟踪）。
          请先到左侧「排版跟踪」→ 点「从候选池纳入」→ 勾选要跟的需求/BUG → 纳入；纳入后系统按系统名自动归属到本版本，本页即出现团队子行。
        </template>
      </el-alert>
      <el-table :data="matrix.grid || []" size="small" border>
        <el-table-column prop="team_name" label="团队 / 系统" min-width="160" fixed="left" />
        <el-table-column v-for="s in matrix.stages || []" :key="s.key" :label="s.label" min-width="100" align="center">
          <template #default="{ row }">
            <span class="pb-cell" @click="drill(row.team_name, s.key)">{{ row.counts?.[s.key] || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total" label="合计" width="90" align="center" />
      </el-table>
      <div class="pb-footnote">{{ matrix.scope_note }} · 点击格内数字下钻，下钻与矩阵同源（同一版本 + 团队 + 环节 + 超期筛选）。</div>
    </el-card>

    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">下钻明细</span>
          <div class="pb-filters">
            <el-select v-model="bulkStage" clearable placeholder="批量改为环节" style="width: 140px">
              <el-option v-for="s in matrix.stages || []" :key="s.key" :label="s.label" :value="s.key" />
            </el-select>
            <el-input v-model="bulkReason" placeholder="回退原因（选填，回退必填）" style="width: 200px" />
            <el-button type="primary" :disabled="!bulkSelected.length || !bulkStage" @click="doBulkStage">批量调整（{{ bulkSelected.length }}）</el-button>
          </div>
        </div>
      </template>
      <el-table :data="matrix.drill || []" size="small" max-height="420" @selection-change="v => bulkSelected = v">
        <el-table-column type="selection" width="42" />
        <el-table-column prop="ticket_no" label="工单号" width="130" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="80"><template #default="{ row }">{{ lbl('ticket_types', row.ticket_type) }}</template></el-table-column>
        <el-table-column prop="team_name" label="团队" width="140" />
        <el-table-column prop="stage_label" label="环节" width="110" />
        <el-table-column label="准入" width="130"><template #default="{ row }">{{ lbl('admit_statuses', row.admit_status) }}</template></el-table-column>
        <el-table-column label="超期" width="80"><template #default="{ row }"><span :class="row.overdue ? 'pb-danger' : ''">{{ row.overdue ? '是' : '否' }}</span></template></el-table-column>
        <el-table-column prop="deadline" label="本环节截止" width="120" />
        <el-table-column prop="supervise_count" label="督办次数" width="90" />
        <el-table-column prop="last_feedback_at" label="最近反馈" width="160" />
        <el-table-column label="调整环节" width="150" fixed="right">
          <template #default="{ row }">
            <el-select :model-value="row.stage" size="small" placeholder="改环节" @change="v => doSingleStage(row, v)">
              <el-option v-for="s in matrix.stages || []" :key="s.key" :label="s.label" :value="s.key" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="(matrix.unresolved || []).length" shadow="never" class="pb-card">
      <template #header><span class="pb-card-title">解析失败待补全</span></template>
      <el-table :data="matrix.unresolved" size="small">
        <el-table-column prop="ticket_no" label="工单号" width="130" />
        <el-table-column prop="team_name" label="解析结果" min-width="180" />
        <el-table-column prop="reason" label="原因" min-width="220" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/Common/PageHeader.vue'
import { makeLabeler } from '@/utils/paibanLabels.js'
import { getPaibanMeta, listVersionPlans, teamMatrix, setTeamStage, batchSetTeamStage } from '@/api/paiban.js'

const meta = ref({}), plans = ref([]), planId = ref(null)
const matrix = ref({ grid: [], drill: [], stages: [] }), loading = ref(false)
const filters = reactive({ team_name: '', stage: '', overdue: '' })
const bulkStage = ref(''), bulkReason = ref(''), bulkSelected = ref([])
const lbl = makeLabeler(meta)

const subtitle = computed(() => '按团队看卡点、找对接人、可下钻到工单')
const teamNames = computed(() => [...new Set((matrix.value.grid || []).map(x => x.team_name))])
const overdueCount = computed(() => (matrix.value.drill || []).filter(x => x.overdue).length)

async function loadAll() {
  loading.value = true
  try {
    meta.value = await getPaibanMeta()
    const p = await listVersionPlans({ status: 'confirmed' })
    plans.value = p.items || []
    if (!planId.value && plans.value.length) planId.value = plans.value[0].id
    await loadMatrix()
  } finally { loading.value = false }
}
async function loadMatrix() {
  bulkSelected.value = []
  matrix.value = await teamMatrix({ plan_id: planId.value || undefined, ...filters })
}
function drill(team, stage) {
  filters.team_name = team
  filters.stage = stage
  loadMatrix()
}
async function doSingleStage(row, stage) {
  if (stage === row.stage) return
  const stages = (matrix.value.stages || []).map(s => s.key)
  const isRollback = stages.indexOf(stage) < stages.indexOf(row.stage)
  let reason = ''
  if (isRollback) {
    reason = window.prompt('环节回退必须填写原因', '') || ''
    if (!reason) { ElMessage.warning('已取消：回退必须填写原因'); await loadMatrix(); return }
  }
  try {
    await setTeamStage(row.team_id, { stage, reason, operator: '页面' })
    ElMessage.success(`${row.ticket_no} 已调整到「${lbl('stages', stage)}」`)
    await loadMatrix()
  } catch (e) {
    ElMessage.error(e?.message || '调整失败')
    await loadMatrix()
  }
}
async function doBulkStage() {
  if (!bulkStage.value || !bulkSelected.value.length) return
  const items = bulkSelected.value.map(r => ({ team_id: r.team_id, stage: bulkStage.value, reason: bulkReason.value }))
  const out = await batchSetTeamStage(items, '页面')
  ElMessage.success(`批量调整：成功 ${out.changed_count}，跳过 ${out.skipped_count}`)
  bulkStage.value = ''; bulkReason.value = ''
  await loadMatrix()
}
onMounted(loadAll)
</script>

<style scoped>
.pb-page { padding: 4px 2px 24px; }
.pb-alert { margin-bottom: 14px; }
.pb-empty-hint { margin-bottom: 12px; }
.pb-card { margin-bottom: 16px; }
.pb-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.pb-card-title { font-weight: 600; }
.pb-filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pb-cell { display: inline-block; min-width: 32px; padding: 3px 8px; border-radius: var(--radius-sm); background: var(--accent-soft); color: var(--accent); cursor: pointer; font-weight: 600; }
.pb-cell:hover { background: var(--accent); color: var(--surface); }
.pb-footnote { margin-top: 12px; color: var(--text-secondary); font-size: 12px; }
.pb-danger { color: var(--danger); font-weight: 600; }
</style>
