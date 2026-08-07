import request from './request.js'

// 基础数据：组织 + 人员主数据（全站选人组件统一数据源）

export const basicDataApi = {
  // 批量导入
  importFromExcel(file) {
    const form = new FormData()
    form.append('file', file)
    return request.post('/basic-data/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 下载导入模板
  downloadTemplate() {
    return request.get('/basic-data/template', {
      responseType: 'blob',
    })
  },

  // 选人组件分组选项：[{ org_id, org_name, options: [{ value, label, email }] }]
  getStaffOptions() {
    return request.get('/basic-data/staff-options')
  },

  // 角色/身份定义 CRUD
  listRoles() {
    return request.get('/basic-data/roles')
  },
  createRole(data) {
    return request.post('/basic-data/roles', data)
  },
  updateRole(id, data) {
    return request.put(`/basic-data/roles/${id}`, data)
  },
  deleteRole(id) {
    return request.delete(`/basic-data/roles/${id}`)
  },

  // 轻量选项（下拉用，不加载全量人员）
  getOrgOptions() {
    return request.get('/basic-data/org-options')
  },
  getRoleOptions() {
    return request.get('/basic-data/role-options')
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

  // 业务领域
  getBusinessDomains(params = {}) {
    return request.get('/basic-data/business-domains', { params })
  },
  createBusinessDomain(data) {
    return request.post('/basic-data/business-domains', data)
  },
  updateBusinessDomain(code, data) {
    return request.put(`/basic-data/business-domains/${code}`, data)
  },
  deleteBusinessDomain(code) {
    return request.delete(`/basic-data/business-domains/${code}`)
  },
  getDomainRelated(code) {
    return request.get(`/basic-data/business-domains/${code}/related`)
  },
}

// ---------------------------------------------------------------------------
// 选人选项模块级缓存（所有 StaffSelect 共享一次加载；管理页变更后调用 refresh）
// L1 同组件实例 — 本组件 ref 更新
// L2 同前端实例 — subscribers 广播（同页面多个 StaffSelect / 跨路由）
// L3 跨标签页   — BroadcastChannel 通知其他标签页刷新
// ---------------------------------------------------------------------------
let optionsCache = null
let optionsPromise = null
const subscribers = new Set()

// L3: BroadcastChannel 跨标签页广播
const _bc =
  typeof BroadcastChannel !== 'undefined'
    ? new BroadcastChannel('pmwb-staff-options')
    : null

if (_bc) {
  _bc.onmessage = (event) => {
    if (event.data?.type === 'refresh') {
      // 收到其他标签页的变更通知，静默刷新本地缓存（不再广播，避免循环）
      _doLoad(true).catch(() => {})
    }
  }
}

function _doLoad(force) {
  if (optionsCache && !force) return Promise.resolve(optionsCache)
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

export async function loadStaffOptions(force = false) {
  return _doLoad(force)
}

export function refreshStaffOptions() {
  // L3: 通知其他标签页
  if (_bc) {
    try {
      _bc.postMessage({ type: 'refresh', ts: Date.now() })
    } catch {}
  }
  return _doLoad(true)
}

// 订阅缓存刷新（StaffSelect 挂载时订阅，卸载时退订）
export function subscribeStaffOptions(fn) {
  subscribers.add(fn)
  return () => subscribers.delete(fn)
}
