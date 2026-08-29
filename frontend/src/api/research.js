import request from './request'

export const researchApi = {
  // 查询一线调研工单列表
  listIssues(params) {
    return request.get('/research/issues', { params })
  },

  // 获取一线调研工单详情
  getIssue(id) {
    return request.get(`/research/issues/${id}`)
  },

  // 创建一线调研工单
  createIssue(data) {
    return request.post('/research/issues', data)
  },

  // 更新一线调研工单
  updateIssue(id, data) {
    return request.put(`/research/issues/${id}`, data)
  },

  // 变更一线调研工单状态
  updateStatus(id, status) {
    return request.post(`/research/issues/${id}/status?status=${encodeURIComponent(status)}`)
  },

  // 删除一线调研工单
  deleteIssue(id) {
    return request.delete(`/research/issues/${id}`)
  },

  // 获取统计
  getStats() {
    return request.get('/research/stats')
  },

  // 上传附件
  uploadAttachment(issueId, file) {
    const form = new FormData()
    form.append('file', file)
    return request.post(`/research/issues/${issueId}/attachments/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 删除附件
  deleteAttachment(issueId, filename) {
    return request.post(`/research/issues/${issueId}/attachments/delete?filename=${encodeURIComponent(filename)}`)
  },

  // 获取附件列表
  listAttachments(issueId) {
    return request.get(`/research/issues/${issueId}/attachments`)
  },
}
