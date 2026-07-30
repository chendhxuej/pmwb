import { ref, watch, onUnmounted, getCurrentInstance } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'

/**
 * 抽屉表单草稿持久化 composable
 *
 * 功能：
 * 1. 自动将表单数据持久化到 localStorage（按 路由+drawerId 维度）
 * 2. 重开抽屉自动恢复草稿
 * 3. 存在未保存修改时关闭前弹二次确认
 * 4. 提交成功后清草稿
 *
 * @param {string} drawerId - 抽屉标识（同路由内唯一）
 * @param {import('vue').Ref<object>} formRef - 响应式表单数据对象
 * @param {object} [options]
 * @param {boolean} [options.enabled=true] - 是否启用草稿功能
 * @param {number} [options.maxAge=30*60*1000] - 草稿最大存活时间（默认30分钟）
 * @param {Function} [options.onBeforeClose] - 自定义关闭前处理（如叠加校验逻辑）
 * @returns {{ dirty: import('vue').Ref<boolean>, restoreDraft: () => void, clearDraft: () => void, handleBeforeClose: (done: Function) => void }}
 */
export function useDrawerDraft(drawerId, formRef, options = {}) {
  const { enabled = true, maxAge = 30 * 60 * 1000, onBeforeClose } = options
  const route = useRoute()
  const dirty = ref(false)

  // 存储 key：路由名 + drawerId 防串台
  const storageKey = `drawer_draft:${route.name || 'unknown'}:${drawerId}`

  // 保存时的快照（用于 dirty 比对）
  let initialSnapshot = null
  let saveTimer = null
  let isRestoring = false

  /** 生成可序列化的表单快照（去除非 JSON 字段） */
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
      const data = snapshot(formRef.value)
      if (data) {
        const payload = JSON.stringify({
          data,
          savedAt: Date.now(),
          route: route.fullPath,
        })
        localStorage.setItem(storageKey, payload)
      }
    } catch (e) {
      console.warn(`[useDrawerDraft] 保存草稿失败:`, e)
    }
  }

  /** 防抖保存，避免高频写 localStorage */
  function debouncedSave() {
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(saveDraft, 300)
  }

  /** 从 localStorage 恢复草稿 */
  function restoreDraft() {
    if (!enabled) return
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (!parsed || !parsed.data) return

      // 检查草稿是否过期
      if (Date.now() - parsed.savedAt > maxAge) {
        localStorage.removeItem(storageKey)
        return
      }

      // 恢复数据
      isRestoring = true
      Object.assign(formRef.value, parsed.data)
      initialSnapshot = snapshot(formRef.value)
      dirty.value = false
      isRestoring = false
    } catch (e) {
      console.warn(`[useDrawerDraft] 恢复草稿失败:`, e)
      isRestoring = false
    }
  }

  /** 清除草稿 */
  function clearDraft() {
    try {
      localStorage.removeItem(storageKey)
    } catch { /* ignore */ }
    initialSnapshot = snapshot(formRef.value)
    dirty.value = false
  }

  /** 关闭前处理 */
  function handleBeforeClose(done) {
    const closeAction = () => {
      clearDraft()
      done()
    }

    // 执行自定义前置逻辑（如果有）
    if (onBeforeClose) {
      const result = onBeforeClose(closeAction)
      // 如果 onBeforeClose 返回了 false，由它自己控制 done
      if (result === false) return
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
      .then(() => {
        clearDraft()
        done()
      })
      .catch(() => {
        // 用户取消，不关闭
      })
  }

  /** 标记初始状态，开始监听 */
  function startWatching() {
    if (!enabled) return
    // 记录初始快照
    initialSnapshot = snapshot(formRef.value)

    // 监听表单变化
    watch(
      formRef,
      (newVal) => {
        if (isRestoring) return
        const current = snapshot(newVal)
        dirty.value = JSON.stringify(current) !== JSON.stringify(initialSnapshot)
        if (dirty.value) {
          debouncedSave()
        }
      },
      { deep: true },
    )
  }

  // 组件卸载时清理
  onUnmounted(() => {
    if (saveTimer) clearTimeout(saveTimer)
  })

  return {
    dirty,
    restoreDraft,
    clearDraft,
    handleBeforeClose,
    startWatching,
  }
}
