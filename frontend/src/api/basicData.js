import request from './request.js'

// 基础数据：组织 + 人员主数据（全站选人组件统一数据源）

export const basicDataApi = {
  // 选人组件分组选项：[{ org_id, org_name, options: [{ value, label, email }] }]
  getStaffOptions() {
    return request.get('/basic-data/staff-options')
  },

  // 组织 CRUD
  listOrgs() {
    return request.get('/basic-data/orgs')
  },
  createOrg(data) {
    return request.post('/basic-data/orgs', data)
  },
  updateOrg(id, data) {
    return request.put(`/basic-data/orgs/${id}`, data)
  },
  deleteOrg(id) {
    return request.delete(`/basic-data/orgs/${id}`)
  },

  // 人员 CRUD
  listStaffs(params) {
    return request.get('/basic-data/staffs', { params })
  },
  createStaff(data) {
    return request.post('/basic-data/staffs', data)
  },
  updateStaff(id, data) {
    return request.put(`/basic-data/staffs/${id}`, data)
  },
  deleteStaff(id) {
    return request.delete(`/basic-data/staffs/${id}`)
  },
}

// ---------------------------------------------------------------------------
// 选人选项模块级缓存（所有 StaffSelect 共享一次加载；管理页变更后调用 refresh）
// ---------------------------------------------------------------------------
let optionsCache = null
let optionsPromise = null
const subscribers = new Set()

export async function loadStaffOptions(force = false) {
  if (optionsCache && !force) return optionsCache
  if (!optionsPromise || force) {
    optionsPromise = basicDataApi
      .getStaffOptions()
      .then((data) => {
        optionsCache = Array.isArray(data) ? data : []
        subscribers.forEach((fn) => fn(optionsCache))
        return optionsCache
      })
      .catch((err) => {
        optionsPromise = null
        throw err
      })
  }
  return optionsPromise
}

export function refreshStaffOptions() {
  return loadStaffOptions(true)
}

// 订阅缓存刷新（StaffSelect 挂载时订阅，卸载时退订）
export function subscribeStaffOptions(fn) {
  subscribers.add(fn)
  return () => subscribers.delete(fn)
}
