import request from './request.js'

const BASE = '/mail-dispatch'

// 邮件正文预览：Markdown → 带样式 + 签名的 HTML，供发件弹窗实时预览
export function previewEmail(data) {
  return request.post(`${BASE}/preview`, data)
}
