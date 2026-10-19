/**
 * 验证「需求与交付 - 生产部署 - 厂家开发状态」（2026-10-16 新增）
 *
 * 背景：
 *   厂家维度此前不存在。本回归确保新卡片在**真实 DOM** 里渲染可用：
 *     1. 生产部署步骤出现「厂家开发状态」卡片与口径提示
 *     2. 厂家行真实渲染（厂家/系统、负责人、工作量、开发单号、状态）
 *     3. 状态下拉的选项是**中文标签**（来自状态注册表 vendor_dev 域），
 *        不能退化成 pending/live 等英文 key（2026-09-20 同类事故）
 *     4. 0 人天厂家显示灰色「0 人天（不参与联动）」标签
 *     5. 「系统别名映射」弹窗**只读**（无输入框），并提供「去人员中台维护」跳转；
 *        跳转后人员中台深链定位到组织管理 Tab，表格出现映射三列
 *
 * 运行：
 *   node tests/e2e/verify_vendor_dev.cjs
 * 前置：前端 5173 + 后端 8000 均已启动。
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_BASE || 'http://127.0.0.1:8000/api/v1';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;
const RENDER_WAIT = Number(process.env.RENDER_WAIT) || 2500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let pass = 0;
let fail = 0;

function check(name, ok, extra = '') {
  if (ok) { pass++; console.log(`  [OK]   ${name}${extra ? ' -> ' + extra : ''}`); }
  else { fail++; console.log(`  [FAIL] ${name}${extra ? ' -> ' + extra : ''}`); }
}

/** 找一个「有团队评估且至少 1 个活跃厂家」的需求（同时返回 0 人天系统名，用于校验剔除） */
async function pickRequirement(page) {
  return page.evaluate(async (API) => {
    const list = await fetch(`${API}/requirements?page=1&page_size=60`).then((r) => r.json());
    const rows = list?.data?.items || list?.data?.list || [];
    for (const r of rows) {
      const evs = await fetch(`${API}/requirements/${encodeURIComponent(r.req_id)}/evaluations`)
        .then((r2) => r2.json()).then((j) => j?.data || []).catch(() => []);
      const active = evs.filter((e) => Number(e.workload) > 0 && e.system_name);
      const zero = evs.filter((e) => !(Number(e.workload) > 0) && e.system_name);
      if (active.length >= 1) {
        return {
          req_id: r.req_id,
          active: new Set(active.map((e) => e.system_name)).size,
          activeNames: [...new Set(active.map((e) => e.system_name))],
          zeroNames: [...new Set(zero.map((e) => e.system_name))],
        };
      }
    }
    return null;
  }, API);
}

async function run() {
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
  } catch (err) {
    console.error(`[FATAL] 浏览器启动失败: ${err.message}`);
    process.exit(2);
  }

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000 });
    page.on('pageerror', (e) => console.log(`  [PAGE-ERROR] ${e.message}`));

    await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2', timeout: TIMEOUT });
    await sleep(RENDER_WAIT);

    const target = await pickRequirement(page);
    if (!target) {
      console.log('[FATAL] 未找到含活跃厂家的需求，无法验证');
      await browser.close();
      process.exit(2);
    }
    console.log(`\n选用需求：${target.req_id}（活跃厂家 ${target.active} / 0人天 ${target.zero}）\n`);

    // 打开该需求的工作流抽屉
    const opened = await page.evaluate((reqId) => {
      const rows = [...document.querySelectorAll('.el-table__body tr')];
      for (const tr of rows) {
        if ((tr.innerText || '').includes(reqId)) { tr.click(); return true; }
      }
      return false;
    }, target.req_id);
    check('点击需求行打开工作流抽屉', opened);
    await sleep(2000);

    // 切到「生产部署」步骤（第 6 步）
    const stepped = await page.evaluate(() => {
      const dots = [...document.querySelectorAll('.pm-step')];
      if (dots.length >= 6) { dots[5].click(); return true; }
      return false;
    });
    check('切换到步骤6「生产部署」', stepped);
    await sleep(2500);

    // 1) 卡片与口径提示
    const card = await page.evaluate(() => {
      const labels = [...document.querySelectorAll('.card-label')].map((e) => e.innerText.trim());
      const hint = [...document.querySelectorAll('.hint-text')]
        .map((e) => e.innerText.trim()).find((t) => t.includes('厂家团队取自') || t.includes('工作量'));
      return { labels, hint: hint || '' };
    });
    check('生产部署含「厂家开发状态」卡片',
      card.labels.some((l) => l.includes('厂家开发状态')), card.labels.join(' | '));
    check('展示厂家来源口径提示', card.hint.includes('工作量'), card.hint.slice(0, 40));

    // 2) 厂家行真实渲染
    // 注意：Element Plus 的表头在独立的 .el-table__header-wrapper，不在 body-wrapper 内
    const rows = await page.evaluate(() => {
      for (const t of document.querySelectorAll('.el-table')) {
        const head = [...t.querySelectorAll('.el-table__header th')].map((th) => th.innerText.trim());
        if (head.includes('厂家 / 系统')) {
          const body = [...t.querySelectorAll('.el-table__body tr')].map((tr) =>
            [...tr.querySelectorAll('td')].map((td) => td.innerText.trim())
          );
          return { head, body };
        }
      }
      return null;
    });
    check('厂家开发状态表格渲染', !!rows, rows ? `表头 ${rows.head.join('/')}` : '未找到');
    if (rows) {
      // ★ 核心口径：厂家行 = 活跃厂家（workload>0），0 人天系统不得建行
      check('厂家行数 = 活跃厂家数', rows.body.length === target.active,
        `DOM ${rows.body.length} vs 活跃 ${target.active}`);
      check('表格含「工作量」列且单位为「人天」',
        rows.head.includes('工作量') && rows.body.some((r) => r.some((c) => c.includes('人天'))),
        rows.body[0] ? rows.body[0].join(' | ') : '');
      if (target.zeroNames.length) {
        const flat = rows.body.map((r) => r.join(' ')).join(' ');
        const leaked = target.zeroNames.filter((n) => flat.includes(n));
        check('0 人天系统未出现在厂家清单', leaked.length === 0,
          leaked.length ? `泄漏 ${leaked.join(',')}` : `已剔除 ${target.zeroNames.join(',')}`);
      } else {
        console.log('  [SKIP] 该需求无 0 人天系统，跳过剔除断言');
      }
    }

    // 3) 系统别名映射 · 只读总览
    //    维护入口已迁至「人员中台 → 组织管理」，这里只断言「只读 + 可跳转」。
    //    注意：必须先于「状态下拉」执行。关下拉的 Escape / 点遮罩都会把 el-drawer
    //    一起关掉，导致后续断言全部失效（血泪：别在抽屉里按 Escape）。
    const dlgDiag = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button')].map((b) => (b.innerText || '').trim());
      const btn = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').includes('系统别名映射'));
      if (btn) btn.click();
      return { found: !!btn, aliasBtns: btns.filter((t) => t.includes('别名')) };
    });
    check('找到「系统别名映射」按钮', dlgDiag.found, dlgDiag.aliasBtns.join(' | '));
    await sleep(2000);
    const dlg = await page.evaluate(() => {
      const all = [...document.querySelectorAll('.el-dialog')];
      const d = all.find((x) => x.offsetParent !== null);
      if (!d) return { count: all.length, visible: 0 };
      const texts = [...d.querySelectorAll('button')].map((b) => (b.innerText || '').trim());
      return {
        count: all.length,
        visible: 1,
        title: (d.querySelector('.el-dialog__title') || {}).innerText || '',
        // 只读校验：dialog 内不应存在任何可输入控件（表头搜索框除外，本弹窗没有）
        editable: d.querySelectorAll('input, textarea').length,
        hasGoto: texts.some((t) => t.includes('去人员中台维护')),
        notSourceHint: (d.innerText || '').includes('不是厂家清单的源头'),
      };
    });
    check('系统别名映射弹窗可打开', dlg.visible === 1,
      dlg.visible ? dlg.title : `dialog 总数 ${dlg.count}，可见 0`);
    if (dlg.visible) {
      check('弹窗只读（无输入框）', dlg.editable === 0, `可编辑控件数 ${dlg.editable}`);
      check('弹窗声明「非厂家清单源头」', dlg.notSourceHint);
      check('弹窗含「去人员中台维护」入口', dlg.hasGoto);
    }
    // 关掉弹窗，回到抽屉（「跳转人员中台」的验证放到脚本最后，避免导航冲掉抽屉）
    await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find((x) => x.offsetParent !== null);
      const close = d && [...d.querySelectorAll('button')].find((b) => (b.innerText || '').includes('关闭'));
      if (close) close.click();
      else if (d) { const x = d.querySelector('.el-dialog__headerbtn'); if (x) x.click() }
    });
    await sleep(900);

    // 4) 状态下拉必须是中文标签（注册表驱动，禁退化英文 key）—— 放最后，无需关下拉
    const opts = await page.evaluate(() => {
      const sels = [...document.querySelectorAll('.el-select')];
      for (const s of sels) {
        const txt = s.innerText || '';
        if (/待开发|开发中|已上线|已完成/.test(txt)) { s.click(); return true; }
      }
      return false;
    });
    await sleep(900);
    const optTexts = await page.evaluate(() =>
      [...document.querySelectorAll('.el-select-dropdown__item')]
        .map((e) => e.innerText.trim())
        .filter((t) => /待开发|开发中|已上线|已完成/.test(t))
    );
    check('状态下拉可展开', opts, `${optTexts.length} 项`);
    check('状态选项为中文标签（未退化英文 key）',
      optTexts.length > 0 && optTexts.every((t) => !/^(pending|developing|live|completed)$/.test(t)),
      optTexts.join(' / '));

    // 5) 「去人员中台维护」跳转 + 深链定位到组织管理 Tab + 映射三列可见
    //    放在最后：一旦触发路由跳转，需求抽屉就没了。
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').includes('系统别名映射'));
      if (btn) btn.click();
    });
    await sleep(2000);
    await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find((x) => x.offsetParent !== null);
      const btn = d && [...d.querySelectorAll('button')].find((b) => (b.innerText || '').includes('去人员中台维护'));
      if (btn) btn.click();
    });
    await sleep(2500);
    const jumped = page.url()
    check('跳转到人员中台 /basic-data?tab=org', /\/basic-data/.test(jumped) && /tab=org/.test(jumped), jumped)
    const pcTab = await page.evaluate(() => {
      // 取当前可见的 tab-pane（其余 pane 是 display:none，innerText 会退化成 textContent 造成误判）
      const pane = [...document.querySelectorAll('.el-tab-pane')].find((p) => p.offsetParent !== null)
      if (!pane) return { visible: false, heads: '' }
      const heads = [...pane.querySelectorAll('th')].map((t) => (t.innerText || '').trim()).filter(Boolean)
      return { visible: true, heads: heads.join(' | ') }
    })
    check('深链定位到组织管理 Tab', pcTab.visible && /组织类型/.test(pcTab.heads), pcTab.heads)
    check('组织表格含映射三列（类型/目标系统名/系统别名）',
      /组织类型/.test(pcTab.heads) && /目标系统名/.test(pcTab.heads) && /系统别名/.test(pcTab.heads),
      pcTab.heads)
    check('组织表格含「配置映射管理」行内入口',
      await page.evaluate(() =>
        [...document.querySelectorAll('.el-tab-pane')]
          .filter((p) => p.offsetParent !== null)
          .some((p) => [...p.querySelectorAll('button')].some((b) => (b.innerText || '').includes('配置映射管理')))))
    // 目标系统名下拉支持「新增平台」（2026-10-19）：弹窗内该字段旁必须有「新增」按钮，
    // 且 select 可输入（filterable）；点按钮应弹出命名输入框（不实际创建，避免污染业务数据）
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.el-table__body tr')]
      const row = rows.find((r) => (r.innerText || '').includes('订单中心')) || rows[0]
      const edit = [...(row ? row.querySelectorAll('button') : [])].find((b) => (b.innerText || '').trim() === '编辑')
      if (edit) edit.click()
    })
    await sleep(1500)
    const tgtField = await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find((x) => x.offsetParent !== null)
      if (!d) return { visible: false }
      const items = [...d.querySelectorAll('.el-form-item')]
      const tgt = items.find((it) => ((it.querySelector('.el-form-item__label') || {}).innerText || '').includes('目标系统名'))
      if (!tgt) return { visible: true, found: false }
      return {
        visible: true,
        found: true,
        btnTexts: [...tgt.querySelectorAll('button')].map((b) => (b.innerText || '').trim()),
        filterable: !!tgt.querySelector('.el-select input'),
      }
    })
    check('组织弹窗「目标系统名」旁有「新增」按钮',
      tgtField.found && (tgtField.btnTexts || []).includes('新增'), JSON.stringify(tgtField.btnTexts || []))
    check('「目标系统名」下拉可输入搜索（filterable）', !!tgtField.filterable)
    await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find((x) => x.offsetParent !== null)
      const close = d && d.querySelector('.el-dialog__headerbtn')
      if (close) close.click()
    })
    await sleep(800)
    // 反向验证深链确实生效（不是默认值凑巧命中）
    await page.goto(`${BASE}/basic-data?tab=staff`, { waitUntil: 'networkidle0' })
    await sleep(2500)
    const staffTab = await page.evaluate(() => {
      const pane = [...document.querySelectorAll('.el-tab-pane')].find((p) => p.offsetParent !== null)
      if (!pane) return { visible: false, heads: '' }
      const heads = [...pane.querySelectorAll('th')].map((t) => (t.innerText || '').trim()).filter(Boolean)
      return { visible: true, heads: heads.join(' | ') }
    })
    check('深链 ?tab=staff 生效（排除默认值凑巧命中）',
      staffTab.visible && /姓名/.test(staffTab.heads) && !/组织类型/.test(staffTab.heads), staffTab.heads)

    console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
    await browser.close();
    process.exit(fail ? 1 : 0);
  } catch (err) {
    console.error(`[FATAL] ${err.message}`);
    if (browser) await browser.close();
    process.exit(2);
  }
}

run();
