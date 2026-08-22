import { ref, watchEffect, onScopeDispose } from 'vue'

/**
 * 粘贴上传 Hook
 * 在指定区域内监听 paste 事件，从剪贴板读取文件对象并交给调用方处理。
 * 主要支持：截图工具复制后 Ctrl+V、资源管理器复制文件后 Ctrl+V。
 *
 * @param {Object} options
 * @param {import('vue').Ref<HTMLElement>} [options.targetRef] 监听区域，默认 document
 * @param {boolean|function|import('vue').Ref<boolean>} [options.enabled=true] 是否启用监听
 * @param {string} [options.accept='*'] 接受的文件类型，如 'image/*,.pdf'
 * @param {function(File, number): string} [options.generateName] 无文件名时的命名函数
 * @param {function(File[]): Promise<void>} options.onFiles 获取到文件后的回调
 */
export function usePasteUpload(options = {}) {
  const {
    targetRef,
    enabled = true,
    accept = '*',
    generateName,
    onFiles,
  } = options

  const isPasting = ref(false)
  const error = ref(null)

  const pad = (n) => String(n).padStart(2, '0')

  const defaultGenerateName = (file, idx) => {
    const now = new Date()
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
    const ext = file.type?.split('/')[1] || 'bin'
    return `paste-${ts}-${idx}.${ext}`
  }

  const genName = generateName || defaultGenerateName
  const placeholderNames = new Set(['image.png', 'image.jpg', 'image.jpeg', 'blob', ''])

  const ensureFileName = (file, idx) => {
    const name = file.name || ''
    if (!placeholderNames.has(name.toLowerCase())) return file
    const newName = genName(file, idx)
    return new File([file], newName, { type: file.type, lastModified: file.lastModified })
  }

  const matchAccept = (file, pattern) => {
    const p = pattern.trim()
    if (!p || p === '*') return true
    if (p.startsWith('.')) {
      return file.name.toLowerCase().endsWith(p.toLowerCase())
    }
    if (p.endsWith('/*')) {
      return file.type.startsWith(p.slice(0, -1))
    }
    return file.type === p
  }

  const filterFiles = (files) => {
    return Array.from(files)
      .filter((f) => f && f.size > 0)
      .map(ensureFileName)
      .filter((f) => {
        if (accept === '*' || !accept) return true
        const patterns = String(accept).split(',').map((s) => s.trim()).filter(Boolean)
        return patterns.some((p) => matchAccept(f, p))
      })
  }

  const isEditableTarget = () => {
    const active = document.activeElement
    if (!active) return false
    return active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable
  }

  const handlePaste = async (event) => {
    const rawFiles = event.clipboardData?.files
    if (!rawFiles || !rawFiles.length) return

    const files = filterFiles(rawFiles)
    if (!files.length) return

    // 如果焦点在可编辑元素内，不阻止默认行为，避免文本粘贴被误拦截
    if (!isEditableTarget()) {
      event.preventDefault()
    }

    error.value = null
    isPasting.value = true
    try {
      await onFiles(files)
    } catch (err) {
      error.value = err
    } finally {
      isPasting.value = false
    }
  }

  let cleanup = null

  watchEffect(() => {
    if (cleanup) {
      cleanup()
      cleanup = null
    }
    const active = typeof enabled === 'function' ? enabled() : enabled
    if (!active) return
    const target = targetRef?.value || document
    target.addEventListener('paste', handlePaste)
    cleanup = () => target.removeEventListener('paste', handlePaste)
  })

  onScopeDispose(() => {
    if (cleanup) {
      cleanup()
      cleanup = null
    }
  })

  return {
    isPasting,
    error,
  }
}
