import request from './request.js'

export function getDevTickets(params) {
  return request.get('/dev-tickets', { params })
}

export function getDevTicket(id) {
  return request.get(`/dev-tickets/${id}`)
}

export function createDevTicket(data) {
  return request.post('/dev-tickets', data)
}

export function updateDevTicket(id, data) {
  return request.put(`/dev-tickets/${id}`, data)
}

export function updateDevTicketStatus(id, data) {
  return request.put(`/dev-tickets/${id}/status`, data)
}

export function deleteDevTicket(id) {
  return request.delete(`/dev-tickets/${id}`)
}

export function getDevTicketStats() {
  return request.get('/dev-tickets/stats')
}

export function getDevTicketSystems() {
  return request.get('/dev-tickets/meta/systems')
}

export function getDevTicketLogs(id) {
  return request.get(`/dev-tickets/${id}/logs`)
}

export function getDevTicketDeliverables(id) {
  return request.get(`/dev-tickets/${id}/deliverables`)
}
