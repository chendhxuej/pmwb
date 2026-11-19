<template>
  <div class="pb-page">
    <PageHeader title="反馈同步" :subtitle="subtitle">
      <template #actions>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" plain @click="doPull">拉取邮件回执</el-button>
      </template>
    </PageHeader>

    <el-alert type="info" show-icon :closable="false" class="pb-alert">
      <template #title>反馈进得来、落得准、查得到、能联动、可纠正</template>
      <template #default>结构化回执（唯一回执码 + 环节/进度/风险/预计完成日四字段）自动采纳；自由文本<b>只出建议进待核对、绝不自动改状态</b>。同批次冲突原文全留，采纳前值可一键回滚。邮件通道不可达标「待自动补跑」，不转人工判定。</template>
    </el-alert>

    <div class="pm-stat-grid pm-stat-grid--4">
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">待核对反馈</span></div>
        <div class="pm-stat__val is-accent">{{ pending.total || 0 }}<span class="pm-stat__unit">条</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">最久未核对</span></div>
        <div class="pm-stat__val">{{ pending.max_age_days || 0 }}<span class="pm-stat__unit">天</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">解析失败/待补跑</span></div>
        <div class="pm-stat__val">{{ parseFailedCount }}<span class="pm-stat__unit">条</span></div></div>
      <div class="pm-stat"><div class="pm-stat__top"><span class="pm-stat__label">冲突待核对</span></div>
        <div class="pm-stat__val">{{ conflictCount }}<span class="pm-stat__unit">条</span></div></div>
    </div>

    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">四通道录入</span>
          <span class="pb-hint">A 邮件回执（自动） · B 团队批量更新 · C 行内记一笔 · D 代录（电话/微信/会议）</span>
        </div>
      </template>
      <el-form :model="form" label-width="110px" class="pb-form">
        <el-form-item label="通道">
          <el-radio-group v-model="form.channel">
            <el-radio value="batch">团队批量更新</el-radio>
            <el-radio value="inline">行内记一笔</el-radio>
            <el-radio value="proxy">代录</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="工单 ID" required><el-input-number v-model="form.track_id" :min="1" style="width: 180px" /></el-form-item>
        <el-form-item label="团队子行 ID"><el-input-number v-model="form.team_id" :min="0" style="width: 180px" /></el-form-item>
        <el-form-item label="环节">
          <el-select v-model="form.stage" clearable placeholder="不选=仅记录进度" style="width: 200px">
            <el-option v-for="s in meta.stages || []" :key="s.key" :label="s.label" :value="s.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="进度说明"><el-input v-model="form.progress" placeholder="实际进展" style="width: 420px" /></el-form-item>
        <el-form-item label="风险描述"><el-input v-model="form.risk" placeholder="风险说明；影响上线请勾选" style="width: 420px" /></el-form-item>
        <el-form-item label="影响上线"><el-checkbox v-model="form.affect_release">是（触发硬门禁与督办候选）</el-checkbox></el-form-item>
        <el-form-item label="预计完成日"><el-date-picker v-model="form.promise_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item v-if="form.channel === 'proxy'" label="反馈人" required><el-input v-model="form.reporter" style="width: 200px" /></el-form-item>
        <el-form-item label="或自由文本">
          <el-input v-model="form.raw_text" type="textarea" :rows="3" style="width: 520px" placeholder="无回执码/字段不全时，只提取建议，不自动改状态" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doSubmit">提交反馈</el-button>
          <span class="pb-hint">四字段齐全（含风险）才自动采纳；缺一项自动进待核对。</span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">待核对反馈</span>
          <el-select v-model="status" clearable placeholder="全部状态" style="width: 140px" @change="loadPending">
            <el-option label="待核对" value="pending" /><el-option label="冲突" value="conflict" /><el-option label="解析失败" value="parse_failed" />
          </el-select>
        </div>
      </template>
      <el-table :data="pending.items || []" size="small" max-height="420">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="track_id" label="工单" width="90" />
        <el-table-column prop="channel" label="通道" width="100" />
        <el-table-column prop="adopt_status" label="状态" width="110">
          <template #default="{ row }"><el-tag size="small" :type="statusTag(row.adopt_status)" effect="light">{{ statusLabel(row.adopt_status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="raw_text" label="原文（全量留存）" min-width="280" show-overflow-tooltip />
        <el-table-column label="建议" min-width="220">
          <template #default="{ row }"><span class="pb-hint">{{ suggestText(row) }}</span></template>
        </el-table-column>
        <el-table-column prop="sender" label="来源人" width="120" />
        <el-table-column prop="age_days" label="停留天数" width="100" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="doReview(row, 'adopt')">采纳</el-button>
            <el-button link @click="doReview(row, 'reject')">驳回</el-button>
            <el-button link type="danger" @click="doRollback(row)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/Common/PageHeader.vue'
import {
  getPaibanMeta, submitPbFeedback, pullMailFeedback, listPendingFeedback,
  reviewPbFeedback, rollbackPbFeedback,
} from '@/api/paiban.js'

const meta = ref({}), pending = ref({ items: [] }), status = ref(''), loading = ref(false)
const form = reactive({ channel: 'inline', track_id: null, team_id: null, stage: '', progress: '', risk: '', affect_release: false, promise_date: '', reporter: '', raw_text: '' })

const subtitle = computed(() => '邮件回执 / 批量更新 / 行内记一笔 / 代录，统一留痕可回滚')
const parseFailedCount = computed(() => (pending.value.items || []).filter(x => x.adopt_status === 'parse_failed').length)
const conflictCount = computed(() => (pending.value.items || []).filter(x => x.adopt_status === 'conflict').length)
const statusLabel = key => ({ pending: '待核对', conflict: '冲突', parse_failed: '解析失败' }[key] || key)
const statusTag = key => ({ pending: 'warning', conflict: 'danger', parse_failed: 'info' }[key] || 'info')
const suggestText = row => {
  const s = row.suggested || row.parsed || {}
  return [s.stage ? `环节=${s.stage}` : '', s.progress ? `进度=${s.progress.slice(0, 40)}` : '',
          s.risk ? `风险=${s.risk.slice(0, 30)}` : '', s.promise_date ? `完成日=${s.promise_date}` : ''].filter(Boolean).join(' / ')
}

async function loadAll() {
  loading.value = true
  try {
    meta.value = await getPaibanMeta()
    await loadPending()
  } finally { loading.value = false }
}
async function loadPending() { pending.value = await listPendingFeedback({ status: status.value }) }
async function doSubmit() {
  if (!form.track_id) { ElMessage.warning('请填写工单 ID'); return }
  const out = await submitPbFeedback({ ...form, operator: '页面' })
  ElMessage.success(out.adopt_status === 'auto' ? '结构化反馈已自动采纳' : '已记录为待核对，未改任何状态')
  await loadPending()
}
async function doPull() {
  const out = await pullMailFeedback({})
  if (!out.ok) { ElMessage.warning(`邮件通道不可用：${out.reason}；已标待自动补跑，不转人工判定`); return }
  ElMessage.success(`扫描 ${out.scanned} 封，新增 ${out.created?.length || 0} 条，重复跳过 ${out.duplicate} 条`)
  await loadPending()
}
async function doReview(row, action) {
  const text = window.prompt(action === 'adopt' ? '采纳说明' : '驳回原因', '')
  if (action === 'adopt' || text) {
    await reviewPbFeedback(row.id, { action, reviewer: '页面', review_note: text || '' })
    ElMessage.success('核对完成')
    await loadPending()
  }
}
async function doRollback(row) {
  await rollbackPbFeedback(row.id, { operator: '页面' })
  ElMessage.success('已回滚到采纳前值，原文与留痕保留')
  await loadPending()
}
onMounted(loadAll)
</script>

<style scoped>
.pb-page { padding: 4px 2px 24px; }
.pb-alert { margin-bottom: 14px; }
.pb-card { margin-bottom: 16px; }
.pb-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.pb-card-title { font-weight: 600; }
.pb-form { padding-top: 6px; }
.pb-hint { color: var(--text-muted); font-size: 12px; }
</style>
