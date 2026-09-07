<template>
  <el-dialog :model-value="modelValue" title="材料分类管理" width="560px" @update:model-value="$emit('update:modelValue', $event)">
    <div class="cat-toolbar">
      <span class="cat-tip">两级分类，支持增 / 改 / 删与启停；删除含子分类的节点会被拦截。</span>
      <el-button type="primary" size="small" @click="openAdd(null)">
        <el-icon><Plus /></el-icon> 新增一级
      </el-button>
    </div>

    <el-tree
      :data="treeData"
      :props="{ label: 'name', children: 'children' }"
      node-key="id"
      default-expand-all
      class="cat-tree"
    >
      <template #default="{ node, data }">
        <span class="cat-node">
          <span class="cat-name">
            {{ data.name }}
            <el-tag v-if="!data.enabled" size="small" type="info">停用</el-tag>
          </span>
          <span class="cat-ops">
            <el-button link type="primary" size="small" @click.stop="openAdd(data.id)">
              <el-icon><Plus /></el-icon> 子
            </el-button>
            <el-button link type="primary" size="small" @click.stop="openEdit(data)">
              <el-icon><Edit /></el-icon> 改
            </el-button>
            <el-button link type="danger" size="small" @click.stop="handleDelete(data)">
              <el-icon><Delete /></el-icon> 删
            </el-button>
          </span>
        </span>
      </template>
    </el-tree>

    <el-dialog :model-value="formVisible" :title="editId ? '编辑分类' : '新增分类'" width="420px" append-to-body @update:model-value="formVisible = $event">
      <el-form :model="form" label-width="84px">
        <el-form-item label="分类名称" required>
          <el-input v-model="form.name" placeholder="如 汇报材料 / 业务联系单" />
        </el-form-item>
        <el-form-item label="分类编码" required>
          <el-input v-model="form.code" placeholder="全局唯一，如 report" :disabled="!!editId" />
        </el-form-item>
        <el-form-item label="父分类">
          <el-tree-select
            v-model="form.parent_id"
            :data="parentOptions"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            value-key="id"
            placeholder="不选择 = 一级分类"
            clearable check-strictly default-expand-all style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" />
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
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCategories, createCategory, updateCategory, deleteCategory } from '@/api/material.js'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'saved'])

const categories = ref([])
const formVisible = ref(false)
const editId = ref(null)
const saving = ref(false)
const form = reactive({ name: '', code: '', parent_id: null, sort_order: 0, enabled: true })

function buildTree(list) {
  const map = {}
  list.forEach((c) => (map[c.id] = { ...c, children: [] }))
  const roots = []
  list.forEach((c) => {
    if (c.parent_id && map[c.parent_id]) map[c.parent_id].children.push(map[c.id])
    else roots.push(map[c.id])
  })
  const s = (nodes) => { nodes.sort((a, b) => a.sort_order - b.sort_order); nodes.forEach((n) => s(n.children)) }
  s(roots)
  return roots
}
const treeData = computed(() => buildTree(categories.value))
// 父分类可选项：编辑时排除自身及其子孙
const parentOptions = computed(() => {
  if (!editId.value) return treeData.value
  const banned = new Set([editId.value])
  const collect = (nodes) => nodes.forEach((n) => { banned.add(n.id); collect(n.children) })
  const filtered = JSON.parse(JSON.stringify(treeData.value))
  const strip = (nodes) => nodes.filter((n) => {
    const keep = !banned.has(n.id)
    if (keep) n.children = strip(n.children)
    return keep
  })
  return strip(filtered)
})

async function load() {
  try { categories.value = (await getCategories()) || [] } catch (e) { /* ignore */ }
}
function openAdd(parentId) {
  editId.value = null
  Object.assign(form, { name: '', code: '', parent_id: parentId || null, sort_order: 0, enabled: true })
  formVisible.value = true
}
function openEdit(data) {
  editId.value = data.id
  Object.assign(form, { name: data.name, code: data.code, parent_id: data.parent_id, sort_order: data.sort_order, enabled: data.enabled })
  formVisible.value = true
}
async function submit() {
  if (!form.name.trim() || !form.code.trim()) { ElMessage.warning('名称和编码必填'); return }
  // 提交前预校验编码唯一（避免无谓的 400 往返，给出即时可读提示）
  const code = form.code.trim()
  const dup = categories.value.find((c) => c.code === code && c.id !== editId.value)
  if (dup) {
    ElMessage.warning(`分类编码「${code}」已存在（分类：${dup.name}），请换一个`)
    return
  }
  saving.value = true
  try {
    if (editId.value) await updateCategory(editId.value, { name: form.name, sort_order: form.sort_order, enabled: form.enabled, parent_id: form.parent_id })
    else await createCategory({ code: form.code, name: form.name, parent_id: form.parent_id, sort_order: form.sort_order, enabled: form.enabled })
    ElMessage.success('已保存')
    formVisible.value = false
    await load()
    emit('saved')
  } catch (e) { /* 拦截已由拦截器提示 */ }
  finally { saving.value = false }
}
function handleDelete(data) {
  ElMessageBox.confirm(`确定删除分类「${data.name}」？其下材料将解除分类归属（不删除文件）。`, '提示', { type: 'warning' })
    .then(async () => {
      try { await deleteCategory(data.id); ElMessage.success('已删除'); await load(); emit('saved') }
      catch (e) { /* 拦截器提示 */ }
    }).catch(() => {})
}

watch(() => props.modelValue, (v) => { if (v) load() })
onMounted(() => { if (props.modelValue) load() })
</script>

<style scoped>
.cat-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; gap: 10px; }
.cat-tip { color: var(--el-text-color-secondary); font-size: 12px; }
.cat-tree { max-height: 420px; overflow: auto; }
.cat-node { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.cat-name { font-weight: 500; }
.cat-ops { display: flex; gap: 2px; }
</style>
