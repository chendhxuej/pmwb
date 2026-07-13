import request from './request'

export const operationApi = {
  // 查询问题列表
  listIssues(params) {
    return request.get('/operation/issues', { params })
  },

  // 获取问题详情
  getIssue(id) {
    return request.get(`/operation/issues/${id}`)
  },

  // 创建问题
  createIssue(data) {
    return request.post('/operation/issues', data)
  },

  // 更新问题
  updateIssue(id, data) {
    return request.put(`/operation/issues/${id}`, data)
  },

  // 删除问题
  deleteIssue(id) {
    return request.delete(`/operation/issues/${id}`)
  },

  // 获取统计
  getStats() {
    return request.get('/operation/stats')
  }
}
