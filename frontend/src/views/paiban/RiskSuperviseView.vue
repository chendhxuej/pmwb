<template>
  <div class="pb-page">
    <PageHeader title="风险与督办" :subtitle="subtitle">
      <template #actions>
        <el-select v-model="planId" filterable clearable placeholder="选择版本计划" style="width: 240px" @change="loadAll">
          <el-option v-for="p in plans" :key="p.id" :label="p.version_no" :value="p.id" />
        </el-select>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <el-alert type="warning" show-icon :closable="false" class="pb-alert">
      <template #title>上线硬门禁 & 督办安全护栏</template>
      <template #default>任一「影响本版上线且未消除」风险存在时，禁止登记「已上线」。督办按团队×类型一键圈定，逐单带唯一回执码；自测一律 dry_run，真发须点击确认发送（confirm_send=true），24h 冷却与 5 类例外逐单可见。</template>
    </el-alert>

    <div class="pm-stat-grid pm-stat-grid--4">
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">未消除风险</span></div>
        <div class="pm-stat__val is-accent">{{ risks.total || 0 }}<span class="pm-stat__unit">条</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">硬门禁风险</span></div>
        <div class="pm-stat__val">{{ risks.blocking_count || 0 }}<span class="pm-stat__unit">条</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">督办批次</span></div>
        <div class="pm-stat__val">{{ batches.total || 0 }}<span class="pm-stat__unit">批</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">回执超时批次</span></div>
        <div class="pm-stat__val">{{ overdueBatches }}<span class="pm-stat__unit">批</span></div></div>
    </div>

    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">风险事件（按工单维度）</span>
          <div class="pb-filters">
            <el-checkbox v-model="onlyBlocking" @change="loadRisks">仅看硬门禁</el-checkbox>
            <el-button type="primary" plain @click="openRiskCreate">手工登记风险</el-button>
          </div>
        </div>
      </template>
      <el-table :data="risks.items || []" size="small" max-height="360">
        <el-table-column prop="ticket_no" label="工单" width="130">
          <template #default="{ row }">{{ row.description?.ticket_no || ('#' + row.track_id) }}</template>
        </el-table-column>
        <el-table-column prop="risk_type_label" label="类型" width="140" />
        <el-table-column prop="description" label="说明（合并更新追加）" min-width="260" show-overflow-tooltip />
        <el-table-column label="影响上线" width="100"><template #default="{ row }"><el-tag :type="row.affect_release ? 'danger' : 'info'" size="small" effect="light">{{ row.affect_release ? '是' : '否' }}</el-tag></template></el-table-column>
        <el-table-column prop="level" label="级别" width="70" />
        <el-table-column label="来源" width="110"><template #default="{ row }">{{ lbl('change_sources', row.source) }}</template></el-table-column>
        <el-table-column prop="status_label" label="状态" width="100" />
        <el-table-column prop="merge_count" label="合并次数" width="90" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="row.status === 'open'" link type="primary" @click="openResolve(row)">消除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pb-footnote">同一（工单，风险类型）存在未消除风险时合并更新、原文追加不覆盖；顺延后风险不重置。</div>
    </el-card>

    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">一键批量督办</span>
          <div class="pb-filters">
            <el-select v-model="previewForm.team_name" filterable clearable placeholder="全部团队" style="width: 170px" @change="loadPreview">
              <el-option v-for="n in teamNames" :key="n" :label="n" :value="n" />
            </el-select>
            <el-select v-model="previewForm.ticket_type" clearable placeholder="全部类型" style="width: 110px" @change="loadPreview">
              <el-option v-for="o in meta.ticket_types || []" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-checkbox v-model="previewForm.ignore_cooldown" @change="loadPreview">忽略冷却</el-checkbox>
            <el-select v-if="previewForm.ignore_cooldown" v-model="previewForm.exception_reason" placeholder="冷却例外原因" style="width: 200px" @change="loadPreview">
              <el-option v-for="o in meta.cooldown_exceptions || []" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-button type="primary" plain @click="loadPreview">圈定对象</el-button>
          </div>
        </div>
      </template>

      <div v-for="g in preview.groups || []" :key="g.team_name + g.ticket_type" class="pb-group">
        <div class="pb-group-head">
          <el-checkbox v-model="chosen[g.team_name + g.ticket_type]">{{ g.team_name }} · {{ g.ticket_type_label }}</el-checkbox>
          <span class="pb-hint">纳入 {{ g.included_count }} · 跳过 {{ g.skipped_count }} · 收件人 {{ g.recipients?.length || 0 }}</span>
          <el-button link type="primary" @click="openMailEdit(g)">预览 / 编辑邮件</el-button>
          <el-tag v-if="editedMails[g.team_name + '|' + g.ticket_type]" type="success" size="small" effect="light">已编辑</el-tag>
        </div>
        <el-table :data="g.items" size="small">
          <el-table-column prop="ticket_no" label="工单号" width="130" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column label="环节" width="110"><template #default="{ row }">{{ lbl('stages', row.stage) }}</template></el-table-column>
          <el-table-column prop="deadline" label="本环节截止" width="120" />
          <el-table-column label="命中规则" min-width="220">
            <template #default="{ row }"><span v-for="r in row.triggers" :key="r.key" class="pb-chip">{{ r.label }}</span></template>
          </el-table-column>
          <el-table-column label="跳过原因" width="180">
            <template #default="{ row }"><span :class="row.skip_reason ? 'pb-warn' : ''">{{ row.skip_reason_label || '—' }}{{ row.cooldown_left_h ? `（剩余 ${row.cooldown_left_h}h）` : '' }}</span></template>
          </el-table-column>
          <el-table-column label="回执码" width="170"><template #default="{ row }"><code>{{ row.receipt_code || '发送时生成' }}</code></template></el-table-column>
        </el-table>
      </div>
      <div v-if="!preview.groups?.length" class="pb-empty">当前筛选下没有命中督办规则的团队×类型分组。</div>

      <div class="pb-send-bar">
        <el-button :disabled="!selectedGroups.length" @click="doSend(true)">预览发送（dry_run）</el-button>
        <el-button type="primary" :disabled="!selectedGroups.length" @click="confirmDialog = true">确认发送（真发）</el-button>
        <span class="pb-footnote">dry_run 不消耗冷却；真发必须页面显式确认。</span>
      </div>
    </el-card>

    <el-card shadow="never" class="pb-card">
      <template #header><span class="pb-card-title">督办批次与回执</span></template>
      <el-table :data="batches.items || []" size="small">
        <el-table-column prop="batch_no" label="批次号" min-width="210" />
        <el-table-column prop="team_name" label="团队" width="150" />
        <el-table-column label="类型" width="80"><template #default="{ row }">{{ lbl('ticket_types', row.ticket_type) }}</template></el-table-column>
        <el-table-column prop="item_count" label="逐单数" width="90" />
        <el-table-column prop="sent_count" label="已发" width="80" />
        <el-table-column prop="skipped_count" label="跳过" width="80" />
        <el-table-column label="模式" width="100"><template #default="{ row }"><el-tag size="small" :type="row.dry_run ? 'info' : 'success'" effect="light">{{ row.dry_run ? 'dry_run' : '实发' }}</el-tag></template></el-table-column>
        <el-table-column prop="receipt_deadline" label="回执截止" width="120" />
        <el-table-column label="回执状态" width="110"><template #default="{ row }">{{ lbl('receipt_statuses', row.receipt_status) }}</template></el-table-column>
        <el-table-column label="操作" width="90"><template #default="{ row }"><el-button link type="primary" @click="openBatch(row.batch_no)">明细</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <!-- 手工登记风险事件：类型闭集来自 meta，同(工单,类型)合并更新不新建 -->
    <el-dialog v-model="riskCreateVisible" title="手工登记风险事件" width="560px" :destroy-on-close="true">
      <el-form label-width="100px" class="pb-form">
        <el-form-item label="关联工单" required>
          <el-select v-model="riskCreate.track_id" filterable placeholder="本版本在跟工单" style="width: 100%">
            <el-option v-for="t in planTracks" :key="t.id" :label="`${t.ticket_no} · ${t.title}`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险类型" required>
          <el-select v-model="riskCreate.risk_type" style="width: 100%">
            <el-option v-for="o in meta.risk_types || []" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="级别">
          <el-select v-model="riskCreate.level" style="width: 100%">
            <el-option v-for="o in meta.risk_levels || []" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险说明" required>
          <el-input v-model="riskCreate.description" type="textarea" :rows="3" placeholder="现象、影响与待处置事项" />
        </el-form-item>
        <el-form-item label="影响本版上线">
          <el-switch v-model="riskCreate.affect_release" :active-value="1" :inactive-value="0" />
          <span class="pb-hint">开启后成为硬门禁：未消除前禁止登记「已上线」</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="riskCreateVisible = false">取消</el-button>
        <el-button type="primary" @click="doRiskCreate">登记风险</el-button>
      </template>
    </el-dialog>

    <!-- 邮件预览/编辑：预览=实发同源，回执码锚点不可删（后端护栏二次校验） -->
    <el-dialog v-model="mailEditVisible" title="预览 / 编辑督办邮件" width="820px" :destroy-on-close="true">
      <el-alert type="info" :closable="false" show-icon class="pb-alert">
        <template #default>
          正文由系统按结构化数据装配，<b>预览即实发内容</b>。可调整称呼与说明，但每单的<b>回执码必须保留</b>（反馈回收唯一锚点，后端会校验），批次号将在发送时替换为真实值。
        </template>
      </el-alert>
      <el-form label-width="70px">
        <el-form-item label="收件人"><span class="pb-hint">{{ (mailEdit.recipients || []).join('、') || '（收件人解析失败，将跳过该组）' }}</span></el-form-item>
        <el-form-item label="主题">
          <el-input v-model="mailEdit.subject" />
        </el-form-item>
        <el-form-item label="正文">
          <el-radio-group v-model="mailEdit.mode" size="small" class="pb-mail-mode">
            <el-radio-button value="visual">可视化</el-radio-button>
            <el-radio-button value="html">HTML 源码</el-radio-button>
          </el-radio-group>
          <div v-if="mailEdit.mode === 'visual'" class="pb-mail-preview" v-html="mailEdit.body_html"></div>
          <el-input v-else v-model="mailEdit.body_html" type="textarea" :rows="12" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetMailEdit">还原系统正文</el-button>
        <el-button @click="mailEditVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMailEdit">保存修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="confirmDialog" title="确认真发督办邮件" width="520px">
      <el-alert type="error" :closable="false" show-icon class="pb-alert">
        <template #default>将向所选团队真实发送 {{ selectedGroups.length }} 个批次的督办邮件，发送结果逐单留痕并启动 24h 冷却。<b>已编辑的邮件将按编辑内容发送</b>（回执码锚点仍由系统校验）。请确认对象与内容无误。</template>
      </el-alert>
      <template #footer>
        <el-button @click="confirmDialog = false">取消</el-button>
        <el-button type="primary" @click="doSend(false)">确认发送</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="batchVisible" title="批次回执明细" size="55%">
      <template v-if="batchDetail.batch">
        <div class="pb-ticket-meta">回执率 {{ Math.round((batchDetail.receipt_rate || 0) * 100) }}% · 状态 {{ lbl('receipt_statuses', batchDetail.batch.receipt_status) }}</div>
        <el-table :data="batchDetail.items || []" size="small" class="pb-space">
          <el-table-column prop="ticket_no" label="工单号" width="130" />
          <el-table-column prop="receipt_code" label="回执码" min-width="180" />
          <el-table-column label="发送状态" width="110"><template #default="{ row }">{{ lbl('send_statuses', row.send_status) }}</template></el-table-column>
          <el-table-column label="回执状态" width="110"><template #default="{ row }">{{ lbl('receipt_statuses', row.receipt_status) }}</template></el-table-column>
          <el-table-column label="跳过原因" width="150"><template #default="{ row }">{{ row.skip_reason ? lbl('supervise_exclude_rules', row.skip_reason) : '—' }}</template></el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/Common/PageHeader.vue'
import { makeLabeler } from '@/utils/paibanLabels.js'
import {
  getPaibanMeta, listVersionPlans, listPbRisks, resolvePbRisk, previewSupervise,
  sendSupervise, listSuperviseBatches, getSuperviseBatch, createPbRisk, listPbTracks,
} from '@/api/paiban.js'

const meta = ref({}), plans = ref([]), planId = ref(null), loading = ref(false)
const risks = ref({ items: [] }), onlyBlocking = ref(false)
const preview = ref({ groups: [] }), previewForm = reactive({ team_name: '', ticket_type: '', ignore_cooldown: false, exception_reason: '' })
const chosen = reactive({}), batches = ref({ items: [] })
const confirmDialog = ref(false), batchVisible = ref(false), batchDetail = ref({})
const resolveForm = reactive({ risk_id: null, resolution: '' })
const riskCreateVisible = ref(false), planTracks = ref([])
const riskCreate = reactive({ track_id: null, risk_type: 'other', level: 'P2', description: '', affect_release: 0 })
const editedMails = reactive({})   // key=team|ticket_type → {subject, body_html}
const mailEditVisible = ref(false)
const mailEdit = reactive({ key: '', subject: '', body_html: '', recipients: [], mode: 'visual', original: null })
const lbl = makeLabeler(meta)

const subtitle = computed(() => '风险硬门禁 + 团队×类型批量督办 + 回执跟踪')
const teamNames = computed(() => [...new Set((preview.value.groups || []).map(x => x.team_name))])
const selectedGroups = computed(() => (preview.value.groups || []).filter(g => chosen[g.team_name + g.ticket_type]))
const overdueBatches = computed(() => (batches.value.items || []).filter(x => x.receipt_status === 'overdue').length)

async function loadAll() {
  loading.value = true
  try {
    meta.value = await getPaibanMeta()
    const p = await listVersionPlans({ status: 'confirmed', future_only: true })
    plans.value = p.items || []
    if (!planId.value && plans.value.length) planId.value = plans.value[0].id
    await Promise.all([loadRisks(), loadPreview(), loadBatches()])
  } finally { loading.value = false }
}
async function loadRisks() {
  if (!planId.value) return
  risks.value = await listPbRisks({ plan_id: planId.value, only_blocking: onlyBlocking.value })
}
async function loadPreview() {
  if (!planId.value) return
  preview.value = await previewSupervise({ plan_id: planId.value, ...previewForm })
}
async function loadBatches() {
  batches.value = await listSuperviseBatches({ plan_id: planId.value || undefined })
}
function openResolve(row) {
  resolveForm.risk_id = row.id
  const text = window.prompt('填写消除说明', '已处置完成')
  if (text) doResolve(row, text)
}
async function doResolve(row, text) {
  await resolvePbRisk(row.id, { resolution: text, operator: '页面' })
  ElMessage.success('风险已消除')
  await loadAll()
}
async function openRiskCreate() {
  if (!planId.value) { ElMessage.warning('请先选择版本计划'); return }
  Object.assign(riskCreate, { track_id: null, risk_type: 'other', level: 'P2', description: '', affect_release: 0 })
  const out = await listPbTracks({ plan_id: planId.value })
  planTracks.value = out.items || []
  riskCreateVisible.value = true
}
async function doRiskCreate() {
  if (!riskCreate.track_id || !riskCreate.description.trim()) { ElMessage.warning('关联工单与风险说明必填'); return }
  await createPbRisk(riskCreate.track_id, { ...riskCreate, operator: '页面' })
  ElMessage.success('风险已登记')
  riskCreateVisible.value = false
  await loadAll()
}
async function doSend(dryRun) {
  confirmDialog.value = false
  const groups = selectedGroups.value.map(g => ({ team_name: g.team_name, ticket_type: g.ticket_type }))
  // 只带上本次选中分组的编辑正文，且确有改动才传（避免空改动触发回执码校验）
  const edits = {}
  for (const g of selectedGroups.value) {
    const k = g.team_name + '|' + g.ticket_type
    if (editedMails[k]) edits[k] = editedMails[k]
  }
  const out = await sendSupervise({
    plan_id: planId.value, groups, dry_run: dryRun, confirm_send: !dryRun,
    ...previewForm, edited_mails: edits, operator: '页面',
  })
  ElMessage.success(dryRun ? 'dry_run 完成：未真发、未消耗冷却' : `已发送 ${out.results.reduce((n, r) => n + r.sent, 0)} 单`)
  await loadAll()
}
function openMailEdit(g) {
  const key = g.team_name + '|' + g.ticket_type
  const mail = g.mail || {}
  const saved = editedMails[key]
  Object.assign(mailEdit, {
    key, subject: saved?.subject ?? mail.subject ?? '',
    body_html: saved?.body_html ?? mail.body_html ?? '',
    recipients: g.recipients || [], mode: 'visual',
    original: { subject: mail.subject || '', body_html: mail.body_html || '' },
  })
  mailEditVisible.value = true
}
function saveMailEdit() {
  if (!mailEdit.body_html || !mailEdit.body_html.trim()) { ElMessage.warning('正文不能为空'); return }
  editedMails[mailEdit.key] = { subject: mailEdit.subject, body_html: mailEdit.body_html }
  mailEditVisible.value = false
  ElMessage.success('邮件修改已保存，发送时将按此内容发出')
}
function resetMailEdit() {
  if (!mailEdit.original) return
  mailEdit.subject = mailEdit.original.subject
  mailEdit.body_html = mailEdit.original.body_html
  delete editedMails[mailEdit.key]
  ElMessage.info('已还原系统正文')
}
async function openBatch(no) {
  batchDetail.value = await getSuperviseBatch(no)
  batchVisible.value = true
}
onMounted(loadAll)
</script>

<style scoped>
.pb-page { padding: 4px 2px 24px; }
.pb-alert { margin-bottom: 14px; }
.pb-card { margin-bottom: 16px; }
.pb-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.pb-card-title { font-weight: 600; }
.pb-filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pb-group { padding: 12px 0; border-top: 1px solid var(--border-subtle); }
.pb-group-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.pb-chip { display: inline-block; margin: 0 6px 4px 0; padding: 2px 8px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 12px; }
.pb-send-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding-top: 14px; }
.pb-footnote { color: var(--text-secondary); font-size: 12px; }
.pb-hint { color: var(--text-muted); font-size: 12px; }
.pb-warn { color: var(--warning); }
.pb-empty { color: var(--text-muted); font-size: 13px; padding: 22px 0; text-align: center; }
.pb-space { margin-top: 12px; }
.pb-mail-mode { margin-bottom: 8px; }
.pb-mail-preview { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px 16px; background: var(--surface); max-height: 340px; overflow-y: auto; line-height: 1.5; font-size: 13px; }
code { font-family: var(--font-mono); font-size: 12px; }
</style>
