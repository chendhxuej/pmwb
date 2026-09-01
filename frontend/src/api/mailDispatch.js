import request from './request.js'

const BASE = '/mail-dispatch'

// 邮件正文预览：Markdown → 带样式 + 签名的 HTML，供发件弹窗实时预览
// 新统一调用：{ scene, subject, variables, rawContent, body, body_format, add_signature }
export function previewEmail(data) {
  return request.post(`${BASE}/preview`, data)
}

// 统一邮件发送入口（全场景收口）
// 请求体：{ to, cc?, subject?, scene?, rawContent?|body?, variables?, templateId?, templateData? }
// confirm_send 固定为 true：代表用户在页面上的显式发送操作（后端 dry_run 护栏据此放行真发）
export function sendEmail(data) {
  return request.post(`${BASE}/send`, { ...data, confirm_send: true })
}
