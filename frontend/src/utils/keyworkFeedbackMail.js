/**
 * 重点工作「周反馈」邮件正文构建（单一实现，从 KeyWorkView.vue 抽出为纯函数）。
 *
 * 抽出的原因：
 *   1) buildFeedbackMailBody 原本是 SFC 内的闭包（依赖 feedbackWeek / detail / isMonthEnd
 *      与若干组件内 helper），无法被单测直接断言；抽成纯函数后 vitest 可直接覆盖。
 *   2) 「在途子项过滤」与「状态中文转译」需同时服务页面模板（周反馈页签 B/C/D）与邮件正文，
 *      放同一模块保证两处口径永远一致。
 *
 * 口径（老大 2026-10-15 确认）：
 *   - 在途 = status 不属于 {completed, cancelled}；not_started / in_progress / delayed 均为在途。
 *   - 状态中文文案唯一来源 = 后端状态注册表（经 constants/statusConfig.js::getStatusMeta 取），
 *     禁在本模块再写第二份状态映射。
 *   - 过滤只依据后端回传的 it.status（不看负责人在表格里尚未提交的本地临时选择）。
 */

import { getStatusMeta } from '@/constants/statusConfig.js'
import { ownerLabel } from '@/utils/owner.js'

/** 子项 type → 后端状态域（月/周计划共用 keywork_plan；成员待办 keywork_task）。 */
const SUB_STATUS_DOMAIN = {
  monthly: 'keywork_plan',
  weekly: 'keywork_plan',
  task: 'keywork_task',
}

/** 终态：不再属于「在途」。（与 backend/constants/status_registry.py 子域五态一致） */
const TERMINAL_STATUS = new Set(['completed', 'cancelled'])

/** 该子项是否处于在途状态（空/未知值保守保留，避免静默丢数据）。 */
export function isInFlightItem(it) {
  if (!it) return false
  return !TERMINAL_STATUS.has(String(it.status ?? ''))
}

/** 过滤出在途子项；返回新数组，绝不改写入参（页面 A 区「上周回顾」按 id 反查依赖原全量数组）。 */
export function inFlightItems(list) {
  return Array.isArray(list) ? list.filter(isInFlightItem) : []
}

/** 子项状态 → 中文文案（走状态注册表，禁写第二份映射）。 */
export function keyworkItemStatusLabel(type, status) {
  return getStatusMeta(SUB_STATUS_DOMAIN[type] || 'keywork_plan', status).label
}

/** 子项展示标签：`【月计划】标题（负责人）`（原 KeyWorkView.vue 内同名实现迁移）。 */
export function itemLabel(it) {
  const title = it.label || it.title || it.content || ''
  const typeName = { monthly: '月计划', weekly: '周计划', task: '成员待办' }[it.type] || it.type
  const suffix = it.assignee ? `（${it.assignee}）` : ''
  return `【${typeName}】${(title || '').slice(0, 40)}${suffix}`
}

/** 该子项是否已在本次反馈中被打勾（`_form.item_updates`）。 */
export function isItemChecked(g, it) {
  const updates = (g && g._form && g._form.item_updates) || []
  return updates.some((u) => u.type === it.type && u.id === it.id)
}

/** 无注入时的只读兜底 taskNote（不写 _form，供单测/纯函数场景）。 */
function _readonlyTaskNote(g, row) {
  const notes = (g && g._form && g._form.member_task_notes) || []
  return (
    notes.find((x) => x.task_id === row.id) || {
      task_id: row.id,
      note: row.note || '',
      status: row.status,
    }
  )
}

/**
 * 生成周反馈请求邮件正文（Markdown）。
 *
 * @param {object} g    负责人分组：{ assignee, monthly_items, weekly_items, task_items, _form }
 * @param {object} ctx  { week, title, workNo, isMonthEnd }
 * @param {object} deps { taskNote } 成员待办进展解析器（注入 SFC 版以保留其写 _form 的既有语义）
 * @returns {string}
 */
export function buildFeedbackMailBody(g, ctx = {}, deps = {}) {
  const { week = '', title = '', workNo = '', isMonthEnd = false } = ctx || {}
  const form = (g && g._form) || {}
  const taskNote = typeof deps.taskNote === 'function' ? deps.taskNote : _readonlyTaskNote

  const lines = []

  // 头部
  lines.push(`【重点工作周反馈】${title}（${workNo}）- ${week} 周`)
  lines.push('')
  lines.push(`负责人：${(g && g.assignee) || ''}`)
  lines.push('')

  // 一、本周工作进展反馈
  lines.push('## 一、本周工作进展反馈')
  lines.push('')

  // 1、月计划完成情况（仅月底显示）
  if (isMonthEnd) {
    lines.push('### 1、月计划完成情况（月底反馈）')
    const monthly = inFlightItems(g && g.monthly_items)
    if (monthly.length) {
      for (const it of monthly) {
        const checked = isItemChecked(g, it)
        lines.push(`- ${checked ? '✅' : '⬜'} ${itemLabel(it)}（${keyworkItemStatusLabel(it.type, it.status)}）`)
      }
    } else {
      lines.push('- （暂无在途月计划）')
    }
    lines.push('')
  }

  // 2、周计划完成情况反馈
  lines.push('### 2、周计划完成情况反馈')
  const weekly = inFlightItems(g && g.weekly_items)
  if (weekly.length) {
    for (const it of weekly) {
      const checked = isItemChecked(g, it)
      lines.push(`- ${checked ? '✅' : '⬜'} ${itemLabel(it)}（${keyworkItemStatusLabel(it.type, it.status)}）`)
    }
  } else {
    lines.push('- （暂无在途周计划）')
  }
  lines.push('')

  // 二、下周工作计划
  lines.push('## 二、下周工作计划')
  lines.push('')

  // 下月计划（仅月底显示）
  if (isMonthEnd) {
    lines.push('### 下月计划（月底反馈）')
    if (form.next_month_summary) {
      lines.push(form.next_month_summary)
    } else {
      lines.push('- （待填写）')
    }
    lines.push('')
  }

  // 下周计划
  lines.push('### 下周计划')
  if (form.next_summary) {
    lines.push(form.next_summary)
  } else {
    lines.push('- （待填写）')
  }
  lines.push('')

  // 三、成员待办管理
  lines.push('## 三、成员待办管理')
  lines.push('')
  const tasks = inFlightItems(g && g.task_items)
  const newTasks = form.new_tasks || []
  if (tasks.length || newTasks.length) {
    if (tasks.length) {
      for (const t of tasks) {
        // 注意：先过滤再取 taskNote —— 被过滤掉的项不再触发其写 _form 的副作用
        const note = taskNote(g, t)
        const assignee = ownerLabel(t.assignee) || '未指派'
        const statusLabel = keyworkItemStatusLabel('task', note.status || t.status)
        const noteText = note.note || t.note || ''
        lines.push(`- **${t.label || t.title || '（未命名）'}** — ${assignee} | ${statusLabel} | ${noteText || '（无进展说明）'}`)
      }
    }
    if (newTasks.length) {
      lines.push('')
      lines.push('#### 新增成员任务')
      for (const t of newTasks) {
        lines.push(`- ${t.title} — ${ownerLabel(t.assignee) || '未指派'} ${t.due_date ? '· ' + t.due_date : ''}`)
      }
    }
  } else {
    lines.push('- （暂无在途成员待办）')
  }
  lines.push('')

  // 四、风险 / 求助事件
  lines.push('## 四、风险 / 求助事件')
  if (form.risk_note) {
    lines.push(form.risk_note)
  } else {
    lines.push('- （无）')
  }
  lines.push('')

  // 整体进度
  lines.push(`**每人一件事整体进度：${form.progress || 0}%**`)
  lines.push('')

  // 底部提示
  lines.push('反馈方式：直接回复本邮件，或线下同步给管理员在 PMWB「重点工作」详情页周反馈页签录入归档。')

  return lines.join('\n')
}
