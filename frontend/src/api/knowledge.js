import request from './request'

export const knowledgeApi = {
  listItems(params) {
    return request.get('/knowledge', { params })
  },

  getItem(id) {
    return request.get(`/knowledge/${id}`)
  },

  getItemContent(id) {
    return request.get(`/knowledge/${id}/content`)
  },

  createItem(data) {
    return request.post('/knowledge', data)
  },

  updateItem(id, data) {
    return request.put(`/knowledge/${id}`, data)
  },

  updateItemContent(id, content) {
    return request.put(`/knowledge/${id}/content`, { content })
  },

  deleteItem(id) {
    return request.delete(`/knowledge/${id}`)
  },

  getCategories() {
    return request.get('/knowledge/meta/categories')
  },

  getSubCategories(category) {
    return request.get('/knowledge/meta/sub-categories', { params: { category } })
  },

  getTags() {
    return request.get('/knowledge/meta/tags')
  }
}
