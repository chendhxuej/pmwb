/**
 * 回归：AI中心 → AI总结 → 需求开发超期专题分析（2026-10-19 新增）
 *
 * 覆盖点：
 *  1. 左侧分类出现「开发超期分析」
 *  2. 生成弹窗下拉含「需求开发超期专题分析」
 *  3. 选中后：超期天数默认 25；起始日期项隐藏；结束日期标签变为「统计基准日」
 *  4. 手改超期天数为 30 后仍保留（不被 watch 重置）
 *  5. 列表中存在 report_type=dev_overdue 的报告，点开详情渲染出明细表（11 列 / 9 行数据）
 *  6. 详情含五个章节标题 + 口径说明；无 Vue 运行时报错
 *
 * 说明：本脚本**不点「生成」**（会真实调 LLM 约 60s），生成链路由
 *      backend/tests/test_dev_overdue_analysis.py 的接口用例覆盖。
 * 红线：build 过 ≠ 能渲染，必须真实 DOM 断言。
 * 注意：本文件为 LF 行尾；.gitignore 忽略 verify_*.cjs，提交需 `git add -f`。
 */
const puppeteer = require('puppeteer-core')

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173'
const API = process.env.API_URL || 'http://127.0.0.1:8000'
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const ROUTE = '/ai-center/summary'

const log = []
const check = (name, cond, extra) => {
  log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  // ── 接口基准：确认库里至少有一份 dev_overdue 报告 ──
  const apiList = (await (await fetch(`${API}/api/v1/work-reports`)).json()).data || []
  const target = apiList.find((r) => r.report_type === 'dev_overdue')
  check('接口存在 dev_overdue 报告', !!target, target ? `id=${target.id}` : '无，请先调 /generate 生成一次')

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 1560, height: 980 })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })

  await page.goto(`${BASE}${ROUTE}`, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForSelector('.cat-list .cat-item', { timeout: 20000 })
  await sleep(600)

  // 1) 左侧分类
  const catTexts = await page.$$eval('.cat-list .cat-item .cat-name', (els) => els.map((e) => e.textContent.trim()))
  check('左侧分类含「开发超期分析」', catTexts.includes('开发超期分析'), catTexts.join('/'))
  check('左侧分类顺序（全部/日报/周报/月报/自定义/需求分析/开发超期分析）',
    catTexts.join(',') === '全部,日报,周报,月报,自定义,需求分析,开发超期分析', catTexts.join(','))

  // 5) 列表里能找到该报告并点开
  const rowHit = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.el-table__body tbody tr')]
    for (let i = 0; i < rows.length; i++) {
      if (rows[i].textContent.includes('需求开发超期专题分析')) return i
    }
    return -1
  })
  check('列表存在「需求开发超期专题分析」行', rowHit >= 0, `rowIndex=${rowHit}`)

  if (rowHit >= 0) {
    await page.evaluate((i) => {
      const rows = [...document.querySelectorAll('.el-table__body tbody tr')]
      rows[i].querySelector('.title-link').click()
    }, rowHit)
    await page.waitForSelector('.el-drawer__body .wr-report', { timeout: 20000 })
    await sleep(900)

    const detail = await page.evaluate(() => {
      const root = document.querySelector('.el-drawer__body .wr-report')
      const tables = [...root.querySelectorAll('table')]
      const t = tables[0]
      const ths = t ? [...t.querySelectorAll('thead th')].map((x) => x.textContent.trim()) : []
      const rows = t ? t.querySelectorAll('tbody tr').length : 0
      return {
        h2: [...root.querySelectorAll('h2')].map((x) => x.textContent.trim()),
        h1: (root.querySelector('h1') || {}).textContent || '',
        ths,
        rows,
        text: root.innerText,
      }
    })
    check('详情 H1 = 需求开发超期专题分析（统计基准日 …）',
      detail.h1.includes('需求开发超期专题分析') && detail.h1.includes('统计基准日'), detail.h1)
    check('五个章节齐全',
      ['一、总体概况', '二、超期需求明细', '三、分布画像', '四、研判与建议', '五、口径与数据质量说明']
        .every((s) => detail.h2.some((h) => h.includes(s))), detail.h2.join('/'))
    check('明细表 11 列', detail.ths.length === 11, detail.ths.join('|'))
    check('明细表表头含「已开发」「厂家开发状态」「风险」',
      ['已开发', '厂家开发状态', '风险'].every((k) => detail.ths.some((h) => h.includes(k))), detail.ths.join('|'))
    check('明细表行数 = 9（当前超期对象数）', detail.rows === 9, `rows=${detail.rows}`)
    check('正文含口径阈值「超过 25 天」', detail.text.includes('超过 25 天'))
    check('正文含回填标记', detail.text.includes('历史回填'))

    // 关闭抽屉
    await page.keyboard.press('Escape')
    await sleep(700)
  }

  // 2-4) 生成弹窗表单行为
  await sleep(900) // 等抽屉遮罩完全卸载
  const clicked = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.pm-page-header__actions button')]
    const b = btns.find((x) => x.textContent.includes('生成报告'))
    if (!b) return false
    b.click()
    return true
  })
  check('「生成报告」按钮可点击', clicked)
  await page.waitForSelector('.el-dialog', { visible: true, timeout: 15000 })
  await sleep(700)

  // 打开报告类型下拉
  await page.evaluate(() => {
    const items = [...document.querySelectorAll('.el-dialog .el-form-item')]
    const it = items.find((x) => x.textContent.includes('报告类型'))
    it.querySelector('.el-select__wrapper, .el-input').click()
  })
  await sleep(700)
  const optionTexts = await page.$$eval('.el-select-dropdown__item', (els) => els.map((e) => e.textContent.trim()))
  check('下拉含「需求开发超期专题分析」', optionTexts.includes('需求开发超期专题分析'), optionTexts.join('/'))

  // 选中
  await page.evaluate(() => {
    const opts = [...document.querySelectorAll('.el-select-dropdown__item')]
    const o = opts.find((x) => x.textContent.trim() === '需求开发超期专题分析')
    o.click()
  })
  await sleep(900)

  const form = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.el-dialog .el-form-item')]
    const byLabel = (lb) => items.find((x) => {
      const l = x.querySelector('.el-form-item__label')
      return l && l.textContent.trim().startsWith(lb)
    })
    const overdue = byLabel('超期天数')
    const start = byLabel('起始日期')
    const end = byLabel('统计基准日') || byLabel('结束日期')
    const val = overdue ? overdue.querySelector('input').value : null
    return {
      hasOverdue: !!overdue,
      overdueVal: val,
      tip: overdue ? (overdue.querySelector('.form-tip') || {}).textContent || '' : '',
      hasStart: !!start,
      endLabel: end ? end.querySelector('.el-form-item__label').textContent.trim() : '',
    }
  })
  check('显示「超期天数」项', form.hasOverdue)
  check('超期天数默认 = 25', String(form.overdueVal) === '25', `val=${form.overdueVal}`)
  check('提示文案说明「开发中且尚未上线」+「默认 25 天」',
    form.tip.includes('开发中') && form.tip.includes('25 天'), form.tip.slice(0, 60))
  check('隐藏「起始日期」项', form.hasStart === false)
  check('结束日期标签改为「统计基准日」', form.endLabel.startsWith('统计基准日'), form.endLabel)

  // 手改 30 并确认不被重置（el-input-number：原生 setter + input 事件，确保 Vue 收到）
  const overdueInput = await page.evaluateHandle(() => {
    const items = [...document.querySelectorAll('.el-dialog .el-form-item')]
    const it = items.find((x) => x.textContent.includes('超期天数'))
    return it.querySelector('.el-input-number input')
  })
  await overdueInput.asElement().click()
  await page.keyboard.down('Control')
  await page.keyboard.press('KeyA')
  await page.keyboard.up('Control')
  await page.keyboard.type('30')
  await page.keyboard.press('Tab')
  await sleep(700)
  const newVal = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.el-dialog .el-form-item')]
    const it = items.find((x) => x.textContent.includes('超期天数'))
    return it.querySelector('.el-input-number input').value
  })
  check('手改超期天数生效（30）', String(newVal) === '30', `val=${newVal}`)

  check('无 Vue 运行时报错', errors.length === 0, errors.slice(0, 3).join(' || '))

  await browser.close()
  console.log(log.join('\n'))
  const fails = log.filter((l) => l.startsWith('FAIL'))
  console.log(`\n${log.length - fails.length}/${log.length} passed`)
  process.exit(fails.length ? 1 : 0)
})().catch((e) => {
  console.error('SCRIPT ERROR', e)
  console.log(log.join('\n'))
  process.exit(2)
})
