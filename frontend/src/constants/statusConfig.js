// src/constants/statusConfig.js
//
// 工单 / 任务类状态 —— 统一视觉语义配置（集中式）
//
// ⚠️ 唯一真相源 = 后端 `backend/constants/status_registry.py`
//    （经 GET /api/v1/meta/status-domains 暴露，由 api/statusMeta.js 拉取）。
//    本文件里的 MODULE_STATUS / MODULE_SUBSTATUS 仅是「首帧兜底 seed」，
//    应用启动 hydrate 后一律以注册表为准。
//    新增状态时**只改后端注册表**，前端本文件无需改动即可自动兼容。
//
// 设计原则（对应工单统一优化方案 Phase 1）：
//   1. 保留各模块自身的 status value + label —— 不动既有状态机、督办、统计、导入逻辑。
//   2. 仅把「语义」映射到统一的视觉色调（SEMANTIC_TONES），做到跨模块视觉一致。
//   3. 同值不同义（如 closed：需求=已上线 / 运营·需求分组=已关闭）通过「按模块保留 label」
//      解决，绝不搞全局单一值映射。
//   4. sensitive=true 的状态（待处理 / 逾期 / 已暂停 等）由徽标呈现脉冲高亮，解决
//      "敏感字段没有差异化展示" 的问题。

import { shallowRef } from 'vue'

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
  // 声明顺序与后端注册表 requirement_group 域一致，避免 hydrate 前后列表重排。
  requirement_group: {
    on_track: { label: '进行中', tone: 'primary' },
    closed: { label: '已关闭', tone: 'info' },
    paused: { label: '已暂停', tone: 'danger', sensitive: true },
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

  // 任务中心（TaskCenterView）—— 统一态 bus：pending/in_progress/done/blocked
  // 历史 bug：此处曾写成 done/cancelled，缺 blocked，导致阻塞态徽标渲染英文原文。
  task_center: {
    pending: { label: '待处理', tone: 'danger', sensitive: true },
    in_progress: { label: '进行中', tone: 'primary' },
    done: { label: '已完成', tone: 'success' },
    blocked: { label: '阻塞/挂起', tone: 'neutral' },
  },

  // 一线调研（ResearchIssueView）—— 状态机与运营工单同构：pending→processing→verify→resolved→closed，suspended 为挂起旁路
  research: {
    pending: { label: '待处理', tone: 'danger', sensitive: true },
    processing: { label: '处理中', tone: 'warning' },
    verify: { label: '验证中', tone: 'primary' },
    resolved: { label: '已解决', tone: 'success' },
    closed: { label: '已关闭', tone: 'info' },
    suspended: { label: '已挂起', tone: 'neutral' },
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
// 注册表 hydrate（后端唯一真相源 → 前端运行时）
// ───────────────────────────────────────────────
// 用 shallowRef 承载：组件 render 中调用 getStatusMeta/domainStatuses 会自动建立
// 依赖，hydrate 后全站徽标/下拉/矩阵自动刷新，无需各页面手动 watch。
const REG = shallowRef(null)

/** 由 api/statusMeta.js 在应用启动时调用，注入后端元数据。 */
export function hydrateStatusMeta(meta) {
  REG.value = meta && meta.domains ? meta : null
}

export function getRawRegistry() {
  return REG.value
}

// 把 seed（MODULE_STATUS / MODULE_SUBSTATUS 的对象映射）归一为注册表同构的数组
function _seedStatuses(module) {
  const map = MODULE_STATUS[module] || MODULE_SUBSTATUS[module] || null
  if (!map) return []
  return Object.entries(map).map(([value, m]) => ({
    value,
    label: m.label != null ? m.label : value,
    tone: m.tone || 'info',
    sensitive: !!m.sensitive,
    unified: '',
    is_terminal: false,
    allowed_next: [],
    required_fields: [],
    _seed: true,
  }))
}

/** 取某状态域的状态定义数组（注册表优先，seed 兜底）。 */
export function domainStatuses(domain) {
  const d = REG.value?.domains?.[domain]
  if (d && Array.isArray(d.statuses) && d.statuses.length) return d.statuses
  return _seedStatuses(domain)
}

/** 该域是否允许就地改状态（注册表声明；seed 兜底视为可写）。 */
export function isDomainWritable(domain) {
  const d = REG.value?.domains?.[domain]
  if (d && typeof d.writable === 'boolean') return d.writable
  return true
}

/** 该域某状态允许流转到的目标原生态值列表。 */
export function allowedNext(domain, value) {
  const s = domainStatuses(domain).find((x) => x.value === resolveStatusValue(domain, value))
  return (s && s.allowed_next) || []
}

export function isTerminal(domain, value) {
  const s = domainStatuses(domain).find((x) => x.value === resolveStatusValue(domain, value))
  return !!(s && s.is_terminal)
}

/** 该域某个状态进入时的必填字段（源表列名）。 */
export function requiredFields(domain, value) {
  const s = domainStatuses(domain).find((x) => x.value === resolveStatusValue(domain, value))
  return (s && s.required_fields) || []
}

/**
 * 原值 → 规范值（走注册表 label_aliases 容错）。
 * 用于自由串状态列（会议行动项 status 为 String(32)）与派生来源的展示性伪值，
 * 让徽标/文案也能命中规范定义而不是把脏值原样吐给用户。
 */
export function resolveStatusValue(domain, value) {
  const v = value == null ? '' : String(value)
  const al = (REG.value?.domains?.[domain]?.label_aliases) || null
  if (al && Object.prototype.hasOwnProperty.call(al, v)) return al[v]
  return v
}

/** 统一态 bus（跨来源四态）。 */
export function unifiedStatuses() {
  return REG.value?.unified_statuses || ['pending', 'in_progress', 'done', 'blocked']
}

export function unifiedLabels() {
  return (
    REG.value?.unified_labels || {
      pending: '待处理',
      in_progress: '进行中',
      done: '已完成',
      blocked: '阻塞/挂起',
    }
  )
}

/** 某域 {原生态值: 中文标签}（供 OwnerMatrix :status-labels、邮件文案等）。 */
export function getDomainLabels(domain) {
  const out = {}
  domainStatuses(domain).forEach((s) => {
    out[s.value] = s.label
  })
  return out
}

/** 某域 [{ key, label }]（供页面自绘的状态筛选标签 / el-select，顺序 = 注册表顺序）。 */
export function domainOptions(domain) {
  return domainStatuses(domain).map((s) => ({ key: s.value, value: s.value, label: s.label }))
}

// 语义色调 → Element Plus el-tag type（页面自绘标签用，保证跨模块色调一致）
const _TAG_TYPE = {
  danger: 'danger',
  warning: 'warning',
  primary: 'primary',
  success: 'success',
  info: 'info',
  neutral: 'info',
}

export function toneToTagType(tone) {
  return _TAG_TYPE[tone] || 'info'
}

/** 某域某状态的 el-tag type（页面自绘标签用）。 */
export function statusTagType(domain, value) {
  const s = domainStatuses(domain).find((x) => x.value === resolveStatusValue(domain, value))
  return toneToTagType(s && s.tone)
}

/** 某域某状态的「label + el-tag type」组件（导出/自绘表格用）。 */
export function statusMetaWithType(domain, value) {
  const m = getStatusMeta(domain, value)
  return { ...m, type: toneToTagType(m.tone) }
}

// 任务中心 source(+source_id) → 状态域（与后端 resolve_domain 同规则）
const _FALLBACK_SOURCE_DOMAIN = {
  todo: 'todo',
  operation_issue: 'operation',
  research_issue: 'research',
  dev_ticket: 'ticket',
  meeting_action: 'meeting_action',
  active_optimization: 'active_optimization',
  requirement_urge: 'requirement_urge',
  key_work: 'keywork',
}
const _FALLBACK_KEYWORK_PREFIX = { task: 'keywork_task', milestone: 'keywork_ms', month: 'keywork_plan', week: 'keywork_plan' }

export function resolveDomain(source, sourceId = '') {
  const sd = REG.value?.source_domain || _FALLBACK_SOURCE_DOMAIN
  if (source === 'key_work') {
    const kp = REG.value?.keywork_prefix || _FALLBACK_KEYWORK_PREFIX
    const prefix = String(sourceId || '').split('-')[0]
    return kp[prefix] || 'keywork'
  }
  return sd[source] || source
}

// ───────────────────────────────────────────────
// 辅助方法（签名保持兼容，下游组件无需改动）
// ───────────────────────────────────────────────
export function getStatusMeta(module, value) {
  // 先走别名容错：会议行动项等自由串状态列的历史脏值也能命中规范定义
  const v = resolveStatusValue(module, value)
  const s = domainStatuses(module).find((x) => x.value === v)
  if (s) return { label: s.label, tone: s.tone || 'info', sensitive: !!s.sensitive }
  return { label: value == null ? '-' : String(value), tone: 'info', sensitive: false }
}

export function getToneVars(tone) {
  return SEMANTIC_TONES[tone] || SEMANTIC_TONES.info
}

// 生成 el-select 选项（用于筛选 / 编辑下拉），保留 label
export function statusSelectOptions(module) {
  return domainStatuses(module).map((s) => ({ value: s.value, label: s.label }))
}

// 取某模块的语义色调集合（用于统计条 / 图例排序）
export function moduleTones(module) {
  return domainStatuses(module)
    .map((s) => ({ value: s.value, label: s.label, tone: s.tone, sensitive: !!s.sensitive }))
    .sort((a, b) => (SEMANTIC_TONES[b.tone]?.rank || 0) - (SEMANTIC_TONES[a.tone]?.rank || 0))
}
