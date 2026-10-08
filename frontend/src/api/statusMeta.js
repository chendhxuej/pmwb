// 状态元数据（状态注册表）前端缓存层
//
// 唯一真相源在后端 backend/constants/status_registry.py，通过
// GET /api/v1/meta/status-domains 暴露。本模块负责：
//   L1 模块级内存缓存（同会话只拉一次）
//   L2 订阅通知（元数据刷新后通知 statusConfig hydrate + 各页面重渲染）
//   L3 BroadcastChannel 跨标签页同步（多开窗口时保持一致）
//
// 新增状态时后端只改注册表，前端**无需改动**：刷新一下元数据即全站生效。

import request from './request.js'

const state = {
  data: null,
  promise: null,
}

const subscribers = new Set()

const bc =
  typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('pmwb-status-meta') : null

if (bc) {
  bc.onmessage = (e) => {
    if (e.data && e.data.type === 'refresh') {
      // 另一个标签页刷新了元数据 → 本页同步重拉
      loadStatusMeta(true).catch(() => {})
    }
  }
}

/**
 * 拉取状态元数据（带缓存）。force=true 强制重拉。
 * @returns {Promise<Object>} { domains, unified_statuses, unified_labels, source_domain, keywork_prefix }
 */
export function loadStatusMeta(force = false) {
  if (!force && state.data) return Promise.resolve(state.data)
  if (!force && state.promise) return state.promise
  state.promise = request
    .get('/meta/status-domains')
    .then((data) => {
      state.data = data || null
      state.promise = null
      subscribers.forEach((fn) => {
        try {
          fn(state.data)
        } catch (e) {
          console.warn('[statusMeta] subscriber error', e)
        }
      })
      return state.data
    })
    .catch((err) => {
      state.promise = null
      throw err
    })
  return state.promise
}

/** 强制刷新并向其他标签页广播。 */
export function refreshStatusMeta() {
  if (bc) {
    try {
      bc.postMessage({ type: 'refresh', ts: Date.now() })
    } catch (e) {
      /* ignore */
    }
  }
  return loadStatusMeta(true)
}

/** 订阅元数据变更；返回取消订阅函数。 */
export function subscribeStatusMeta(fn) {
  subscribers.add(fn)
  return () => subscribers.delete(fn)
}

/** 同步读取已缓存的元数据（未加载时为 null）。 */
export function getStatusMetaCache() {
  return state.data
}

export default { loadStatusMeta, refreshStatusMeta, subscribeStatusMeta, getStatusMetaCache }
