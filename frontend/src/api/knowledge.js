import request from './request'

export const knowledgeApi = {
  listItems(params) {
    return request.get('/knowledge', { params })
  },

  // 业务全过程时间线（双源：知识关联 + 归属工单）
  getBusinessTimeline(params) {
    return request.get('/knowledge/business-timeline', { params })
  },

  // 把需求/用户故事/关联事件回流到指定领域主笔记的自动区（人工区零覆盖，幂等）
  syncMainNote(domainCode) {
    return request.post('/knowledge/sync-main-note', { domain_code: domainCode })
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

  // 条目维度关联：按知识条目 id 获取/建立/移除过程性对象关联
  listByItem(id) {
    return request.get(`/knowledge/${id}/links`)
  },

  createItemLink(id, payload) {
    return request.post(`/knowledge/${id}/links`, payload)
  },

  deleteItemLink(id, sourceType, sourceId) {
    return request.delete(`/knowledge/${id}/links/${sourceType}/${sourceId}`)
  },

  // 新建业务知识主笔记（选领域后生成标准模板，幂等）
  createMainNote(domainCode) {
    return request.post('/knowledge/main-note', { domain_code: domainCode })
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

  // 把运营工单的结构化经验追加到主笔记「场景规则」子笔记
  sedimentOperationRules(issueId) {
    return request.post(`/knowledge/sediment/operation/${issueId}/rules`)
  },
}
