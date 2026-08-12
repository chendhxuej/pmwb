import { ref, watch, unref, isRef, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'

/**
 * 抽屉/弹窗表单草稿持久化 composable
 *
 * 功能：
 * 1. 自动将表单数据持久化到 localStorage（按 路由 + drawerId + 记录标识 维度）
 * 2. 重开抽屉自动恢复草稿（同一条记录才恢复，避免串台）
 * 3. 存在未保存修改时关闭前弹二次确认
 * 4. 提交成功后清草稿
 *
 * @param {string} drawerId - 抽屉标识（同路由内唯一）
 * @param {import('vue').Ref<object>|object} formSource - 表单数据（支持 ref 或 reactive 对象）
 * @param {object} [options]
 * @param {boolean} [options.enabled=true] - 是否启用草稿功能
 * @param {number} [options.maxAge=30*60*1000] - 草稿最大存活时间（默认 30 分钟）
 * @param {Function|import('vue').Ref} [options.keySuffix] - 记录标识（如工单 id），用于区分不同记录的草稿
 * @param {Function} [options.onBeforeClose] - 自定义关闭前处理，返回 false 表示由其自行控制关闭
 * @returns {{ dirty: import('vue').Ref<boolean>, restoreDraft: Function, clearDraft: Function, handleBeforeClose: Function }}
 */
export function useDrawerDraft(drawerId, formSource, options = {}) {
  const { enabled = true, maxAge = 30 * 60 * 1000, keySuffix, onBeforeClose } = options
  const route = useRoute()
  const dirty = ref(false)

  let initialSnapshot = null
  let saveTimer = null
  let isRestoring = false

  /** 读取当前表单对象（兼容 ref / reactive） */
  function getForm() {
    return isRef(formSource) ? formSource.value : formSource
  }

  /** 计算存储 key：路由 + drawerId + 记录标识，防止不同记录草稿串台 */
  function getStorageKey() {
    let suffix = ''
    if (typeof keySuffix === 'function') suffix = keySuffix()
    else if (keySuffix !== undefined) suffix = unref(keySuffix)
    return `drawer_draft:${route.name || 'unknown'}:${drawerId}:${suffix ?? ''}`
  }

  /** 生成可序列化的表单快照 */
  function snapshot(value) {
    if (!value || typeof value !== 'object') return value
    try {
      return JSON.parse(JSON.stringify(value))
    } catch {
      return null
    }
  }

  /** 持久化草稿到 localStorage */
  function saveDraft() {
    if (!enabled || isRestoring) return
    try {
      const data = snapshot(getForm())
      if (!data) return
      localStorage.setItem(
        getStorageKey(),
        JSON.stringify({ data, savedAt: Date.now(), route: route.fullPath }),
      )
    } catch (e) {
      console.warn('[useDrawerDraft] 保存草稿失败:', e)
    }
  }

  /** 防抖保存，避免高频写 localStorage */
  function debouncedSave() {
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(saveDraft, 300)
  }

  /** 重新以当前表单为基线（不写 localStorage） */
  function resetBaseline() {
    initialSnapshot = snapshot(getForm())
    dirty.value = false
  }

  /** 从 localStorage 恢复草稿；调用方应在打开弹窗、表单填充完成后触发 */
  function restoreDraft() {
    if (!enabled) {
      resetBaseline()
      return false
    }
    isRestoring = true
    try {
      const key = getStorageKey()
      const raw = localStorage.getItem(key)
      if (!raw) return false
      const parsed = JSON.parse(raw)
      if (!parsed || !parsed.data) return false

      // 草稿过期则丢弃
      if (Date.now() - parsed.savedAt > maxAge) {
        localStorage.removeItem(key)
        return false
      }

      Object.assign(getForm(), parsed.data)
      return true
    } catch (e) {
      console.warn('[useDrawerDraft] 恢复草稿失败:', e)
      return false
    } finally {
      // 恢复后以「当前内容」为基线，避免刚打开就判定为脏
      initialSnapshot = snapshot(getForm())
      dirty.value = false
      isRestoring = false
    }
  }

  /** 清除草稿并重置基线（提交成功 / 确认丢弃后调用） */
  function clearDraft() {
    try {
      localStorage.removeItem(getStorageKey())
    } catch {
      /* ignore */
    }
    resetBaseline()
  }

  /** 关闭前处理：脏数据二次确认 */
  function handleBeforeClose(done) {
    const doClose = typeof done === 'function' ? done : () => {}
    const closeAction = () => {
      clearDraft()
      doClose()
    }

    if (onBeforeClose) {
      // 返回 false 表示由自定义逻辑接管（如保存中禁止关闭）
      if (onBeforeClose(closeAction) === false) return
    }

    if (!dirty.value) {
      closeAction()
      return
    }

    ElMessageBox.confirm('当前有未保存的修改，确定要关闭吗？', '提示', {
      confirmButtonText: '确定关闭',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(closeAction)
      .catch(() => {
        /* 用户取消，不关闭 */
      })
  }

  // 立即建立监听（原实现依赖调用方手动调用 startWatching，导致草稿功能完全不生效）
  if (enabled) {
    initialSnapshot = snapshot(getForm())
    watch(
      () => (isRef(formSource) ? formSource.value : formSource),
      (newVal) => {
        if (isRestoring) return
        dirty.value = JSON.stringify(snapshot(newVal)) !== JSON.stringify(initialSnapshot)
        if (dirty.value) debouncedSave()
      },
      { deep: true },
    )
  }

  onUnmounted(() => {
    if (saveTimer) clearTimeout(saveTimer)
  })

  return { dirty, restoreDraft, clearDraft, resetBaseline, handleBeforeClose }
}
