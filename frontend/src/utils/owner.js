/**
 * 多负责人字段工具（单一实现，各视图共用）。
 *
 * 存储约定：多选责任人在库中以逗号分隔字符串保存（沿用运营监控工单 handler 的既有做法），
 * 界面用数组维护；历史单值数据天然兼容（无分隔符即为单责任人）。
 */

/** 逗号串 / 数组 → 姓名数组（去空白、去重、剔除空项） */
export function ownerList(raw) {
  if (Array.isArray(raw)) {
    return [...new Set(raw.map((s) => String(s).trim()).filter(Boolean))]
  }
  const text = String(raw == null ? '' : raw)
  if (!text.trim()) return []
  return [...new Set(text.split(/[,，;；、]+/).map((s) => s.trim()).filter(Boolean))]
}

/** 数组 / 逗号串 → 落库用逗号分隔字符串 */
export function ownerText(raw) {
  return ownerList(raw).join(',')
}

/** 多负责人展示文案（顿号连接），空值返回 '' */
export function ownerLabel(raw) {
  return ownerList(raw).join('、')
}
