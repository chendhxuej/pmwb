<template>
  <div class="mail-records">
    <div class="page-header">
      <div class="page-title">邮件记录</div>
      <div class="page-actions">
        <el-select v-model="limit" size="default" style="width: 120px" @change="loadData">
          <el-option label="最近 50 条" :value="50" />
          <el-option label="最近 100 条" :value="100" />
          <el-option label="最近 200 条" :value="200" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="tableData" border stripe style="width: 100%">
      <el-table-column prop="created_at" label="发送时间" width="180" sortable />
      <el-table-column prop="subject" label="主题" min-width="220" show-overflow-tooltip />
      <el-table-column prop="recipient" label="收件人" width="200" show-overflow-tooltip />
      <el-table-column prop="recipient_name" label="收件人姓名" width="110" />
      <el-table-column prop="req_id" label="需求编号" width="180" show-overflow-tooltip />
      <el-table-column prop="req_name" label="需求名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="email_type" label="类型" width="130" />
      <el-table-column prop="send_status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.send_status === 'success' ? 'success' : 'danger'">
            {{ row.send_status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="showDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="detailVisible" title="邮件详情" width="640px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="发送时间">{{ detail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="主题">{{ detail.subject }}</el-descriptions-item>
        <el-descriptions-item label="收件人">{{ detail.recipient }}</el-descriptions-item>
        <el-descriptions-item label="收件人姓名">{{ detail.recipient_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="需求编号">{{ detail.req_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ detail.email_type }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag size="small" :type="detail.send_status === 'success' ? 'success' : 'danger'">
            {{ detail.send_status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.error_msg" label="错误信息">
          {{ detail.error_msg }}
        </el-descriptions-item>
      </el-descriptions>
      <div class="detail-body">
        <div class="detail-section-title">邮件正文</div>
        <pre class="detail-pre">{{ detail.content || '(无正文)' }}</pre>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getReminderRecordsList } from '@/api/reminder.js'

const loading = ref(false)
const limit = ref(50)
const tableData = ref([])
const detailVisible = ref(false)
const detail = ref({})

async function loadData() {
  loading.value = true
  try {
    const res = await getReminderRecordsList(limit.value)
    tableData.value = res || []
  } catch (err) {
    ElMessage.error(err.message || '获取邮件记录失败')
  } finally {
    loading.value = false
  }
}

function showDetail(row) {
  detail.value = row
  detailVisible.value = true
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.mail-records {
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
.detail-body {
  margin-top: 16px;
}
.detail-section-title {
  font-weight: bold;
  margin-bottom: 8px;
}
.detail-pre {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: monospace;
  font-size: 13px;
  line-height: 1.6;
  max-height: 320px;
  overflow-y: auto;
}
</style>
