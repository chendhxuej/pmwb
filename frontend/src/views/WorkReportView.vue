<template>
  <div class="work-report-page">
    <el-container class="wr-layout">
      <el-aside width="184px" class="wr-aside">
        <div class="aside-title">报告分类</div>
        <ul class="cat-list">
          <li
            v-for="c in categoryList"
            :key="c.value"
            :class="['cat-item', { active: activeCategory === c.value }]"
            @click="activeCategory = c.value"
          >
            <span class="cat-name">{{ c.label }}</span>
            <el-badge :value="c.count" :max="999" class="cat-badge" />
          </li>
        </ul>
      </el-aside>

      <el-container class="wr-main">
        <div class="page-header">
          <div class="page-title">AI总结</div>
          <div class="page-actions">
            <el-button type="primary" :icon="EditPen" @click="openGenerate">生成报告</el-button>
            <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
          </div>
        </div>

        <el-table :data="filteredList" v-loading="loading" border stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="report_type_label" label="类型" width="90" />
          <el-table-column label="标题" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="title-link" @click="openDetail(row)">{{ row.title }}</span>
            </template>
          </el-table-column>
          <el-table-column label="统计区间" width="200">
            <template #default="{ row }">
              {{ row.date_start || '-' }} ~ {{ row.date_end || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ row.status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">查看</el-button>
              <el-button link type="danger" @click="doDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-container>
    </el-container>

    <!-- 生成报告弹窗 -->
    <el-dialog v-model="generateVisible" title="生成AI总结" width="460px" :close-on-click-modal="false" :close-on-press-escape="false">
      <el-form v-if="!genLoading" label-width="90px">
        <el-form-item label="报告类型">
          <el-select v-model="genForm.report_type" style="width: 100%">
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
            <el-option label="月报" value="monthly" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始日期">
          <el-date-picker v-model="genForm.date_start" type="date" value-format="YYYY-MM-DD" placeholder="缺省自动推算" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="genForm.date_end" type="date" value-format="YYYY-MM-DD" placeholder="默认今天，可改" style="width: 100%" />
        </el-form-item>
      </el-form>
      <div v-else class="gen-loading-overlay">
        <el-icon class="is-loading" :size="30"><Loading /></el-icon>
        <p>AI 正在生成报告，请稍候…</p>
        <p class="gen-elapsed">已用时 {{ genElapsed }} 秒</p>
      </div>
      <template #footer>
        <el-button :disabled="genLoading" @click="generateVisible = false">取消</el-button>
        <el-button type="primary" :loading="genLoading" @click="doGenerate">生成</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" :size="'70%'" :title="current.title || '报告详情'">
      <template #header>
        <div class="detail-header">
          <span class="detail-title">{{ current.title || '报告详情' }}</span>
          <el-tag :type="statusTagType(current.status)">{{ current.status_label }}</el-tag>
          <el-tag v-if="current.obsidian_path" type="success" class="path-tag">
            <el-icon><FolderChecked /></el-icon>
            <span class="path-text" :title="current.obsidian_path">{{ current.obsidian_path }}</span>
            <el-icon class="copy-icon" @click="copyPath"><CopyDocument /></el-icon>
          </el-tag>
        </div>
      </template>

      <div class="detail-body">
        <el-alert
          v-if="showRuleBanner"
          type="warning"
          :closable="false"
          show-icon
          class="rule-banner"
        >
          <template #title>本次未使用大模型（规则模板版，非 AI 润色）</template>
          <div class="rule-banner-body">
            <span>{{ current.gen_notice || '所有已启用的大模型均不可用，已按规则模板生成，内容仍可使用。' }}</span>
            <div class="rule-banner-actions">
              <el-button size="small" type="primary" @click="goManage">前往大模型管理</el-button>
              <el-button size="small" @click="openGenerate">重试生成</el-button>
            </div>
          </div>
        </el-alert>
        <div v-if="!editing" class="wr-report">
          <MarkdownRender :content="current.content || ''" />
        </div>
        <el-input v-else type="textarea" v-model="editContent" :rows="26" placeholder="可手工编辑报告内容" />
      </div>

      <template #footer>
        <div class="detail-footer">
          <el-button v-if="!editing" type="primary" :icon="Edit" @click="startEdit">编辑</el-button>
          <template v-else>
            <el-button :icon="Check" type="success" @click="saveEdit">保存</el-button>
            <el-button @click="editing = false">取消</el-button>
          </template>
          <el-button v-if="current.status === 'draft'" type="warning" :icon="Stamp" :loading="finalizeLoading" @click="doFinalize">定稿</el-button>
          <el-button type="primary" :icon="Message" @click="openEmail">邮件发送</el-button>
          <el-button type="danger" :icon="Delete" @click="doDelete(current)">删除</el-button>
        </div>
      </template>
    </el-drawer>

    <MailComposeDialog
      v-model="mailDialogVisible"
      title="发送工作总结邮件"
      scene="work_report"
      :default-to="mailDialogTo"
      :default-cc="mailDialogCc"
      :default-subject="mailDialogSubject"
      :default-body="mailDialogBody"
      value-key="email"
      :custom-send="handleSendMail"
      @success="handleMailSuccess"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EditPen, Edit, Check, Message, Delete, Stamp, FolderChecked, CopyDocument, Refresh, Loading } from '@element-plus/icons-vue'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import { formatDateTime } from '@/utils/format'
import {
  listWorkReports, getWorkReport, generateWorkReport,
  updateWorkReport, deleteWorkReport, finalizeWorkReport, sendWorkReport,
} from '@/api/workReport'

const list = ref([])
const loading = ref(false)

// 左侧栏分类（含数量徽标）
const activeCategory = ref('all')
const categoryList = computed(() => {
  const counts = { all: list.value.length, daily: 0, weekly: 0, monthly: 0, custom: 0 }
  for (const r of list.value) counts[r.report_type] = (counts[r.report_type] || 0) + 1
  return [
    { label: '全部', value: 'all', count: counts.all },
    { label: '日报', value: 'daily', count: counts.daily },
    { label: '周报', value: 'weekly', count: counts.weekly },
    { label: '月报', value: 'monthly', count: counts.monthly },
    { label: '自定义', value: 'custom', count: counts.custom },
  ]
})
const filteredList = computed(() =>
  activeCategory.value === 'all'
    ? list.value
    : list.value.filter(r => r.report_type === activeCategory.value)
)
const generateVisible = ref(false)
const genLoading = ref(false)
const genElapsed = ref(0)
let _genTimer = null
function _startGenTimer() {
  genElapsed.value = 0
  _genTimer = setInterval(() => { genElapsed.value++ }, 1000)
}
function _stopGenTimer() {
  if (_genTimer) { clearInterval(_genTimer); _genTimer = null }
}
const genForm = reactive({ report_type: 'daily', date_start: '', date_end: '' })

function todayStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
function shiftDays(n) {
  const d = new Date()
  d.setDate(d.getDate() + n)
  const p = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
function applyDefaultDates(type) {
  genForm.date_end = todayStr()
  if (type === 'weekly' || type === 'custom') genForm.date_start = shiftDays(-6)
  else if (type === 'monthly') genForm.date_start = shiftDays(1 - new Date().getDate())
  else genForm.date_start = todayStr()
}
watch(() => genForm.report_type, (t) => applyDefaultDates(t))

const detailVisible = ref(false)
const current = ref({})
const router = useRouter()

// 规则模板版横幅：仅当本次确实未用大模型且有说明（gen_notice）时提示，避免历史报告误弹
const showRuleBanner = computed(() => current.value && current.value.gen_used_llm === 0 && !!current.value.gen_notice)
function goManage() {
  router.push('/llm-provider')
}
const editing = ref(false)
const editContent = ref('')
const finalizeLoading = ref(false)

const mailDialogVisible = ref(false)
const mailDialogTo = ref([])
const mailDialogCc = ref([])
const mailDialogSubject = ref('')
const mailDialogBody = ref('')

async function handleSendMail(payload) {
  // payload 可能包含 scene/variables 等额外字段，后端 SendRequest 只接受 to/cc/subject/body
  const data = await sendWorkReport(current.value.id, {
    to: payload.to || [],
    cc: payload.cc || [],
    subject: payload.subject || '',
    body: payload.body || payload.variables?.body || '',
  })
  return { success: true, data }
}

function statusTagType(status) {
  if (status === 'sent') return 'success'
  if (status === 'finalized') return 'warning'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    list.value = await listWorkReports()
  } catch (e) {
    ElMessage.error('加载报告列表失败')
  } finally {
    loading.value = false
  }
}

function openGenerate() {
  genForm.report_type = 'daily'
  applyDefaultDates('daily')
  generateVisible.value = true
}

async function doGenerate() {
  genLoading.value = true
  _startGenTimer()
  try {
    const r = await generateWorkReport({ ...genForm })
    if (r.used_llm) {
      ElMessage.success(`已生成（${r.provider_name || 'AI'} 润色）`)
    } else {
      ElMessage.warning('大模型不可用，已生成规则模板版（详见报告顶部提示）')
    }
    generateVisible.value = false
    await load()
    openDetail(r)
  } catch (e) {
    ElMessage.error('生成失败')
  } finally {
    _stopGenTimer()
    genLoading.value = false
  }
}

async function openDetail(row) {
  try {
    const r = await getWorkReport(row.id)
    current.value = r
    editing.value = false
    editContent.value = r.content || ''
    detailVisible.value = true
  } catch (e) {
    ElMessage.error('打开详情失败')
  }
}

function startEdit() {
  editContent.value = current.value.content || ''
  editing.value = true
}

async function saveEdit() {
  try {
    const r = await updateWorkReport(current.value.id, { content: editContent.value })
    current.value = r
    editing.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function doFinalize() {
  try {
    await ElMessageBox.confirm('定稿后将自动归档到 Obsidian 知识库，且不可再次编辑/定稿。确认定稿？', '定稿确认', { type: 'warning' })
  } catch {
    return
  }
  finalizeLoading.value = true
  try {
    const r = await finalizeWorkReport(current.value.id)
    current.value = r
    ElMessage.success('已定稿并归档')
    await load()
  } catch (e) {
    ElMessage.error('定稿失败')
  } finally {
    finalizeLoading.value = false
  }
}

async function doDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除报告「${row.title || row.id}」？此操作不可恢复。`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteWorkReport(row.id)
    ElMessage.success('已删除')
    if (detailVisible.value && current.value.id === row.id) detailVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

function openEmail() {
  mailDialogTo.value = (current.value.recipient || '').split(',').map(s => s.trim()).filter(Boolean)
  mailDialogCc.value = (current.value.cc || '').split(',').map(s => s.trim()).filter(Boolean)
  mailDialogSubject.value = current.value.title || ''
  mailDialogBody.value = current.value.content || ''
  mailDialogVisible.value = true
}

async function handleMailSuccess(res) {
  current.value = res?.data || current.value
  await load()
}

async function copyPath() {
  try {
    await navigator.clipboard.writeText(current.value.obsidian_path || '')
    ElMessage.success('已复制归档路径')
  } catch {
    ElMessage.info(current.value.obsidian_path || '')
  }
}

onMounted(load)
</script>

<style scoped>
.work-report-page { padding: 16px; }
.wr-layout { min-height: calc(100vh - 120px); }
.wr-aside {
  background: var(--el-bg-color-page, #f5f7fa);
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
  padding: 12px 8px;
}
.aside-title { font-size: 13px; color: #909399; padding: 4px 8px 10px; letter-spacing: 1px; }
.cat-list { list-style: none; margin: 0; padding: 0; }
.cat-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 12px; border-radius: 6px; cursor: pointer;
  font-size: 14px; color: #303133; margin-bottom: 4px; transition: background .15s;
}
.cat-item:hover { background: rgba(64, 158, 255, .08); }
.cat-item.active { background: var(--el-color-primary, #409eff); color: #fff; }
.cat-item.active .cat-badge :deep(.el-badge__content) { border-color: #fff; color: var(--el-color-primary, #409eff); background: #fff; }
.cat-badge :deep(.el-badge__content) { font-size: 11px; }
.wr-main { padding-left: 16px; flex-direction: column; }
.wr-main .page-header { margin-bottom: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 600; }
.detail-header { display: flex; align-items: center; gap: 10px; }
.detail-title { font-size: 16px; font-weight: 600; }
.path-tag { display: inline-flex; align-items: center; gap: 4px; max-width: 360px; }
.path-text { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.copy-icon { cursor: pointer; }
.detail-body { padding: 4px 8px; }
.rule-banner { margin-bottom: 12px; }
.rule-banner-body { font-size: 13px; line-height: 1.6; }
.rule-banner-actions { margin-top: 10px; display: flex; gap: 8px; }
.detail-footer { display: flex; gap: 8px; flex-wrap: wrap; }
.title-link { color: var(--el-color-primary); cursor: pointer; }
.title-link:hover { text-decoration: underline; }
.gen-loading-overlay { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px 20px; gap: 10px; color: var(--el-text-color-secondary); }
.gen-loading-overlay p { margin: 0; }
.gen-elapsed { font-size: 13px; color: var(--el-color-primary); font-weight: 600; }

/* ---- AI总结报告专属排版层（仅作用于报告 markdown，不影响共用 MarkdownRender 其他场景）---- */
.wr-report { --wr-accent: var(--el-color-primary, #409eff); }
.wr-report :deep(.markdown-body) {
  font-size: 14px;
  line-height: 1.72;
  color: #2b3445;
}
/* 报告主标题：hero 色带 */
.wr-report :deep(.markdown-body > h1:first-child) {
  margin: 0 0 18px;
  padding: 16px 20px;
  font-size: 22px;
  line-height: 1.3;
  color: #fff;
  background: linear-gradient(100deg, var(--wr-accent), color-mix(in srgb, var(--wr-accent) 55%, #ffffff));
  border: none;
  border-radius: 12px;
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.18);
}
/* 一级章节：左侧色条 + 序号徽标观感 */
.wr-report :deep(.markdown-body h2) {
  position: relative;
  margin: 28px 0 12px;
  padding: 6px 0 6px 14px;
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
  border: none;
  border-left: 4px solid var(--wr-accent);
  background: linear-gradient(90deg, color-mix(in srgb, var(--wr-accent) 8%, transparent), transparent 60%);
  border-radius: 0 6px 6px 0;
}
.wr-report :deep(.markdown-body h3) {
  margin: 18px 0 8px;
  padding-left: 10px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid color-mix(in srgb, var(--wr-accent) 60%, #c0c4cc);
}
/* 关键判断 callout 强化 */
.wr-report :deep(.markdown-body blockquote) {
  margin: 14px 0;
  padding: 12px 16px;
  background: #eef5ff;
  border-left: 4px solid var(--wr-accent);
  border-radius: 0 8px 8px 0;
  color: #2b3445;
}
.wr-report :deep(.markdown-body blockquote p) {
  margin: 2px 0;
  font-weight: 500;
}
/* 分布/指标表格：首列加粗、斑马纹、圆角 */
.wr-report :deep(.markdown-body .table-wrap) { border: none; border-radius: 10px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05); }
.wr-report :deep(.markdown-body table) { min-width: 0; border-radius: 10px; overflow: hidden; }
.wr-report :deep(.markdown-body thead th) { background: color-mix(in srgb, var(--wr-accent) 12%, #f5f7fa); }
.wr-report :deep(.markdown-body tbody tr:first-child td:first-child),
.wr-report :deep(.markdown-body tbody tr td:first-child) { font-weight: 600; color: #1f2d3d; }
/* 列表项间距更舒适 */
.wr-report :deep(.markdown-body li) { margin: 6px 0; }
.wr-report :deep(.markdown-body ul) { padding-left: 22px; }

</style>
