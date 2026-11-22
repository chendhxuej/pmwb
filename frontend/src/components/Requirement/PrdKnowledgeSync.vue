<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getSyncSystems, getSyncStatus, triggerSync,
} from '@/api/prdAnalysis.js'

const emit = defineEmits(['synced', 'update:selectedDirs'])

const collapsed = ref(true)
const systems = ref([])        // [{id,name,cloned,dirs:[...]}]
const checkedSystems = ref([]) // 要同步的系统
const checkedDirs = ref([])    // 分析时装载的业务子目录 "SYS/dir"
const syncStatus = ref({ status: 'idle', task_installed: false })
const note = ref('')
const triggering = ref(false)
let timer = null

const STATUS_META = {
  idle: { label: '未同步', cls: 'st-idle' },
  running: { label: '同步中…', cls: 'st-running' },
  ok: { label: '同步成功', cls: 'st-ok' },
  error: { label: '同步失败', cls: 'st-error' },
  stale: { label: '同步超时', cls: 'st-error' },
}
const statusMeta = computed(() => STATUS_META[syncStatus.value.status] || STATUS_META.idle)
const dirCount = computed(() => systems.value.reduce((n, s) => n + s.dirs.length, 0))
const canSync = computed(() => syncStatus.value.task_installed && syncStatus.value.status !== 'running')

async function loadSystems() {
  try {
    const res = await getSyncSystems()
    systems.value = res?.systems || []
    note.value = res?.note || ''
  } catch (e) { /* 静默：面板折叠时不影响主分析 */ }
}

async function pollStatus(silent = true) {
  try {
    const res = await getSyncStatus()
    const prev = syncStatus.value.status
    syncStatus.value = res || {}
    if (!silent && prev === 'running' && ['ok', 'error', 'stale'].includes(syncStatus.value.status)) {
      if (syncStatus.value.status === 'ok') {
        ElMessage.success('知识同步完成，索引已自动重载')
        emit('synced')
      } else {
        ElMessage.error(`同步失败：${syncStatus.value.error || '未知错误'}`)
      }
    }
    return syncStatus.value.status
  } catch (e) { return null }
}

function startPolling() {
  stopPolling()
  timer = setInterval(async () => {
    const st = await pollStatus(false)
    if (['ok', 'error', 'stale', 'idle'].includes(st)) stopPolling()
  }, 3000)
}
function stopPolling() { if (timer) { clearInterval(timer); timer = null } }

async function doSync() {
  if (!syncStatus.value.task_installed) {
    ElMessage.warning('请先以本人身份运行计划任务安装脚本（见交付说明）')
    return
  }
  triggering.value = true
  try {
    const res = await triggerSync(checkedSystems.value)
    if (res?.ok) {
      syncStatus.value = { ...syncStatus.value, status: 'running' }
      startPolling()
    } else {
      ElMessage.error(res?.reason === 'task_not_installed' ? '计划任务未安装' : `无法触发：${res?.reason || '未知'}`)
    }
  } catch (e) {
    ElMessage.error('触发同步失败')
  } finally { triggering.value = false }
}

function toggleDir(sysId, dir) {
  const key = `${sysId}/${dir}`
  const i = checkedDirs.value.indexOf(key)
  if (i >= 0) checkedDirs.value.splice(i, 1)
  else checkedDirs.value.push(key)
  emit('update:selectedDirs', [...checkedDirs.value])
}
function clearDirs() {
  checkedDirs.value = []
  emit('update:selectedDirs', [])
}

onMounted(async () => {
  await Promise.all([loadSystems(), pollStatus(false)])
  if (syncStatus.value.status === 'running') startPolling()
})
onUnmounted(stopPolling)
</script>

<template>
  <div class="ksync">
    <div class="ksync-head" @click="collapsed = !collapsed">
      <span class="ksync-title">知识源同步</span>
      <span class="ksync-badge" :class="statusMeta.cls">{{ statusMeta.label }}</span>
      <span class="ksync-meta">{{ systems.length }} 系统 · {{ dirCount }} 个业务目录</span>
      <span class="ksync-toggle">{{ collapsed ? '展开' : '收起' }}</span>
    </div>

    <div v-show="!collapsed" class="ksync-body">
      <div v-if="!syncStatus.task_installed" class="ksync-warn">
        同步需以你本人身份运行的计划任务（服务端零凭据）。请先执行一次安装脚本后刷新本页。
      </div>

      <div class="ksync-section">
        <div class="ksync-label">同步系统（内网 Git，可多选；留空=全部）</div>
        <div class="ksync-chips">
          <label v-for="s in systems" :key="s.id" class="ksync-chip" :class="{ on: checkedSystems.includes(s.id) }">
            <input type="checkbox" :value="s.id" v-model="checkedSystems" />
            <span>{{ s.name }}</span>
            <span class="ksync-chip-sub">{{ s.cloned ? '已克隆' : '未克隆' }}</span>
          </label>
        </div>
      </div>

      <div class="ksync-section">
        <div class="ksync-label">
          分析时装载的业务目录（可多选，留空=全部）
          <span v-if="checkedDirs.length" class="ksync-clear" @click="clearDirs">清空({{ checkedDirs.length }})</span>
        </div>
        <div v-for="s in systems.filter(x => x.cloned)" :key="s.id" class="ksync-dirgroup">
          <span class="ksync-dirsys">{{ s.name }}</span>
          <div class="ksync-chips">
            <label v-for="d in s.dirs" :key="d" class="ksync-chip sm" :class="{ on: checkedDirs.includes(s.id + '/' + d) }">
              <input type="checkbox" :checked="checkedDirs.includes(s.id + '/' + d)" @change="toggleDir(s.id, d)" />
              <span :title="d">{{ d }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="ksync-foot">
        <button class="ksync-btn" :disabled="!canSync || triggering" @click="doSync">
          {{ triggering ? '触发中…' : (syncStatus.status === 'running' ? '同步进行中…' : '立即同步') }}
        </button>
        <span v-if="syncStatus.synced_at" class="ksync-synced">上次同步：{{ syncStatus.synced_at }}</span>
        <span v-if="syncStatus.error" class="ksync-err">错误：{{ syncStatus.error }}</span>
      </div>
      <div class="ksync-note">{{ note || '仅已接入内网 Git 的系统可同步知识；其余涉及系统按无知识分析。' }}</div>
    </div>
  </div>
</template>

<style scoped>
.ksync { border: 1px solid var(--border); border-radius: 10px; margin-bottom: 14px; background: #fff; overflow: hidden; }
.ksync-head { display: flex; align-items: center; gap: 10px; padding: 10px 14px; cursor: pointer; user-select: none; }
.ksync-head:hover { background: var(--border-subtle); }
.ksync-title { font-weight: 600; font-size: 14px; color: var(--text-primary); }
.ksync-badge { font-size: 12px; padding: 2px 8px; border-radius: 10px; }
.st-idle { background: var(--border-subtle); color: var(--text-secondary); }
.st-running { background: #fff7e6; color: #b7791f; }
.st-ok { background: #eafbf0; color: #1a8754; }
.st-error { background: #fdecec; color: #c0392b; }
.ksync-meta { font-size: 12px; color: var(--text-muted); }
.ksync-toggle { margin-left: auto; font-size: 12px; color: var(--accent); }
.ksync-body { padding: 4px 14px 14px; border-top: 1px solid var(--border-subtle); }
.ksync-warn { margin: 10px 0; padding: 8px 10px; background: #fff7e6; color: #b7791f; border-radius: 6px; font-size: 12px; line-height: 1.6; }
.ksync-section { margin-top: 12px; }
.ksync-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }
.ksync-clear { color: var(--accent); cursor: pointer; margin-left: 8px; }
.ksync-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ksync-chip { display: inline-flex; align-items: center; gap: 5px; padding: 4px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; color: var(--text-secondary); cursor: pointer; }
.ksync-chip.on { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
.ksync-chip input { margin: 0; width: 13px; height: 13px; }
.ksync-chip.sm { padding: 3px 7px; font-size: 11px; }
.ksync-chip-sub { color: var(--text-muted); font-size: 11px; }
.ksync-dirgroup { margin-bottom: 8px; }
.ksync-dirsys { display: inline-block; min-width: 70px; font-size: 12px; font-weight: 600; color: var(--text-primary); }
.ksync-foot { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
.ksync-btn { background: var(--accent); color: #fff; border: none; border-radius: 6px; padding: 7px 16px; font-size: 13px; cursor: pointer; }
.ksync-btn:disabled { opacity: .5; cursor: not-allowed; }
.ksync-synced { font-size: 12px; color: var(--text-muted); }
.ksync-err { font-size: 12px; color: #c0392b; }
.ksync-note { margin-top: 10px; font-size: 11px; color: var(--text-muted); line-height: 1.6; }
</style>
