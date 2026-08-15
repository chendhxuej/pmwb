<template>
  <div class="page-container ai-qa">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <div class="page-title">AI 问答</div>
        <div class="page-sub">基于项目数据库（需求 / 工单 / 会议 / 运营 / 知识库）与 Obsidian 笔记，智能查询你的工作信息</div>
      </div>
      <div class="page-actions">
        <span class="status-chip" :class="statusClass">
          <span class="dot" />
          {{ statusText }}
        </span>
      </div>
    </div>

    <!-- 对话区 -->
    <div class="chat-wrap">
      <div class="chat-body" ref="chatBody">
        <!-- 空态 -->
        <div v-if="!messages.length" class="chat-empty">
          <el-icon class="ce-icon"><ChatDotRound /></el-icon>
          <p class="ce-title">向你的工作台提问</p>
          <p class="ce-sub">例如：一网通宽带当前有哪些在开发的需求？FTTO 相关的运营问题有哪些？</p>
          <div class="suggest-row">
            <button v-for="s in suggestions" :key="s" class="suggest-chip" @click="send(s)">{{ s }}</button>
          </div>
        </div>

        <!-- 消息流 -->
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="msg-avatar" :class="m.role">
            <el-icon v-if="m.role === 'user'"><User /></el-icon>
            <el-icon v-else><Cpu /></el-icon>
          </div>
          <div class="msg-main">
            <div class="msg-bubble" :class="m.role">
              <div v-if="m.role === 'assistant' && m.loading" class="loading-row">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在检索项目数据并生成回答…</span>
              </div>
              <div v-else class="msg-text" style="white-space: pre-wrap">{{ m.content }}</div>
            </div>

            <!-- 助手消息：未用大模型提示 -->
            <div v-if="m.role === 'assistant' && !m.loading && m.used_llm === false" class="no-llm-tip">
              ⚠️ 未连接到可用的大模型（请到「大模型管理」添加并启用一个），以下仅展示检索到的相关资料。
            </div>

            <!-- 检索透明度：便于判断回答可信度 -->
            <div v-if="m.role === 'assistant' && !m.loading && m.retrieval" class="retrieval-meta">
              <el-icon><Search /></el-icon>
              <span>检索到 {{ m.retrieval.used }} 条相关资料</span>
              <span class="rm-sep">·</span>
              <span>数据库 {{ m.retrieval.db_hits }} / 笔记 {{ m.retrieval.ob_hits }}</span>
              <span class="rm-sep">·</span>
              <span>语义扩展：{{ m.retrieval.semantic_rewrite ? '已开启' : '未开启' }}</span>
            </div>

            <!-- 来源引用 -->
            <div v-if="m.role === 'assistant' && !m.loading && (m.sources || []).length" class="sources">
              <button class="src-toggle" @click="toggleSources(i)">
                <el-icon><Link /></el-icon>
                参考来源（{{ m.sources.length }}）
                <el-icon class="caret" :class="{ open: expanded[i] }"><ArrowDown /></el-icon>
              </button>
              <div v-show="expanded[i]" class="src-list">
                <div v-for="s in m.sources" :key="s.idx" class="src-item">
                  <span class="src-idx">[{{ s.idx }}]</span>
                  <div class="src-body">
                    <div class="src-head">
                      <span class="src-kind">{{ s.type === 'db' ? '数据库' : 'Obsidian' }}</span>
                      <span class="src-title">{{ s.title }}</span>
                      <span class="src-ref">{{ s.ref }}</span>
                    </div>
                    <div class="src-snippet">{{ s.snippet }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="chat-input">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="输入你的问题，Enter 发送，Shift+Enter 换行"
          @keydown.enter.exact.prevent="send()"
        />
        <el-button type="primary" :loading="loading" :disabled="!input.trim()" @click="send()">
          <el-icon><Promotion /></el-icon> 发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Loading, Link, ArrowDown, User, Cpu, ChatDotRound, Search } from '@element-plus/icons-vue'
import { aiQaAsk, aiQaStatus } from '@/api/ai_qa.js'

const messages = ref([])
const input = ref('')
const loading = ref(false)
const expanded = reactive({})
const chatBody = ref(null)

const status = ref({ enabled: false, provider_name: null, model: null, reachable: false, error: null })
const statusLoading = ref(false)

const suggestions = [
  '一网通宽带当前有哪些在开发的需求？',
  'FTTO 相关的运营问题有哪些？',
  '最近一次会议讨论了什么？',
  '安防产品交付流程涉及哪些系统？',
]

const statusClass = ref('')
const statusText = ref('检测中…')
function refreshStatusView() {
  if (statusLoading.value) { statusText.value = '检测中…'; statusClass.value = ''; return }
  if (status.value.reachable) {
    statusClass.value = 'on'
    statusText.value = `已连接：${status.value.provider_name || ''} / ${status.value.model || ''}`.trim()
  } else if (status.value.enabled) {
    statusClass.value = 'warn'
    statusText.value = '已配置但未连通'
  } else {
    statusClass.value = 'off'
    statusText.value = '未配置大模型'
  }
}

async function loadStatus() {
  statusLoading.value = true
  refreshStatusView()
  try {
    const r = await aiQaStatus()
    status.value = r || { enabled: false, provider_name: null, model: null, reachable: false, error: null }
  } catch {
    status.value = { enabled: false, provider_name: null, model: null, reachable: false, error: null }
  } finally {
    statusLoading.value = false
    refreshStatusView()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
  })
}

function toggleSources(i) {
  expanded[i] = !expanded[i]
}

async function send(text) {
  const q = (text ?? input.value).trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', content: q })
  input.value = ''
  scrollToBottom()

  // 历史：取最近若干轮（排除当前这条用户消息）
  const history = messages.value
    .slice(0, -1)
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .slice(-6)
    .map((m) => ({ role: m.role, content: m.content }))

  // 先放一个 loading 占位
  const placeholderIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '', loading: true, sources: [], used_llm: null })
  loading.value = true
  scrollToBottom()

  try {
    const res = await aiQaAsk(q, history)
    messages.value[placeholderIdx] = {
      role: 'assistant',
      content: res.answer,
      sources: res.sources || [],
      used_llm: res.used_llm,
      provider_name: res.provider_name,
      notice: res.notice,
      retrieval: res.retrieval || null,
      semantic_rewrite: res.semantic_rewrite,
      loading: false,
    }
  } catch (e) {
    messages.value[placeholderIdx] = {
      role: 'assistant',
      content: '调用失败，请稍后重试。',
      sources: [],
      used_llm: false,
      loading: false,
    }
    ElMessage.error('问答请求失败')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

onMounted(() => {
  loadStatus()
})
</script>

<style scoped>
.page-sub { font-size: 12.5px; color: var(--text-secondary); margin-top: 4px }
.page-actions { display: flex; align-items: center }

.status-chip {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 999px;
  background: var(--bg-app); border: 1px solid var(--border-subtle);
}
.status-chip .dot { width: 8px; height: 8px; border-radius: 50%; background: #bbb }
.status-chip.on { color: #389e0d; background: #f6ffed; border-color: #b7eb8f }
.status-chip.on .dot { background: #52c41a }
.status-chip.warn { color: #d48806; background: #fff7e6; border-color: #ffd591 }
.status-chip.warn .dot { background: #faad14 }
.status-chip.off { color: #8c8c8c }
.status-chip.off .dot { background: #bfbfbf }

.chat-wrap {
  display: flex; flex-direction: column;
  height: calc(100vh - 150px);
  background: var(--surface, #fff);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  overflow: hidden;
}
.chat-body { flex: 1; overflow-y: auto; padding: 20px 24px }

.chat-empty { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center }
.ce-icon { font-size: 44px; color: var(--accent); margin-bottom: 8px }
.ce-title { font-size: 17px; font-weight: 700; color: var(--text-primary); margin: 0 0 4px }
.ce-sub { font-size: 13px; color: var(--text-muted); max-width: 520px; margin: 0 }
.suggest-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 18px; max-width: 640px }
.suggest-chip {
  font-size: 12.5px; color: var(--text-secondary);
  background: var(--bg-app); border: 1px solid var(--border-subtle);
  border-radius: 999px; padding: 7px 14px; cursor: pointer; font-family: inherit;
  transition: all .15s;
}
.suggest-chip:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft) }

.msg { display: flex; gap: 12px; margin-bottom: 20px }
.msg.user { flex-direction: row-reverse }
.msg-avatar {
  width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 18px; color: #fff;
}
.msg-avatar.user { background: var(--accent) }
.msg-avatar.assistant { background: #722ed1 }
.msg-main { max-width: 78%; min-width: 0 }
.msg.user .msg-main { display: flex; flex-direction: column; align-items: flex-end }

.msg-bubble {
  padding: 12px 14px; border-radius: 12px; font-size: 13.5px; line-height: 1.7;
  color: var(--text-primary); word-break: break-word;
}
.msg-bubble.assistant { background: var(--bg-app); border: 1px solid var(--border-subtle); border-top-left-radius: 2px }
.msg-bubble.user { background: var(--accent); color: #fff; border-top-right-radius: 2px }

.loading-row { display: flex; align-items: center; gap: 8px; color: var(--text-secondary) }

.no-llm-tip {
  margin-top: 8px; font-size: 12px; color: #ad6800;
  background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px; padding: 7px 10px;
}

.retrieval-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 5px;
  margin-top: 8px; font-size: 11.5px; color: var(--text-muted);
}
.retrieval-meta .el-icon { font-size: 13px; color: var(--accent) }
.rm-sep { color: var(--border); }

.sources { margin-top: 8px }
.src-toggle {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; font-weight: 600; color: var(--accent);
  background: transparent; border: none; cursor: pointer; padding: 2px 0; font-family: inherit;
}
.src-toggle .caret { transition: transform .2s }
.src-toggle .caret.open { transform: rotate(180deg) }

.src-list { margin-top: 8px; display: flex; flex-direction: column; gap: 8px }
.src-item { display: flex; gap: 8px; padding: 10px 12px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: 10px }
.src-idx { font-weight: 700; color: var(--accent); flex-shrink: 0 }
.src-body { min-width: 0 }
.src-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin-bottom: 4px }
.src-kind { font-size: 10.5px; font-weight: 600; padding: 1px 7px; border-radius: 999px; background: var(--accent-soft); color: var(--accent) }
.src-title { font-size: 13px; font-weight: 600; color: var(--text-primary) }
.src-ref { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono) }
.src-snippet { font-size: 12px; color: var(--text-secondary); line-height: 1.6; white-space: pre-wrap }

.chat-input {
  display: flex; gap: 10px; align-items: flex-end;
  padding: 14px 16px; border-top: 1px solid var(--border-subtle); background: var(--surface, #fff);
}
.chat-input :deep(.el-textarea__inner) { box-shadow: none; border: 1px solid var(--border); border-radius: 10px }
.chat-input .el-button { flex-shrink: 0; height: 40px }
</style>
