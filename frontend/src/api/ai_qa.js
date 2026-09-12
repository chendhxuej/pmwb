import request from './request.js'

export function aiQaAsk(question, history = null) {
  // 大模型（含 reasoning）响应较慢，与全局超时保持一致（900s），不做短超时管控
  return request.post('/ai-qa/ask', { question, history }, { timeout: 900000 })
}

export function aiQaStatus() {
  return request.get('/ai-qa/status')
}
