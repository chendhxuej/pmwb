import request from './request.js'

// 任务中心统计（总待办/超期/临期/各来源/各状态）
export function getTaskStats() {
  return request.get('/task-center/stats')
}

// 统一任务列表（来源/状态/超期/关键字筛选 + 分页）
export function getTasks(params) {
  return request.get('/task-center/tasks', { params })
}

// 任务详情
export function getTaskDetail(source, sourceId) {
  return request.get(`/task-center/tasks/${source}/${encodeURIComponent(sourceId)}`)
}

// 按姓名解析邮箱（统一邮件中心通讯录）
export function resolveTaskContacts(names) {
  return request.post('/task-center/resolve-contacts', { names })
}

// 发送任务通知/催办邮件（正文自动附任务清单）
export function sendTaskEmail(data) {
  return request.post('/task-center/send', data)
}

// 预览邮件正文（dry_run：后端按模板拼装完整结构化正文，所见即所得，不发送不落库）
export function previewTaskEmail(tasks, sendType) {
  return request.post('/task-center/send', {
    tasks,
    send_type: sendType || 'urge',
    dry_run: true,
  })
}
