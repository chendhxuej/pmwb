<template>
  <div class="complaint-actions">
    <PageHeader title="客诉改进措施台账" :subtitle="subTitle">
      <template #actions>
        <el-button :icon="Promotion" :disabled="!overdueCnt" @click="openUrge">
          督办（{{ overdueCnt }} 项到期/超期）
        </el-button>
        <el-button :icon="CircleCheck" @click="doVerify">结算验证</el-button>
        <el-button type="primary" :icon="Plus" @click="formVisible = true">登记措施</el-button>
      </template>
    </PageHeader>

    <el-table v-loading="loading" :data="rows" size="default" border stripe>
      <el-table-column prop="action_no" label="措施编号" width="158">
        <template #default="{ row }"><b>{{ row.action_no }}</b></template>
      </el-table-column>
      <el-table-column prop="category_l2" label="针对场景" min-width="150" show-overflow-tooltip />
      <el-table-column prop="title" label="措施标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="owner" label="责任人" width="100" show-overflow-tooltip />
      <el-table-column label="要求完成" width="100">
        <template #default="{ row }">
          <span :class="{ 'due-overdue': isOverdue(row) }">{{ row.due_date ? String(row.due_date).slice(0, 10) : '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="基线/目标" width="104" align="center">
        <template #default="{ row }">
          {{ row.baseline_cnt ?? '—' }} / 降{{ row.target_drop_pct ?? 50 }}%
        </template>
      </el-table-column>
      <el-table-column label="上周/降幅" width="104" align="center">
        <template #default="{ row }">
          {{ row.last_week_cnt ?? '—' }} /
          <b :class="dropClass(row.actual_drop_pct)">{{ row.actual_drop_pct != null ? row.actual_drop_pct + '%' : '—' }}</b>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="112" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTone(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="关联工单" width="130">
        <template #default="{ row }">
          <el-link v-if="row.issue_no" type="primary" size="small" @click="goIssue(row)">
            {{ row.issue_no }}
          </el-link>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="196" fixed="right" align="center">
        <template #default="{ row }">
          <el-button
            v-for="t in nextTargets(row.status)"
            :key="t.value"
            size="small"
            :type="t.value === 'effective' ? 'success' : (t.value === 'ineffective' ? 'danger' : 'default')"
            text
            @click="doTransition(row, t)"
          >{{ t.label }}</el-button>
          <el-button v-if="row.status === 'in_progress'" size="small" text type="primary" @click="openGoLive(row)">
            标记生效
          </el-button>
          <el-button size="small" text @click="editAction(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <ActionFormDialog v-model="formVisible" :action="editingRow" @saved="load" />

    <!-- 标记生效 -->
    <el-dialog v-model="goLiveVisible" title="标记措施生效并绑定基线" width="420px">
      <el-form label-width="88px" size="default">
        <el-form-item label="措施">{{ goLiveRow?.action_no }}</el-form-item>
        <el-form-item label="生效日" required>
          <el-date-picker v-model="goLiveDate" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <div class="gl-tip">
        基线 = 生效日前 {{ baselineWeeks }} 周该场景周均单量；进入验证期后按周结算降幅，
        满 {{ verifyWeeks }} 周自动定论（降幅 ≥ 目标 = 有效，否则未达标升级）。
      </div>
      <template #footer>
        <el-button @click="goLiveVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveGoLive">确认</el-button>
      </template>
    </el-dialog>

    <!-- 督办预览/发送 -->
    <el-dialog v-model="urgeVisible" title="客诉措施督办" width="520px">
      <el-alert type="info" :closable="false" show-icon class="urge-tip">
        将向全部到期/超期措施的责任人发送督办邮件。先预览（dry_run 落库验证），确认后才会真发。
      </el-alert>
      <div v-for="r in urgeResults" :key="r.owner" class="urge-line">
        <b>{{ r.owner }}</b>：
        <template v-if="r.skipped"><span class="warn">{{ r.skipped }}</span></template>
        <template v-else>
          {{ r.task_cnt }} 项措施 → {{ r.to }}
          <el-tag :type="r.dry_run ? 'info' : 'success'" size="small">
            {{ r.dry_run ? 'dry_run 已落库' : '已发送' }}
          </el-tag>
        </template>
      </div>
      <template #footer>
        <el-button @click="urgeVisible = false">关闭</el-button>
        <el-button v-if="!urgeDone" :loading="urging" @click="doUrge(false)">预览（dry_run）</el-button>
        <el-button v-if="urgeDone" type="danger" :loading="urging" @click="doUrge(true)">
          确认真发
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, Plus, Promotion } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import ActionFormDialog from './components/ActionFormDialog.vue'
import { complaintApi } from '@/api/complaint'
import { updateTaskStatus } from '@/api/taskCenter'
import { domainStatuses, allowedNext } from '@/constants/statusConfig'

const route = useRoute()
const router = useRouter()
const DOMAIN = 'complaint_action'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const formVisible = ref(false)
const editingRow = ref(null)

const goLiveVisible = ref(false)
const goLiveRow = ref(null)
const goLiveDate = ref('')
const urgeVisible = ref(false)
const urgeResults = ref([])
const urgeDone = ref(false)
const urging = ref(false)

const statusDefs = computed(() => {
  const map = {}
  for (const s of domainStatuses(DOMAIN)) map[s.value] = s
  return map
})

const subTitle = computed(() => {
  const open = rows.value.filter(r => !['effective', 'cancelled'].includes(r.status)).length
  return `共 ${rows.value.length} 项措施（在办 ${open}）｜压降闭环：基线 → 生效 → 周度验证 → 自动定论`
})

const overdueCnt = computed(() =>
  rows.value.filter(r => isOverdue(r) && !['effective', 'cancelled'].includes(r.status)).length
)

function statusLabel(v) { return statusDefs.value[v]?.label || v }
function statusTone(v) {
  const t = statusDefs.value[v]?.tone || 'info'
  return { danger: 'danger', warning: 'warning', primary: 'primary', success: 'success', info: 'info', neutral: 'info' }[t] || 'info'
}
function nextTargets(current) {
  return allowedNext(DOMAIN, current).map(v => ({ value: v, label: statusLabel(v) }))
}
function isOverdue(row) {
  if (!row.due_date) return false
  const d = String(row.due_date).slice(0, 10)
  const today = new Date().toISOString().slice(0, 10)
  return d < today
}
function dropClass(v) {
  if (v == null) return ''
  return v >= 50 ? 'drop-ok' : (v > 0 ? 'drop-part' : 'drop-bad')
}
function goIssue(row) {
  router.push({ path: '/operation/overview', query: { issueNo: row.issue_no } })
}

async function load() {
  loading.value = true
  try {
    rows.value = await complaintApi.listActions()
    // 深链定位：?action_no=CACT-xxx → 高亮滚动（简单处理：过滤或提示）
    const no = route.query.action_no
    if (no) {
      const hit = rows.value.find(r => r.action_no === no)
      if (hit) ElMessage.info(`已定位措施 ${no}`)
    }
  } catch (e) {
    rows.value = []
  } finally {
    loading.value = false
  }
}

function editAction(row) {
  editingRow.value = row
  formVisible.value = true
}

async function doTransition(row, t) {
  const extra = {}
  if ((t.value === 'verifying' || t.value === 'in_progress') && !row.owner) {
    ElMessage.warning('该状态需先填写责任人（编辑措施补充）')
    return
  }
  if (t.value === 'verifying' && !row.go_live_date) {
    openGoLive(row)
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认将 ${row.action_no} 置为「${t.label}」？`,
      '状态流转',
      { type: 'warning' }
    )
  } catch (e) { return }
  try {
    await updateTaskStatus('complaint_action', row.action_no, t.value, extra)
    ElMessage.success(`已置为「${t.label}」`)
    load()
  } catch (e) { /* request 已提示 */ }
}

function openGoLive(row) {
  goLiveRow.value = row
  goLiveDate.value = new Date().toISOString().slice(0, 10)
  goLiveVisible.value = true
}

async function saveGoLive() {
  if (!goLiveDate.value) {
    ElMessage.warning('请选择生效日')
    return
  }
  saving.value = true
  try {
    await complaintApi.goLive(goLiveRow.value.action_no, goLiveDate.value)
    ElMessage.success(`${goLiveRow.value.action_no} 已进入验证期（基线已绑定）`)
    goLiveVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

async function doVerify() {
  try {
    const rs = await complaintApi.verifyActions()
    if (!rs || !rs.length) {
      ElMessage.info('无验证中的措施')
      return
    }
    const done = rs.filter(r => r.status === 'effective' || r.status === 'ineffective').length
    ElMessage.success(`结算完成：${rs.length} 项刷新，${done} 项定论`)
    load()
  } catch (e) { /* request 已提示 */ }
}

function openUrge() {
  urgeResults.value = []
  urgeDone.value = false
  urgeVisible.value = true
}

async function doUrge(confirmSend) {
  urging.value = true
  try {
    const data = await complaintApi.urgePreview({ confirm_send: confirmSend })
    if (data.skipped) {
      ElMessage.info(data.skipped)
      urgeVisible.value = false
      return
    }
    urgeResults.value = data.sent || []
    if (confirmSend) {
      ElMessage.success('督办邮件已发送')
      urgeVisible.value = false
    } else {
      urgeDone.value = true
    }
  } catch (e) { /* request 已提示 */ } finally {
    urging.value = false
  }
}

const baselineWeeks = 4
const verifyWeeks = 4

onMounted(load)
</script>

<style scoped>
.complaint-actions {
  display: flex;
  flex-direction: column;
}
.due-overdue {
  color: var(--danger);
  font-weight: 600;
}
.drop-ok {
  color: var(--success);
}
.drop-part {
  color: var(--warning);
}
.drop-bad {
  color: var(--danger);
}
.gl-tip,
.urge-tip {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 6px;
}
.urge-line {
  font-size: 12.5px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}
.urge-line .warn {
  color: var(--warning);
}
</style>
