import request from './request'

export const operationApi = {
  // 查询工单列表
  listIssues(params) {
    return request.get('/operation/issues', { params })
  },

  // 获取工单详情
  getIssue(id) {
    return request.get(`/operation/issues/${id}`)
  },

  // 创建工单
  createIssue(data) {
    return request.post('/operation/issues', data)
  },

  // 更新工单
  updateIssue(id, data) {
    return request.put(`/operation/issues/${id}`, data)
  },

  // 删除工单
  deleteIssue(id) {
    return request.delete(`/operation/issues/${id}`)
  },

  // 批量删除工单
  batchDeleteIssues(ids) {
    return request.post('/operation/issues/batch-delete', { ids })
  },

  // 获取统计（category 不传返回全部，传则限定某大类）
  getStats(category) {
    return request.get('/operation/stats', { params: category ? { category } : {} })
  },

  // 责任人维度统计：责任人 × 工单类别 × 状态 的数量矩阵（总览页责任人分布）
  getStatsByHandler() {
    return request.get('/operation/stats/by-handler')
  },

  // 下载主动运营分析 Excel 模板
  downloadAnalysisTemplate() {
    return request.get('/operation/analysis-template/download', {
      responseType: 'blob',
    })
  },

  // 解析主动运营分析工单（不落库，返回预览 + 建议分类 + 告警）
  parseAnalysis(file) {
    const form = new FormData()
    form.append('file', file)
    return request.post('/operation/analysis/parse', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 获取分析工单明细 + 关联遗留任务（用于详情展示）
  getAnalysisDetail(id) {
    return request.get(`/operation/issues/${id}/analysis`)
  },

  // 确认导入：解析 + 按选定分类创建遗留任务工单
  // legacyTasks 为预览后回传的遗留任务列表（含 content/handlers/category/issue_type/due_date）
  importAnalysisConfirm(file, legacyTasks) {
    const form = new FormData()
    form.append('file', file)
    if (legacyTasks && legacyTasks.length) {
      form.append('legacy_tasks', JSON.stringify(legacyTasks))
    }
    return request.post('/operation/analysis/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 导入主动运营分析工单（file 传原生 File 对象，内部自动包 FormData）—— 旧一键导入兜底
  importAnalysis(file) {
    const form = new FormData()
    form.append('file', file)
    return request.post('/operation/analysis/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}
