import request from './request.js'

// 需求「厂家开发状态」（生产部署环节）
// 口径铁律：厂家清单 = 团队评估中工作量 > 0 人天的系统，由后端 active_team_systems 唯一实现，
// 前端不做第二份过滤/判定，只负责展示与下发操作。

export function listVendorDevs(reqId) {
  return request.get(`/requirements/${encodeURIComponent(reqId)}/vendor-devs`)
}

export function createVendorDev(reqId, data) {
  return request.post(`/requirements/${encodeURIComponent(reqId)}/vendor-devs`, data)
}

export function updateVendorDev(reqId, vendorDevId, data) {
  return request.put(
    `/requirements/${encodeURIComponent(reqId)}/vendor-devs/${vendorDevId}`,
    data
  )
}

export function deleteVendorDev(reqId, vendorDevId) {
  return request.delete(`/requirements/${encodeURIComponent(reqId)}/vendor-devs/${vendorDevId}`)
}

// 厂家操作手册上传：JSON body 传 base64（走 URL 会撞长度上限）
export function uploadVendorManual(reqId, vendorDevId, filename, contentBase64) {
  return request.post(
    `/requirements/${encodeURIComponent(reqId)}/vendor-devs/${vendorDevId}/manual`,
    { filename, content_base64: contentBase64 }
  )
}

// ── 厂家团队「别名映射」字典 ──
export function listVendorTeams() {
  return request.get('/meta/vendor-teams')
}

export function createVendorTeam(data) {
  return request.post('/meta/vendor-teams', data)
}

export function updateVendorTeam(teamId, data) {
  return request.put(`/meta/vendor-teams/${teamId}`, data)
}

export function deleteVendorTeam(teamId) {
  return request.delete(`/meta/vendor-teams/${teamId}`)
}
