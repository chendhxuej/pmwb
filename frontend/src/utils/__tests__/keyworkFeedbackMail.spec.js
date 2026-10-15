/**
 * 重点工作「周反馈」邮件正文构建单测
 *
 * 覆盖 2026-10-15 修复：
 *   1) 在途过滤：completed / cancelled 的月计划·周计划·成员待办不得进入邮件正文与页面清单
 *   2) 状态转译：改为中文（走状态注册表），正文不得残留 not_started / in_progress / delayed 等英文 key
 *   3) 零回归：过滤不得改写入参数组（页面 A 区「上周回顾」按 id 反查依赖原全量数组）
 *   4) 零副作用：被过滤掉的成员待办不得触发 taskNote（其会写 _form.member_task_notes）
 */
import { describe, it, expect, vi } from 'vitest'
import {
  isInFlightItem,
  inFlightItems,
  keyworkItemStatusLabel,
  itemLabel,
  isItemChecked,
  buildFeedbackMailBody,
} from '@/utils/keyworkFeedbackMail.js'

/** 固定 fixture：三类子项各含 2 个终态项 + 1 个在途项 */
function makeGroup() {
  return {
    assignee: '陈大海',
    monthly_items: [
      { type: 'monthly', id: 1, assignee: '陈大海', label: '月计划A在途', status: 'in_progress' },
      { type: 'monthly', id: 2, assignee: '陈大海', label: '月计划B已完成', status: 'completed' },
      { type: 'monthly', id: 3, assignee: '陈大海', label: '月计划C已作废', status: 'cancelled' },
    ],
    weekly_items: [
      { type: 'weekly', id: 11, assignee: '陈大海', label: '周计划A未开始', status: 'not_started' },
      { type: 'weekly', id: 12, assignee: '', label: '周计划B已完成', status: 'completed' },
    ],
    task_items: [
      { type: 'task', id: 21, assignee: '陈大海', label: '待办A延期', status: 'delayed', note: '' },
      { type: 'task', id: 22, assignee: '陈大海', label: '待办B已完成', status: 'completed', note: '' },
      { type: 'task', id: 23, assignee: '', label: '待办C已作废', status: 'cancelled', note: '' },
    ],
    _form: {
      week: '2026-W42',
      item_updates: [{ type: 'weekly', id: 11, status: 'completed' }],
      member_task_notes: [],
      new_tasks: [],
      next_summary: '下周推进 X',
      risk_note: '存在风险 Y',
      progress: 60,
    },
  }
}

const CTX = { week: '2026-W42', title: '一网通选址统一化', workNo: 'ZDFZ2026001', isMonthEnd: false }
/** 月底上下文：月计划段/下月计划段才会渲染（沿用改造前口径） */
const CTX_MONTHEND = { ...CTX, isMonthEnd: true }

describe('isInFlightItem / inFlightItems', () => {
  it('completed 与 cancelled 视为终态（不在途）', () => {
    expect(isInFlightItem({ status: 'completed' })).toBe(false)
    expect(isInFlightItem({ status: 'cancelled' })).toBe(false)
  })

  it('not_started / in_progress / delayed 视为在途', () => {
    expect(isInFlightItem({ status: 'not_started' })).toBe(true)
    expect(isInFlightItem({ status: 'in_progress' })).toBe(true)
    expect(isInFlightItem({ status: 'delayed' })).toBe(true)
  })

  it('空状态保守保留，非对象返回 false', () => {
    expect(isInFlightItem({ status: '' })).toBe(true)
    expect(isInFlightItem({ status: null })).toBe(true)
    expect(isInFlightItem({})).toBe(true)
    expect(isInFlightItem(null)).toBe(false)
    expect(isInFlightItem(undefined)).toBe(false)
  })

  it('inFlightItems 过滤正确，且不改写入参数组（页面 A 区反查依赖原全量数据）', () => {
    const list = makeGroup().task_items
    const before = list.length
    const kept = inFlightItems(list)
    expect(kept.map((x) => x.id)).toEqual([21])
    expect(list).toHaveLength(before)
    expect(list.map((x) => x.id)).toEqual([21, 22, 23])
  })

  it('inFlightItems 对非数组入参返回空数组', () => {
    expect(inFlightItems(null)).toEqual([])
    expect(inFlightItems(undefined)).toEqual([])
  })
})

describe('keyworkItemStatusLabel（走状态注册表，禁第二份映射）', () => {
  it('月/周计划 → keywork_plan 域中文', () => {
    expect(keyworkItemStatusLabel('monthly', 'not_started')).toBe('未开始')
    expect(keyworkItemStatusLabel('monthly', 'in_progress')).toBe('进行中')
    expect(keyworkItemStatusLabel('weekly', 'delayed')).toBe('已延期')
  })

  it('成员待办 → keywork_task 域中文', () => {
    expect(keyworkItemStatusLabel('task', 'not_started')).toBe('未开始')
    expect(keyworkItemStatusLabel('task', 'in_progress')).toBe('进行中')
    expect(keyworkItemStatusLabel('task', 'delayed')).toBe('已延期')
    expect(keyworkItemStatusLabel('task', 'completed')).toBe('已完成')
    expect(keyworkItemStatusLabel('task', 'cancelled')).toBe('已作废')
  })

  it('未知值回退原串，未知 type 兜底 keywork_plan', () => {
    expect(keyworkItemStatusLabel('task', 'weird_value')).toBe('weird_value')
    expect(keyworkItemStatusLabel('unknown_type', 'in_progress')).toBe('进行中')
  })
})

describe('itemLabel / isItemChecked 行为保持', () => {
  it('itemLabel 保持 【类型】标题（负责人） 格式', () => {
    expect(itemLabel({ type: 'monthly', label: '选题', assignee: '陈大海' })).toBe('【月计划】选题（陈大海）')
    expect(itemLabel({ type: 'weekly', label: '选题', assignee: '' })).toBe('【周计划】选题')
    expect(itemLabel({ type: 'task', title: '待办名' })).toBe('【成员待办】待办名')
  })

  it('isItemChecked 依据 _form.item_updates 命中', () => {
    const g = makeGroup()
    expect(isItemChecked(g, { type: 'weekly', id: 11 })).toBe(true)
    expect(isItemChecked(g, { type: 'weekly', id: 12 })).toBe(false)
    expect(isItemChecked({ _form: {} }, { type: 'weekly', id: 11 })).toBe(false)
    expect(isItemChecked(null, { type: 'weekly', id: 11 })).toBe(false)
  })
})

describe('buildFeedbackMailBody', () => {
  it('不包含已完成 / 已作废的子项，包含在途子项', () => {
    const body = buildFeedbackMailBody(makeGroup(), CTX_MONTHEND, {})
    expect(body).toContain('月计划A在途')
    expect(body).toContain('周计划A未开始')
    expect(body).toContain('待办A延期')

    expect(body).not.toContain('月计划B已完成')
    expect(body).not.toContain('月计划C已作废')
    expect(body).not.toContain('周计划B已完成')
    expect(body).not.toContain('待办B已完成')
    expect(body).not.toContain('待办C已作废')
  })

  it('状态已转中文，正文无英文状态裸值残留', () => {
    const body = buildFeedbackMailBody(makeGroup(), CTX_MONTHEND, {})
    expect(body).toContain('（进行中）')
    expect(body).toContain('（未开始）')
    expect(body).toContain('| 已延期 |') // 成员待办行为「| 状态 |」格式
    expect(body).not.toMatch(/（(not_started|in_progress|completed|cancelled|delayed)）/)
    expect(body).not.toMatch(/\| (not_started|in_progress|delayed) \|/)
  })

  it('在途子项保留 ✅/⬜ 勾选标记与中文状态', () => {
    const body = buildFeedbackMailBody(makeGroup(), CTX_MONTHEND, {})
    expect(body).toContain('- ✅ 【周计划】周计划A未开始（陈大海）（未开始）')
    expect(body).toContain('- ⬜ 【月计划】月计划A在途（陈大海）（进行中）')
  })

  it('成员待办行格式与有效状态（note.status 优先、回退 t.status）保持', () => {
    const g = makeGroup()
    g._form.member_task_notes = [{ task_id: 21, note: '已联系厂商', status: 'in_progress' }]
    const body = buildFeedbackMailBody(g, CTX, {})
    expect(body).toContain('- **待办A延期** — 陈大海 | 进行中 | 已联系厂商')
  })

  it('被过滤的成员待办不触发 taskNote（避免脏写 _form.member_task_notes）', () => {
    const spy = vi.fn((gg, row) => ({ status: row.status, note: row.note }))
    buildFeedbackMailBody(makeGroup(), CTX, { taskNote: spy })
    const ids = spy.mock.calls.map((c) => c[1].id)
    expect(ids).toEqual([21])
    expect(ids).not.toContain(22)
    expect(ids).not.toContain(23)
  })

  it('全部为终态时输出在途空态文案', () => {
    const g = makeGroup()
    g.monthly_items = [{ type: 'monthly', id: 1, label: '月已完', status: 'completed' }]
    g.weekly_items = [{ type: 'weekly', id: 11, label: '周已废', status: 'cancelled' }]
    g.task_items = [{ type: 'task', id: 21, label: '待办已完', status: 'completed' }]
    g._form.item_updates = []
    const body = buildFeedbackMailBody(g, { ...CTX, isMonthEnd: true }, {})
    expect(body).toContain('- （暂无在途月计划）')
    expect(body).toContain('- （暂无在途周计划）')
    expect(body).toContain('- （暂无在途成员待办）')
    expect(body).not.toContain('月已完')
    expect(body).not.toContain('周已废')
    expect(body).not.toContain('待办已完')
  })

  it('非月底不渲染月计划段', () => {
    const body = buildFeedbackMailBody(makeGroup(), { ...CTX, isMonthEnd: false }, {})
    expect(body).not.toContain('### 1、月计划完成情况')
    expect(body).not.toContain('下月计划（月底反馈）')
  })

  it('月底渲染月计划段与下月计划段', () => {
    const body = buildFeedbackMailBody(makeGroup(), { ...CTX, isMonthEnd: true }, {})
    expect(body).toContain('### 1、月计划完成情况（月底反馈）')
    expect(body).toContain('### 下月计划（月底反馈）')
  })

  it('该负责人本周尚无任何子项时仍能成文（不抛错）', () => {
    const body = buildFeedbackMailBody({ assignee: '陈大海', _form: {} }, CTX, {})
    expect(body).toContain('【重点工作周反馈】一网通选址统一化（ZDFZ2026001）- 2026-W42 周')
    expect(body).toContain('负责人：陈大海')
    expect(body).toContain('- （暂无在途成员待办）')
    expect(body).toContain('- （无）')
  })

  it('传 null 分组不抛错', () => {
    expect(() => buildFeedbackMailBody(null, CTX, {})).not.toThrow()
  })
})
