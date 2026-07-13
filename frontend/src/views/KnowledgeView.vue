<template>
  <div class="knowledge-view">
    <h2 class="page-title">知识库</h2>

    <!-- 搜索表单 -->
    <el-card class="search-card" shadow="never">
      <el-form :model="queryForm" inline>
        <el-form-item label="关键字">
          <el-input v-model="queryForm.keyword" placeholder="标题/摘要/编号" clearable />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="queryForm.category" placeholder="全部" clearable @change="handleCategoryChange">
            <el-option
              v-for="item in categoryOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="子分类">
          <el-select v-model="queryForm.sub_category" placeholder="全部" clearable>
            <el-option
              v-for="item in subCategoryOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="queryForm.tag" placeholder="全部" clearable>
            <el-option
              v-for="item in tagOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">新增知识条目</el-button>
      <el-button @click="loadMeta">刷新分类标签</el-button>
    </div>

    <!-- 知识卡片列表 -->
    <div v-loading="loading" class="knowledge-list">
      <el-row :gutter="16">
        <el-col
          v-for="item in tableData"
          :key="item.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="8"
          class="knowledge-card-col"
        >
          <el-card shadow="hover" class="knowledge-card">
            <div class="card-header">
              <el-tag size="small">{{ item.category }}</el-tag>
              <span class="card-id">{{ item.item_id }}</span>
            </div>
            <h3 class="card-title" @click="handleViewContent(item)">{{ item.title }}</h3>
            <p class="card-summary">{{ item.summary || '暂无摘要' }}</p>
            <div class="card-tags">
              <el-tag v-for="tag in splitTags(item.tags)" :key="tag" size="small" type="info" class="tag">
                {{ tag }}
              </el-tag>
            </div>
            <div class="card-footer">
              <span class="update-time">{{ formatDateTime(item.updated_at) }}</span>
              <div class="card-actions">
                <el-button link type="primary" @click="handleViewContent(item)">查看</el-button>
                <el-button link type="primary" @click="handleEdit(item)">编辑</el-button>
                <el-button link type="danger" @click="handleDelete(item)">删除</el-button>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.page_size"
      :total="pagination.total"
      :page-sizes="[12, 24, 48]"
      layout="total, sizes, prev, pager, next, jumper"
      class="pagination"
      @size-change="loadData"
      @current-change="loadData"
    />

    <!-- 新增/编辑元数据弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑知识条目' : '新增知识条目'"
      width="650px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-form-item label="条目编号" prop="item_id">
          <el-input v-model="form.item_id" placeholder="如 KNOW-20260713-001" />
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="知识条目标题" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" placeholder="请选择" style="width: 100%" allow-create filterable>
            <el-option
              v-for="item in categoryOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="子分类" prop="sub_category">
          <el-input v-model="form.sub_category" placeholder="子分类" />
        </el-form-item>
        <el-form-item label="标签" prop="tags">
          <el-input v-model="form.tags" placeholder="标签，用逗号分隔" />
        </el-form-item>
        <el-form-item label="来源类型" prop="source_type">
          <el-select v-model="form.source_type" placeholder="请选择" style="width: 100%" clearable>
            <el-option label="需求" value="requirement" />
            <el-option label="工单" value="ticket" />
            <el-option label="运营问题" value="operation" />
            <el-option label="会议" value="meeting" />
            <el-option label="手动创建" value="manual" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源ID" prop="source_id">
          <el-input v-model="form.source_id" placeholder="关联对象编号" />
        </el-form-item>
        <el-form-item label="摘要" prop="summary">
          <el-input v-model="form.summary" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存并编辑正文</el-button>
      </template>
    </el-dialog>

    <!-- 内容编辑/查看弹窗 -->
    <el-dialog
      v-model="contentDialogVisible"
      :title="currentContent.title"
      width="900px"
      destroy-on-close
    >
      <el-input
        v-model="currentContent.content"
        type="textarea"
        :rows="20"
        placeholder="在此编辑 Markdown 正文..."
      />
      <template #footer>
        <el-button @click="contentDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveContent">保存内容</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeApi } from '@/api/knowledge'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const dialogVisible = ref(false)
const contentDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const tableData = ref([])

const pagination = reactive({
  page: 1,
  page_size: 12,
  total: 0,
})

const queryForm = reactive({
  keyword: '',
  category: '',
  sub_category: '',
  tag: '',
})

const categoryOptions = ref([])
const subCategoryOptions = ref([])
const tagOptions = ref([])

const defaultForm = {
  item_id: '',
  title: '',
  category: '',
  sub_category: '',
  tags: '',
  obsidian_path: '',
  source_type: '',
  source_id: '',
  summary: '',
  content: '',
}

const form = reactive({ ...defaultForm })

const rules = {
  item_id: [{ required: true, message: '请输入条目编号', trigger: 'blur' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  obsidian_path: [{ required: true, message: '请填写 Obsidian 路径', trigger: 'blur' }],
}

const currentContent = reactive({
  id: null,
  item_id: '',
  title: '',
  obsidian_path: '',
  content: '',
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await knowledgeApi.listItems({
      ...queryForm,
      page: pagination.page,
      page_size: pagination.page_size,
    })
    tableData.value = res.items || []
    pagination.total = res.total || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadMeta = async () => {
  try {
    const [categories, tags] = await Promise.all([
      knowledgeApi.getCategories(),
      knowledgeApi.getTags(),
    ])
    categoryOptions.value = categories || []
    tagOptions.value = tags || []
  } catch (error) {
    ElMessage.error('加载元数据失败')
  }
}

const handleCategoryChange = async (val) => {
  if (val) {
    try {
      const res = await knowledgeApi.getSubCategories(val)
      subCategoryOptions.value = res || []
    } catch (error) {
      subCategoryOptions.value = []
    }
  } else {
    subCategoryOptions.value = []
  }
  queryForm.sub_category = ''
}

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const handleReset = () => {
  queryForm.keyword = ''
  queryForm.category = ''
  queryForm.sub_category = ''
  queryForm.tag = ''
  pagination.page = 1
  loadData()
}

const splitTags = (tags) => {
  if (!tags) return []
  return tags.split(',').map((t) => t.trim()).filter(Boolean)
}

const buildObsidianPath = (item) => {
  const category = item.category || '未分类'
  const date = new Date().toISOString().slice(0, 10)
  const safeTitle = item.title.replace(/[\\/:*?"<>|]/g, '_')
  return `知识库/${category}/${date}-${safeTitle}.md`
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(form, {
    ...defaultForm,
    item_id: generateItemId(),
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

const handleViewContent = async (row) => {
  try {
    const res = await knowledgeApi.getItemContent(row.id)
    Object.assign(currentContent, {
      id: row.id,
      item_id: res.item_id,
      title: res.title,
      obsidian_path: res.obsidian_path,
      content: res.content,
    })
    contentDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载内容失败')
  }
}

const handleSaveContent = async () => {
  try {
    await knowledgeApi.updateItemContent(currentContent.id, currentContent.content)
    ElMessage.success('保存成功')
    contentDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除知识条目「${row.title}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await knowledgeApi.deleteItem(row.id)
    ElMessage.success('删除成功')
    loadData()
  })
}

const handleSubmit = async () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return

    const payload = { ...form }
    if (!payload.obsidian_path) {
      payload.obsidian_path = buildObsidianPath(payload)
    }
    if (!payload.content) {
      payload.content = `# ${payload.title}\n\n${payload.summary || ''}\n`
    }

    try {
      let res
      if (isEdit.value) {
        res = await knowledgeApi.updateItem(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        res = await knowledgeApi.createItem(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadData()
      handleViewContent(res)
    } catch (error) {
      ElMessage.error(error.response?.data?.message || '操作失败')
    }
  })
}

const generateItemId = () => {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `KNOW-${date}-${random}`
}

onMounted(() => {
  loadData()
  loadMeta()
})
</script>

<style scoped>
.knowledge-view {
  padding: 20px;
}

.page-title {
  margin-bottom: 20px;
  font-size: 20px;
  font-weight: 600;
}

.search-card {
  margin-bottom: 16px;
}

.toolbar {
  margin-bottom: 16px;
}

.knowledge-list {
  margin-bottom: 20px;
}

.knowledge-card-col {
  margin-bottom: 16px;
}

.knowledge-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-id {
  font-size: 12px;
  color: #909399;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
  cursor: pointer;
  color: #303133;
}

.card-title:hover {
  color: #409eff;
}

.card-summary {
  font-size: 14px;
  color: #606266;
  line-height: 1.5;
  margin-bottom: 12px;
  min-height: 42px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-tags {
  margin-bottom: 12px;
}

.card-tags .tag {
  margin-right: 8px;
  margin-bottom: 6px;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
  margin-top: auto;
}

.update-time {
  font-size: 12px;
  color: #909399;
}

.pagination {
  justify-content: flex-end;
}
</style>
