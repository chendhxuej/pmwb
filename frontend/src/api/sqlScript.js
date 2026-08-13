import request from './request.js'

// SQL脚本库：归档常用业务统计脚本
// 字段：脚本说明(title) / SQL(sql_text) / 创建时间(created_at) / 输出字段样例(output_fields: [{name,type,desc}])

export const sqlScriptApi = {
  listSqlScripts({ keyword, category, domain_code, page, page_size } = {}) {
    const params = {}
    if (keyword) params.keyword = keyword
    if (category) params.category = category
    if (domain_code) params.domain_code = domain_code
    if (page) params.page = page
    if (page_size) params.page_size = page_size
    return request.get('/sql-scripts', { params })
  },

  getSqlScriptStats() {
    return request.get('/sql-scripts/stats')
  },

  getSqlScript(id) {
    return request.get(`/sql-scripts/${id}`)
  },

  createSqlScript(data) {
    return request.post('/sql-scripts', data)
  },

  updateSqlScript(id, data) {
    return request.put(`/sql-scripts/${id}`, data)
  },

  deleteSqlScript(id) {
    return request.delete(`/sql-scripts/${id}`)
  },
}
