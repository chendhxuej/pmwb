<template>
  <el-drawer
    v-model="visible"
    size="1000px"
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <template #header>
      <div class="mi-head">
        <div>
          <div class="pm-drawer-title">从邮件导入周反馈</div>
          <div class="mi-head-sub">
            收件箱里专题负责人回的「【周反馈请求】」邮件 → 自动比对计划/待办 → 你确认后落库
          </div>
        </div>
        <el-button size="small" :loading="loading" @click="fetchPreview">
          <el-icon><Refresh /></el-icon> 重新解析
        </el-button>
      </div>
    </template>

    <!-- 前置状态 + 区间 -->
    <div class="mi-bar">
      <div class="mi-bar-left">
        <span class="pm-field-label">处理区间</span>
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="→"
          start-placeholder="起"
          end-placeholder="止"
          size="small"
          style="width: 250px"
          @change="fetchPreview"
        />
        <span class="mi-hint">按邮件发送日期，上次收口日 {{ statusInfo.last_run || '—' }}</span>
      </div>
      <div class="mi-bar-right">
        <span class="pm-tag" :class="statusInfo.mail_db_ready ? 'green' : 'red'">
          {{ statusInfo.mail_db_ready ? '邮件中心已连接' : '邮件中心不可读' }}
        </span>
        <span class="mi-hint">区间内 {{ statusInfo.pending_mail_count || 0 }} 封</span>
      </div>
    </div>

    <el-alert
      v-if="statusInfo.mail_db_ready === false"
      type="error"
      :closable="false"
      show-icon
      title="读不到邮件中心的收件箱库"
      :description="statusInfo.mail_db_reason"
      class="mb-12"
    />

    <!-- 空态 -->
    <el-empty
      v-if="!loading && preview && !preview.mails.length"
      description="该区间没有周反馈邮件（先到邮件中心收件箱点「立即同步」）"
    />

    <template v-if="preview && preview.mails.length">
      <!-- 概要 -->
      <div class="mi-summary">
        <div class="mi-stat">
          <div class="mi-stat-num">{{ preview.summary.mail_count }}</div>
          <div class="mi-stat-label">邮件（{{ preview.summary.unmatched_count }} 封未匹配专题）</div>
        </div>
        <div class="mi-stat">
          <div class="mi-stat-num accent">{{ preview.summary.status_count }}</div>
          <div class="mi-stat-label">状态变更</div>
        </div>
        <div class="mi-stat">
          <div class="mi-stat-num">{{ preview.summary.note_count }}</div>
          <div class="mi-stat-label">进展备注</div>
        </div>
        <div class="mi-stat">
          <div class="mi-stat-num">{{ preview.summary.add_count }}</div>
          <div class="mi-stat-label">拟新增</div>
        </div>
        <div class="mi-stat">
          <div class="mi-stat-num warning">{{ preview.summary.doubt_count }}</div>
          <div class="mi-stat-label">存疑待定</div>
        </div>
        <div class="mi-stat">
          <div class="mi-stat-num muted">{{ preview.summary.blocked_count }}</div>
          <div class="mi-stat-label">回退被拦</div>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="mi-tabs">
        <el-tab-pane :label="`状态变更 ${preview.changes.filter((c) => !c.note_only).length}`" name="status">
          <div class="mi-tab-bar">
            <el-button link type="primary" size="small" @click="setAll('changes', 'status', true)">全选可执行</el-button>
            <el-button link size="small" @click="setAll('changes', 'status', false)">全不选</el-button>
            <span class="mi-hint">已是终点的条目无法回退，只保留备注</span>
          </div>
          <el-table :data="statusRows" size="small" border stripe max-height="420">
            <el-table-column width="46" align="center">
              <template #default="{ row }">
                <el-checkbox
                  :model-value="row._checked"
                  :disabled="!row._selectable"
                  @change="(v) => (row._checked = v)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="kw_title" label="专题" min-width="150" show-overflow-tooltip />
            <el-table-column label="类型" width="86">
              <template #default="{ row }">{{ KIND_LABEL[row.kind] || row.kind }}</template>
            </el-table-column>
            <el-table-column prop="sys_title" label="系统条目" min-width="200" show-overflow-tooltip />
            <el-table-column label="变更" width="176">
              <template #default="{ row }">
                <span class="mi-arrow">
                  {{ STATUS_LABEL[row.sys_status] || row.sys_status }} →
                  <b>{{ STATUS_LABEL[row.mail_status] || row.mail_status }}</b>
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="src" label="来源" width="122" />
            <el-table-column label="提示" width="96">
              <template #default="{ row }">
                <span v-if="row.blocked_from" class="pm-tag gray">已是终点</span>
                <span v-else-if="row.hint === 'routine'" class="pm-tag amber">例行任务</span>
                <span v-else-if="row.hint === 'unfinished'" class="pm-tag amber">仍待办</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`进展备注 ${preview.changes.filter((c) => c.note_only).length}`" name="note">
          <div class="mi-tab-bar">
            <el-button link type="primary" size="small" @click="setAll('changes', 'note', true)">全选</el-button>
            <el-button link size="small" @click="setAll('changes', 'note', false)">全不选</el-button>
            <span class="mi-hint">计划类备注追加到任务描述的 [Wxx] 行，待办写入进展说明</span>
          </div>
          <el-table :data="noteRows" size="small" border stripe max-height="420">
            <el-table-column width="46" align="center">
              <template #default="{ row }">
                <el-checkbox :model-value="row._checked" @change="(v) => (row._checked = v)" />
              </template>
            </el-table-column>
            <el-table-column prop="kw_title" label="专题" min-width="150" show-overflow-tooltip />
            <el-table-column label="类型" width="86">
              <template #default="{ row }">{{ KIND_LABEL[row.kind] || row.kind }}</template>
            </el-table-column>
            <el-table-column prop="sys_title" label="系统条目" min-width="190" show-overflow-tooltip />
            <el-table-column prop="note" label="邮件里的进展说明" min-width="240" show-overflow-tooltip />
            <el-table-column prop="src" label="来源" width="122" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`拟新增 ${preview.adds.length}`" name="add">
          <div class="mi-tab-bar">
            <el-button link type="primary" size="small" @click="setAll('adds', '', true)">全选</el-button>
            <el-button link size="small" @click="setAll('adds', '', false)">全不选</el-button>
            <span class="mi-hint">已在系统里的同名条目已自动剔除</span>
          </div>
          <el-table :data="preview.adds" size="small" border stripe max-height="420">
            <el-table-column width="46" align="center">
              <template #default="{ row }">
                <el-checkbox :model-value="row._checked" @change="(v) => (row._checked = v)" />
              </template>
            </el-table-column>
            <el-table-column prop="kw_title" label="专题" min-width="150" show-overflow-tooltip />
            <el-table-column label="类型" width="86">
              <template #default="{ row }">{{ KIND_LABEL[row.kind] || row.kind }}</template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
            <el-table-column prop="assignee" label="责任人" width="96" />
            <el-table-column prop="period" label="周期" width="96" />
            <el-table-column label="状态" width="86">
              <template #default="{ row }">{{ STATUS_LABEL[row.status] || row.status }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`存疑 ${preview.doubts.length}`" name="doubt">
          <div class="mi-tab-bar">
            <span class="mi-hint">相似度 0.6~0.82，系统不敢自动认领；默认「忽略」，需要你指定怎么处理</span>
          </div>
          <el-table :data="preview.doubts" size="small" border stripe max-height="420">
            <el-table-column prop="kw_title" label="专题" min-width="140" show-overflow-tooltip />
            <el-table-column label="类型" width="80">
              <template #default="{ row }">{{ KIND_LABEL[row.kind] || row.kind }}</template>
            </el-table-column>
            <el-table-column prop="sys_title" label="系统条目" min-width="170" show-overflow-tooltip />
            <el-table-column prop="mail_title" label="邮件措辞" min-width="180" show-overflow-tooltip />
            <el-table-column label="相似度" width="76">
              <template #default="{ row }">{{ row.score }}</template>
            </el-table-column>
            <el-table-column label="处理" width="152">
              <template #default="{ row }">
                <el-select v-model="doubtActions[row.key]" size="small" style="width: 132px">
                  <el-option label="忽略" value="skip" />
                  <el-option label="按状态更新" value="update_status" :disabled="!row.mail_status" />
                  <el-option label="新建待办" value="add_todo" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`邮件 ${preview.mails.length}`" name="mail">
          <el-table :data="preview.mails" size="small" border stripe max-height="420">
            <el-table-column prop="date" label="发送日期" width="106" />
            <el-table-column prop="week" label="周次" width="92" />
            <el-table-column prop="kw_title" label="匹配专题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="from" label="发件人" min-width="170" show-overflow-tooltip />
            <el-table-column label="抓到的条目" width="176">
              <template #default="{ row }">
                <span class="mi-counts">
                  月{{ row.counts.month_review }} 周{{ row.counts.week_review }} 下月{{ row.counts.next_month }}
                  下周{{ row.counts.next_week }} 待办{{ row.counts.todos }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="preview.unmatched_mails.length" class="mi-unmatched">
            <div class="mi-unmatched-title">未匹配到专题（不会处理）</div>
            <div v-for="m in preview.unmatched_mails" :key="m.id" class="mi-unmatched-row">
              {{ m.date }} · {{ m.subject }} · {{ m.from }}
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 执行结果 -->
      <div v-if="result" class="mi-result">
        <div class="mi-result-title">导入完成</div>
        <div class="mi-result-body">
          反馈 {{ result.feedback }} 条 · 状态 {{ result.status }} 项 · 备注 {{ result.note }} 项 ·
          待办 {{ result.task }} 条 · 周计划 {{ result.week_plan }} 条 · 月计划 {{ result.month_plan }} 条 ·
          幂等跳过 {{ result.skipped_feedback }} 组
        </div>
        <div v-for="(f, i) in result.failed || []" :key="i" class="mi-result-fail">{{ f }}</div>
      </div>

      <!-- 底部 -->
      <div class="mi-footer">
        <span class="mi-hint">
          已选 {{ checkedCount }} / {{ selectableCount }} 条；落库后状态只进不退
        </span>
        <div class="mi-footer-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" :loading="applying" :disabled="!checkedCount" @click="submit">
            执行导入
          </el-button>
        </div>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as kwApi from '../../api/keywork.js'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'applied'])

const KIND_LABEL = { month_plan: '月计划', week_plan: '周计划', todo: '成员待办' }
const STATUS_LABEL = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  delayed: '已延期',
  cancelled: '已作废',
}

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const applying = ref(false)
const statusInfo = ref({})
const preview = ref(null)
const result = ref(null)
const activeTab = ref('status')
const range = ref([])
const doubtActions = reactive({})

const statusRows = computed(() => (preview.value?.changes || []).filter((c) => !c.note_only))
const noteRows = computed(() => (preview.value?.changes || []).filter((c) => c.note_only))
const selectableCount = computed(() => {
  if (!preview.value) return 0
  const ch = (preview.value.changes || []).filter((c) => c._selectable).length
  return ch + (preview.value.adds || []).length
})
const checkedCount = computed(() => {
  if (!preview.value) return 0
  const ch = (preview.value.changes || []).filter((c) => c._checked).length
  const ad = (preview.value.adds || []).filter((a) => a._checked).length
  return ch + ad
})

function today() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

async function handleOpen() {
  result.value = null
  preview.value = null
  try {
    const st = (await kwApi.getMailImportStatus()) || {}
    statusInfo.value = st
    range.value = [st.last_run || '2026-10-29', today()]
  } catch (e) {
    ElMessage.error('读取导入状态失败：' + (e?.message || e))
    return
  }
  await fetchPreview()
}

async function fetchPreview() {
  const r = range.value || []
  if (!r[0] || !r[1]) return
  loading.value = true
  result.value = null
  try {
    const p = (await kwApi.previewMailImport({ since: r[0], until: r[1] })) || {}
    // 默认勾选：可执行的变更 + 全部拟新增；提示类（例行/仍待办）默认不勾，等人判断
    for (const c of p.changes || []) {
      c._selectable = !c.blocked_from
      c._checked = c._selectable && !c.hint
    }
    for (const a of p.adds || []) a._checked = true
    for (const d of p.doubts || []) if (!doubtActions[d.key]) doubtActions[d.key] = 'skip'
    preview.value = p
    activeTab.value = p.changes?.some((c) => !c.note_only) ? 'status' : 'note'
  } catch (e) {
    ElMessage.error('解析失败：' + (e?.message || e))
    preview.value = null
  } finally {
    loading.value = false
  }
}

function setAll(bucket, scope, value) {
  const list = preview.value?.[bucket] || []
  for (const row of list) {
    if (scope === 'status' && (row.note_only || !row._selectable)) continue
    if (scope === 'note' && !row.note_only) continue
    row._checked = value
  }
}

async function submit() {
  if (!preview.value) return
  const exclude = []
  for (const c of preview.value.changes || []) if (!c._checked) exclude.push(c.key)
  for (const a of preview.value.adds || []) if (!a._checked) exclude.push(a.key)
  applying.value = true
  try {
    const res =
      (await kwApi.applyMailImport({
        since: preview.value.since,
        until: preview.value.until,
        exclude,
        doubt_actions: { ...doubtActions },
        snapshot_id: preview.value.snapshot_id,
      })) || {}
    result.value = res
    const total = (res.status || 0) + (res.note || 0) + (res.task || 0) + (res.week_plan || 0) + (res.month_plan || 0)
    if (total === 0) ElMessage.info('这批邮件没有需要写库的变更（幂等跳过）')
    else ElMessage.success(`已写入 ${total} 项变更`)
    emit('applied')
    await fetchPreview()
  } catch (e) {
    ElMessage.error('导入失败：' + (e?.message || e))
  } finally {
    applying.value = false
  }
}
</script>

<style scoped>
.mi-head { display: flex; align-items: flex-start; justify-content: space-between; width: 100%; padding-right: 24px; }
.mi-head-sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.mi-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 10px 14px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); margin-bottom: 14px; }
.mi-bar-left, .mi-bar-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.mi-hint { font-size: 12px; color: var(--text-muted); }
.mi-summary { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.mi-stat { background: var(--surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 12px; }
.mi-stat-num { font-size: 21px; font-weight: 700; color: var(--text-primary); line-height: 1.2; }
.mi-stat-num.accent { color: var(--accent); }
.mi-stat-num.warning { color: var(--warning); }
.mi-stat-num.muted { color: var(--text-muted); }
.mi-stat-label { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
.mi-tabs { margin-top: 4px; }
.mi-tab-bar { display: flex; align-items: center; gap: 10px; padding: 0 2px 8px; }
.mi-arrow { font-size: 12.5px; color: var(--text-muted); }
.mi-arrow b { color: var(--text-primary); }
.mi-counts { font-size: 12px; color: var(--text-secondary); }
.mi-unmatched { margin-top: 10px; padding: 10px 12px; border: 1px dashed var(--border); border-radius: var(--radius-sm); background: var(--bg-app); }
.mi-unmatched-title { font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
.mi-unmatched-row { font-size: 12px; color: var(--text-muted); line-height: 1.7; }
.mi-result { margin-top: 14px; padding: 12px 14px; border: 1px solid var(--border-subtle); border-left: 3px solid var(--success); border-radius: var(--radius-sm); background: var(--success-soft); }
.mi-result-title { font-size: 13px; font-weight: 600; color: var(--success); margin-bottom: 4px; }
.mi-result-body { font-size: 12.5px; color: var(--text-primary); line-height: 1.7; }
.mi-result-fail { font-size: 12px; color: var(--danger); line-height: 1.6; }
.mi-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 2px 4px; border-top: 1px solid var(--border-subtle); margin-top: 14px; }
.mi-footer-actions { display: flex; gap: 8px; }
.mb-12 { margin-bottom: 12px; }

@media (max-width: 1100px) {
  .mi-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 768px) {
  .mi-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mi-footer { flex-direction: column; align-items: stretch; }
}
</style>
