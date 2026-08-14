import request from './request'

export function listWorkReports(params) {
  return request({ url: '/work-reports', method: 'get', params })
}

export function getWorkReport(id) {
  return request({ url: `/work-reports/${id}`, method: 'get' })
}

export function createWorkReport(data) {
  return request({ url: '/work-reports', method: 'post', data })
}

export function updateWorkReport(id, data) {
  return request({ url: `/work-reports/${id}`, method: 'put', data })
}

export function deleteWorkReport(id) {
  return request({ url: `/work-reports/${id}`, method: 'delete' })
}

export function generateWorkReport(data) {
  return request({ url: '/work-reports/generate', method: 'post', data })
}

export function getWorkReportGenStatus(id) {
  return request({ url: `/work-reports/${id}/gen-status`, method: 'get' })
}

export function finalizeWorkReport(id) {
  return request({ url: `/work-reports/${id}/finalize`, method: 'post' })
}

export function previewWorkReport(id, data) {
  return request({ url: `/work-reports/${id}/preview`, method: 'post', data })
}

export function sendWorkReport(id, data) {
  return request({ url: `/work-reports/${id}/send`, method: 'post', data })
}
