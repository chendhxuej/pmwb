/**
 * 邮件模板管理 composable
 *
 * 按 scene 维度存储/加载收件人/抄送人模板。
 * 数据持久化在 localStorage: pmwb_mail_templates
 */
import { ref } from 'vue'

const STORAGE_KEY = 'pmwb_mail_templates'

function loadTemplates() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveTemplates(templates) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(templates))
}

let templates = ref(loadTemplates())

// 监听跨实例变更（同一页面多个弹窗场景）
window.addEventListener('storage', (e) => {
  if (e.key === STORAGE_KEY) {
    templates.value = loadTemplates()
  }
})

/**
 * 获取指定场景的模板列表（最新优先）
 */
export function getSceneTemplates(scene) {
  return templates.value
    .filter((t) => t.scene === scene)
    .sort((a, b) => b.updatedAt - a.updatedAt)
}

/**
 * 新增模板
 */
export function addTemplate({ scene, name, to, cc }) {
  const now = Date.now()
  const template = {
    id: `tpl_${now}_${Math.random().toString(36).slice(2, 6)}`,
    scene,
    name: name || `模板 ${new Date().toLocaleDateString('zh-CN')}`,
    to: to || [],
    cc: cc || [],
    createdAt: now,
    updatedAt: now,
  }
  const list = [...templates.value, template]
  templates.value = list
  saveTemplates(list)
  return template
}

/**
 * 删除模板
 */
export function deleteTemplate(id) {
  const list = templates.value.filter((t) => t.id !== id)
  templates.value = list
  saveTemplates(list)
}

/**
 * 清空指定场景的所有模板
 */
export function clearSceneTemplates(scene) {
  const list = templates.value.filter((t) => t.scene !== scene)
  templates.value = list
  saveTemplates(list)
}
