import request from './request.js'

// ── 敏感需求跟踪（需求与交付子模块，2026-10-25）──────────────────
// P0/P1 需求端到端倒排跟踪：5 阶段（评估/方案/开发/测试/上线交付）× 团队，
// 上线要求时间权威源 = pmwb_requirement_ext.version_required_date（不另存）。

// 敏感需求列表（跟踪态/团队/超期/关键字筛选 + 分页）
// 默认仅返回「在跟池」（track_status ∈ active/delayed/escalated），include_closed=true 放开历史态
export function getSensitiveReqs(params) {
  return request.get('/sensitive-reqs', { params })
}

// 在跟池统计：跟踪态 / 级别 / 团队 / 超期 / 临期 / 逾期未上线
export function getSensitiveReqStats() {
  return request.get('/sensitive-reqs/stats')
}

// 同步敏感需求池（幂等）：扫描 ext → 敏感判定 → upsert → 里程碑逾期回写跟踪态
export function syncSensitiveReqs() {
  return request.post('/sensitive-reqs/sync')
}

// 人工更新跟踪态 / 设置人工覆盖（lock 锁定 / dismiss 移出；空串清除）
export function updateSensitiveReqTrack(reqId, payload) {
  return request.patch(`/sensitive-reqs/track/${encodeURIComponent(reqId)}`, payload)
}

// 单个需求详情：跟踪态 + 需求本体 + 全量里程碑（含团队泳道分组 lanes）
export function getSensitiveReqDetail(reqId) {
  return request.get(`/sensitive-reqs/${encodeURIComponent(reqId)}/detail`)
}

// 按模板缓冲生成 5 阶段倒排建议（不落库），供确认调整后保存
export function getSensitiveReqSuggestion(reqId) {
  return request.get(`/sensitive-reqs/${encodeURIComponent(reqId)}/plan-suggestion`)
}

// 全量覆盖保存倒排里程碑（PUT 语义，未提交的旧行删除）
export function saveSensitiveReqMilestones(reqId, items) {
  return request.put(`/sensitive-reqs/${encodeURIComponent(reqId)}/milestones`, { items })
}

// 人工修正单个里程碑（owner/planned/actual/status/risk_note）
export function updateSensitiveReqMilestone(milestoneId, payload) {
  return request.patch(`/sensitive-reqs/milestone/${milestoneId}`, payload)
}

// 邮件正文 Markdown 草稿（主题 + 正文 + 结构化清单）
export function requestSensitiveReqDraft(tasks, sendType, body, recipientName) {
  return request.post('/sensitive-reqs/draft', {
    tasks,
    send_type: sendType || 'urge',
    body: body || '',
    recipient_name: recipientName || '',
  })
}

// 发送督办/同步邮件；真发须带 confirm_send=true（前端点击触发），dry_run 仅预览
export function sendSensitiveReqEmail(data) {
  return request.post('/sensitive-reqs/send', data)
}
