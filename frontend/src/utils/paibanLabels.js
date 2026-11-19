/**
 * 排版管理枚举转译工具（唯一实现）。
 * 标签字典来自 /paiban/meta 的 labels（后端 constants/paiban.py 单一真相源）。
 * 接口降级时用空字典兜底 → 直接回显 key，绝不硬编码第二份中文映射。
 */
export function makeLabeler(metaRef) {
  return function lbl(group, key) {
    if (key === undefined || key === null || key === '') return '—'
    return metaRef?.value?.labels?.[group]?.[key] ?? key
  }
}
