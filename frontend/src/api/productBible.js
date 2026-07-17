import request from './request'

export const productBibleApi = {
  // 业务目录（key + 名称）
  getCatalog() {
    return request.get('/product-bible')
  },

  // 指定业务的产品圣经内容
  getBible(key) {
    return request.get(`/product-bible/${key}`)
  },

  // 保存编辑后的 markdown 写回 Obsidian 源文件
  updateBible(key, markdown) {
    return request.put(`/product-bible/${key}`, { markdown })
  },

  // docx 内嵌图片的直链（后端 media 路由）
  getMediaUrl(key, filename) {
    return `/api/v1/product-bible/${key}/media/${encodeURIComponent(filename)}`
  },
}
