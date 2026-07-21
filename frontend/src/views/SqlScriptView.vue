<template>
  <div class="sql-script-view">
    <!-- 顶部栏 -->
    <div class="ss-topbar">
      <div class="ss-titles">
        <h2 class="ss-title">SQL脚本库</h2>
        <div class="ss-crumb">知识中心 · 业务统计脚本归档</div>
      </div>
      <div class="ss-actions">
        <el-input
          v-model="searchKeyword"
          class="ss-search"
          placeholder="搜索脚本说明 / 编号"
          clearable
          @input="onSearch"
          @clear="onSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select
          v-model="filterCategory"
          class="ss-cat"
          placeholder="全部分类"
          clearable
          @change="loadList"
        >
          <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon><span>新增脚本</span>
        </el-button>
      </div>
    </div>

    <!-- 列表 -->
    <div class="ss-card">
      <el-table
        v-loading="loading"
        :data="pagedItems"
        class="ss-table"
        row-key="id"
        @row-dblclick="openDetail"
      >
        <el-table-column prop="script_no" label="脚本编号" width="170">
          <template #default="{ row }">
            <span class="ss-mono">{{ row.script_no }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="脚本说明" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="ss-title-cell">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.category" size="small" effect="light" type="primary">{{ row.category }}</el-tag>
            <span v-else class="ss-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span class="ss-muted">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无 SQL 脚本，点击「新增脚本」归档第一条" />
        </template>
      </el-table>

      <div class="ss-pager" v-if="filteredItems.length > pageSize">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filteredItems.length"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="page = 1"
        />
      </div>
    </div>

    <!-- 新增 / 编辑 抽屉 -->
    <el-drawer v-model="editVisible" :title="isEdit ? '编辑 SQL 脚本' : '新增 SQL 脚本'" size="580px" direction="rtl" destroy-on-close>
      <el-form ref="editRef" :model="editForm" :rules="editRules" label-width="92px" class="ss-form">
        <el-form-item label="脚本说明" prop="title">
          <el-input v-model="editForm.title" placeholder="如：各业务线活跃用户数统计" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category" placeholder="选择或输入业务线" filterable allow-create default-first-option clearable style="width: 100%">
            <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="editForm.description" type="textarea" :rows="2" placeholder="脚本用途、适用库表等备注" />
        </el-form-item>
        <el-form-item label="SQL" prop="sql_text">
          <el-input
            v-model="editForm.sql_text"
            type="textarea"
            :rows="10"
            class="ss-sql-input"
            placeholder="SELECT ..."
            spellcheck="false"
          />
        </el-form-item>
        <el-form-item label="输出字段样例">
          <div class="ss-fields">
            <div class="ss-field-head">
              <span>字段名</span><span>类型</span><span>说明</span><span></span>
            </div>
            <div v-for="(f, idx) in editForm.output_fields" :key="idx" class="ss-field-row">
              <el-input v-model="f.name" placeholder="字段名" />
              <el-input v-model="f.type" placeholder="类型" />
              <el-input v-model="f.desc" placeholder="说明" />
              <el-button circle size="small" type="danger" plain @click="removeField(idx)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button size="small" plain @click="addField">
              <el-icon><Plus /></el-icon><span>添加字段</span>
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-drawer>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="SQL 脚本详情" size="640px" direction="rtl">
      <div v-loading="detailLoading" class="ss-detail">
        <div class="ss-d-meta">
          <div class="ss-d-row"><span class="ss-d-label">脚本编号</span><span class="ss-mono">{{ detail.script_no }}</span></div>
          <div class="ss-d-row"><span class="ss-d-label">脚本说明</span><span>{{ detail.title }}</span></div>
          <div class="ss-d-row">
            <span class="ss-d-label">分类</span>
            <el-tag v-if="detail.category" size="small" effect="light" type="primary">{{ detail.category }}</el-tag>
            <span v-else class="ss-muted">—</span>
          </div>
          <div class="ss-d-row"><span class="ss-d-label">创建时间</span><span class="ss-muted">{{ formatDate(detail.created_at) }}</span></div>
          <div class="ss-d-row" v-if="detail.description">
            <span class="ss-d-label">补充说明</span><span>{{ detail.description }}</span>
          </div>
        </div>

        <div class="ss-d-section">
          <div class="ss-d-h">SQL<span class="ss-copy" @click="copySql(detail.sql_text)">复制</span></div>
          <pre class="ss-sql">{{ detail.sql_text }}</pre>
        </div>

        <div class="ss-d-section">
          <div class="ss-d-h">输出字段样例<span class="ss-d-count">{{ detail.output_fields?.length || 0 }} 个</span></div>
          <el-table v-if="detail.output_fields && detail.output_fields.length" :data="detail.output_fields" size="small" class="ss-field-table">
            <el-table-column prop="name" label="字段名" min-width="120">
              <template #default="{ row }"><span class="ss-mono">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="120">
              <template #default="{ row }"><span class="ss-muted">{{ row.type || '—' }}</span></template>
            </el-table-column>
            <el-table-column prop="desc" label="说明" min-width="160" show-overflow-tooltip>
              <template #default="{ row }"><span>{{ row.desc || '—' }}</span></template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="未登记输出字段" :image-size="60" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { sqlScriptApi } from '@/api/sqlScript'
import { formatDate } from '@/utils/format'

/* ---------- 状态 ---------- */
const loading = ref(false)
const detailLoading = ref(false)
const saving = ref(false)

const allItems = ref([])
const searchKeyword = ref('')
const filterCategory = ref('')
const categoryOptions = ref([])

const page = ref(1)
const pageSize = ref(20)

const editVisible = ref(false)
const detailVisible = ref(false)
const isEdit = ref(false)
const editRef = ref(null)
const editId = ref(null)
const detail = reactive({})
const detailItem = ref(null)

const editForm = reactive({
  title: '',
  category: '',
  description: '',
  sql_text: '',
  output_fields: [],
})

const editRules = {
  title: [{ required: true, message: '请输入脚本说明', trigger: 'blur' }],
  sql_text: [{ required: true, message: '请输入 SQL', trigger: 'blur' }],
}

/* ---------- 过滤 + 分页 ---------- */
const filteredItems = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  return allItems.value.filter((it) => {
    if (filterCategory.value && it.category !== filterCategory.value) return false
    if (kw) {
      const hay = `${it.title || ''} ${it.script_no || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

const pagedItems = computed(() => {
  const arr = filteredItems.value
  const start = (page.value - 1) * pageSize.value
  return arr.slice(start, start + pageSize.value)
})

watch(filteredItems, () => { page.value = 1 })

/* ---------- 加载 ---------- */
const loadList = async () => {
  loading.value = true
  try {
    const res = await sqlScriptApi.listSqlScripts({ page: 1, page_size: 200, category: filterCategory.value || undefined })
    allItems.value = res.items || []
    // 分类下拉：合并当前筛选结果中的分类 + 已选
    const cats = new Set()
    allItems.value.forEach((it) => it.category && cats.add(it.category))
    categoryOptions.value = Array.from(cats)
  } catch (e) {
    ElMessage.error('加载 SQL 脚本失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => { /* 计算属性实时过滤 */ }

/* ---------- 新增 / 编辑 ---------- */
const openCreate = () => {
  isEdit.value = false
  editId.value = null
  Object.assign(editForm, {
    title: '', category: '', description: '', sql_text: '', output_fields: [],
  })
  editVisible.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editId.value = row.id
  Object.assign(editForm, {
    title: row.title,
    category: row.category || '',
    description: row.description || '',
    sql_text: row.sql_text,
    output_fields: Array.isArray(row.output_fields) ? row.output_fields.map((f) => ({ ...f })) : [],
  })
  editVisible.value = true
}

const addField = () => {
  editForm.output_fields.push({ name: '', type: '', desc: '' })
}
const removeField = (idx) => {
  editForm.output_fields.splice(idx, 1)
}

const submitEdit = () => {
  editRef.value.validate(async (valid) => {
    if (!valid) return
    const payload = {
      title: editForm.title,
      category: editForm.category || undefined,
      description: editForm.description || undefined,
      sql_text: editForm.sql_text,
      output_fields: editForm.output_fields.filter((f) => f.name && f.name.trim()),
    }
    saving.value = true
    try {
      if (isEdit.value) {
        await sqlScriptApi.updateSqlScript(editId.value, payload)
        ElMessage.success('已更新')
      } else {
        await sqlScriptApi.createSqlScript(payload)
        ElMessage.success('已新增')
      }
      editVisible.value = false
      loadList()
    } catch (e) {
      ElMessage.error(isEdit.value ? '更新失败' : '新增失败')
    } finally {
      saving.value = false
    }
  })
}

/* ---------- 详情 ---------- */
const openDetail = async (row) => {
  detailItem.value = row
  detailVisible.value = true
  detailLoading.value = true
  Object.assign(detail, { script_no: row.script_no, title: row.title, category: row.category, created_at: row.created_at, description: row.description })
  try {
    const res = await sqlScriptApi.getSqlScript(row.id)
    Object.assign(detail, res)
  } catch (e) {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

const copySql = async (sql) => {
  if (!sql) return
  try {
    await navigator.clipboard.writeText(sql)
    ElMessage.success('SQL 已复制到剪贴板')
  } catch (e) {
    // 降级方案
    const ta = document.createElement('textarea')
    ta.value = sql
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch (_) {}
    document.body.removeChild(ta)
    ElMessage.success('SQL 已复制')
  }
}

/* ---------- 删除 ---------- */
const remove = (row) => {
  ElMessageBox.confirm(`确认删除脚本「${row.title}」？此操作不可恢复。`, '删除确认', {
    type: 'warning',
  }).then(async () => {
    try {
      await sqlScriptApi.deleteSqlScript(row.id)
      ElMessage.success('已删除')
      loadList()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(() => {
  loadList()
})
</script>

<style scoped>
.sql-script-view {
  padding: 20px 24px 32px;
}

/* 顶部栏 */
.ss-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}
.ss-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.ss-crumb {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 4px;
}
.ss-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ss-search { width: 240px; }
.ss-cat { width: 150px; }

/* 卡片 */
.ss-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: 8px 8px 4px;
}
.ss-table { width: 100%; }
.ss-title-cell { font-weight: 600; color: var(--text-primary); }
.ss-mono { font-family: var(--font-mono); font-size: 12.5px; }
.ss-muted { color: var(--text-muted); font-size: 13px; }

.ss-pager {
  display: flex;
  justify-content: flex-end;
  padding: 12px 8px 8px;
}

/* 表单 */
.ss-sql-input :deep(textarea) {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
}
.ss-fields { width: 100%; }
.ss-field-head,
.ss-field-row {
  display: grid;
  grid-template-columns: 1fr 110px 1fr 40px;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.ss-field-head {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

/* 详情 */
.ss-detail { padding: 4px 6px; }
.ss-d-meta {
  background: var(--border-subtle);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 18px;
}
.ss-d-row {
  display: flex;
  gap: 12px;
  padding: 5px 0;
  font-size: 13.5px;
  color: var(--text-primary);
}
.ss-d-label {
  width: 72px;
  flex-shrink: 0;
  color: var(--text-muted);
}
.ss-d-section { margin-bottom: 20px; }
.ss-d-h {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.ss-d-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 1px 9px;
  border-radius: 20px;
}
.ss-copy {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
  padding: 3px 10px;
  border: 1px solid var(--accent-soft);
  border-radius: 8px;
}
.ss-copy:hover { background: var(--accent-soft); }
.ss-sql {
  background: #0f172a;
  color: #e2e8f0;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.65;
  padding: 16px 18px;
  border-radius: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}
.ss-field-table { margin-top: 4px; }

@media (max-width: 900px) {
  .ss-search, .ss-cat { width: 100%; }
}
</style>
