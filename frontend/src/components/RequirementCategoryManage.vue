<template>
  <el-dialog :model-value="modelValue" title="需求分类管理" width="640px" @update:model-value="$emit('update:modelValue', $event)">
    <div class="rc-toolbar">
      <span class="rc-tip">分类即工单落库值（唯一真相源）；改名自动同步存量工单；被引用的分类只能停用不能删。</span>
      <el-button type="primary" size="small" @click="openAdd">
        <el-icon><Plus /></el-icon> 新增分类
      </el-button>
    </div>

    <el-table ref="pmTbl1" :data="categories" size="small" class="rc-table" empty-text="暂无分类，点击右上角新增">
      <el-table-column prop="name" label="分类名称" min-width="120">
        <template #default="{ row }">
          <span class="rc-name">{{ row.name }}</span>
          <el-tag v-if="!row.enabled" size="small" type="info">停用</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="说明" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.remark || '—' }}</template>
      </el-table-column>
      <el-table-column prop="ref_count" label="工单数" width="80" align="center" />
      <el-table-column prop="sort_order" label="排序" width="70" align="center" />
      <el-table-column label="操作" width="150" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="toggleEnabled(row)">
            {{ row.enabled ? '停用' : '启用' }}
          </el-button>
          <el-button link type="primary" size="small" @click="openEdit(row)">
            <el-icon><Edit /></el-icon> 改
          </el-button>
          <el-button link type="danger" size="small" :disabled="row.ref_count > 0" @click="handleDelete(row)">
            <el-icon><Delete /></el-icon> 删
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog :model-value="formVisible" :title="editId ? '编辑分类' : '新增分类'" width="420px" append-to-body @update:model-value="formVisible = $event">
      <el-form :model="form" label-width="84px">
        <el-form-item label="分类名称" required>
          <el-input v-model="form.name" maxlength="64" placeholder="如 业务流程优化 / 一线操作提效" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.remark" maxlength="255" placeholder="用途说明（可选）" />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRequirementCategories, createRequirementCategory, updateRequirementCategory, deleteRequirementCategory } from '@/api/requirement.js'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'saved'])

const categories = ref([])
const formVisible = ref(false)
const editId = ref(null)
const saving = ref(false)
const form = reactive({ name: '', remark: '', sort_order: 0 })

async function load() {
  try { categories.value = (await getRequirementCategories()) || [] } catch (e) { /* 拦截器提示 */ }
}
function openAdd() {
  editId.value = null
  Object.assign(form, { name: '', remark: '', sort_order: (categories.value.length + 1) * 10 })
  formVisible.value = true
}
function openEdit(row) {
  editId.value = row.id
  Object.assign(form, { name: row.name, remark: row.remark || '', sort_order: row.sort_order })
  formVisible.value = true
}
async function submit() {
  if (!form.name.trim()) { ElMessage.warning('分类名称必填'); return }
  const name = form.name.trim()
  const dup = categories.value.find((c) => c.name === name && c.id !== editId.value)
  if (dup) {
    ElMessage.warning(`分类「${name}」已存在，请换一个`)
    return
  }
  saving.value = true
  try {
    if (editId.value) await updateRequirementCategory(editId.value, { name, remark: form.remark, sort_order: form.sort_order })
    else await createRequirementCategory({ name, remark: form.remark, sort_order: form.sort_order })
    ElMessage.success('已保存')
    formVisible.value = false
    await load()
    emit('saved')
  } catch (e) { /* 拦截器提示 */ }
  finally { saving.value = false }
}
function toggleEnabled(row) {
  const next = !row.enabled
  ElMessageBox.confirm(
    next ? `确定启用分类「${row.name}」？` : `确定停用分类「${row.name}」？停用后下拉不再出现，存量工单保留展示。`,
    '提示',
    { type: 'warning' }
  ).then(async () => {
    try {
      await updateRequirementCategory(row.id, { enabled: next })
      ElMessage.success(next ? '已启用' : '已停用')
      await load()
      emit('saved')
    } catch (e) { /* 拦截器提示 */ }
  }).catch(() => {})
}
function handleDelete(row) {
  ElMessageBox.confirm(`确定删除分类「${row.name}」？`, '提示', { type: 'warning' })
    .then(async () => {
      try { await deleteRequirementCategory(row.id); ElMessage.success('已删除'); await load(); emit('saved') }
      catch (e) { /* 拦截器提示（被引用时后端 400 拦截） */ }
    }).catch(() => {})
}

watch(() => props.modelValue, (v) => { if (v) load() })
onMounted(() => { if (props.modelValue) load() })
</script>

<style scoped>
.rc-toolbar { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; gap: 10px; }
.rc-tip { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.rc-table { max-height: 420px; overflow: auto; }
.rc-name { font-weight: 500; margin-right: 6px; }
</style>
