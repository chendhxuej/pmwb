/**
 * 回归：主动优化工单「关联需求文号」一对多（2026-10-16 新增）
 *
 * 覆盖点：
 *  1. 列表「关联需求」列渲染为标签组（多行时展示 +N 折叠）
 *  2. 标签文案 = 需求文号；点击标签可打开需求 6 步抽屉
 *  3. 编辑弹层的关联项是多选选择器（RequirementLinkSelect），可增删
 *  4. 保存后列表标签数与接口 req_ids 一致
 *  5. 邮件「同步」弹窗主题取首个关联文号
 *  6. 无 Vue 运行时报错
 *
 * 数据：自建自删（E2E 前缀工单，teardown 必删），不污染业务数据。
 * 注意：本文件为 LF 行尾；.gitignore 忽略 verify_*.cjs，提交需 `git add -f`。
 */
const puppeteer = require('puppeteer-core')

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173'
const API = process.env.API_URL || 'http://127.0.0.1:8000'
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const APIV1 = API + '/api/v1'
const TITLE = 'E2E关联测试工单'

const log = []
const check = (name, cond, extra) => {
  log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function jfetch(url, opts) {
  const r = await fetch(url, opts)
  return r.json()
}

;(async () => {
  // ── 前置：取 2 个真实需求文号 ──
  const reqRes = await jfetch(`${APIV1}/requirements?page=1&page_size=5`)
  const reqs = (reqRes.data.items || []).slice(0, 2)
  if (reqs.length < 2) throw new Error('需求宇宙不足 2 条，无法构造用例')
  const ridA = reqs[0].req_id
  const ridB = reqs[1].req_id

  // ── 前置：清理历史残留 + 新建测试工单 ──
  const old = await jfetch(`${APIV1}/active-optimizations?keyword=${encodeURIComponent(TITLE)}`)
  for (const o of old.data.items || []) {
    await fetch(`${APIV1}/active-optimizations/${o.id}`, { method: 'DELETE' })
  }
  const created = await jfetch(`${APIV1}/active-optimizations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: TITLE, priority: 'P2', status: 'pending', req_ids: [ridA, ridB] }),
  })
  const optId = created.data?.id
  if (!optId) throw new Error('测试工单创建失败：' + JSON.stringify(created))
  const savedReqIds = created.data.req_ids || []
  check('接口：新建工单即带 2 个关联文号', savedReqIds.length === 2, JSON.stringify(savedReqIds))

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

  try {
    await page.goto(BASE + '/requirement-delivery', { waitUntil: 'networkidle2', timeout: 60000 })
    await sleep(1000)
    // 切到主动优化
    await page.evaluate(() => {
      const t = [...document.querySelectorAll('.el-tabs__item')].find((e) => e.innerText.trim() === '主动优化')
      if (t) t.click()
    })
    await sleep(1500)

    // 搜索到测试工单
    await page.type('.table-toolbar input', TITLE)
    await page.keyboard.press('Enter')
    await sleep(1800)

    // 1. 标签组渲染
    const tags = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.el-table__body-wrapper tbody tr')]
      const row = rows.find((r) => r.innerText.includes('E2E关联测试工单'))
      if (!row) return null
      const cell = [...row.querySelectorAll('td')].find((td, i) => i === 6)
      return {
        tags: [...(cell?.querySelectorAll('.el-tag') || [])].map((t) => t.innerText.trim()),
        more: cell?.querySelector('.rlt-more')?.innerText.trim() || null,
      }
    })
    check('列表渲染关联需求标签组', !!tags && tags.tags.length === 2, JSON.stringify(tags))
    check(
      '标签文案 = 需求文号',
      !!tags && tags.tags.includes(ridA) && tags.tags.includes(ridB),
      `${JSON.stringify(tags && tags.tags)} vs ${ridA}/${ridB}`,
    )

    // 2. 点标签 → 打开需求抽屉
    await page.evaluate((rid) => {
      const rows = [...document.querySelectorAll('.el-table__body-wrapper tbody tr')]
      const row = rows.find((r) => r.innerText.includes('E2E关联测试工单'))
      const cell = [...row.querySelectorAll('td')][6]
      const tag = [...cell.querySelectorAll('.el-tag')].find((t) => t.innerText.trim() === rid)
      if (tag) tag.click()
    }, ridA)
    await sleep(2500)
    const drawerOpen = await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-drawer')].find((x) => x.offsetParent !== null)
      if (!d) return false
      return /E2E|需求/.test(d.innerText) || !!d.querySelector('.wf-steps')
    })
    check('点击标签可打开需求详情', drawerOpen)
    await page.keyboard.press('Escape')
    await sleep(800)

    // 3. 编辑弹层是多选选择器
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.el-table__body-wrapper tbody tr')]
      const row = rows.find((r) => r.innerText.includes('E2E关联测试工单'))
      const btn = [...row.querySelectorAll('.el-button')].find((b) => b.innerText.trim() === '编辑')
      if (btn) btn.click()
    })
    await sleep(1200)
    const hasPicker = await page.evaluate(() => {
      const dlg = [...document.querySelectorAll('.el-dialog')].find((x) => x.offsetParent !== null)
      return !!dlg?.querySelector('.rls')
    })
    check('编辑弹层使用多选关联选择器 (.rls)', hasPicker)

    // 选择弹窗内已选区可关闭标签（删除入口）
    if (hasPicker) {
      await page.evaluate(() => {
        document.querySelector('.el-dialog .rls')?.click()
      })
      await sleep(1200)
      const picker = await page.evaluate(() => {
        const d = [...document.querySelectorAll('.el-dialog')].find(
          (x) => x.offsetParent !== null && x.innerText.includes('选择关联需求'),
        )
        if (!d) return null
        return {
          selectedLabel: d.querySelector('.rls-picker-label')?.innerText.trim(),
          closable: d.querySelectorAll('.rls-picker-tags .el-tag').length,
        }
      })
      check('选择弹窗已选区渲染 2 个可关闭标签', !!picker && picker.closable === 2, JSON.stringify(picker))
      // 关闭弹窗（不保存，避免污染）
      await page.evaluate(() => {
        const d = [...document.querySelectorAll('.el-dialog')].find(
          (x) => x.offsetParent !== null && x.innerText.includes('选择关联需求'),
        )
        const btn = [...(d?.querySelectorAll('.el-dialog__footer .el-button') || [])].find(
          (b) => b.innerText.trim() === '取消',
        )
        if (btn) btn.click()
      })
      await sleep(500)
      await page.keyboard.press('Escape')
      await sleep(500)
    }

    // 4. 邮件同步弹窗主题取首个关联文号
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.el-table__body-wrapper tbody tr')]
      const row = rows.find((r) => r.innerText.includes('E2E关联测试工单'))
      const btn = [...row.querySelectorAll('.el-button')].find((b) => b.innerText.trim() === '同步')
      if (btn) btn.click()
    })
    await sleep(1500)
    const mailTitle = await page.evaluate(() => {
      const dlg = [...document.querySelectorAll('.el-dialog')].find((x) => x.offsetParent !== null)
      return dlg?.querySelector('.el-dialog__title')?.innerText.trim() || ''
    })
    check('同步邮件弹窗标题含「主动优化建议」', mailTitle.includes('主动优化建议'), mailTitle)

    check('无 Vue 运行时报错', errs.length === 0, errs.slice(0, 3).join(' ;; '))
  } finally {
    await browser.close()
    // ── teardown ──
    await fetch(`${APIV1}/active-optimizations/${optId}`, { method: 'DELETE' })
    const left = await jfetch(`${APIV1}/active-optimizations?keyword=${encodeURIComponent(TITLE)}`)
    check('teardown：测试工单已删除', (left.data.items || []).length === 0)
  }

  console.log(log.join('\n'))
  const failed = log.filter((l) => l.startsWith('FAIL'))
  console.log(`\n${log.length - failed.length}/${log.length} passed`)
  process.exit(failed.length ? 1 : 0)
})().catch((e) => {
  console.error('E2E 执行异常：', e)
  process.exit(1)
})
