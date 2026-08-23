// src/constants/statusConfig.js
//
// 工单 / 任务类状态 —— 统一视觉语义配置（集中式）
//
// 设计原则（对应工单统一优化方案 Phase 1）：
//   1. 保留各模块自身的 status value + label —— 不动既有状态机、督办、统计、导入逻辑。
//   2. 仅把「语义」映射到统一的视觉色调（SEMANTIC_TONES），做到跨模块视觉一致。
//   3. 同值不同义（如 closed：需求=已上线 / 运营·需求分组=已关闭）通过「按模块保留 label」
//      解决，绝不搞全局单一值映射。
//   4. sensitive=true 的状态（待处理 / 逾期 / 已暂停 等）由徽标呈现脉冲高亮，解决
//      "敏感字段没有差异化展示" 的问题。

// ───────────────────────────────────────────────
// 统一语义色调 → 视觉变量（全站唯一视觉语言）
// danger 红(紧急/逾期) · warning 橙(待处理·警示) · primary 蓝(进行中)
// success 绿(完成/上线) · info 灰(中性·关闭) · neutral 浅灰(无效·取消)
// ───────────────────────────────────────────────
export const SEMANTIC_TONES = {
  danger: { color: '#f5222d', bg: '#fff1f0', border: '#ffa39e', dot: '#f5222d', rank: 5 },
  warning: { color: '#e6a23c', bg: '#fdf6ec', border: '#f5dab1', dot: '#e6a23c', rank: 3 },
  primary: { color: '#409eff', bg: '#ecf5ff', border: '#b3d8ff', dot: '#409eff', rank: 4 },
  success: { color: '#67c23a', bg: '#f0f9eb', border: '#c2e7b0', dot: '#67c23a', rank: 1 },
  info: { color: '#909399', bg: '#f4f4f5', border: '#dcdfe6', dot: '#909399', rank: 0 },
  neutral: { color: '#a8abb2', bg: '#f4f4f5', border: '#dcdfe6', dot: '#c0c4cc', rank: 0 },
}

// ───────────────────────────────────────────────
// 各模块状态映射：value -> { label, tone, sensitive? }
// ───────────────────────────────────────────────
export const MODULE_STATUS = {
  // 运营工单（OperationView / WorkOrderView 共用）
  operation: {
    pending: { label: '待处理', tone: 'danger', sensitive: true },
    processing: { label: '处理中', tone: 'warning' },
    verify: { label: '验证中', tone: 'primary' },
    resolved: { label: '已解决', tone: 'success' },
    closed: { label: '已关闭', tone: 'info' },
    suspended: { label: '已挂起', tone: 'neutral' },
  },

  // 开发工单（TicketView）
  ticket: {
    created: { label: '已创建', tone: 'info' },
    design_reviewed: { label: '设计已评审', tone: 'primary' },
    dev_completed: { label: '开发完成', tone: 'warning' },
    test_completed: { label: '测试完成', tone: 'warning' },
    live: { label: '已上线', tone: 'success' },
    archived: { label: '已归档', tone: 'neutral' },
  },

  // 待办（TodoView）—— 状态值为后端 Pydantic 枚举：todo/in_progress/done/cancelled
  todo: {
    todo: { label: '未开始', tone: 'info' },
    in_progress: { label: '进行中', tone: 'primary' },
    done: { label: '已完成', tone: 'success' },
    cancelled: { label: '已取消', tone: 'neutral' },
  },

  // 会议行动项（MeetingActionsView）—— 后端真实枚举：pending / in_progress / done / not_attended
  meeting_action: {
    pending: { label: '未开始', tone: 'info', sensitive: true },
    in_progress: { label: '进行中', tone: 'primary' },
    done: { label: '已完成', tone: 'success' },
    not_attended: { label: '未参会', tone: 'neutral' },
  },

  // 重点工作（KeyWorkView STATUS_MAP）
  keywork: {
    planning: { label: '规划中', tone: 'neutral' },
    in_progress: { label: '进行中', tone: 'primary' },
    completed: { label: '已完成', tone: 'success' },
    paused: { label: '已暂停', tone: 'warning' },
    cancelled: { label: '已取消', tone: 'neutral' },
  },

  // 需求（RequirementView 主视图）—— closed=已上线(success)
  requirement: {
    proposed: { label: '建议中', tone: 'neutral' },
    accepted: { label: '已受理', tone: 'primary' },
    dev: { label: '开发中', tone: 'warning' },
    closed: { label: '已上线', tone: 'success' },
    paused: { label: '已暂停', tone: 'danger', sensitive: true },
  },

  // 需求分组（RequirementGroupView）—— closed=已关闭(info)，与需求主视图语义不同！
  requirement_group: {
    closed: { label: '已关闭', tone: 'info' },
    paused: { label: '已暂停', tone: 'danger', sensitive: true },
    on_track: { label: '进行中', tone: 'primary' },
  },

  // 需求交付 - 需求状态（RequirementDeliveryView ext.status）
  requirement_delivery: {
    proposed: { label: '建议中', tone: 'neutral' },
    accepted: { label: '已采纳', tone: 'primary' },
    dev: { label: '开发中', tone: 'warning' },
    closed: { label: '已上线', tone: 'success' },
    paused: { label: '暂停', tone: 'warning' },
  },

  // 需求交付 - 版本状态（RequirementDeliveryView version.status）
  requirement_version: {
    created: { label: '已创建', tone: 'info' },
    design_reviewed: { label: '设计已评审', tone: 'primary' },
    dev_completed: { label: '开发完成', tone: 'warning' },
    test_completed: { label: '测试完成', tone: 'warning' },
    live: { label: '已上线', tone: 'success' },
    archived: { label: '已归档', tone: 'neutral' },
  },

  // 主动优化（RequirementDeliveryView active_opt.status）
  active_optimization: {
    pending: { label: '待评估', tone: 'warning' },
    adopted: { label: '已采纳', tone: 'success' },
    rejected: { label: '不采纳', tone: 'neutral' },
  },

  // 任务中心（TaskCenterView）
  task_center: {
    pending: { label: '待处理', tone: 'danger', sensitive: true },
    in_progress: { label: '进行中', tone: 'primary' },
    done: { label: '已完成', tone: 'success' },
    cancelled: { label: '已取消', tone: 'neutral' },
  },
}

// 重点工作子状态（里程碑 / 月周计划 / 成员待办）统一五态
export const MODULE_SUBSTATUS = {
  keywork_ms: {
    not_started: { label: '未开始', tone: 'neutral' },
    in_progress: { label: '进行中', tone: 'primary' },
    completed: { label: '已完成', tone: 'success' },
    cancelled: { label: '已作废', tone: 'neutral' },
    delayed: { label: '已延期', tone: 'danger', sensitive: true },
  },
  keywork_plan: {
    not_started: { label: '未开始', tone: 'neutral' },
    in_progress: { label: '进行中', tone: 'primary' },
    completed: { label: '已完成', tone: 'success' },
    cancelled: { label: '已作废', tone: 'neutral' },
    delayed: { label: '已延期', tone: 'danger', sensitive: true },
  },
  keywork_task: {
    not_started: { label: '未开始', tone: 'neutral' },
    in_progress: { label: '进行中', tone: 'primary' },
    completed: { label: '已完成', tone: 'success' },
    cancelled: { label: '已作废', tone: 'neutral' },
    delayed: { label: '已延期', tone: 'danger', sensitive: true },
  },
}

// ───────────────────────────────────────────────
// 辅助方法
// ───────────────────────────────────────────────
export function getStatusMeta(module, value) {
  const map = MODULE_STATUS[module] || MODULE_SUBSTATUS[module] || {}
  const meta = map[value] || {}
  return {
    label: meta.label || (value == null ? '-' : String(value)),
    tone: meta.tone || 'info',
    sensitive: !!meta.sensitive,
  }
}

export function getToneVars(tone) {
  return SEMANTIC_TONES[tone] || SEMANTIC_TONES.info
}

// 生成 el-select 选项（用于筛选 / 编辑下拉），保留 label
export function statusSelectOptions(module) {
  const map = MODULE_STATUS[module] || {}
  return Object.entries(map).map(([value, m]) => ({ value, label: m.label }))
}

// 取某模块的语义色调集合（用于统计条 / 图例排序）
export function moduleTones(module) {
  const map = MODULE_STATUS[module] || {}
  return Object.entries(map)
    .map(([value, m]) => ({ value, label: m.label, tone: m.tone, sensitive: !!m.sensitive }))
    .sort((a, b) => (SEMANTIC_TONES[b.tone]?.rank || 0) - (SEMANTIC_TONES[a.tone]?.rank || 0))
}
