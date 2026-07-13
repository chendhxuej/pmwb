import request from './request'

export const dashboardApi = {
  getDashboard() {
    return request.get('/dashboard')
  }
}
