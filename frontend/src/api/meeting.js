import request from './request'

export const meetingApi = {
  listMeetings(params) {
    return request.get('/meetings', { params })
  },

  // ── 会议类型字典（唯一真相源 = pmwb_meeting_type）──
  listMeetingTypes() {
    return request.get('/meetings/types')
  },

  listMeetingTypeOptions() {
    return request.get('/meetings/types/options')
  },

  createMeetingType(data) {
    return request.post('/meetings/types', data)
  },

  updateMeetingType(id, data) {
    return request.put(`/meetings/types/${id}`, data)
  },

  deleteMeetingType(id) {
    return request.delete(`/meetings/types/${id}`)
  },

  // ── 参会人预制模板（挂会议类型，一键批量填入）──
  listAttendeeTemplates(params) {
    return request.get('/meetings/attendee-templates', { params })
  },

  createAttendeeTemplate(data) {
    return request.post('/meetings/attendee-templates', data)
  },

  updateAttendeeTemplate(id, data) {
    return request.put(`/meetings/attendee-templates/${id}`, data)
  },

  deleteAttendeeTemplate(id) {
    return request.delete(`/meetings/attendee-templates/${id}`)
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
    // confirm_send 固定为 true：代表用户在页面上的显式发送操作（后端 dry_run 护栏据此放行真发）
    return request.post(`/meetings/${meetingId}/send-mail`, { ...data, confirm_send: true })
  },

  // ── 会议附件（唯一实现=后端 services/meeting_attachment.py；上传=同名替换）──
  uploadAttachment(meetingId, file) {
    const fd = new FormData()
    fd.append('file', file)
    return request.post(`/meetings/${meetingId}/attachments`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  deleteAttachment(meetingId, name) {
    return request.delete(`/meetings/${meetingId}/attachments`, { params: { name } })
  },

  // 附件下载地址（带 JWT 须走 utils/download.js::downloadWithAuth，禁裸 URL / window.open）
  attachmentDownloadUrl(meetingId, name) {
    return `/api/v1/meetings/${meetingId}/attachments/download?name=${encodeURIComponent(name)}`
  }
}
