/**
 * 鉴权直链下载 / 内联预览统一入口
 *
 * 背景（2026-11-04）：mb-3 开启全局 JWT 鉴权后，凡是 `<a href="/api/...">`、
 * `window.open(url)`、`<iframe src="/api/...">` 这类"浏览器直连"的方式都拿不到
 * axios 拦截器注入的 Authorization 头，后端 AuthMiddleware 一律返回
 * {"code":401,"message":"未登录或登录已过期"}——表现为「周报下载/资料库文件下载」
 * 全部失败。这里统一改成 fetch 带 token 取 blob，再用 objectURL 落地。
 *
 * 使用约束：
 * - 所有 /api/v1 下的下载、图片/PDF 内联预览都必须走本模块，禁止再写裸 URL。
 * - 返回的 blob URL 由调用方负责释放（见 revokeBlobUrl），否则会内存泄漏。
 */

const TOKEN_KEY = 'pmwb_token'

function authHeaders() {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** 从 Content-Disposition 解析文件名（兼容 RFC 5987 的 filename*=UTF-8''） */
export function parseFilename(disposition, fallback = '') {
  if (!disposition) return fallback
  const star = /filename\*=(?:UTF-8|utf-8)''([^;]+)/i.exec(disposition)
  if (star && star[1]) {
    try {
      return decodeURIComponent(star[1].replace(/^"|"$/g, ''))
    } catch (e) {
      /* 落到下面的普通分支 */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(disposition)
  if (plain && plain[1]) {
    try {
      return decodeURIComponent(plain[1])
    } catch (e) {
      return plain[1]
    }
  }
  return fallback
}

async function readError(resp) {
  let msg = `下载失败（HTTP ${resp.status}）`
  if (resp.status === 401) msg = '未登录或登录已过期，请重新登录后再试'
  try {
    const text = await resp.text()
    if (text) {
      try {
        const j = JSON.parse(text)
        if (j && (j.message || j.detail)) msg = j.message || j.detail
      } catch (e) {
        if (text.length < 200) msg = text
      }
    }
  } catch (e) {
    /* 读不到 body 就用默认文案 */
  }
  return msg
}

/**
 * 带鉴权下载文件（触发浏览器保存）
 * @param {string} url 以 /api/v1 开头的后端路径
 * @param {string} [filename] 指定文件名；不传则用响应头里的名字
 * @returns {Promise<string>} 实际使用的文件名
 */
export async function downloadWithAuth(url, filename) {
  const resp = await fetch(url, { headers: authHeaders() })
  if (!resp.ok) throw new Error(await readError(resp))
  const blob = await resp.blob()
  const name =
    filename ||
    parseFilename(resp.headers.get('Content-Disposition'), '') ||
    decodeURIComponent(url.split('?')[0].split('/').pop() || 'download')

  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = name
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  // 60s 后释放：太快释放会让部分浏览器的下载中断
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
  return name
}

/**
 * 带鉴权在新标签页打开（替代 window.open(裸URL)，如客诉周报 HTML 报告）
 *
 * 注意：window.open 必须在点击手势内**同步**调用，否则会被浏览器当弹窗拦截，
 * 因此先占位空窗口、拿到数据后再改 location。
 * @param {string} url
 * @param {string} [mime] 渲染类型，默认 text/html
 */
export async function openWithAuth(url, mime = 'text/html') {
  const win = window.open('', '_blank')
  try {
    const resp = await fetch(url, { headers: authHeaders() })
    if (!resp.ok) throw new Error(await readError(resp))
    const blob = await resp.blob()
    const objectUrl = URL.createObjectURL(new Blob([blob], { type: mime }))
    if (win) {
      win.location.href = objectUrl
    } else {
      const a = document.createElement('a')
      a.href = objectUrl
      a.target = '_blank'
      document.body.appendChild(a)
      a.click()
      a.remove()
    }
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
  } catch (e) {
    if (win) win.close()
    throw e
  }
}

/**
 * 取 blob URL 供 iframe / img 内联预览（这类标签无法携带 Authorization 头）
 * @param {string} url
 * @param {string} [mime] 强制指定 MIME（后端若以 application/octet-stream 返回
 *   一份 HTML，iframe 会变成下载而不是渲染，此时需要显式指定 text/html）
 * @returns {Promise<string>} blob URL，用完请调用 revokeBlobUrl
 */
export async function fetchBlobUrl(url, mime) {
  const resp = await fetch(url, { headers: authHeaders() })
  if (!resp.ok) throw new Error(await readError(resp))
  const raw = await resp.blob()
  const blob = mime ? new Blob([raw], { type: mime }) : raw
  return URL.createObjectURL(blob)
}

/** 释放 fetchBlobUrl 产生的 objectURL */
export function revokeBlobUrl(url) {
  if (url && String(url).startsWith('blob:')) URL.revokeObjectURL(url)
}
