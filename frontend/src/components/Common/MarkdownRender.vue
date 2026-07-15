<template>
  <div ref="contentRef" class="markdown-body" v-html="renderedHtml"></div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import mermaid from 'mermaid'

const props = defineProps({
  content: { type: String, default: '' },
})
const emit = defineEmits(['toc'])

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: false,
})

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  fontFamily: 'inherit',
})

const contentRef = ref(null)
const renderedHtml = ref('')
let mermaidSeq = 0

function wrapTables(root) {
  root.querySelectorAll('table').forEach((t) => {
    if (t.parentElement && t.parentElement.classList.contains('table-wrap')) return
    const wrap = document.createElement('div')
    wrap.className = 'table-wrap'
    t.parentNode.insertBefore(wrap, t)
    wrap.appendChild(t)
  })
}

function buildToc(root) {
  const heads = root.querySelectorAll('h2, h3')
  const toc = []
  let idx = 0
  heads.forEach((h) => {
    const text = (h.textContent || '').trim()
    if (text === '目录') return // 跳过文档自带的目录章节
    idx += 1
    const id = `sec-${idx}`
    h.id = id
    h.classList.add('bible-heading')
    toc.push({ id, text, level: h.tagName === 'H2' ? 2 : 3 })
  })
  emit('toc', toc)
}

async function renderMermaid(root) {
  const blocks = root.querySelectorAll('pre code.language-mermaid')
  for (const block of blocks) {
    const code = block.textContent || ''
    const id = `mermaid-${mermaidSeq++}`
    try {
      const { svg } = await mermaid.render(id, code)
      const pre = block.parentElement
      const wrapper = document.createElement('div')
      wrapper.className = 'mermaid-block'
      wrapper.innerHTML = svg
      if (pre && pre.parentElement) {
        pre.parentElement.replaceChild(wrapper, pre)
      }
    } catch (e) {
      if (block.parentElement) block.parentElement.classList.add('mermaid-error')
    }
  }
}

async function render() {
  renderedHtml.value = md.render(props.content || '')
  await nextTick()
  const root = contentRef.value
  if (!root) return
  wrapTables(root)
  buildToc(root)
  await renderMermaid(root)
}

onMounted(render)
watch(() => props.content, render)
</script>

<style>
.markdown-body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 15px;
  line-height: 1.75;
  color: #303133;
  word-wrap: break-word;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  font-weight: 600;
  line-height: 1.4;
  color: #1f2d3d;
  margin: 28px 0 14px;
}

.markdown-body h1 {
  font-size: 26px;
  padding-bottom: 12px;
  border-bottom: 2px solid #ebeef5;
}

.markdown-body h2 {
  font-size: 21px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.markdown-body h3 {
  font-size: 17px;
  color: #303133;
}

.markdown-body .bible-heading {
  scroll-margin-top: 80px;
}

.markdown-body p {
  margin: 12px 0;
}

.markdown-body a {
  color: #409eff;
  text-decoration: none;
}

.markdown-body a:hover {
  text-decoration: underline;
}

.markdown-body ul,
.markdown-body ol {
  padding-left: 24px;
  margin: 12px 0;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body blockquote {
  margin: 14px 0;
  padding: 10px 16px;
  background: #f4f8ff;
  border-left: 4px solid #409eff;
  color: #5a6573;
  border-radius: 0 6px 6px 0;
}

.markdown-body blockquote p {
  margin: 4px 0;
}

.markdown-body hr {
  border: none;
  border-top: 1px solid #ebeef5;
  margin: 24px 0;
}

/* 行内代码 */
.markdown-body code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  background: #f0f2f5;
  color: #d6326e;
  padding: 2px 6px;
  border-radius: 4px;
}

/* 代码块 */
.markdown-body pre {
  margin: 14px 0;
  border-radius: 8px;
  overflow: auto;
}

.markdown-body pre code {
  display: block;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  font-size: 13px;
  line-height: 1.6;
  border-radius: 8px;
}

/* mermaid 图块 */
.markdown-body .mermaid-block {
  margin: 18px 0;
  padding: 12px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow-x: auto;
  text-align: center;
}

.markdown-body .mermaid-block svg {
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}

.markdown-body pre.mermaid-error {
  border: 1px solid #f56c6c;
}

/* 表格：包一层横向滚动，避免超宽表格撑破布局 */
.markdown-body .table-wrap {
  margin: 16px 0;
  overflow-x: auto;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  min-width: 720px;
  font-size: 13.5px;
  background: #fff;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid #ebeef5;
  padding: 9px 12px;
  text-align: left;
  vertical-align: top;
  white-space: normal;
}

.markdown-body thead th {
  background: #f5f7fa;
  font-weight: 600;
  color: #1f2d3d;
  position: sticky;
  top: 0;
}

.markdown-body tbody tr:nth-child(even) {
  background: #fafbfc;
}

.markdown-body tbody tr:hover {
  background: #f0f7ff;
}

.markdown-body img {
  max-width: 100%;
}
</style>
