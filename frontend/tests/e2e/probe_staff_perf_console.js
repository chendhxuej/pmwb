// ============================================================
// 选人弹窗性能探针（真实 Chrome 控制台粘贴运行）
// 用途：在老大真实浏览器里量化"组织/身份下拉"卡顿到底卡在哪一跳。
// 用法：
//   1. 用真实 Chrome 打开 localhost:5173（或 127.0.0.1:5173），进入任意选人弹窗；
//   2. F12 → Console，把本文件全文粘贴回车；
//   3. 点击「组织」下拉（或「身份」下拉），控制台会输出：
//        [组织下拉] 点击→弹层可见: Nms      ← 弹层渲染跳耗时
//      再运行 __staffProbe.report() 看长任务汇总（主线程被什么烧时间）。
// 注意：本脚本只读 + 观测，不改动任何数据。
// ============================================================
(() => {
  const longTasks = [];
  try {
    new PerformanceObserver((list) => {
      list.getEntries().forEach((e) => longTasks.push(Math.round(e.duration)));
    }).observe({ entryTypes: ['longtask'] });
  } catch (e) {
    console.warn('当前浏览器不支持 longtask 观测', e);
  }

  const getSelect = (idx) =>
    document.querySelectorAll('.staff-picker-filters .el-select')[idx];

  function arm(idx, label) {
    const sel = getSelect(idx);
    if (!sel) {
      console.log(`未找到第 ${idx + 1} 个筛选器（${label}），请确认选人弹窗已打开`);
      return;
    }
    sel.addEventListener(
      'click',
      () => {
        const start = performance.now();
        performance.mark(`${label}_click`);
        const iv = setInterval(() => {
          const popper = document.querySelector('.el-select-dropdown.el-popper, .el-popper');
          if (popper && popper.getBoundingClientRect().height > 0) {
            const dt = Math.round(performance.now() - start);
            performance.mark(`${label}_popper`);
            console.log(`[${label}] 点击→弹层可见: ${dt}ms`);
            clearInterval(iv);
          }
          if (performance.now() - start > 8000) {
            clearInterval(iv);
            console.log(`[${label}] 8s 内弹层未出现 —— 主线程大概率冻结（longtask 见 report）`);
          }
        }, 30);
      },
      true,
    );
  }

  arm(0, '组织');
  arm(1, '身份');

  window.__staffProbe = {
    report() {
      const sum = longTasks.reduce((a, b) => a + b, 0);
      console.log('长任务(>50ms) 列表(ms):', longTasks);
      console.log(`长任务总数: ${longTasks.length}，累计阻塞主线程: ${sum}ms`);
      console.log(
        longTasks.length > 5 || sum > 1000
          ? '=> 主线程被长任务持续阻塞，符合"5秒冻结"现象；瓶颈在主线程（渲染/脚本），非网络。'
          : '=> 长任务不多，瓶颈可能在别处（网络/驱动劫持），需结合 Network 面板看。',
      );
    },
  };

  console.log('探针已挂载。请点击「组织」/「身份」下拉；结束后运行 __staffProbe.report() 看长任务汇总。');
})();
