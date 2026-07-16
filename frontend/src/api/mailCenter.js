import request from './request.js'

// 统一邮件中心(3210)健康状态
export function getMailCenterHealth() {
  return request.get('/mail-center/health')
}
