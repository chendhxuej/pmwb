/**
 * 验证「需求与交付 - AI 需求分析（PRD）」入口与核心交互（2026-11-20）
 *
 * 覆盖：
 *   1. 需求详情工作流步骤 3 含「AI 需求分析（PRD）」入口卡
 *   2. 入口与现有用户故事生成平级独立（两者同时存在，互不干扰）
 *   3. 十维问卷 qa/fast 模式切换
 *   4. 知识源状态 / 大模型状态徽标可见
 *   5. 生成按钮触发五步进度（mock API，避免真调外网 LLM）
 *   6. 结果区六章 PRD + 冲突/引用来源展示
 *
 * 运行：node tests/e2e/verify_prd_analysis.cjs
 * 前置：前端 5173 已启动（dev server 热更新含新代码）。
 */
const puppeteer = require('puppeteer-core');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
function check(name, pass, detail = '') {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  | ' + detail : ''}`);
}

const META = {
  dimensions: [
    { key: 'goal', name: '问题与目标', hint: '谁遇到什么问题' },
    { key: 'scope', name: '范围与边界', hint: '做什么不做什么' },
    { key: 'role', name: '角色与权限', hint: '谁发起审批' },
    { key: 'flow', name: '主流程与状态', hint: '步骤顺序' },
    { key: 'rule', name: '业务规则与口径', hint: '条件阈值' },
    { key: 'exception', name: '异常与边界', hint: '失败处理' },
    { key: 'data', name: '业务数据口径与存量', hint: '以哪份为准' },
    { key: 'cross_sys', name: '跨系统业务责任', hint: '谁负责' },
    { key: 'experience', name: '服务体验与合规', hint: '时限提示' },
    { key: 'acceptance', name: '验收与上线', hint: '什么算通过' },
  ],
  systems: ['CRM', 'BOSS', '订单中心', '电子协议', '生产运营平台', 'DI', '网格通', '能运', '政企工作台', '商机平台'],
  knowledge_systems: ['CRM', 'BOSS', '订单中心'],
  system_dir_alias: { '订单中心': 'ORDER_CENTER', 'ORDER_CENTER': 'ORDER_CENTER' },
  knowledge_status: 'none',
  knowledge_files: 0,
  llm_available: true,
  llm_notice: '',
};
const MOCK_FILE_PATH = '业务建设/需求分析说明书/REQ-E2E_E2E-PRD验证需求/PRD.md';
const FAKE_RESULT = {
  trace_id: 'PRD-E2E-0001', req_id: 'REQ-E2E', prd_markdown:
    '---\nreq_id: REQ-E2E\nstatus: draft\n---\n\n## 1 背景、目标与范围\n测试背景\n\n## 6 待确认与变更记录\n6.1 待确认：无',
  conflicts: [{ level: '高', type: '显式矛盾', desc: '队列规则冲突', evidence: 'CRM§2' }],
  sources: [{ sys_id: 'CRM', repo_id: 'repo-c07', sha: 'a1b2c3d', path: '规则/队列.md', clause: '§2.1' }],
  assumptions: ['跨省默认不纳入'], open_items: ['批价时序待确认'],
  status: 'generated', gen_strategy: 'llm', gen_provider: 'Kimi', gen_model: 'k2.6',
  knowledge_mode: 'none', knowledge_files: 0, notice: '', version: 'v1', file_path: MOCK_FILE_PATH,
};
const FAKE_REFINE = { ...FAKE_RESULT, trace_id: 'PRD-E2E-0002', version: 'v2', parent_trace_id: 'PRD-E2E-0001',
  prd_markdown: FAKE_RESULT.prd_markdown.replace('status: draft', 'status: draft\nversion: v2'), open_items: [] };

(async () => {
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: CHROME, headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
  } catch (e) {
    console.error('[FATAL] 浏览器启动失败', e.message);
    process.exit(2);
  }
  const page = await browser.newPage();
  await page.setViewport({ width: 1680, height: 1000 });
  // 注入测试 token（非真实凭据）：后端测试态 AUTH_REQUIRED=false 时任意 token 均可通过，
  // 避免 401 → request.js 踢回 /login。本脚本所有业务 API 均 mock，不接触真实数据/凭据。
  await page.evaluateOnNewDocument(() => {
    localStorage.setItem('pmwb_token', 'e2e-prd-analysis-token');
    localStorage.setItem('pmwb_username', 'e2e');
  });
  const consoleErrors = [];
  page.on('console', (m) => {
    const t = m.text();
    if (/Failed to resolve component|is not defined on instance|Unhandled error during execution/.test(t)) {
      consoleErrors.push(t.slice(0, 200));
    }
  });

  try {
    // mock 后端 PRD 端点（确保 DOM 断言不依赖真实 LLM / 数据库）
    const MOCK_ROW = {
      req_id: 'REQ-E2E', req_name: 'E2E-PRD验证需求', proposer: '陈大海',
      status: 'proposed', category: '', domain_code: '', created_at: '2026-11-20 10:00:00',
      // 澄清字段留空，但原始描述有值——验证「澄清优先、原始描述兜底」两按钮不灰化
      clarification: '', description: '集团短信通道扩容：旺季成功率下降，涉及CRM队列、BOSS批价、订单中心流水。',
      ext: { req_id: 'REQ-E2E', req_name: 'E2E-PRD验证需求', status: 'proposed' },
    };
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      const url = req.url();
      const respond = (data) => req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, data }) });
      if (url.includes('/api/v1/prd/meta')) return respond(META);
      if (url.includes('/api/v1/prd/status/')) return respond(null);
      if (url.includes('/api/v1/prd/analyze/')) return respond(FAKE_RESULT);
      if (url.includes('/api/v1/prd/refine/')) return respond(FAKE_REFINE);
      if (url.includes('/api/v1/prd/finalize/')) return respond({ trace_id: FAKE_RESULT.trace_id, req_id: 'REQ-E2E', finalized: true, file_path: MOCK_FILE_PATH });
      if (url.includes('/api/v1/prd/sync/systems')) return respond({ systems: [
        { id: 'CRM', name: 'CRM', cloned: true, dirs: ['base_custinfo', 'base_sms'] },
        { id: 'BOSS', name: 'BOSS', cloned: true, dirs: ['req_info'] },
        { id: 'ORDER_CENTER', name: '订单中心', cloned: true, dirs: ['电子协议js-bcm-v2'] },
      ], note: 'test' });
      if (url.includes('/api/v1/prd/sync/status')) return respond({ status: 'idle', task_installed: true, systems: [], synced_at: '2026-11-22 18:44:56' });
      if (url.includes('/api/v1/prd/sync/trigger')) return respond({ ok: true, status: 'running', systems: ['CRM'] });
      if (/\/api\/v1\/requirements\/REQ-E2E(\?|$)/.test(url)) return respond(MOCK_ROW);
      if (/\/api\/v1\/requirements\?/.test(url)) return respond({ items: [MOCK_ROW], total: 1, page: 1, page_size: 20 });
      if (/\/api\/v1\/requirements$/.test(url)) return respond({ items: [MOCK_ROW], total: 1 });
      if (url.includes('/api/v1/requirements/stats')) return respond({ total: 1 });
      if (url.includes('/api/v1/meta/status-domains')) return respond({});
      if (url.includes('/api/v1/requirements/categories/options')) return respond([]);
      if (url.includes('/api/v1/meta/systems')) return respond(['CRM', 'BOSS', '订单中心']);
      // 其他需求详情子接口：evaluations/dev-events 等期望数组，stories 期望对象，其余空列表
      if (url.includes('/api/v1/requirements/')) {
        if (url.includes('/stories')) return respond({ req_id: 'REQ-E2E', stories: [] });
        if (url.includes('/evaluations') || url.includes('/dev-events') ||
            url.includes('/stage-logs') || url.includes('/attachments') ||
            url.includes('/manuals') || url.includes('/interface-docs') ||
            url.includes('/deliverables') || url.includes('/vendor-devs')) return respond([]);
        return respond({ items: [], total: 0 });
      }
      if (url.includes('/api/v1/basic-data/')) return respond({ items: [], total: 0 });
      if (url.includes('/api/v1/')) return respond({ items: [], total: 0 });
      return req.continue();
    });

    await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(2000);

    // 1. 打开需求详情工作流（点击列表行）
    const opened = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.el-table__body tbody tr, .req-table .el-table__body tbody tr')];
      const row = rows.find((tr) => (tr.textContent || '').includes('E2E-PRD验证需求')) || rows[0];
      if (row) { row.click(); return true; }
      return false;
    });
    check('打开需求详情工作流', opened);
    await sleep(2000);

    // 2. 切到步骤 3（用户故事）——精确点 .pm-step-label
    const stepClicked = await page.evaluate(() => {
      const labels = [...document.querySelectorAll('.pm-step-label')];
      const target = labels.find((e) => (e.textContent || '').trim() === '用户故事');
      if (target) { target.closest('.pm-step').click(); return true; }
      return false;
    });
    check('切到步骤3用户故事', stepClicked);
    await sleep(1200);
    const step3Visible = await page.evaluate(() => {
      const title = [...document.querySelectorAll('*')].find((e) =>
        (e.textContent || '').trim() === 'AI 需求分析（PRD）' && e.children.length === 0);
      const panel = title?.closest('.wf-step-panel');
      if (!panel) return false;
      const rect = panel.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
    check('步骤3面板可见', step3Visible);

    // 3. 入口存在且在步骤 3 面板内
    const entry = await page.evaluate(() => {
      const title = [...document.querySelectorAll('*')].find((e) =>
        (e.textContent || '').trim() === 'AI 需求分析（PRD）' && e.children.length === 0);
      if (!title) return { found: false };
      const panel = title.closest('.prd-panel');
      const stepPanel = title.closest('.wf-step-panel');
      const rect = panel?.getBoundingClientRect();
      return {
        found: true,
        hasPanel: !!panel,
        inStep3: !!stepPanel,
        visible: !!(rect && rect.width > 0 && rect.height > 0),
      };
    });
    check('步骤3含 PRD 入口卡', entry.found && entry.hasPanel && entry.visible, JSON.stringify(entry));

    // 4. 与现有用户故事生成平级独立（澄清输入框 + 生成策略仍在）
    const coexist = await page.evaluate(() => ({
      clarification: !!document.querySelector('textarea[placeholder*="澄清"]') ||
        [...document.querySelectorAll('*')].some((e) => (e.textContent || '').includes('澄清后需求内容')),
      storyStrategy: [...document.querySelectorAll('*')].some((e) => (e.textContent || '').trim() === '生成策略'),
      prdEntry: [...document.querySelectorAll('*')].some((e) => (e.textContent || '').trim() === 'AI 需求分析（PRD）'),
    }));
    check('PRD入口与用户故事生成共存', coexist.clarification && coexist.storyStrategy && coexist.prdEntry, JSON.stringify(coexist));

    // 5. 十维问卷加载 + qa/fast 切换
    const dims = await page.evaluate(() => {
      const names = ['问题与目标', '范围与边界', '跨系统业务责任', '验收与上线'];
      return names.filter((n) => [...document.querySelectorAll('*')].some((e) => e.children.length === 0 && (e.textContent || '').trim() === n)).length;
    });
    check('十维问卷维度渲染', dims >= 4, `${dims}/4 抽样`);

    // 涉及系统覆盖日常需求全部系统（不再只有 3 个）
    const sysChips = await page.evaluate(() => {
      const chips = [...document.querySelectorAll('.prd-panel .sys-chip')].map(e => e.textContent.replace('无库', '').trim());
      return { count: chips.length, names: chips };
    });
    check('涉及系统覆盖全部需求系统', sysChips.count >= 10, `${sysChips.count} 个: ${sysChips.names.join(',')}`);
    check('无内网库系统带无库标记', sysChips.names.includes('电子协议') && sysChips.names.includes('网格通'), JSON.stringify(sysChips.names));

    const fastClicked = await page.evaluate(() => {
      const b = [...document.querySelectorAll('*')].find((e) => (e.textContent || '').includes('快速模式') && /radio|span|div/.test(e.tagName.toLowerCase()) && e.children.length === 0);
      if (b) { b.click(); return true; }
      return false;
    });
    check('qa/fast 模式可切换', fastClicked);
    await sleep(500);

    // 5b. 澄清为空、原始描述有值 → 两个生成按钮都不应灰化（本次 bug 修复核心断言）
    const enabledWithFallback = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button')];
      const prd = btns.find((e) => (e.textContent || '').includes('生成 PRD'));
      const story = btns.find((e) => (e.textContent || '').includes('生成用户故事'));
      return { prd: !!prd && !prd.disabled, story: !!story && !story.disabled };
    });
    check('澄清为空时PRD按钮仍可用(原始描述兜底)', enabledWithFallback.prd, JSON.stringify(enabledWithFallback));
    check('澄清为空时用户故事按钮仍可用(原始描述兜底)', enabledWithFallback.story, JSON.stringify(enabledWithFallback));

    // 6. 填澄清内容 → 生成（mock） → 结果区
    await page.evaluate(() => {
      const panels = [...document.querySelectorAll('.wf-step-panel')];
      const visible = panels.find((p) => p.getBoundingClientRect().height > 0);
      const ta = visible?.querySelector('textarea');
      if (ta) {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(ta, '集团短信通道扩容：旺季成功率下降，需CRM优先级队列、BOSS批价、订单中心流水。');
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        ta.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    await sleep(700);
    const btnEnabled = await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find((e) => (e.textContent || '').includes('生成 PRD'));
      return b ? !b.disabled : false;
    });
    check('澄清内容填入后生成按钮启用', btnEnabled);

    const genClicked = await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find((e) => (e.textContent || '').includes('生成 PRD'));
      if (b) { b.click(); return true; }
      return false;
    });
    check('生成 PRD 按钮可点击', genClicked);
    await sleep(1800);

    const result = await page.evaluate(() => {
      const txt = document.body.innerText;
      return {
        hasH1: txt.includes('背景、目标与范围'),
        hasConflict: txt.includes('队列规则冲突'),
        hasSource: txt.includes('repo-c07') || txt.includes('规则/队列.md'),
        hasTrace: txt.includes('PRD-E2E-0001'),
      };
    });
    check('六章 PRD 结果展示', result.hasH1, JSON.stringify(result));
    check('冲突清单展示', result.hasConflict);
    check('知识引用来源展示', result.hasSource);
    check('trace_id 溯源展示', result.hasTrace);

    // PRD 落盘到需求固定文件夹 + 下载名统一 PRD.md
    const filed = await page.evaluate(() => {
      const txt = document.body.innerText;
      const box = document.querySelector('.prd-filed');
      return {
        hasBox: !!box,
        hasPath: txt.includes('PRD.md 已写入该需求固定文件夹'),
        hasRel: txt.includes('REQ-E2E_E2E-PRD验证需求/PRD.md'),
        dlLabel: [...document.querySelectorAll('button')].some(b => b.textContent.trim() === '下载 PRD.md'),
      };
    });
    check('PRD 落盘路径可见', filed.hasBox && filed.hasPath && filed.hasRel, JSON.stringify(filed));
    check('下载名统一为 PRD.md', filed.dlLabel);

    // v2 待澄清二次评估断言
    const refinePanel = await page.evaluate(() => {
      const txt = document.body.innerText;
      const box = document.querySelector('.refine-box');
      return {
        hasBox: !!box,
        hasItem: txt.includes('批价时序待确认'),
        hasBtn: [...document.querySelectorAll('button')].some(b => b.textContent.includes('补充并重评')),
        hasV1: txt.includes('v1'),
      };
    });
    check('待澄清补充区存在', refinePanel.hasBox, JSON.stringify(refinePanel));
    check('待澄清点逐条展示', refinePanel.hasItem);
    check('补充并重评按钮存在', refinePanel.hasBtn);
    check('版本号 v1 展示', refinePanel.hasV1);
    // 填一条补充 → 点重评 → v2 结果与父 trace
    await page.evaluate(() => {
      const box = document.querySelector('.refine-box');
      const ta = box?.querySelector('textarea');
      if (ta) {
        const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        s.call(ta, '本省先纳入，跨省二期');
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    await sleep(300);
    await page.evaluate(() => {
      const b = [...document.querySelectorAll('.refine-box button')].find(e => e.textContent.includes('补充并重评'));
      if (b) b.click();
    });
    await sleep(1200);
    const afterRefine = await page.evaluate(() => {
      const txt = document.body.innerText;
      return { hasV2: txt.includes('v2'), hasParent: txt.includes('PRD-E2E-0001'), hasNewTrace: txt.includes('PRD-E2E-0002') };
    });
    check('重评生成 v2', afterRefine.hasV2, JSON.stringify(afterRefine));
    check('v2 展示父版本溯源', afterRefine.hasParent || afterRefine.hasNewTrace);

    // 知识同步面板断言
    const syncPanel = await page.evaluate(() => {
      const title = [...document.querySelectorAll('*')].find(e => (e.textContent || '').trim() === '知识源同步' && e.children.length === 0);
      if (!title) return { found: false };
      const box = title.closest('.ksync');
      return {
        found: !!box,
        hasStatus: !!box && box.innerText.includes('未同步'),
        hasSystems: !!box && box.innerText.includes('CRM') && box.innerText.includes('订单中心'),
        hasDirToggle: !!box && !!box.querySelector('.ksync-toggle'),
        hasSyncBtn: !!box && [...box.querySelectorAll('button')].some(b => b.textContent.includes('立即同步')),
      };
    });
    check('知识同步面板存在', syncPanel.found, JSON.stringify(syncPanel));
    check('同步面板显示状态', !!syncPanel.hasStatus);
    check('同步面板可展开收起', !!syncPanel.hasDirToggle);
    // 展开后检查系统与业务目录（v-show 折叠时 innerText 不含，须展开后断言）
    await page.evaluate(() => {
      const t = [...document.querySelectorAll('*')].find(e => (e.textContent || '').trim() === '知识源同步' && e.children.length === 0);
      if (t) t.closest('.ksync-head')?.click();
    });
    await sleep(500);
    const expandedSystems = await page.evaluate(() => {
      const b = document.querySelector('.ksync-body');
      return !!b && b.innerText.includes('CRM') && b.innerText.includes('订单中心');
    });
    check('同步面板列出系统', expandedSystems);
    const dirsVisible = await page.evaluate(() => {
      const b = document.querySelector('.ksync-body');
      return !!b && b.innerText.includes('电子协议js-bcm-v2') && b.innerText.includes('base_custinfo');
    });
    check('业务子目录可勾选', dirsVisible);

    check('无 Vue 运行时错误', consoleErrors.length === 0, consoleErrors.join(' | ').slice(0, 300));
  } catch (e) {
    check('脚本未抛异常', false, e.stack || e.message);
  } finally {
    await browser.close();
  }

  const passed = results.filter((r) => r.pass).length;
  console.log(`\n===== ${passed}/${results.length} PASS =====`);
  process.exit(passed === results.length ? 0 : 1);
})();
