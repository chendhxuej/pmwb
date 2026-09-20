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

// 工单大类 key -> 色调语义（组件内禁硬编码十六进制，色值一律由 design.css 令牌承载）
export const CATEGORY_TONE = {
  bug: 'danger',
  data: 'accent',
  prod: 'warning',
  task: 'violet',
  complaint: 'success',
}

// 工单状态 key -> 中文标签（单一源）
// 与后端 OperationIssueService.STATUS_ORDER 一一对应，顺序即展示顺序。
// 用途：总览责任人矩阵的图例 / 表头 / 悬浮提示；严禁在页面里再写第二份映射，
// 也严禁把 key 直接当文案展示（历史缺陷：漏传 statusLabels 导致页面出现 pending 等英文原文）。
export const ISSUE_STATUS_LABELS = {
  pending: '待处理',
  processing: '处理中',
  verify: '验证中',
  resolved: '已解决',
  closed: '已关闭',
  suspended: '已挂起',
}

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
