import request from './request.js'

export function sendReminder(data) {
  return request.post('/reminders/send', data)
}

export function getReminderRecords(reqId) {
  return request.get(`/reminders/${reqId}`)
}
