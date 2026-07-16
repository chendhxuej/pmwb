<template>
  <div class="reminder-center">
    <div class="page-header">
      <div class="page-title">催办中心</div>
      <div class="page-actions">
        <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <!-- 概览卡片 -->
    <div class="stats-row">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-value">{{ summary.total }}</div>
        <div class="stat-label">待催办需求</div>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <div class="stat-value">{{ summary.saCount }}</div>
        <div class="stat-label">涉及 SA</div>
      </el-card>
      <el-card shadow="hover" class="stat-card stat-warning">
        <div class="stat-value">{{ summary.unassigned }}</div>
        <div class="stat-label">未分配 SA</div>
      </el-card>
    </div>

    <div class="table-hint">
      按 SA 分组的待催办需求（is_involved=1 且工作量未登记）。点击「批量催办」向该 SA 群发一封汇总邮件；
      点击单行「催办」则单独发送该需求。收件人邮箱按姓名从统一邮件中心通讯录自动解析。
    </div>

    <el-empty v-if="!loading && !groups.length" description="暂无待催办需求" />

    <el-card
      v-for="group in groups"
      :key="group.sa_name"
      shadow="never"
      class="sa-card"
    >
      <template #header>
        <div class="sa-header">
          <div class="sa-title">
            <el-icon><User /></el-icon>
            <span class="sa-name">{{ group.sa_name }}</span>
            <el-tag size="small" type="info">{{ group.count }} 个需求</el-tag>
          </div>
          <el-button
            type="warning"
            size="small"
            :disabled="group.sa_name === '未分配'"
            @click="openBatch(group)"
          >
            批量催办
          </el-button>
        </div>
      </template>

      <el-table :data="group.items" size="small" border stripe>
        <el-table-column prop="req_id" label="需求编号" width="200" show-overflow-tooltip />
        <el-table-column prop="req_name" label="需求名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="system_name" label="负责系统" width="140" show-overflow-tooltip />
        <el-table-column prop="proposer" label="提出人" width="90" />
        <el-table-column label="操作" width="80" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="warning" size="small" @click="openSingle(row)">催办</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 催办邮件对话框 -->
    <el-dialog v-model="dialogVisible" title="发送催办邮件" width="600px">
      <el-form :model="reminderForm" label-width="100px">
        <el-form-item label="需求编号">
          <el-input v-model="reminderForm.req_id" disabled />
        </el-form-item>
        <el-form-item label="收件人">
          <el-input v-model="reminderForm.to" placeholder="多个收件人用逗号分隔" />
          <div class="form-hint">收件人邮箱按姓名自动从邮件中心通讯录解析；若未匹配到，请手动填写真实邮箱。</div>
        </el-form-item>
        <el-form-item label="抄送">
          <el-input v-model="reminderForm.cc" placeholder="多个抄送人用逗号分隔" />
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="reminderForm.subject" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="reminderForm.body" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="reminderLoading" @click="handleSend">发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { User } from '@element-plus/icons-vue'
import { getPendingReminders, resolveContacts, sendReminder } from '@/api/reminder.js'

const loading = ref(false)
const groups = ref([])
const dialogVisible = ref(false)
const reminderLoading = ref(false)
const reminderForm = reactive({
  req_id: '', req_name: '', to: '', cc: '', recipient_name: '', subject: '', body: '',
})

const summary = computed(() => {
  const total = groups.value.reduce((s, g) => s + g.count, 0)
  const saCount = groups.value.filter((g) => g.sa_name !== '未分配').length
  const unassigned = (groups.value.find((g) => g.sa_name === '未分配') || {}).count || 0
  return { total, saCount, unassigned }
})

async function loadData() {
  loading.value = true
  try {
    const res = await getPendingReminders()
    groups.value = res || []
  } catch (err) {
    ElMessage.error(err.message || '获取待催办列表失败')
  } finally {
    loading.value = false
  }
}

// 严格邮箱正则（ASCII 本地名），与后端校验保持一致
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

function validateEmailsField(raw) {
  if (!raw) return []
  return raw
    .split(/[,;，；\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((s) => !EMAIL_RE.test(s))
}

async function prefillRecipients(names) {
  reminderForm.recipient_name = (names || []).join(', ')
  reminderForm.to = ''
  const list = (names || []).filter(Boolean)
  if (!list.length) return
  try {
    const map = (await resolveContacts(list)) || {}
    const resolved = []
    const missing = []
    for (const n of list) {
      const email = map[n] || map[n.trim()]
      if (email) resolved.push(email)
      else missing.push(n)
    }
    reminderForm.to = resolved.join(', ')
    if (missing.length) {
      ElMessage.warning(
        `以下 SA 未在邮件中心通讯录找到邮箱，请手动填写真实邮箱或先在邮件中心添加：${missing.join('、')}`
      )
    }
  } catch (e) {
    console.error('解析收件人邮箱失败', e)
  }
}

function buildBatchBody(saName, items) {
  const lines = [
    `${saName}（相关团队）：`,
    ``,
    `你们负责的以下 ${items.length} 个需求现在到前期评估环节了，麻烦尽快把每个需求的①前期评估（可行性、范围、依赖）②工作量初评（大概多少人天）和预计完成时间反馈给我：`,
    ``,
  ]
  items.forEach((it, i) => {
    lines.push(`${i + 1}. [${it.req_id}] ${it.req_name}`)
    lines.push(`   系统：${it.system_name || '未指定'} | 提出人：${it.proposer || '未知'}`)
  })
  lines.push(
    ``,
    `收到后尽快回我哈，辛苦了！`,
    ``,
    `——产品经理工作台（PMWB）`,
  )
  return lines.join('\n')
}

function buildSingleBody(item) {
  return [
    `${item.sa_name || '相关团队'}（${item.system_name || '相关'}团队）：`,
    ``,
    `你负责的需求现在到前期评估环节了，麻烦尽快把下面两件事搞定，然后反馈给我：`,
    `1. 需求前期评估（可行性、范围、依赖这些）；`,
    `2. 工作量初评（大概要多少人天）和预计完成时间。`,
    ``,
    `需求信息：`,
    `需求编号：${item.req_id || ''}`,
    `需求名称：${item.req_name || ''}`,
    `提出人：${item.proposer || ''}`,
    ...(item.system_name ? [`负责系统：${item.system_name}`] : []),
    ``,
    `收到后尽快回我评估结果哈，辛苦了！`,
    ``,
    `——产品经理工作台（PMWB）`,
  ].join('\n')
}

function openBatch(group) {
  if (group.sa_name === '未分配') {
    ElMessage.warning('该组需求未分配 SA，无法自动解析收件人，请到需求管理指定 SA 后催办。')
    return
  }
  reminderForm.req_id = group.items.map((i) => i.req_id).join('; ')
  reminderForm.req_name = ''
  reminderForm.cc = ''
  reminderForm.subject = `催办：${group.sa_name} 负责的 ${group.count} 个需求评估`
  reminderForm.body = buildBatchBody(group.sa_name, group.items)
  prefillRecipients([group.sa_name])
  dialogVisible.value = true
}

function openSingle(item) {
  reminderForm.req_id = item.req_id
  reminderForm.req_name = item.req_name
  reminderForm.cc = ''
  reminderForm.subject = `催办：${item.req_name || item.req_id}`
  reminderForm.body = buildSingleBody(item)
  prefillRecipients(item.sa_name ? [item.sa_name] : [])
  dialogVisible.value = true
}

async function handleSend() {
  if (!reminderForm.to || !reminderForm.subject) {
    ElMessage.warning('请填写收件人和主题')
    return
  }
  const bad = [...validateEmailsField(reminderForm.to), ...validateEmailsField(reminderForm.cc)]
  if (bad.length) {
    ElMessage.warning(
      `收件人邮箱格式不正确：${bad.join('、')}（请填写真实邮箱，可在邮件中心通讯录按姓名查询）`
    )
    return
  }
  reminderLoading.value = true
  try {
    const res = await sendReminder({
      req_id: reminderForm.req_id,
      req_name: reminderForm.req_name,
      to: reminderForm.to,
      cc: reminderForm.cc,
      recipient_name: reminderForm.recipient_name,
      subject: reminderForm.subject,
      body: reminderForm.body,
      operator: 'pmwb',
    })
    if (res && res.success) {
      ElMessage.success('催办邮件发送成功')
      dialogVisible.value = false
      await loadData()
    } else {
      ElMessage.warning(res?.message || '催办邮件发送失败')
    }
  } catch (err) {
    console.error('催办邮件发送失败', err)
  } finally {
    reminderLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.reminder-center {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
}
.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.stat-card {
  flex: 1;
  min-width: 140px;
  text-align: center;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #409eff;
}
.stat-label {
  font-size: 14px;
  color: #606266;
  margin-top: 8px;
}
.stat-warning .stat-value {
  color: #e6a23c;
}
.table-hint {
  font-size: 13px;
  color: #909399;
  margin: 4px 2px 16px;
  line-height: 1.6;
}
.sa-card {
  margin-bottom: 16px;
}
.sa-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sa-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sa-name {
  font-size: 16px;
  font-weight: 600;
}
.form-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 4px;
}
</style>
