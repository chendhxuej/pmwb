// 运营工单 共享常量（与后端 WorkOrderCategory / IssueType 对齐）
// 抽取自 OperationView 与 WorkOrderView，消除重复定义，保证前后端类别一致。

// 工单大类（key / 标签 / 颜色语义）
export const WORK_ORDER_CATEGORIES = [
  { key: 'bug', label: 'BUG 管理', color: 'danger' },
  { key: 'data', label: '数据异常管理', color: 'warning' },
  { key: 'prod', label: '主动运营分析', color: 'primary' },
  { key: 'task', label: '临时交办任务', color: 'success' },
  { key: 'complaint', label: '热点投诉', color: 'danger' },
]

// 每个大类对应的子类（issue_type）选项
export const TYPE_BY_CAT = {
  bug: [
    { value: 'bug', label: '系统缺陷' },
    { value: 'other', label: '其他' },
  ],
  data: [
    { value: 'data_abnormal', label: '数据异常' },
    { value: 'other', label: '其他' },
  ],
  prod: [
    { value: 'topic_analysis', label: '专题分析' },
    { value: 'spot_event', label: '投点事件' },
    { value: 'other', label: '其他' },
  ],
  task: [
    { value: 'temp_task', label: '临时任务' },
    { value: 'other', label: '其他' },
  ],
  complaint: [
    { value: 'spot_event', label: '投点事件' },
    { value: 'other', label: '其他' },
  ],
}

// 工单大类 key -> label
export const CATEGORY_LABEL = Object.fromEntries(
  WORK_ORDER_CATEGORIES.map((c) => [c.key, c.label])
)

// 工单大类 key -> 摘要 chips 用简称（控制宽度，避免卡片被长名撑开）
export const CATEGORY_SHORT = { bug: 'BUG', data: '数据', prod: '运营', task: '交办', complaint: '投诉' }

// 工单大类 key -> color
export const CATEGORY_COLOR = Object.fromEntries(
  WORK_ORDER_CATEGORIES.map((c) => [c.key, c.color])
)

// 子类（issue_type）展示标签
export const issueTypeLabel = (category, type) =>
  (TYPE_BY_CAT[category] || []).find((o) => o.value === type)?.label || type || '其他'

// issue_type -> ElTag type
export const issueTypeTag = (type) => {
  if (type === 'bug') return 'danger'
  if (type === 'data_abnormal') return 'warning'
  if (type === 'topic_analysis') return 'primary'
  if (type === 'spot_event') return 'info'
  if (type === 'temp_task') return 'success'
  return 'info'
}
