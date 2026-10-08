// 运营工单 共享常量（与后端 WorkOrderCategory / IssueType 对齐）
// 抽取自 OperationView 与 WorkOrderView，消除重复定义，保证前后端类别一致。

import { domainStatuses, getDomainLabels } from './statusConfig.js'

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

// 工单状态 —— 中文标签唯一源 = 后端状态注册表 `constants/status_registry.py` 的 operation 域
// （经 GET /api/v1/meta/status-domains 下发，statusConfig.js hydrate）。
// ⚠️ 严禁在本文件再维护第二份「状态 key → 中文」映射；新增状态只改后端注册表即自动生效
//    （历史缺陷：两份硬编码不同步，导致 OwnerMatrix 漏传 statusLabels 时渲染出 pending 等英文原文）。
//
// 注意：这里导出的是**取值函数**而非静态对象——注册表是应用启动后异步 hydrate 的，
// 静态对象会锁死在首帧 seed 上，新增状态无法反映到页面。调用方需在 computed 中使用。
export const issueStatusLabels = () => getDomainLabels('operation')

// 运营工单状态选项（key/label；顺序 = 注册表声明顺序 = pending/processing/verify/resolved/closed/suspended）
export const issueStatusOptions = () =>
  domainStatuses('operation').map((s) => ({ key: s.value, value: s.value, label: s.label }))

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
