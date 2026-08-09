import request from './request'

export function listLlmProviders() {
  return request({ url: '/llm-providers', method: 'get' })
}

export function getLlmProviderPresets() {
  return request({ url: '/llm-providers/presets', method: 'get' })
}

export function createLlmProvider(data) {
  return request({ url: '/llm-providers', method: 'post', data })
}

export function updateLlmProvider(id, data) {
  return request({ url: `/llm-providers/${id}`, method: 'put', data })
}

export function deleteLlmProvider(id) {
  return request({ url: `/llm-providers/${id}`, method: 'delete' })
}

export function setDefaultLlmProvider(id) {
  return request({ url: `/llm-providers/${id}/set-default`, method: 'post' })
}

export function testLlmProvider(id) {
  return request({ url: `/llm-providers/${id}/test`, method: 'post' })
}
