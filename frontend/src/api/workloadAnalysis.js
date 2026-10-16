import request from './request.js'

// 工作量分析：统计的**单一数据源**——汇总卡 / 趋势图 / 分桶表全部取本接口，前端禁止自己算
export function getWorkloadStats(params) {
  return request.get('/workload-analysis/stats', { params })
}

export function exportWorkloadStats(params) {
  return request.get('/workload-analysis/export', { params, responseType: 'blob' })
}
