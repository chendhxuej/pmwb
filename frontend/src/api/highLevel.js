import request from './request.js'

// ── 高级别工单（任务中心子模块，2026-10-15）──────────────────────

// 高级别工单列表（跟踪态/来源/级别/责任人/统一态/超期/关键字筛选 + 分页）
// 默认仅返回「在跟池」（track_status ∈ open/tracking/escalated），include_closed=true 放开历史态
export function getHighLevelTasks(params) {
  return request.get('/high-level/tasks', { params })
}

// 在跟池统计：来源 / 级别 / 跟踪态 / 超期 / 已升级 / 未分配责任人
export function getHighLevelStats() {
  return request.get('/high-level/stats')
}

// 同步高级别工单池（幂等）：采集全部来源 → 规则判定 → 刷跟踪表 → 源消失检测
export function syncHighLevel() {
  return request.post('/high-level/sync')
}

// 人工更新跟踪态 / 设置人工覆盖（lock 锁定 / escalate 提级 / dismiss 移出；空串清除）
export function updateHighLevelTrack(source, sourceId, payload) {
  return request.patch(`/high-level/track/${source}/${encodeURIComponent(sourceId)}`, payload)
}

// 批量更新跟踪态：items = [{source, source_id, track_status?, manual_override?, operator?}]
export function updateHighLevelTrackBatch(items) {
  return request.post('/high-level/track/batch', { items })
}

// 邮件正文 Markdown 草稿（主题 + 正文），供左侧编辑区默认值
export function requestHighLevelDraft(tasks, sendType, body, recipientName) {
  return request.post('/high-level/draft', {
    tasks,
    send_type: sendType || 'urge',
    body: body || '',
    recipient_name: recipientName || '',
  })
}

// 发送督办/同步邮件；真发须带 confirm_send=true（前端点击触发），dry_run 仅预览
export function sendHighLevelEmail(data) {
  return request.post('/high-level/send', data)
}
