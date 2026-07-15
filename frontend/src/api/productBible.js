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
}
