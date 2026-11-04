import request from './request'

// 客诉专题分析 API（后端 prefix=/api/v1/complaint，routers/complaint.py）
export const complaintApi = {
  // ── 台账 ──
  listTickets(params) {
    return request.get('/complaint/tickets', { params })
  },
  getTicket(id) {
    return request.get(`/complaint/tickets/${id}`)
  },
  // 人工校正分类（classify_by 置 manual，reclassify 不覆盖）
  correctCategory(id, data) {
    return request.put(`/complaint/tickets/${id}/category`, data)
  },
  listClusters(week) {
    return request.get('/complaint/clusters', { params: week ? { week } : {} })
  },

  // ── 分类字典 ──
  listCategories() {
    return request.get('/complaint/categories')
  },
  toggleCategory(id, enabled) {
    return request.put(`/complaint/categories/${id}/enabled`, { enabled })
  },

  // ── 措施台账 ──
  listActions() {
    return request.get('/complaint/actions')
  },
  createAction(data) {
    return request.post('/complaint/actions', data)
  },
  updateAction(actionNo, data) {
    return request.put(`/complaint/actions/${actionNo}`, data)
  },
  // 标记措施生效并绑定基线（生效日前 N 周该场景周均单量）
  goLive(actionNo, goLiveDate) {
    return request.post(`/complaint/actions/${actionNo}/go-live`, { go_live_date: goLiveDate })
  },
  // 结算验证中的措施（到观察期自动定论 effective/ineffective）
  verifyActions() {
    return request.post('/complaint/actions/verify')
  },
  // 督办邮件：默认 dry_run；confirmSend=true 真发（仅限用户显式点击）
  urgePreview(data) {
    return request.post('/complaint/actions/urge-preview', data)
  },

  // LLM 主导归类状态（AI 归类率/待人工确认数）
  classifyStatus() {
    return request.get('/complaint/classify-status')
  },
  // 手动重跑 LLM 归类（导入路径自动后台触发，一般无需手动调）
  runLlmClassify(params) {
    return request.post('/complaint/llm-classify', null, { params })
  },

  // ── 指标与周报 ──
  getMetrics(week) {
    return request.get('/complaint/metrics', { params: week ? { week } : {} })
  },
  genReport(data) {
    return request.post('/complaint/reports', data)
  },
  reportDownloadUrl(week, ext = 'html') {
    return `/api/v1/complaint/reports/${week}/download?ext=${ext}`
  },

  // ── 每周导入（multipart，withReport=true 导入后直接出周报）──
  importWeekly(file, withReport, withPdf = true) {
    const form = new FormData()
    form.append('file', file)
    form.append('with_report', String(withReport))
    form.append('with_pdf', String(withPdf))
    return request.post('/complaint/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })
  },

  // ── 共性问题台账（闭环管理）──
  // 热点投诉 TOP 榜（近一周按二级场景统计+环比标注）
  getHotspots(params) {
    return request.get('/complaint/hotspots', { params })
  },
    listProblems(params) {
    return request.get('/complaint/problems', { params })
  },
  // 可选观察周列表（台账按周查看）
  listWeeks(n = 20) {
    return request.get('/complaint/weeks', { params: { n } })
  },
  listCandidates() {
    return request.get('/complaint/problems/candidates')
  },
  scanProblems(week, dryRun = true) {
    return request.post('/complaint/problems/scan', null, {
      params: { ...(week ? { week } : {}), dry_run: dryRun },
    })
  },
  createProblem(data) {
    return request.post('/complaint/problems', data)
  },
  getProblem(problemNo) {
    return request.get(`/complaint/problems/${problemNo}`)
  },
  // 「问题 → 建运营工单」代入上下文：summary（情况说明预填）+ tickets（明细预览）
  getIssueContext(problemNo, weeks = 1) {
    return request.get(`/complaint/problems/${problemNo}/issue-context`, { params: { weeks } })
  },
  updateProblem(problemNo, data) {
    return request.put(`/complaint/problems/${problemNo}`, data)
  },
  changeProblemStatus(problemNo, data) {
    return request.patch(`/complaint/problems/${problemNo}/status`, data)
  },
  confirmProblem(problemNo, data) {
    return request.post(`/complaint/problems/${problemNo}/confirm`, data)
  },
  linkProblemAction(problemNo, data) {
    return request.post(`/complaint/problems/${problemNo}/actions`, data)
  },
  unlinkProblemAction(problemNo, actionNo) {
    return request.delete(`/complaint/problems/${problemNo}/actions/${actionNo}`)
  },
  closureSuggestions() {
    return request.get('/complaint/problems/closure-suggestions')
  },
  problemsUrge(data) {
    return request.post('/complaint/problems/urge-preview', data)
  },

  // ── 根因层 / 根因库（2026-11-03 客诉根因深化）──
  rootcauseStatus() {
    return request.get('/complaint/rootcause/status')
  },
  rootcauseMeta() {
    return request.get('/complaint/rootcause/meta')
  },
  runRootcause(params) {
    return request.post('/complaint/rootcause/analyze', null, { params })
  },
  runRootcauseCluster(params) {
    return request.post('/complaint/rootcause/cluster', null, { params })
  },
  rootcauseTop(params) {
    return request.get('/complaint/rootcause/top', { params })
  },
  rootcauseBatch(params) {
    return request.get('/complaint/rootcause/batch', { params })
  },
  rootcauseReview(params) {
    return request.get('/complaint/rootcause/review', { params })
  },
  listRootcauseClusters(params) {
    return request.get('/complaint/rootcause/clusters', { params })
  },
  getRootcauseCluster(rcNo) {
    return request.get(`/complaint/rootcause/clusters/${rcNo}`)
  },
  createRootcauseCluster(data) {
    return request.post('/complaint/rootcause/clusters', data)
  },
  updateRootcauseCluster(rcNo, data) {
    return request.put(`/complaint/rootcause/clusters/${rcNo}`, data)
  },
  splitRootcauseCluster(rcNo, data) {
    return request.post(`/complaint/rootcause/clusters/${rcNo}/split`, data)
  },
  moveRootcauseTickets(data) {
    return request.post('/complaint/rootcause/tickets/move', data)
  },
  confirmRootcauseCluster(rcNo, data) {
    return request.post(`/complaint/rootcause/clusters/${rcNo}/confirm`, data)
  },
  mergeRootcauseCluster(rcNo, dstNo) {
    return request.post(`/complaint/rootcause/clusters/${rcNo}/merge`, { dst_no: dstNo })
  },
  disableRootcauseCluster(rcNo, reopen = false) {
    return request.post(`/complaint/rootcause/clusters/${rcNo}/disable`, { reopen })
  },
  correctTicketRootcause(id, data) {
    return request.put(`/complaint/tickets/${id}/rootcause`, data)
  },

  // ── 客诉 v4.2 逐单问题点自动化分析（分析过程不依赖人）──
  problemV42Status() {
    return request.get('/complaint/problem-v42/status')
  },
  problemV42Classes(params) {
    return request.get('/complaint/problem-v42/classes', { params })
  },
  problemV42Unclassified(params) {
    return request.get('/complaint/problem-v42/unclassified', { params })
  },
  problemV42Run(data) {
    return request.post('/complaint/problem-v42/run', data)
  },
  problemV42RerunPending(data) {
    return request.post('/complaint/problem-v42/rerun-pending', data)
  },
}
