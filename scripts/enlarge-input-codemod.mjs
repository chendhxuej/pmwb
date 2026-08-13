/**
 * 一次性 codemod：把 frontend/src 下所有 <el-input ...> 重命名为 <EnlargeInput ...>。
 *
 * 设计：
 * - 仅匹配小写 <el-input 且其后紧跟空白 / > / /（避免误伤 <el-input-number> 等）。
 * - 同时替换闭合标签 </el-input> -> </EnlargeInput>。
 * - 不修改 import、不新增 import（EnlargeInput 已在 main.js 全局注册）。
 *
 * 运行：node scripts/enlarge-input-codemod.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SRC_DIR = path.resolve(__dirname, '../frontend/src')

const OPEN_RE = /<el-input(?=[\s>/])/g
const CLOSE_RE = /<\/el-input>/g

let totalOpen = 0
let totalClose = 0
let filesChanged = 0
const changedFiles = []

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      walk(full)
    } else if (entry.isFile() && entry.name.endsWith('.vue')) {
      processFile(full)
    }
  }
}

function processFile(file) {
  const src = fs.readFileSync(file, 'utf8')
  let out = src
  out = out.replace(OPEN_RE, (m) => {
    totalOpen++
    return '<EnlargeInput'
  })
  out = out.replace(CLOSE_RE, () => {
    totalClose++
    return '</EnlargeInput>'
  })
  if (out !== src) {
    fs.writeFileSync(file, out, 'utf8')
    filesChanged++
    changedFiles.push(path.relative(SRC_DIR, file))
  }
}

walk(SRC_DIR)

console.log('=== enlarge-input codemod 结果 ===')
console.log(`扫描并重命名：<el-input 出现 ${totalOpen} 次，</el-input> 出现 ${totalClose} 次`)
console.log(`改动文件数：${filesChanged}`)
changedFiles.forEach((f) => console.log('  - ' + f))

// 校验：确认没有残留的 <el-input（应为 0，除非 EP 内部引用——本项目模板里理论上没有）
const leftover = []
function checkLeftover(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) checkLeftover(full)
    else if (entry.isFile() && entry.name.endsWith('.vue')) {
      const s = fs.readFileSync(full, 'utf8')
      // 排除 <ElInput（大写，安全）与 <el-input-number 等
      const m = s.match(/<el-input(?![A-Za-z-])/g)
      if (m) leftover.push(path.relative(SRC_DIR, full) + ` (${m.length})`)
    }
  }
}
checkLeftover(SRC_DIR)
console.log(`残留 <el-input（应排除大写与 number 等，正常应为 0）：${leftover.length}`)
leftover.forEach((f) => console.log('  残留: ' + f))
