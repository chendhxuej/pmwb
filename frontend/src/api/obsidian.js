import request from './request'

// Obsidian 知识笔记联动（读取/写回/列表），供工单关联与知识沉淀页使用
export const obsidianApi = {
  // 列出 vault 指定目录下的笔记（不传 folders 用后端配置的运营目录）
  listNotes(folders) {
    return request.get('/obsidian/notes', {
      params: folders && folders.length ? { folders } : {},
    })
  },

  // 读取单条笔记内容
  getNoteContent(path) {
    return request.get('/obsidian/content', { params: { path } })
  },

  // 编辑后写回 Obsidian 源文件
  updateNoteContent(path, content) {
    return request.put('/obsidian/content', { path, content })
  },
}
