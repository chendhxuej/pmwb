<template>
  <div class="staff-select" v-bind="$attrs" :class="{ 'is-disabled': disabled }" @click="openDialog">
    <div class="staff-select-trigger">
      <template v-if="displayedSelected.length">
        <el-tag
          v-for="opt in displayedSelected"
          :key="opt.value"
          size="small"
          closable
          :disable-transitions="true"
          @close.stop="removeSelected(opt.value)"
        >
          {{ opt.label }}
        </el-tag>
        <span v-if="collapsedCount" class="staff-select-more">+{{ collapsedCount }}</span>
      </template>
      <span v-else class="staff-select-placeholder">{{ placeholder }}</span>
    </div>
    <el-icon v-if="showClear" class="staff-select-clear" @click.stop="clearAll">
      <CircleClose />
    </el-icon>
  </div>

  <el-dialog
    v-model="dialogVisible"
    title="选择人员"
    width="760px"
    :close-on-click-modal="false"
    append-to-body
    destroy-on-close
  >
    <div class="staff-picker">
      <!-- 搜索 + 筛选 -->
      <div class="staff-picker-header">
        <el-input
          v-model="dialogQuery"
          class="staff-picker-search"
          placeholder="搜索姓名 / 邮箱"
          clearable
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div class="staff-picker-filters">
          <el-select
            v-model="filterOrg"
            placeholder="全部组织"
            clearable
            size="small"
            class="staff-picker-filter-item"
          >
            <el-option v-for="o in allOrgs" :key="o" :label="o" :value="o" />
          </el-select>
          <el-select
            v-model="filterRole"
            placeholder="全部身份"
            clearable
            size="small"
            class="staff-picker-filter-item"
          >
            <el-option v-for="r in allRoles" :key="r" :label="r" :value="r" />
          </el-select>
        </div>
      </div>

      <!-- 已选 -->
      <div class="staff-picker-selected">
        <span class="staff-picker-label">已选 {{ selectedValues.length }} 人</span>
        <div class="staff-picker-tags">
          <el-tag
            v-for="opt in selectedOptions"
            :key="opt.value"
            size="small"
            closable
            :disable-transitions="true"
            @close="removeSelected(opt.value)"
          >
            {{ opt.label }}
          </el-tag>
          <span v-if="!selectedValues.length" class="staff-picker-none">未选择</span>
        </div>
        <el-button v-if="selectedValues.length" link type="primary" size="small" @click="clearAll">
          清空
        </el-button>
      </div>

      <!-- 人员列表（单 computed visibleGroups 一次遍历产出，模板零函数调用；轻量勾选标记替代 93 个 el-checkbox 重组件） -->
      <div class="staff-picker-groups">
        <div
          v-for="vg in visibleGroups"
          :key="vg.group.org_id"
          class="staff-picker-group"
        >
          <div class="staff-picker-group-title">
            <el-icon><OfficeBuilding /></el-icon>
            <span>{{ vg.group.org_name }}</span>
            <span class="staff-picker-group-count">{{ vg.options.length }}人</span>
            <el-button
              v-if="multiple"
              link
              type="primary"
              size="small"
              class="staff-picker-group-select-all"
              @click="toggleGroup(vg)"
            >
              {{ vg.allSelected ? '取消全选' : '全选' }}
            </el-button>
          </div>
          <div class="staff-picker-group-body">
            <div
              v-for="item in vg.options"
              :key="item.opt.value"
              class="staff-picker-option"
              :class="{ active: item.selected }"
              @click="toggleOption(item.opt)"
            >
              <span v-if="multiple" class="staff-picker-check" aria-hidden="true"></span>
              <span class="staff-picker-name">{{ item.opt.label }}</span>
              <span v-if="item.opt.role_hint" class="staff-picker-role">{{ item.opt.role_hint }}</span>
              <span v-if="item.opt.email && valueKey === 'email'" class="staff-picker-email">{{ item.opt.email }}</span>
            </div>
          </div>
        </div>
        <el-empty v-if="visibleGroups.length === 0" description="没有匹配的团队或人员" :image-size="80" />
      </div>

      <!-- 自定义添加 -->
      <div v-if="allowCreate" class="staff-picker-custom">
        <span class="staff-picker-custom-label">未找到？手动添加：</span>
        <el-input
          v-model="customName"
          class="staff-picker-custom-input"
          placeholder="输入姓名后按回车添加"
          size="small"
          @keyup.enter="addCustom"
        />
        <el-button type="primary" size="small" @click="addCustom">添加</el-button>
      </div>
    </div>

    <template #footer>
      <div class="staff-picker-footer">
        <el-button link type="primary" size="small" @click="goManage">
          <el-icon><Setting /></el-icon>
          <span>管理人员名单</span>
        </el-button>
        <div class="staff-picker-footer-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmSelection">确认</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { CircleClose, OfficeBuilding, Search, Setting } from '@element-plus/icons-vue'
import { loadStaffOptions, subscribeStaffOptions, basicDataApi } from '@/api/basicData.js'
import { useStaffAdmin } from '@/composables/useStaffAdmin.js'

/**
 * 统一人员选择组件（弹窗式）
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
  placeholder: { type: String, default: '请选择人员' },
  valueKey: { type: String, default: 'value' }, // 'value' | 'email'
})

// 多根组件（trigger div + el-dialog），手动透传 $attrs 到 trigger div
defineOptions({ inheritAttrs: false })
const emit = defineEmits(['update:modelValue', 'change'])

const { openStaffAdmin } = useStaffAdmin()
// shallowRef：93 人嵌套对象不递归 proxy 化，去掉深层响应式初始化/访问开销（数据只读）
const groups = shallowRef([])
const orgOptions = ref([])
const roleOptions = ref([])
const pickerOptionsPromise = ref(null)
const dialogVisible = ref(false)
const dialogQuery = ref('')
const customName = ref('')

// 筛选
const filterOrg = ref('')
const filterRole = ref('')

let unsubscribe = null

async function ensurePickerOptions() {
  if (pickerOptionsPromise.value) return pickerOptionsPromise.value
  pickerOptionsPromise.value = (async () => {
    const [orgs, roles] = await Promise.all([
      basicDataApi.getOrgOptions().catch(() => []),
      basicDataApi.getRoleOptions().catch(() => []),
    ])
    orgOptions.value = Array.isArray(orgs) ? orgs : []
    roleOptions.value = Array.isArray(roles) ? roles : []
  })()
  try {
    await pickerOptionsPromise.value
  } finally {
    pickerOptionsPromise.value = null
  }
}

onMounted(async () => {
  unsubscribe = subscribeStaffOptions((data) => {
    groups.value = data
  })
  // 并行预热：人员列表 + 组织/身份下拉选项，打开弹窗时数据已就绪
  try {
    const [staffOptions] = await Promise.all([
      loadStaffOptions(),
      ensurePickerOptions(),
    ])
    groups.value = staffOptions
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

const flatOptions = computed(() => {
  const list = []
  normalizedGroups.value.forEach((g) => {
    g.options.forEach((o) => list.push(o))
  })
  return list
})

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
    .map((v) => ({ value: v, label: v, email: '', role_hint: '', org_name: '' })),
)

const selectedOptions = computed(() => {
  return selectedValues.value
    .filter((v) => v)
    .map((v) => {
      const found = flatOptions.value.find((o) => o.value === v)
      if (found) return found
      const extra = extraOptions.value.find((o) => o.value === v)
      return extra || { value: v, label: v, email: '', role_hint: '', org_name: '' }
    })
})

const displayedSelected = computed(() => {
  if (!props.collapseTags) return selectedOptions.value
  return selectedOptions.value.slice(0, 1)
})

const collapsedCount = computed(() => {
  if (!props.collapseTags) return 0
  return Math.max(0, selectedOptions.value.length - 1)
})

const showClear = computed(() => {
  return props.clearable && !props.disabled && selectedValues.value.length > 0
})

// --- 筛选器选项（直接从定义接口获取，轻量） ---
const allOrgs = computed(() => {
  return orgOptions.value.map((o) => o.name).sort()
})

const allRoles = computed(() => {
  return roleOptions.value.map((r) => r.name).sort()
})

// --- 组合过滤：单 computed 一次遍历产出 visibleGroups，模板零函数调用（消除每次重渲 370+ 次逐人计算）---
const q = computed(() => dialogQuery.value.trim().toLowerCase())

const visibleGroups = computed(() => {
  const kw = q.value
  const kws = kw ? kw.split(/\s+/).filter(Boolean) : []
  const useOrg = filterOrg.value
  const useRole = filterRole.value
  const sel = new Set(selectedValues.value) // O(1) 命中，替代 isSelected 的 includes(O(n))

  const result = []
  for (const g of normalizedGroups.value) {
    const items = []
    let allSelected = true
    let hasAny = false
    for (const o of g.options) {
      if (kws.length) {
        const match = kws.every(
          (k) =>
            (o.label || '').toLowerCase().includes(k) ||
            (o.email || '').toLowerCase().includes(k) ||
            (o.org_name || '').toLowerCase().includes(k),
        )
        if (!match) continue
      }
      if (useOrg && g.org_name !== useOrg) continue
      if (useRole && (o.role_hint || '') !== useRole) continue
      const selected = sel.has(o.value)
      if (!selected) allSelected = false
      items.push({ opt: o, selected })
      hasAny = true
    }
    if (hasAny) {
      result.push({ group: g, options: items, allSelected })
    }
  }
  return result
})

// --- 全选 / 取消全选（接收 visibleGroups 项 vg，复用其 options/allSelected，零额外遍历）---
function toggleGroup(vg) {
  if (!props.multiple) return
  const vis = vg.options.map((i) => i.opt)
  if (!vis.length) return
  if (vg.allSelected) {
    // 取消全选本组（仅当前可见成员）
    const removeSet = new Set(vis.map((o) => o.value))
    const vals = selectedValues.value.filter((v) => !removeSet.has(v))
    emit('update:modelValue', vals)
    emit('change', vals)
  } else {
    // 全选本组（仅当前可见成员）
    const existing = new Set(selectedValues.value)
    vis.forEach((o) => existing.add(o.value))
    const vals = [...existing]
    emit('update:modelValue', vals)
    emit('change', vals)
  }
}

// --- 单选 / 多选 ---
function toggleOption(opt) {
  if (!props.multiple) {
    emit('update:modelValue', opt.value)
    emit('change', opt.value)
    dialogVisible.value = false
    dialogQuery.value = ''
    return
  }
  const vals = [...selectedValues.value]
  const idx = vals.indexOf(opt.value)
  if (idx >= 0) {
    vals.splice(idx, 1)
  } else {
    vals.push(opt.value)
  }
  emit('update:modelValue', vals)
  emit('change', vals)
}

function removeSelected(value) {
  if (props.disabled) return
  if (!props.multiple) {
    emit('update:modelValue', '')
    emit('change', '')
    return
  }
  const vals = selectedValues.value.filter((v) => v !== value)
  emit('update:modelValue', vals)
  emit('change', vals)
}

function clearAll() {
  if (props.disabled) return
  if (!props.multiple) {
    emit('update:modelValue', '')
    emit('change', '')
    return
  }
  emit('update:modelValue', [])
  emit('change', [])
}

function openDialog() {
  if (props.disabled) return
  dialogQuery.value = ''
  filterOrg.value = ''
  filterRole.value = ''
  customName.value = ''
  dialogVisible.value = true
}

function confirmSelection() {
  dialogVisible.value = false
  dialogQuery.value = ''
}

function addCustom() {
  const name = customName.value.trim()
  if (!name) return
  if (!props.multiple) {
    emit('update:modelValue', name)
    emit('change', name)
    customName.value = ''
    dialogVisible.value = false
    return
  }
  if (!selectedValues.value.includes(name)) {
    const vals = [...selectedValues.value, name]
    emit('update:modelValue', vals)
    emit('change', vals)
  }
  customName.value = ''
}

function goManage() {
  openStaffAdmin()
  dialogVisible.value = false
}
</script>

<style scoped>
.staff-select {
  position: relative;
  width: 100%;
  min-height: 32px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s;
  display: flex;
  align-items: center;
  padding: 0 8px;
  box-sizing: border-box;
}
.staff-select:hover {
  border-color: #c0c4cc;
}
.staff-select.is-disabled {
  background: #f5f7fa;
  cursor: not-allowed;
}
.staff-select-trigger {
  flex: 1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px 0;
  min-height: 24px;
  overflow: hidden;
}
.staff-select-placeholder {
  color: #a8abb2;
  font-size: 14px;
}
.staff-select-more {
  font-size: 12px;
  color: #909399;
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 4px;
}
.staff-select-clear {
  color: #a8abb2;
  margin-left: 4px;
  cursor: pointer;
}
.staff-select-clear:hover {
  color: #409eff;
}

/* ---------- 弹窗内部 ---------- */
.staff-picker {
  display: flex;
  flex-direction: column;
  max-height: 58vh;
}
.staff-picker-header {
  margin-bottom: 10px;
}
.staff-picker-search {
  width: 100%;
  margin-bottom: 8px;
}
.staff-picker-filters {
  display: flex;
  gap: 10px;
}
.staff-picker-filter-item {
  flex: 1;
}

/* 已选区域 */
.staff-picker-selected {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 8px;
  flex-wrap: wrap;
}
.staff-picker-label {
  font-size: 13px;
  color: #606266;
  font-weight: 600;
  flex-shrink: 0;
  padding-top: 4px;
}
.staff-picker-tags {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.staff-picker-none {
  font-size: 13px;
  color: #909399;
  padding-top: 4px;
}

/* 分组列表 */
.staff-picker-groups {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}
.staff-picker-group {
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
}
.staff-picker-group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #f5f7fa;
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}
.staff-picker-group-count {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}
.staff-picker-group-select-all {
  margin-left: auto;
}

.staff-picker-group-body {
  padding: 6px 8px;
}
.staff-picker-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.staff-picker-option:hover {
  background: #f5f7fa;
}
.staff-picker-option.active {
  background: #eaf1ff;
}
.staff-picker-check {
  width: 16px;
  height: 16px;
  border: 1px solid #dcdfe6;
  border-radius: 2px;
  box-sizing: border-box;
  flex-shrink: 0;
  position: relative;
  background: #fff;
  transition: background 0.15s, border-color 0.15s;
}
.staff-picker-option:hover .staff-picker-check {
  border-color: #409eff;
}
.staff-picker-option.active .staff-picker-check {
  background: #409eff;
  border-color: #409eff;
}
.staff-picker-option.active .staff-picker-check::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 2px;
  width: 3px;
  height: 7px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
  box-sizing: border-box;
}
.staff-picker-name {
  flex: 1;
  font-size: 14px;
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.staff-picker-role {
  flex-shrink: 0;
  font-size: 12px;
  color: #2f6fed;
  background: #eaf1ff;
  padding: 0 6px;
  border-radius: 4px;
}
.staff-picker-email {
  flex-shrink: 0;
  font-size: 12px;
  color: #8a94a6;
}

/* 自定义添加 */
.staff-picker-custom {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}
.staff-picker-custom-label {
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
}
.staff-picker-custom-input {
  flex: 1;
  max-width: 240px;
}

/* 底部 */
.staff-picker-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.staff-picker-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
