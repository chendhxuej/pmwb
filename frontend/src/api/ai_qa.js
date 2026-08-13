import request from './request.js'

export function aiQaAsk(question, history = null) {
  // 大模型（含 reasoning）响应较慢，放宽到 120s
  return request.post('/ai-qa/ask', { question, history }, { timeout: 120000 })
}

export function aiQaStatus() {
  return request.get('/ai-qa/status')
}
