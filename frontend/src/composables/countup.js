// 数字滚动动画指令：v-countup="目标数字"
// 从 0 缓动到目标值（easeOutCubic），整数带千分位、小数保留原精度。
// 指令自管一个子节点 <span class="cu-num"> 作为唯一写入目标，
// 不与模板里的 {{ }} 插值节点冲突（使用本指令时模板不要再写 {{ }}）。
function formatNumber(val, original) {
  const num = Number(val)
  if (!isFinite(num)) return val == null ? '' : String(val)
  const decimals = (String(original).split('.')[1] || '').length
  if (decimals > 0) return num.toFixed(decimals)
  return Math.round(num).toLocaleString('en-US')
}

function animate(el, target) {
  const to = Number(target) || 0
  const duration = 600
  const start = performance.now()
  function frame(now) {
    const p = Math.min((now - start) / duration, 1)
    const eased = 1 - Math.pow(1 - p, 3)
    el.textContent = formatNumber(to * eased, target)
    if (p < 1) requestAnimationFrame(frame)
    else el.textContent = formatNumber(to, target)
  }
  requestAnimationFrame(frame)
}

// 取/建指令专属子节点，避免覆盖 Vue 管理的其它内容
function getTarget(el) {
  let span = el.querySelector(':scope > .cu-num')
  if (!span) {
    el.textContent = ''
    span = document.createElement('span')
    span.className = 'cu-num'
    el.appendChild(span)
  }
  return span
}

export const countup = {
  mounted(el, binding) {
    animate(getTarget(el), binding.value)
  },
  updated(el, binding) {
    if (binding.value !== binding.oldValue) animate(getTarget(el), binding.value)
  },
}
