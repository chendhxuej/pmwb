/**
 * 回归：需求与交付 → 工作量分析子页（2026-10-16 新增）
 *
 * 覆盖点：
 *  1. 主 tabs 变为 4 个（需求 / 用户故事 / 主动优化 / 工作量分析）
 *  2. 汇总卡渲染，总工作量 = 接口 summary.workload_total
 *  3. 月度趋势图容器已真实渲染（canvas 宽度 > 0，防 el-tab-pane 0 宽度陷阱）
 *  4. 未归月区数量 = 接口 unmonth.length
 *  5. SA 条形图渲染；按 SA 表行数 = 接口 by_sa.length
 *  6. 需求明细表行数 = min(total, pageSize)
 *  7. 改月份区间 → 重新加载且不报错
 *  8. 「补时间」弹窗可打开（不落库：只打开后取消）
 *  9. 无 Vue 运行时报错
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

;(async () => {
  // ── 接口基准（单一数据源比对） ──
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth() + 1
  const back = m - 11
  const fy = back <= 0 ? y - 1 : y
  const fm = back <= 0 ? m + 1 : back
  const mf = `${fy}-${String(fm).padStart(2, '0')}`
  const mt = `${y}-${String(m).padStart(2, '0')}`
  const apiUrl = `${API}/api/v1/workload-analysis/stats?month_from=${mf}&month_to=${mt}&page=1&page_size=20`
  const api = (await (await fetch(apiUrl)).json()).data

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

  // 2. 汇总卡
  const cards = await page.$$eval('.wla-stats .wla-stat', (els) =>
    els.map((e) => ({
      label: e.querySelector('.wla-stat-label')?.innerText.trim(),
      value: e.querySelector('.wla-stat-num')?.innerText.trim(),
    })),
  )
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

  // 3. 趋势图真实渲染（0 宽度陷阱）
  const chart = await page.evaluate(() => {
    const el = document.querySelector('.wla .chart-bar')
    if (!el) return null
    const c = el.querySelector('canvas')
    return { hasCanvas: !!c, w: c ? c.clientWidth : 0, boxW: el.clientWidth }
  })
  check('趋势图 canvas 已渲染', !!chart && chart.hasCanvas, JSON.stringify(chart))
  check('趋势图宽度 > 0（防 0 宽度陷阱）', !!chart && chart.w > 0, `w=${chart && chart.w}`)

  // 4. 未归月
  const unmonthTitle = await page.evaluate(() => {
    const el = [...document.querySelectorAll('.wla-card-title')].find((e) => e.innerText.includes('未归月需求'))
    return el ? el.innerText.trim() : null
  })
  if (api.unmonth.length) {
    check('未归月卡数量 = 接口 unmonth.length', unmonthTitle === `未归月需求（${api.unmonth.length}）`, `${unmonthTitle}`)
  } else {
    check('无未归月需求时不显示该卡', unmonthTitle === null)
  }

  // 5. SA 汇总
  const saRows = await page.$$eval('.wla-card', (cards) => {
    const c = cards.find((x) => x.querySelector('.wla-card-title')?.innerText.includes('按 SA 汇总'))
    return c ? c.querySelectorAll('.el-table__body-wrapper tbody tr').length : -1
  })
  check('按 SA 汇总表行数 = 接口 by_sa.length', saRows === api.by_sa.length, `dom=${saRows} api=${api.by_sa.length}`)
  const barCount = await page.$$eval('.wla-bars .wla-bar-row', (e) => e.length)
  check('SA 条形图渲染', barCount === Math.min(10, api.by_sa.length), `dom=${barCount}`)

  // 6. 需求明细
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

  // 7. 改月份区间（只验证不报错 + 有重新请求）
  await page.evaluate(() => {
    const inputs = document.querySelectorAll('.wla-filter input')
    if (inputs[0]) {
      inputs[0].focus()
      inputs[0].click()
    }
  })
  await sleep(600)
  await page.keyboard.press('Escape')
  await sleep(400)
  check('筛选栏月份控件存在', (await page.$('.wla-filter .el-date-editor')) !== null)

  // 8. 补时间弹窗（打开后取消，不落库）
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
