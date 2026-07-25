<template>
  <el-select
    :model-value="modelValue"
    :multiple="multiple"
    filterable
    :filter-method="onFilter"
    :allow-create="allowCreate"
    default-first-option
    :clearable="clearable"
    :placeholder="placeholder"
    :disabled="disabled"
    :collapse-tags="collapseTags"
    :collapse-tags-tooltip="collapseTags"
    class="staff-select"
    @update:model-value="onChange"
  >
    <el-option-group
      v-for="group in displayedGroups"
      :key="group.org_id"
      :label="group.org_name"
    >
      <el-option
        v-for="opt in group.options"
        :key="`${group.org_id}-${opt.value}`"
        :value="opt.value"
        :label="opt.label"
      >
        <div class="staff-option">
          <span class="staff-option-name">{{ opt.label }}</span>
          <span v-if="opt.role_hint" class="staff-option-role">{{ opt.role_hint }}</span>
          <span v-if="opt.email && valueKey === 'email'" class="staff-option-email">{{ opt.email }}</span>
        </div>
      </el-option>
    </el-option-group>
    <!-- 历史/自由姓名或邮箱回显：不在名单里的已选值补成临时选项 -->
    <el-option
      v-for="item in extraOptions"
      :key="`extra-${item.value}`"
      :value="item.value"
      :label="item.label"
    />
    <template #header>
      <div class="staff-search-hint">
        <el-icon><Info-Filled /></el-icon>
        <span>支持按组织 / 身份 / 姓名组合查找</span>
      </div>
    </template>
    <template #footer>
      <el-button link type="primary" size="small" @click="goManage">
        <el-icon style="margin-right: 4px"><Setting /></el-icon>管理人员名单
      </el-button>
    </template>
  </el-select>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { InfoFilled, Setting } from '@element-plus/icons-vue'
import { loadStaffOptions, subscribeStaffOptions } from '@/api/basicData.js'

/**
 * 统一人员选择组件
 *
 * v-model 约定：
 * - multiple=true 时为 string[]；否则为 string。
 * - valueKey='value'(默认) 时返回姓名；valueKey='email' 时返回邮箱（无邮箱则回退姓名）。
 * 组件内不做 join/split，各调用方按业务表存储格式自行转换。
 */
const props = defineProps({
  modelValue: { type: [String, Array], default: () => '' },
  multiple: { type: Boolean, default: false },
  allowCreate: { type: Boolean, default: true },
  clearable: { type: Boolean, default: true },
  collapseTags: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '请输入组织 / 身份 / 姓名查找' },
  valueKey: { type: String, default: 'value' }, // 'value' | 'email'
})
const emit = defineEmits(['update:modelValue', 'change'])

const router = useRouter()
const groups = ref([])
const filterQuery = ref('')
let unsubscribe = null

onMounted(async () => {
  unsubscribe = subscribeStaffOptions((data) => {
    groups.value = data
  })
  try {
    groups.value = await loadStaffOptions()
  } catch {
    groups.value = []
  }
})

onBeforeUnmount(() => {
  if (unsubscribe) unsubscribe()
})

const optionValue = (opt) => {
  if (props.valueKey === 'email') {
    return opt.email || opt.value
  }
  return opt.value
}

const normalizedGroups = computed(() => {
  return (groups.value || []).map((g) => ({
    ...g,
    options: (g.options || []).map((o) => ({
      ...o,
      value: optionValue(o),
      label: o.label || o.value,
      org_name: g.org_name,
    })),
  }))
})

const displayedGroups = computed(() => {
  const q = filterQuery.value.trim()
  if (!q) return normalizedGroups.value
  const kws = q.toLowerCase().split(/\s+/).filter(Boolean)
  return normalizedGroups.value
    .map((g) => {
      const opts = g.options.filter((o) =>
        kws.every(
          (kw) =>
            (o.label || '').toLowerCase().includes(kw) ||
            (o.role_hint || '').toLowerCase().includes(kw) ||
            (o.org_name || '').toLowerCase().includes(kw),
        ),
      )
      return opts.length ? { ...g, options: opts } : null
    })
    .filter(Boolean)
})

// 已选但不在名单中的值（历史数据/手输），补成临时选项保证回显
const knownValues = computed(() => {
  const s = new Set()
  normalizedGroups.value.forEach((g) => g.options.forEach((o) => s.add(o.value)))
  return s
})
const selectedValues = computed(() => {
  if (props.multiple) {
    return Array.isArray(props.modelValue) ? props.modelValue : []
  }
  return props.modelValue ? [props.modelValue] : []
})
const extraOptions = computed(() =>
  selectedValues.value
    .filter((v) => v && !knownValues.value.has(v))
    .map((v) => ({ value: v, label: v })),
)

function onFilter(query) {
  filterQuery.value = query
}

function onChange(val) {
  emit('update:modelValue', val)
  emit('change', val)
}

function goManage() {
  router.push('/basic-data')
}
</script>

<style scoped>
.staff-select {
  width: 100%;
}
.staff-search-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: #8a94a6;
  border-bottom: 1px solid #f2f4f8;
}
.staff-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 8px;
}
.staff-option-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
.staff-option-role {
  flex-shrink: 0;
  font-size: 12px;
  color: #2f6fed;
  background: #eaf1ff;
  padding: 0 6px;
  border-radius: 4px;
}
.staff-option-email {
  flex-shrink: 0;
  font-size: 12px;
  color: #8a94a6;
}
</style>
