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

  sedimentMeeting(id) {
    return request.post(`/meetings/${id}/sediment`)
  },

  syncActionTodo(meetingId, actionId) {
    return request.post(`/meetings/${meetingId}/actions/${actionId}/sync-todo`)
  }
}
