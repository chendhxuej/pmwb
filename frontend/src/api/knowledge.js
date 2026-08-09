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
  },

  // 为所有「有子笔记但缺主笔记」的领域自动保活主笔记并重建子笔记摘要
  ensureMainNotes() {
    return request.post('/knowledge/ensure-main-notes')
  },

  // 从 Obsidian Vault 反向同步笔记到知识索引
  syncFromVault(data) {
    return request.post('/knowledge/sync-from-vault', data)
  },

  // ---- 多对多关联 ----
  getLinks(sourceType, sourceId) {
    return request.get('/knowledge/links', {
      params: { source_type: sourceType, source_id: sourceId },
    })
  },

  createLink(data) {
    return request.post('/knowledge/links', data)
  },

  createLinkByPath(data) {
    return request.post('/knowledge/links/by-path', data)
  },

  deleteLink(linkId) {
    return request.delete(`/knowledge/links/${linkId}`)
  },

  // 把需求沉淀为知识条目（force=true 覆盖更新）
  sedimentRequirement(reqId, force = false) {
    return request.post(`/knowledge/sediment/requirement/${reqId}`, null, {
      params: { force },
    })
  },

  // 把用户故事的业务规则沉淀为业务知识笔记
  sedimentUserStory(storyId, force = false) {
    return request.post(`/knowledge/sediment/user-story/${storyId}`, null, {
      params: { force },
    })
  },

  // 把某需求的用户故事业务规则追加到主笔记「场景规则」子笔记
  sedimentRequirementRules(reqId) {
    return request.post(`/knowledge/sediment/requirement/${reqId}/rules`)
  },

  // 把需求关联开发工单的操作手册交付物归档到业务知识
  archiveRequirementManual(reqId) {
    return request.post(`/knowledge/sediment/requirement/${reqId}/archive-manual`)
  },
}
