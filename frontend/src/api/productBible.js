import request from './request'

export const productBibleApi = {
  // 业务目录（key=domain_code + 名称）
  getCatalog() {
    return request.get('/product-bible')
  },

  // 指定业务「知识标准化管理」主笔记标准结构视图
  // 返回 { key, name, title, updated_at, sections:[{key,title,level,kind,editable,kind_label,markdown}] }
  getMainNote(domainCode) {
    return request.get(`/knowledge/main-note/${domainCode}`)
  },

  // 编辑主笔记某一人工基线章节（按 key 定位）
  updateMainNoteSection(domainCode, key, markdown) {
    return request.put(`/knowledge/main-note/${domainCode}/section`, { key, markdown })
  },
}
