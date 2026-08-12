import request from './request'

export const todoApi = {
  listTodos(params) {
    return request.get('/todos', { params })
  },

  getTodo(id) {
    return request.get(`/todos/${id}`)
  },

  createTodo(data) {
    return request.post('/todos', data)
  },

  updateTodo(id, data) {
    return request.put(`/todos/${id}`, data)
  },

  updateTodoStatus(id, status) {
    return request.patch(`/todos/${id}/status`, null, { params: { status } })
  },

  deleteTodo(id) {
    return request.delete(`/todos/${id}`)
  },

  getStats() {
    return request.get('/todos/stats')
  }
}
