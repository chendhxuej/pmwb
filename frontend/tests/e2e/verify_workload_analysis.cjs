/**
 * 回归：需求与交付 → 工作量分析子页（2026-10-16 新增，2026-10-16 UI 整改）
 *
 * 覆盖点：
 *  1. 主 tabs 变为 4 个（需求 / 用户故事 / 主动优化 / 工作量分析）
 *  2. 默认区间锚定后端 data_range（有 dev 记录的起止月），不再硬编码近 12 月
 *  3. Bento 12 栅格容器 + KPI 收成 4 张主卡（标签序列固定）
 *  4. 汇总卡数值 = 接口 summary（单一数据源）
 *  5. 数据质量提示条 .pm-notice 渲染，未归月 chip 可点击并滚动定位到 #wla-unmonth
 *  6. 趋势图容器已真实渲染（canvas 宽度 > 0，防 el-tab-pane 0 宽度陷阱）+ 8 列跨度占比
 *  7. 快捷预设 5 个（数据区间/近3月/近6月/近12月/本年），点「近 3 月」生效
 *  8. 按 SA 表行数 = 接口 by_sa.length；SA 条形图渲染；按系统分布表行数 = by_system.length
 *  9. 需求明细表行数 = min(total, pageSize)
 * 10. 「补时间」弹窗可打开（不落库：只打开后取消）
 * 11. 无 Vue 运行时报错
 *
 * 红线：build 过 ≠ 能渲染。本脚本必须真实 DOM 断言。
 * 注意：本文件为 LF 行尾；.gitignore 忽略 verify_*.cjs，提交需 `git add -f`。
 */
const puppeteer = require('puppeteer-core')

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173'
const API = process.env.API_URL || 'http://127.0.0.1:8000'
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const ROUTE = '/requirement-delivery'

const log = []
const check = (name, cond, extra) => {
  log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const num = (s) => Math.round(parseFloat(String(s || '0').replace(/[^\d.]/g, '')) * 100) / 100
const mm = (y, m) => `${y}-${String(m).padStart(2, '0')}`

;(async () => {
  // ── 接口基准（单一数据源比对）──
  // 首次不带 month_from/month_to → 后端用 data_range 锚定；前端首屏发的是同一个请求
  const probeUrl = `${API}/api/v1/workload-analysis/stats?page=1&page_size=20`
  const api = (await (await fetch(probeUrl)).json()).data
  const dr = api.data_range || {}

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1680, height: 1100 },
  })
  const page = await browser.newPage()
  const errs = []
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message))
  page.on('console', (c) => {
    if (c.type() === 'error') {
      const t = c.text()
      if (!/favicon|404 \(Not Found\)/i.test(t)) errs.push('console: ' + t)
    }
  })

  await page.goto(BASE + ROUTE, { waitUntil: 'networkidle2', timeout: 60000 })
  await sleep(1200)

  // 1. tabs 数量
  const tabCount = await page.$$eval('.el-tabs__item', (els) => els.length)
  check('主 tabs 数量为 4', tabCount === 4, `实际=${tabCount}`)
  const hasWorkloadTab = await page.evaluate(() =>
    [...document.querySelectorAll('.el-tabs__item')].some((e) => e.innerText.trim() === '工作量分析'),
  )
  check('存在「工作量分析」tab', hasWorkloadTab)

  // 切到工作量分析
  await page.evaluate(() => {
    const t = [...document.querySelectorAll('.el-tabs__item')].find((e) => e.innerText.trim() === '工作量分析')
    if (t) t.click()
  })
  await sleep(2500)

  check('面板根节点渲染 (.wla)', (await page.$('.wla')) !== null)

  // 3. Bento 12 栅格
  const gridCols = await page.evaluate(() => {
    const el = document.querySelector('.wla .bento-grid')
    if (!el) return -1
    return getComputedStyle(el).gridTemplateColumns.split(' ').length
  })
  check('页面使用 12 列 Bento 栅格', gridCols === 12, `列数=${gridCols}`)

  // 4. KPI 主卡
  const cards = await page.$$eval('.wla-stats .wla-stat', (els) =>
    els.map((e) => ({
      label: e.querySelector('.wla-stat-label')?.innerText.trim(),
      value: e.querySelector('.wla-stat-num')?.innerText.trim(),
      sub: e.querySelector('.pm-stat__sub')?.innerText.trim(),
      hasIco: !!e.querySelector('.pm-stat__ico'),
    })),
  )
  check('KPI 主卡数为 4', cards.length === 4, `实际=${cards.length}`)
  const expectLabels = '覆盖需求,总工作量(人天),月均工作量,峰值月'
  check(
    'KPI 标签序列正确',
    cards.map((c) => c.label).join(',') === expectLabels,
    cards.map((c) => c.label).join(','),
  )
  check('KPI 卡均有图标 chip', cards.length === 4 && cards.every((c) => c.hasIco))

  const totalCard = cards.find((c) => c.label === '总工作量(人天)')
  check(
    '汇总卡「总工作量」= 接口 summary.workload_total',
    num(totalCard?.value) === num(api.summary.workload_total),
    `dom=${totalCard?.value} api=${api.summary.workload_total}`,
  )
  const reqCard = cards.find((c) => c.label === '覆盖需求')
  check(
    '汇总卡「覆盖需求」= 接口 summary.req_count',
    num(reqCard?.value) === num(api.summary.req_count),
    `dom=${reqCard?.value} api=${api.summary.req_count}`,
  )
  check(
    '首卡副文案含「评估记录 N 条」',
    (reqCard?.sub || '').includes(`评估记录 ${api.summary.eval_count} 条`),
    reqCard?.sub,
  )

  // 5. 数据质量提示条
  const notice = await page.evaluate(() => {
    const el = document.querySelector('.wla .pm-notice')
    if (!el) return null
    const link = el.querySelector('.pm-notice__chip.is-link')
    return {
      text: el.innerText.replace(/\s+/g, ' ').trim(),
      hasLink: !!link,
      linkText: link ? link.innerText.replace(/\s+/g, ' ').trim() : '',
    }
  })
  if (api.summary.unmonth_req_count > 0) {
    check(
      '提示条含可点击「未归月」chip',
      !!notice && notice.hasLink && notice.linkText.includes(`未归月 ${api.summary.unmonth_req_count} 个`),
      JSON.stringify(notice),
    )
  } else {
    check(
      '无未归月时提示条为「数据质量良好」',
      !!notice && notice.text.includes('数据质量良好'),
      JSON.stringify(notice),
    )
  }

  // 6. 趋势图真实渲染（0 宽度陷阱）
  const chart = await page.evaluate(() => {
    const el = document.querySelector('.wla .chart-bar')
    if (!el) return null
    const c = el.querySelector('canvas')
    return { hasCanvas: !!c, w: c ? c.clientWidth : 0, boxW: el.clientWidth }
  })
  check('趋势图 canvas 已渲染', !!chart && chart.hasCanvas, JSON.stringify(chart))
  check('趋势图宽度 > 0（防 0 宽度陷阱）', !!chart && chart.w > 0, `w=${chart && chart.w}`)

  // 7. 趋势图卡 8 列跨度占比
  const trendRatio = await page.evaluate(() => {
    const grid = document.querySelector('.wla .bento-grid')
    const card = document.querySelector('.wla .chart-bar')?.closest('.card')
    if (!grid || !card) return -1
    return card.getBoundingClientRect().width / grid.getBoundingClientRect().width
  })
  check('趋势图卡占约 8/12 宽（左右分栏）', trendRatio > 0.6 && trendRatio < 0.72, `占比=${trendRatio.toFixed(3)}`)

  // 8. 快捷预设
  const presets = await page.$$eval('.wla-presets .el-radio-button', (els) =>
    els.map((e) => e.innerText.trim()),
  )
  check('快捷预设数为 5', presets.length === 5, `实际=${presets.length}`)
  check(
    '快捷预设文案正确',
    presets.join(',') === '数据区间,近 3 月,近 6 月,近 12 月,本年',
    presets.join(','),
  )

  // 9. 按 SA 汇总表
  const saRows = await page.$$eval('.wla-card', (cardEls) => {
    const c = cardEls.find((x) => x.querySelector('.wla-card-title')?.innerText.includes('按 SA 汇总'))
    return c ? c.querySelectorAll('.el-table__body-wrapper tbody tr').length : -1
  })
  check('按 SA 汇总表行数 = 接口 by_sa.length', saRows === api.by_sa.length, `dom=${saRows} api=${api.by_sa.length}`)

  const barCount = await page.$$eval('.wla-bars .wla-bar-row', (e) => e.length)
  check('SA 条形图渲染', barCount === Math.min(10, api.by_sa.length), `dom=${barCount}`)

  // 10. 按系统分布（激活原死数据 by_system）
  const sysRows = await page.$$eval('.wla-card', (cardEls) => {
    const c = cardEls.find((x) => x.querySelector('.wla-card-title')?.innerText.trim() === '按系统分布')
    return c ? c.querySelectorAll('.el-table__body-wrapper tbody tr').length : -1
  })
  check(
    '按系统分布表行数 = 接口 by_system.length',
    sysRows === api.by_system.length,
    `dom=${sysRows} api=${api.by_system.length}`,
  )

  // 11. 需求明细
  const detailRows = await page.evaluate(() => {
    const c = [...document.querySelectorAll('.wla-card')].find(
      (x) => x.querySelector('.wla-card-title')?.innerText.trim() === '需求明细',
    )
    return c ? c.querySelectorAll('.el-table__body-wrapper tbody tr').length : -1
  })
  check(
    '需求明细表行数 = min(total, 20)',
    detailRows === Math.min(api.requirements.total, 20),
    `dom=${detailRows} api=${api.requirements.total}`,
  )

  // 12. 筛选栏 + 默认区间锚定 data_range
  check('筛选栏月份控件存在', (await page.$('.wla-filter .el-date-editor')) !== null)
  const domRange = await page.evaluate(() => {
    const inputs = document.querySelectorAll('.wla-filter .el-date-editor input')
    return [inputs[0]?.value || '', inputs[1]?.value || '']
  })
  check(
    '后端默认区间锚定 data_range',
    !!dr.has_data && api.range.month_from === dr.month_from && api.range.month_to === dr.month_to,
    `range=${api.range.month_from}~${api.range.month_to} data_range=${dr.month_from}~${dr.month_to}`,
  )
  check(
    '日期控件回填 = 默认区间',
    domRange[0] === api.range.month_from && domRange[1] === api.range.month_to,
    `dom=${domRange.join('~')}`,
  )

  // 13. 未归月卡
  const unmonthTitle = await page.evaluate(() => {
    const el = [...document.querySelectorAll('.wla-card-title')].find((e) => e.innerText.includes('未归月需求'))
    return el ? el.innerText.trim() : null
  })
  if (api.unmonth.length) {
    check('未归月卡数量 = 接口 unmonth.length', unmonthTitle === `未归月需求（${api.unmonth.length}）`, `${unmonthTitle}`)
    // 提示条 chip 点击 → 滚动定位
    const located = await page.evaluate(async () => {
      const chip = document.querySelector('.wla .pm-notice__chip.is-link')
      if (!chip) return false
      chip.click()
      await new Promise((r) => setTimeout(r, 1200))
      const el = document.getElementById('wla-unmonth')
      if (!el) return false
      const top = el.getBoundingClientRect().top
      return top > -20 && top < window.innerHeight
    })
    check('点击「未归月」chip 可滚动定位到未归月卡', located)
  } else {
    check('无未归月需求时不显示该卡', unmonthTitle === null)
  }

  // 14. 补时间弹窗（打开后取消，不落库）
  if (api.unmonth.length) {
    const opened = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('.el-button')].filter((b) => b.innerText.trim() === '补时间')
      if (!btns.length) return false
      btns[0].click()
      return true
    })
    await sleep(800)
    const dlg = await page.evaluate(() =>
      [...document.querySelectorAll('.el-dialog__title')].some((t) => t.innerText.includes('补录「启动开发」时间')),
    )
    check('「补时间」弹窗可打开', opened && dlg)
    await page.keyboard.press('Escape')
    await sleep(300)
  }

  // 15. 快捷预设生效（放最后：会改变统计区间）
  //     用「近 6 月」而非「近 3 月」——后者可能与 data_range 恰好重合，无法证明点击生效。
  const clicked = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('.wla-presets .el-radio-button')].find(
      (e) => e.innerText.trim() === '近 6 月',
    )
    if (!btn) return false
    btn.querySelector('input')?.click()
    btn.click()
    return true
  })
  await sleep(2500)
  const after = await page.evaluate(() => {
    const i = document.querySelectorAll('.wla-filter .el-date-editor input')
    return [i[0]?.value || '', i[1]?.value || '']
  })
  const now = new Date()
  const t6 = now.getFullYear() * 12 + now.getMonth() - 5
  const expectFrom = mm(Math.floor(t6 / 12), (t6 % 12) + 1)
  const expectTo = mm(now.getFullYear(), now.getMonth() + 1)
  check(
    '点「近 6 月」后区间切换到该预置窗口',
    clicked && after[0] === expectFrom && after[1] === expectTo,
    `after=${after.join('~')} expect=${expectFrom}~${expectTo}`,
  )

  const api6 = (
    await (
      await fetch(
        `${API}/api/v1/workload-analysis/stats?month_from=${expectFrom}&month_to=${expectTo}&page=1&page_size=20`,
      )
    ).json()
  ).data
  const domTotal6 = await page.evaluate(() => {
    const el = [...document.querySelectorAll('.wla-stats .wla-stat')].find(
      (e) => e.querySelector('.wla-stat-label')?.innerText.trim() === '总工作量(人天)',
    )
    return el?.querySelector('.wla-stat-num')?.innerText.trim() || ''
  })
  check(
    '切换区间后汇总卡随之刷新且与接口一致',
    num(domTotal6) === num(api6.summary.workload_total),
    `dom=${domTotal6} api=${api6.summary.workload_total}`,
  )

  const activeChip = await page.evaluate(
    () => document.querySelector('.wla-presets .el-radio-button.is-active')?.innerText.trim() || '',
  )
  check('预设 chip 高亮跟随', activeChip === '近 6 月', `高亮=${activeChip}`)

  check('无 Vue 运行时报错', errs.length === 0, errs.slice(0, 3).join(' ;; '))

  await browser.close()

  console.log(log.join('\n'))
  const failed = log.filter((l) => l.startsWith('FAIL'))
  console.log(`\n${log.length - failed.length}/${log.length} passed`)
  process.exit(failed.length ? 1 : 0)
})().catch((e) => {
  console.error('E2E 执行异常：', e)
  process.exit(1)
})
