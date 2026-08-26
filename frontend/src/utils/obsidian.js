// 打开 Obsidian 笔记的统一入口。
// 采用 vault + file 相对路径协议，与 DomainKnowledgeView 已验证可用写法一致。
const OBSIDIAN_VAULT = '知识图谱'

export function openObsidianNote(relPath) {
  if (!relPath) return
  const url = `obsidian://open?vault=${encodeURIComponent(OBSIDIAN_VAULT)}&file=${encodeURIComponent(relPath)}`
  window.open(url, '_blank')
}
