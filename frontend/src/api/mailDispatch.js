import request from './request.js'

const BASE = '/mail-dispatch'

// 邮件正文预览：Markdown → 带样式 + 签名的 HTML，供发件弹窗实时预览
// 新统一调用：{ scene, subject, variables, rawContent, body, body_format, add_signature }
export function previewEmail(data) {
  return request.post(`${BASE}/preview`, data)
}

// 统一邮件发送入口（全场景收口）
// 请求体：{ to, cc?, subject?, scene?, rawContent?|body?, variables?, templateId?, templateData? }
export function sendEmail(data) {
  return request.post(`${BASE}/send`, data)
}
