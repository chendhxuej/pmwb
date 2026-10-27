<template>
  <el-dialog
    :model-value="modelValue"
    :title="isEdit ? '编辑改进措施' : '登记改进措施'"
    width="640px"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form :model="form" label-width="110px" size="default">
      <el-form-item label="二级场景" required>
        <el-select
          v-model="form.l2"
          filterable
          placeholder="选择问题场景（来自分类字典）"
          :disabled="isEdit"
          style="width: 100%"
        >
          <el-option v-for="g in l2Groups" :key="g.label" :label="g.label" :value="g.value">
            <span v-if="g.group" style="color: var(--text-secondary); font-size: 12px">{{ g.label }}</span>
            <span v-else>{{ g.label }}</span>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="措施标题" required>
        <el-input v-model="form.title" maxlength="255" placeholder="一句话说明本措施做什么" />
      </el-form-item>
      <el-form-item label="责任人" required>
        <el-input v-model="form.owner" placeholder="责任人姓名，多负责人用逗号分隔" />
      </el-form-item>
      <el-form-item label="要求完成">
        <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="验收标准" required>
        <el-input
          v-model="form.acceptance"
          type="textarea"
          :rows="2"
          placeholder="可验证的标准，如：同类单日峰值降至 5 单以下"
        />
      </el-form-item>
      <el-form-item label="情况说明">
        <el-input v-model="form.desc" type="textarea" :rows="2" placeholder="背景/根因简述（可选）" />
      </el-form-item>
      <el-form-item v-if="!isEdit" label="同步建工单">
        <el-switch v-model="form.create_issue" />
        <span class="switch-tip">同时在运营监控创建 P1 工单做督办载体（父子关联）</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { complaintApi } from '@/api/complaint'

const props = defineProps({
  modelValue: Boolean,
  // 编辑时传入措施行
  action: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const saving = ref(false)
const categories = ref([])
const isEdit = computed(() => !!props.action)

const form = reactive({
  l2: '', title: '', owner: '', due_date: '', acceptance: '', desc: '', create_issue: true,
})

watch(() => props.modelValue, async (open) => {
  if (!open) return
  try {
    categories.value = await complaintApi.listCategories()
  } catch (e) { /* request 已提示 */ }
  if (props.action) {
    Object.assign(form, {
      l2: props.action.category_l2 || '',
      title: props.action.title || '',
      owner: props.action.owner || '',
      due_date: props.action.due_date ? String(props.action.due_date).slice(0, 10) : '',
      acceptance: props.action.acceptance || '',
      desc: props.action.note || '',
      create_issue: false,
    })
  } else {
    Object.assign(form, { l2: '', title: '', owner: '', due_date: '', acceptance: '', desc: '', create_issue: true })
  }
})

// 二级场景按一级性质分组展示（group 标记用于渲染分组头）
const l2Groups = computed(() => {
  const out = []
  for (const c of categories.value) {
    if (c.level === 1 && c.enabled) {
      out.push({ label: `── ${c.name} ──`, value: `__group_${c.id}`, group: true })
    } else if (c.level === 2 && c.enabled) {
      out.push({ label: `　${c.name}`, value: c.name, group: false })
    }
  }
  return out
})

async function save() {
  if (isEdit.value) {
    saving.value = true
    try {
      await complaintApi.updateAction(props.action.action_no, {
        title: form.title,
        owner: form.owner,
        due_date: form.due_date || null,
        acceptance: form.acceptance,
        note: form.desc || null,
      })
      ElMessage.success('措施已更新')
      emit('saved')
      emit('update:modelValue', false)
    } catch (e) { /* request 已提示 */ } finally {
      saving.value = false
    }
    return
  }
  if (!form.l2 || form.l2.startsWith('__group_')) {
    ElMessage.warning('请选择二级问题场景')
    return
  }
  if (!form.title || !form.owner || !form.acceptance) {
    ElMessage.warning('标题 / 责任人 / 验收标准为必填')
    return
  }
  saving.value = true
  try {
    const r = await complaintApi.createAction({ ...form })
    ElMessage.success(`已登记措施 ${r.action_no}${r.issue_no ? `，并创建运营工单 ${r.issue_no}` : ''}`)
    emit('saved')
    emit('update:modelValue', false)
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.switch-tip {
  margin-left: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
