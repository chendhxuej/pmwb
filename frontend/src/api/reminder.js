import request from './request.js'

export function sendReminder(data) {
  return request.post('/reminders/send', data)
}

export function getReminderRecords(reqId) {
  return request.get(`/reminders/${reqId}`)
}

export function resolveContacts(names) {
  return request.post('/reminders/resolve-contacts', { names })
}
