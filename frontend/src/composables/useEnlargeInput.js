/**
 * 放大输入框 —— 全局单例状态
 *
 * 用法：
 *   const { open, save, close } = useEnlargeInput()
 *   open({ value, type, rows, onSave })  // 打开放大编辑对话框
 *
 * EnlargeInput 组件在点击放大按钮时调用 open()；
 * EnlargeInputDialog 组件挂载于 MainLayout，监听 visible 并渲染大号编辑框。
 */
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'

const _visible = ref(false)
const _value = ref('')
const _type = ref('')
const _rows = ref(undefined)
let _onSave = null
let _snapshot = ''

export function useEnlargeInput() {
  function open(payload = {}) {
    _value.value = payload.value ?? ''
    _type.value = payload.type || ''
    _rows.value = payload.rows
    _onSave = payload.onSave || null
    _snapshot = _value.value
    _visible.value = true
  }

  // 保存：写回原输入框并关闭
  function save() {
    if (_onSave) _onSave(_value.value)
    _onSave = null
    _visible.value = false
  }

  // 关闭：若内容有改动，二次确认是否放弃
  async function close() {
    if (_value.value !== _snapshot) {
      try {
        await ElMessageBox.confirm('内容已修改，确定放弃修改并关闭？', '提示', {
          confirmButtonText: '放弃修改',
          cancelButtonText: '继续编辑',
          type: 'warning',
        })
      } catch {
        return // 取消关闭，保持对话框
      }
    }
    _onSave = null
    _visible.value = false
  }

  return {
    visible: _visible,
    value: _value,
    type: _type,
    rows: _rows,
    open,
    save,
    close,
  }
}
