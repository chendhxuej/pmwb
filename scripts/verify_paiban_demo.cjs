const fs = require('fs');
const { JSDOM } = require(__dirname + '/../frontend/node_modules/jsdom');
const html = fs.readFileSync(__dirname + '/../docs/排版管理_页面Demo.html', 'utf8');
let pass = 0, fail = 0;
function ck(name, cond, extra) {
  if (cond) { pass++; console.log('  PASS  ' + name); }
  else { fail++; console.log('  FAIL  ' + name + (extra ? '  :: ' + extra : '')); }
}
const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  beforeParse(w) {
    w.scrollTo = () => {};
    w.Element.prototype.scrollIntoView = function () {};
  }
});
const d = dom.window.document;
const $ = s => d.querySelector(s);
const $$ = s => Array.from(d.querySelectorAll(s));
const click = el => el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
const tab = k => click($('[data-act="page"][data-k="' + k + '"]'));
const pageText = () => $('#page').textContent;

console.log('=== A 首屏（排版跟踪） ===');
ck('A1 五个二级页签', $$('.tab').length === 5, 'got ' + $$('.tab').length);
ck('A2 默认落地排版跟踪', $('.tab.active') && $('.tab.active').textContent.indexOf('排版跟踪') >= 0);
ck('A3 版本选择器 6 条计划', $('#verSel') && $('#verSel').options.length === 6);
ck('A4 当前版本=CRM 11 月', $('#versionbar').textContent.indexOf('CRM 2026-11 常规版') >= 0);
ck('A5 概览 8 张 KPI', $$('.kpi').length === 8, 'got ' + $$('.kpi').length);
ck('A6 四环节泳道', $$('.lane').length === 4);
ck('A7 准入模拟器存在（v1.2 默认顺延 + 手工处理）', !!$('#gateSim') && pageText().indexOf('默认自动顺延') >= 0 && pageText().indexOf('手工处理') >= 0);
ck('A8 工单卡可点', $$('.tkt').length >= 3, 'got ' + $$('.tkt').length);
ck('A9 侧栏菜单位置正确', (() => {
  const items = $$('.nav-item').map(x => x.textContent.trim());
  const i = items.findIndex(x => x.indexOf('排版管理') >= 0);
  return i > 0 && items[i - 1].indexOf('任务中心') >= 0 && items[i + 1].indexOf('需求与交付') >= 0;
})(), JSON.stringify($$('.nav-item').map(x => x.textContent.trim())));

console.log('=== B 版本计划 ===');
tab('plan');
ck('B1 计划表 6 行', $$('.card table tbody tr').length >= 6, 'got ' + $$('.card table tbody tr').length);
ck('B2 CRM 默认顺延 + 手工例外可见', pageText().indexOf('禁止（默认顺延）') >= 0 && pageText().indexOf('可逐单手工例外') >= 0);
ck('B3 默认计划回落提示', pageText().indexOf('回落') >= 0 && pageText().indexOf('不落副本') >= 0);
ck('B4 倒排 −15/−8/−3/−1', pageText().indexOf('−15 / −8 / −3 / −1') >= 0);
click($('[data-act="addPlan"]'));
ck('B5 登记弹窗含准入模式', $('.modal.show') && $('.modal.show').textContent.indexOf('准入模式') >= 0);
$('#pfGate') && ($('#pfGate').value = '7', $('#pfGate').dispatchEvent(new dom.window.Event('change')));
ck('B6 选 CRM 硬闸后临时合入被锁', $('#pfTemp') && $('#pfTemp').disabled === true && $('#pfTemp').checked === false);
click($('[data-act="close"]'));

console.log('=== C 团队跟踪 ===');
tab('team');
ck('C1 团队矩阵 4 行', $$('table.matrix tbody tr').length === 4);
ck('C2 口径不可加总声明', pageText().indexOf('不可加总') >= 0);
ck('C3 行操作含三种督办 + 批量更新', $$('[data-act="supervise"]').length === 12 && $$('[data-act="bulkUpdate"]').length >= 4);
click($('[data-act="supervise"][data-type="全部"]'));
ck('C4 督办预览含回执码', $('.modal.show') && $('.modal.show').textContent.indexOf('RC-20261118') >= 0);
ck('C5 督办预览含 dry_run 红线', $('.modal.show').textContent.indexOf('dry_run') >= 0);
ck('C6 跳过清单有冷却原因', $('.modal.show').textContent.indexOf('冷却中，剩余 18h') >= 0);
click($('[data-act="doSend"]'));
ck('C7 确认发送未真发（仅提示）', $('#toast').textContent.indexOf('未真发') >= 0);

console.log('=== D 风险与督办 ===');
tab('risk');
ck('D1 风险台账 5 条', $$('.card table tbody tr').length >= 5);
ck('D2 硬门禁说明', pageText().indexOf('硬门禁') >= 0);
ck('D3 督办批次 3 条 + 回执状态', pageText().indexOf('SUP-20261117-01') >= 0 && pageText().indexOf('超时未回') >= 0);
ck('D4 冷却 24h + 5 类例外', pageText().indexOf('24h 冷却') >= 0 && pageText().indexOf('5 类例外') >= 0);

console.log('=== E 反馈同步 ===');
tab('feedback');
ck('E1 四通道', $$('.chan-c').length === 4);
ck('E2 待核对/冲突/解析失败均在列', pageText().indexOf('待核对') >= 0 && pageText().indexOf('冲突') >= 0 && pageText().indexOf('解析失败') >= 0);
ck('E3 结构化回执自动采纳记录', pageText().indexOf('自动采纳') >= 0 && pageText().indexOf('RC-20261116-02-01') >= 0);
ck('E4 自由文本不自动改状态', pageText().indexOf('只出建议，不自动改状态') >= 0);
ck('E5 可回滚', $$('[data-act="rollback"]').length === 1);
ck('E6 通道不可用→待自动补跑', pageText().indexOf('待自动补跑') >= 0);
click($('[data-act="bulkUpdate"]'));
ck('E7 批量更新弹窗可用', $('.modal.show') && $('.modal.show').textContent.indexOf('团队批量更新') >= 0);
click($('[data-act="close"]'));

console.log('=== K v1.2 手工处理与例外放行（老大决策第 3 项） ===');
tab('track');
click($('[data-act="sim"][data-d="-6"]'));
ck('K1 未准入态有两个动作按钮', $$('[data-act="defer"]').length >= 1 && $$('[data-act="manual"]').length === 1, 'defer=' + $$('[data-act="defer"]').length + ' manual=' + $$('[data-act="manual"]').length);
ck('K2 默认顺延文案', $('#gateSim .sim-out').textContent.indexOf('默认自动顺延下一版') >= 0 && $('#gateSim .sim-out').textContent.indexOf('无需人工确认') >= 0);
click($('[data-act="manual"]'));
ck('K3 手工处理弹窗含原判定事实与口径', $('.modal.show') && $('.modal.show').textContent.indexOf('原判定事实') >= 0 && $('.modal.show').textContent.indexOf('不计入按计划上线率分子') >= 0);
click($('[data-act="doManual"]'));
ck('K4 未选原因提交被拒', $('#toast').textContent.indexOf('必须选择原因') >= 0);
$('#manReason').value = '其他（需在说明中写明）';
click($('[data-act="doManual"]'));
ck('K5 选「其他」未填说明被拒', $('#toast').textContent.indexOf('必须填写说明') >= 0);
$('#manReason').value = '客户承诺';
click($('[data-act="doManual"]'));
ck('K6 例外放行生效并留痕', $('#toast').textContent.indexOf('例外放行已生效') >= 0 && $('#toast').textContent.indexOf('变更日志') >= 0);
ck('K7 泳道卡显示人工例外', pageText().indexOf('人工例外准入') >= 0 && $$('.tkt .badge.b-gate').length >= 1);
ck('K8 概览标注口径单列', $$('.kpi')[3].textContent.indexOf('人工例外 1 单（不进按计划上线率分子）') >= 0, $$('.kpi')[3].textContent);
click($('[data-act="ticket"][data-id="REQ-2026-1091"]'));
ck('K9 抽屉含留痕与撤销入口', $('#drawer').textContent.indexOf('人工例外放行') >= 0 && $$('[data-act="undoManual"]').length === 1);
click($('#drawer [data-act="close"]'));

console.log('=== F 准入闸门与自动顺延（老大补充 1/2） ===');
tab('track');
click($('[data-act="sim"][data-d="-8"]'));
ck('F1 −8 天 → 已准入', $('#gateSim .sim-out').classList.contains('ok') && $('#gateSim .sim-out').textContent.indexOf('✓ 已准入') >= 0);
click($('[data-act="sim"][data-d="-6"]'));
ck('F2 −6 天 → 未准入 + 自动顺延', $('#gateSim .sim-out').classList.contains('no') && $('#gateSim .sim-out').textContent.indexOf('✕ 未准入') >= 0 && $('#gateSim .sim-out').textContent.indexOf('自动顺延下一版') >= 0);
ck('F3 无强制合入按钮', $$('[data-act*="force"]').length === 0 && pageText().indexOf('没有') >= 0);
const before = $$('.tkt').length;
click($('[data-act="defer"]'));
ck('F4 顺延后主行离开本版（不关闭）', $$('.tkt').length === before - 1, 'before=' + before + ' after=' + $$('.tkt').length);
ck('F5 顺延动作留痕提示', $('#toast').textContent.indexOf('顺延次数 +1') >= 0 && $('#toast').textContent.indexOf('自动登记风险') >= 0);

console.log('=== G 上线结果硬门禁 ===');
const gBefore = $$('.tkt').length;
click($$('.tkt')[0]);
ck('G1 工单抽屉打开', $('#drawer').classList.contains('show') && $('#drawer').textContent.indexOf('登记上线结果') >= 0);
const res = $('#resSel'); res.value = '已上线';
click($('[data-act="doResult"]'));
ck('G2 有未消除风险 → 已上线被拦截', $('#toast').textContent.indexOf('硬门禁拦截') >= 0);
res.value = '上线失败';
$('#resReason').value = '发布窗口验证不通过，已回滚';
click($('[data-act="doResult"]'));
ck('G3 上线失败 → 自动顺延', $('#toast').textContent.indexOf('自动顺延下一版') >= 0);
ck('G4 上线失败后主行确实改挂下一版', $$('.tkt').length === gBefore - 1, 'before=' + gBefore + ' after=' + $$('.tkt').length);

console.log('=== H 决策清单 ===');
click($('#decBtn'));
ck('H1 决策面板 7 项且结论已回填', $('#decPanel').classList.contains('show') && $$('.dec-item').length === 7 && $('#decCount').textContent === '7');
ck('H2 第 3 项=要调整且备注含默认顺延', $$('.opt.on-no').length === 1 && $('[data-note="2"]').value.indexOf('默认顺延') >= 0, 'got ' + $('[data-note="2"]').value);
ck('H3 决策项文案已同步 v1.2', $('#decPanel').textContent.indexOf('默认自动顺延下一版') >= 0 && $('#decPanel').textContent.indexOf('手工处理') >= 0);

console.log('=== I 版本切换全页联动 ===');
const sel = $('#verSel'); sel.value = 'def11'; sel.dispatchEvent(new dom.window.Event('change'));
ck('I1 切到默认计划版本', $('#versionbar').textContent.indexOf('统一默认 2026-11 版') >= 0 && $('#versionbar').textContent.indexOf('默认计划') >= 0);
ck('I2 准入模式随版本变化（开放）', $('#versionbar').textContent.indexOf('准入：开放') >= 0);
ck('I3 页面重渲染且泳道仍存在', $$('.lane').length === 4);

console.log('\n=== RESULT ===');
console.log('PASS=' + pass + '  FAIL=' + fail);
process.exit(fail ? 1 : 0);
