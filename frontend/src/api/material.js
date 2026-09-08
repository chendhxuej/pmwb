import request from './request.js'

// 材料
export function getMaterials(params) {
  return request.get('/materials', { params })
}
export function syncMaterials() {
  return request.post('/materials/sync')
}
export function previewMaterial(id) {
  return request.get(`/materials/${id}/preview`)
}
export function reassignMaterialCategory(id, categoryId) {
  return request.post(`/materials/${id}/category`, { category_id: categoryId })
}
export function deleteMaterial(id, removePhysical = false) {
  return request.delete(`/materials/${id}`, { params: { remove_physical: removePhysical } })
}
// 批量改分类
export function batchReassignCategory(ids, categoryId) {
  return request.post('/materials/batch-reassign', { ids, category_id: categoryId })
}
// 批量删除索引（removePhysical=true 时仅对手工上传生效）
export function batchDeleteMaterials(ids, removePhysical = false) {
  return request.post('/materials/batch-delete', { ids, remove_physical: removePhysical })
}
// 上传用 FormData，axios 自动加 multipart
export function uploadMaterial(formData) {
  return request.post('/materials/upload', formData)
}
// 批量上传：formData 内 files 为多个文件，另附 category_id / note / dup_action
export function batchUploadMaterials(formData) {
  return request.post('/materials/upload-batch', formData)
}
// 上传前重名预检
export function checkUploadConflict(payload) {
  return request.post('/materials/upload-check', payload)
}

// 分类
export function getCategories() {
  return request.get('/material-categories')
}
export function createCategory(data) {
  return request.post('/material-categories', data)
}
export function updateCategory(id, data) {
  return request.put(`/material-categories/${id}`, data)
}
export function deleteCategory(id) {
  return request.delete(`/material-categories/${id}`)
}

// 预览/下载直链（供 iframe / a 标签使用，绕过响应解包）
export function inlineMaterialUrl(id) {
  return `/api/v1/materials/${id}/inline`
}
export function downloadMaterialUrl(id) {
  return `/api/v1/materials/${id}/download`
}
