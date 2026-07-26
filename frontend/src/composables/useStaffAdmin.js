/**
 * 人员管理抽屉 —— 全局单例状态
 *
 * 用法：
 *   const { visible, openStaffAdmin, closeStaffAdmin } = useStaffAdmin()
 *   openStaffAdmin()  // 打开管理面板
 *
 * StaffAdminDrawer 组件监听 visible 并渲染；
 * StaffSelect 调 openStaffAdmin() 替代 router.push。
 */
import { ref } from 'vue'

const _visible = ref(false)
const _activeOrgId = ref(null) // 打开时可指定聚焦的团队

export function useStaffAdmin() {
  function openStaffAdmin(orgId = null) {
    _activeOrgId.value = orgId
    _visible.value = true
  }

  function closeStaffAdmin() {
    _visible.value = false
  }

  return {
    visible: _visible,
    activeOrgId: _activeOrgId,
    openStaffAdmin,
    closeStaffAdmin,
  }
}
