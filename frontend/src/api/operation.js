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

  // 获取统计（category 不传返回全部，传则限定某大类）
  getStats(category) {
    return request.get('/operation/stats', { params: category ? { category } : {} })
  }
}
