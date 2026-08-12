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

// 按 SA 分组的待催办需求列表（催办中心批量催办）
export function getPendingReminders() {
  return request.get('/reminders/pending')
}

// 全局邮件发送记录（最近 limit 条）
export function getReminderRecordsList(limit = 50) {
  return request.get('/reminders/records', { params: { limit } })
}
