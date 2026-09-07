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

// 邮件正文 Markdown 草稿（左侧 Markdown 编辑区默认值）
// 2026-09-07：后端按场景装配引导语 + 任务卡片 Markdown 源（含 H3/超期/字段表/工单内容），
// 用户可基于此继续编辑；编辑后通过 TaskSendRequest.body 透传回后端再次渲染。
export function requestTaskCenterDraft(tasks, sendType, body) {
  return request.post('/task-center/draft', {
    tasks,
    send_type: sendType || 'urge',
    body: body || '',
  })
}
