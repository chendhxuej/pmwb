import request from './request'

export const healthApi = {
  check() {
    return request.get('/health')
  },
}
