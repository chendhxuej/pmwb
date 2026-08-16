import request from './request'

export const meetingApi = {
  listMeetings(params) {
    return request.get('/meetings', { params })
  },

  getMeeting(id) {
    return request.get(`/meetings/${id}`)
  },

  createMeeting(data) {
    return request.post('/meetings', data)
  },

  updateMeeting(id, data) {
    return request.put(`/meetings/${id}`, data)
  },

  deleteMeeting(id) {
    return request.delete(`/meetings/${id}`)
  },

  sedimentMeeting(id, force = false) {
    return request.post(`/meetings/${id}/sediment`, null, { params: { force } })
  },

  deleteMeetingMinutes(id) {
    return request.delete(`/meetings/${id}/minutes`)
  },

  syncActionTodo(meetingId, actionId) {
    return request.post(`/meetings/${meetingId}/actions/${actionId}/sync-todo`)
  },

  listActions(params) {
    return request.get('/meetings/actions', { params })
  },

  getAction(actionId) {
    return request.get(`/meetings/actions/${actionId}`)
  },

  updateAction(meetingId, actionId, data) {
    return request.put(`/meetings/${meetingId}/actions/${actionId}`, data)
  },

  updateActionStatus(meetingId, actionId, data) {
    return request.put(`/meetings/${meetingId}/actions/${actionId}/status`, data)
  },

  superviseAction(meetingId, actionId, data) {
    return request.post(`/meetings/${meetingId}/actions/${actionId}/supervise`, data)
  },

  sendMeetingMail(meetingId, data) {
    return request.post(`/meetings/${meetingId}/send-mail`, data)
  }
}
