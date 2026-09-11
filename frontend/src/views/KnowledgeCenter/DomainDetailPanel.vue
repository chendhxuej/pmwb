<template>
  <!-- 领域详情主体（可复用）：单列布局。
       主笔记 tab 以「人工维护区」为主体，自动区/系统维护区降为默认折叠的附录；
       规则沉淀 tab 承载「自动识别 → 智能归类 → 沉淀到场景规则（自动区）」。
       由「领域详情」独立子页与知识中心首页驾驶舱共用，code 变化时自动重载。 -->
  <div class="detail-body" v-loading="loading">
    <div class="detail-right">
      <div class="dtabs">
        <div class="dtab" :class="{ on: activeTab === 'bible' }" @click="activeTab = 'bible'">主笔记</div>
        <div class="dtab" :class="{ on: activeTab === 'rule' }" @click="activeTab = 'rule'">
          规则沉淀
          <span v-if="rulePending" class="dtab-dot">{{ rulePending }}</span>
        </div>
        <div class="dtab" :class="{ on: activeTab === 'rel' }" @click="activeTab = 'rel'">关联对象</div>
        <div class="dtab" :class="{ on: activeTab === 'tl' }" @click="activeTab = 'tl'">时间线</div>
        <div class="dtab" :class="{ on: activeTab === 'auto' }" @click="activeTab = 'auto'">自动区状态</div>
      </div>

      <div class="dbody">
        <!-- ── 主笔记 tab：人工维护区为主体 + 自动/系统区折叠附录 ── -->
        <div v-if="activeTab === 'bible'" class="tab-content">
          <template v-if="isEditing">
            <div class="bible-edit">
              <div class="edit-tip">编辑主笔记全文（Markdown 源码），下方为实时预览</div>
              <textarea v-model="editingContent" class="bible-textarea" spellcheck="false"></textarea>
              <div class="edit-preview">
                <div class="preview-label">实时预览</div>
                <div class="preview-content bible-md" v-html="renderMarkdown(editingContent)"></div>
              </div>
              <div class="edit-actions">
                <el-button @click="cancelEdit">取消</el-button>
                <el-button type="success" :loading="saving" @click="saveAllChanges">保存全部</el-button>
              </div>
            </div>
          </template>

          <template v-else>
            <div v-if="bibleLoading" class="bible-loading">主笔记加载中...</div>

            <template v-else-if="hasSections">
              <!-- 人工维护区（主体，手工管理为主） -->
              <div class="zone-block">
                <div class="zone-head manual">
                  <span class="zone-title">人工维护区</span>
                  <span class="zone-tip">主笔记主体内容，由你手工维护，系统永不覆盖</span>
                  <span class="zone-fill" :class="manualFillClass">
                    已填 {{ manualFilled }}/{{ manualSections.length }}
                  </span>
                </div>
                <div
                  v-for="s in manualSections"
                  :key="'m-' + s.key"
                  class="sec-card"
                  :class="{ empty: isEmptySection(s) }"
                >
                  <div class="sec-head">
                    <span class="sec-title">{{ s.title }}</span>
                    <span class="sec-badge manual">人工维护</span>
                  </div>
                  <div v-if="!isEmptySection(s)" class="sec-body bible-md" v-html="renderMarkdown(s.markdown)"></div>
                  <div v-else class="sec-empty">待补充 · 点击右上角「编辑主笔记」填写</div>
                </div>
                <el-empty v-if="!manualSections.length" description="该模板无人工维护章节" :image-size="50" />
              </div>

              <!-- 自动区 / 系统维护区（附录，默认折叠） -->
              <div class="zone-block appendix">
                <el-collapse v-model="appendixOpen">
                  <el-collapse-item name="auto">
                    <template #title>
                      <span class="appendix-title">
                        系统自动区 · 系统维护区（附录）
                        <em>{{ autoSections.length }} 个章节，由系统自动回流</em>
                      </span>
                    </template>
                    <div
                      v-for="s in autoSections"
                      :key="'a-' + s.key"
                      class="sec-card"
                      :class="{ empty: isEmptySection(s) }"
                    >
                      <div class="sec-head">
                        <span class="sec-title">{{ s.title }}</span>
                        <span class="sec-badge" :class="s.kind === 'system' ? 'system' : 'auto'">
                          {{ s.kind_label }}
                        </span>
                      </div>
                      <div v-if="!isEmptySection(s)" class="sec-body bible-md" v-html="renderMarkdown(s.markdown)"></div>
                      <div v-else class="sec-empty">暂无自动回流内容</div>
                    </div>
                    <el-empty v-if="!autoSections.length" description="该模板无自动区章节" :image-size="50" />
                  </el-collapse-item>
                </el-collapse>
                <div class="appendix-note">
                  附录区由系统维护（规则沉淀、关联索引、时间线等），请勿手工编辑；内容以主笔记源文件为准。
                </div>
              </div>
            </template>

            <div v-else-if="bibleContent" class="bible-full-content bible-md" v-html="renderMarkdown(bibleContent)"></div>
            <el-empty v-else description="该领域暂无主笔记内容，点击顶部「同步主笔记」一键创建" />
          </template>
        </div>

        <!-- ── 规则沉淀 tab ── -->
        <div v-if="activeTab === 'rule'" class="tab-content">
          <div class="rule-head">
            <div class="rule-stat">
              <div class="rs"><b>{{ ruleDomain?.total || 0 }}</b><span>已识别规则</span></div>
              <div class="rs warn"><b>{{ ruleDomain?.pending || 0 }}</b><span>待沉淀</span></div>
              <div class="rs ok"><b>{{ (ruleDomain?.total || 0) - (ruleDomain?.pending || 0) }}</b><span>已沉淀</span></div>
            </div>
            <el-button type="primary" :loading="sedimenting" @click="sedimentDomainRules">
              <el-icon><MagicStick /></el-icon>
              <span>沉淀到「场景规则（自动区）」</span>
            </el-button>
          </div>
          <div class="rule-tip">
            系统自动识别需求用户故事中的业务规则，按关键词智能归类（资费/开通/工单/权限/数据/接口/变更/风控），
            再幂等写入本主笔记的「场景规则（自动区）」章节。
          </div>

          <template v-if="ruleGrouped.length">
            <div v-for="g in ruleGrouped" :key="g.name" class="rule-group">
              <div class="rule-group-head">
                <span class="rg-name">{{ g.name }}规则</span>
                <span class="rg-count">{{ g.rules.length }}</span>
              </div>
              <div
                v-for="r in g.rules"
                :key="r.fingerprint"
                class="rule-row"
                :class="{ done: r.sedimented }"
              >
                <span class="rule-text">{{ r.text }}</span>
                <span class="rule-src">{{ r.req_id }}</span>
                <span class="rule-flag">{{ r.sedimented ? '已沉淀' : '待沉淀' }}</span>
              </div>
            </div>
          </template>
          <el-empty v-else description="该领域暂无自动识别到的规则（来源：需求用户故事的业务规则）" :image-size="60" />
        </div>

        <!-- 关联对象 tab -->
        <div v-if="activeTab === 'rel'" class="tab-content">
          <div class="filt">
            <span class="f" :class="{ on: relFilter === 'all' }" @click="relFilter = 'all'">全部</span>
            <span class="f" :class="{ on: relFilter === 'req' }" @click="relFilter = 'req'">需求</span>
            <span class="f" :class="{ on: relFilter === 'issue' }" @click="relFilter = 'issue'">工单</span>
            <span class="f" :class="{ on: relFilter === 'meeting' }" @click="relFilter = 'meeting'">会议</span>
          </div>
          <table class="rel-table">
            <thead>
              <tr>
                <th style="width:80px">类型</th>
                <th>标题</th>
                <th style="width:100px">状态</th>
                <th style="width:80px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredRelations" :key="item.code">
                <td><span class="ptag">{{ typeLabel(item.status || item.category || '知识') }}</span></td>
                <td>{{ item.title }}</td>
                <td>{{ item.sub_title || '-' }}</td>
                <td><a href="#" @click.prevent="viewItem(item)" class="link-btn">查看</a></td>
              </tr>
              <tr v-if="!filteredRelations.length"><td colspan="4" class="empty-row">暂无关联对象</td></tr>
            </tbody>
          </table>
        </div>

        <!-- 时间线 tab -->
        <div v-if="activeTab === 'tl'" class="tab-content">
          <BusinessTimeline :domain-code="code" :limit="20" />
        </div>

        <!-- 自动区状态 tab -->
        <div v-if="activeTab === 'auto'" class="tab-content">
          <div class="auto-status">
            <div class="auto-item">
              <span class="auto-label">主笔记已建</span>
              <span :class="['auto-val', detail.has_main_note ? 'ok' : 'warn']">{{ detail.has_main_note ? '✅ 是' : '❌ 否' }}</span>
            </div>
            <div class="auto-item">
              <span class="auto-label">结构完整性</span>
              <span :class="['auto-val', detail.structure_ok ? 'ok' : 'warn']">{{ detail.structure_ok ? '✅ 完整' : '⚠️ 残缺' }}</span>
            </div>
            <div class="auto-item">
              <span class="auto-label">人工维护区填充</span>
              <span class="auto-val">{{ manualFilled }}/{{ manualSections.length || '-' }}</span>
            </div>
            <div class="auto-item">
              <span class="auto-label">场景规则（自动区）</span>
              <span class="auto-val">{{ (ruleDomain?.total || 0) - (ruleDomain?.pending || 0) }}/{{ ruleDomain?.total || 0 }} 条已沉淀</span>
            </div>
            <div class="auto-item">
              <span class="auto-label">最后同步</span>
              <span class="auto-val">{{ detail.updated_at || '未知' }}</span>
            </div>
          </div>
          <div class="note">自动区由系统维护，无需手动操作。</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { basicDataApi } from '@/api/basicData'
import { knowledgeApi } from '@/api/knowledge'
import { productBibleApi } from '@/api/productBible'
import BusinessTimeline from '@/components/Common/BusinessTimeline.vue'
import { openObsidianNote } from '@/utils/obsidian'
import { marked } from 'marked'

const props = defineProps({
  code: { type: String, required: true },
})

const loading = ref(false)
const detail = ref({})
const bibleContent = ref('') // 存储原始完整内容
const bibleLoading = ref(false)
const sections = ref([])
const relations = ref([])
const relFilter = ref('all')
const activeTab = ref('bible')
const appendixOpen = ref([]) // 默认全部折叠：自动区降为附录

// 编辑模式状态
const isEditing = ref(false)
const saving = ref(false)
const editingContent = ref('')
const mainNoteItemId = ref(null) // item_id from backend
const syncing = ref(false)

// 规则沉淀
const ruleDomain = ref(null)
const sedimenting = ref(false)

const filteredRelations = computed(() => {
  if (relFilter.value === 'all') return relations.value
  const map = { req: 'requirement', issue: 'operation', meeting: 'meeting' }
  return relations.value.filter(r => r.status === map[relFilter.value])
})

const hasSections = computed(() => sections.value.length > 0)
// 人工维护区（baseline）= 主笔记主体；其余（auto/system）= 附录
const manualSections = computed(() => sections.value.filter((s) => s.kind === 'baseline'))
const autoSections = computed(() => sections.value.filter((s) => s.kind !== 'baseline'))

const isEmptySection = (s) => {
  const md = (s?.markdown || '').trim()
  return !md || md === '_暂无数据_'
}
const manualFilled = computed(() => manualSections.value.filter((s) => !isEmptySection(s)).length)
const manualFillClass = computed(() => {
  const total = manualSections.value.length
  if (!total) return ''
  const rate = manualFilled.value / total
  if (rate >= 0.7) return 'ok'
  if (rate >= 0.3) return 'mid'
  return 'low'
})

const rulePending = computed(() => ruleDomain.value?.pending || 0)
const ruleGrouped = computed(() => {
  const rows = ruleDomain.value?.rules || []
  const map = new Map()
  for (const r of rows) {
    if (!map.has(r.category)) map.set(r.category, [])
    map.get(r.category).push(r)
  }
  return [...map.entries()]
    .map(([name, rules]) => ({ name, rules }))
    .sort((a, b) => b.rules.length - a.rules.length)
})

function renderMarkdown(md) {
  if (!md) return ''
  return marked.parse(md)
}

async function loadDetail() {
  loading.value = true
  try {
    const res = await basicDataApi.getDomainRelated(props.code)
    detail.value = res || {}
    relations.value = [
      ...(res.requirements || []).map(r => ({ ...r, status: 'requirement' })),
      ...(res.issues || []).map(r => ({ ...r, status: 'operation' })),
      ...(res.meetings || []).map(r => ({ ...r, status: 'meeting' })),
      ...(res.knowledge_items || []).map(r => ({ ...r, status: 'knowledge' })),
    ]
  } catch {
    ElMessage.error('加载领域详情失败')
  } finally {
    loading.value = false
  }
}

async function loadBible() {
  bibleLoading.value = true
  try {
    const res = await productBibleApi.getMainNote(props.code)
    bibleContent.value = res?.content || ''
    sections.value = Array.isArray(res?.sections) ? res.sections : []
    mainNoteItemId.value = res?.item_id || null
  } catch {
    bibleContent.value = ''
    sections.value = []
  } finally {
    bibleLoading.value = false
  }
}

async function loadRules() {
  try {
    const res = await knowledgeApi.getRuleCandidates(props.code)
    const list = (res?.domains || []).filter((d) => d.domain_code === props.code)
    ruleDomain.value = list[0] || null
  } catch {
    ruleDomain.value = null
  }
}

async function sedimentDomainRules() {
  sedimenting.value = true
  try {
    const res = await knowledgeApi.sedimentRules([props.code])
    const r = (res?.results || [])[0]
    if (!r || !r.success) {
      ElMessage.warning(r?.error || '沉淀失败')
      return
    }
    if (r.action === 'written') {
      ElMessage.success(`已沉淀 ${r.rules} 条规则到「场景规则（自动区）」`)
    } else {
      ElMessage.info('场景规则已是最新，无需重复沉淀')
    }
    await Promise.all([loadRules(), loadBible()])
  } catch (e) {
    ElMessage.error(e?.message || '沉淀失败')
  } finally {
    sedimenting.value = false
  }
}

// 编辑模式管理
function startEdit() {
  isEditing.value = true
  editingContent.value = bibleContent.value
  ElMessage.info('已进入编辑模式')
}

function cancelEdit() {
  isEditing.value = false
  editingContent.value = ''
  ElMessage.info('已取消编辑')
}

async function saveAllChanges() {
  if (!mainNoteItemId.value) {
    ElMessage.error('主笔记 ID 未找到，无法保存')
    return
  }
  saving.value = true
  try {
    await knowledgeApi.updateItemContent(mainNoteItemId.value, editingContent.value)
    ElMessage.success('所有更改已保存')
    isEditing.value = false
    await loadBible()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function syncMainNote() {
  // 直接调用同步接口（把需求/用户故事/关联事件回流到主笔记自动区）
  syncing.value = true
  try {
    const res = await knowledgeApi.syncMainNote(props.code)
    const blocks = res?.blocks_written || []
    if (res?.changed) {
      ElMessage.success(`主笔记已同步，写入 ${blocks.length} 个自动区章节`)
    } else {
      ElMessage.info('主笔记无变更（关联数据未发生变化）')
    }
    await Promise.all([loadBible(), loadRules()])
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = false
  }
}

function openObsidian() {
  if (detail.value.obsidian_path) {
    openObsidianNote(detail.value.obsidian_path)
  }
}

function typeLabel(s) {
  const map = { requirement: '需求', operation: '工单', meeting: '会议', knowledge: '知识' }
  return map[s] || s || '知识'
}

function viewItem(item) {
  // TODO: 根据类型跳转到对应页面
  ElMessage.info(`查看 ${item.title}`)
}

// code 变化（首页切换领域 / 独立子页路由复用）时重载；先退编辑态避免脏写
watch(() => props.code, async (nc, oc) => {
  if (!nc || nc === oc) return
  isEditing.value = false
  editingContent.value = ''
  activeTab.value = 'bible'
  appendixOpen.value = []
  await loadDetail()
  await loadBible()
  await loadRules()
}, { immediate: true })

// 切到规则沉淀 tab 时确保数据已加载
watch(activeTab, (t) => {
  if (t === 'rule' && !ruleDomain.value) loadRules()
})

// 向父组件（领域详情子页 topbar）暴露编辑/同步等能力
defineExpose({
  detail,
  isEditing,
  saving,
  syncing,
  startEdit,
  cancelEdit,
  saveAllChanges,
  syncMainNote,
  openObsidian,
})
</script>

<script>
export default { name: 'DomainDetailPanel' }
</script>

<style scoped>
.detail-body {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  align-items: start;
}
.detail-right { display: flex; flex-direction: column; gap: 14px; }

/* 右侧 tab */
.dtabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 14px;
}
.dtab {
  padding: 9px 14px;
  cursor: pointer;
  color: #64748b;
  font-size: 13px;
  border-bottom: 2px solid transparent;
  display: flex;
  align-items: center;
  gap: 6px;
}
.dtab.on { color: #2f6fed; border-color: #2f6fed; }
.dtab-dot {
  font-size: 10px;
  background: #f0a64a;
  color: #fff;
  border-radius: 999px;
  padding: 0 5px;
  line-height: 15px;
}
.dbody { min-height: 300px; }
.tab-content { padding: 4px 0; }

/* ── 主笔记：人工区主体 + 附录 ── */
.zone-block { margin-bottom: 18px; }
.zone-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.zone-title {
  font-size: 14.5px;
  font-weight: 700;
  color: #1f2d3d;
  padding-left: 9px;
  border-left: 3px solid #2f6fed;
  line-height: 1.2;
}
.zone-tip { font-size: 11.5px; color: #909399; flex: 1; }
.zone-fill {
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 999px;
  background: #fdecec;
  color: #e47470;
}
.zone-fill.mid { background: #fdf2e8; color: #f0a64a; }
.zone-fill.ok { background: #eafaf3; color: #10b981; }

.sec-card {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 10px;
  background: #fff;
  transition: .15s;
}
.sec-card:hover { border-color: #c7d9fb; }
.sec-card.empty { background: #fcfcfd; border-style: dashed; }
.sec-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 8px;
}
.sec-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
  flex: 1;
}
.sec-badge {
  font-size: 10.5px;
  padding: 1px 8px;
  border-radius: 6px;
  font-weight: 600;
  flex-shrink: 0;
}
.sec-badge.manual { background: #eef4ff; color: #2f6fed; }
.sec-badge.auto { background: #eafaf3; color: #10b981; }
.sec-badge.system { background: #f5f7fa; color: #64748b; }
.sec-body { font-size: 13px; }
.sec-empty { font-size: 12px; color: #b6bfcc; }

.appendix .appendix-title {
  font-size: 13.5px;
  font-weight: 700;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 8px;
}
.appendix .appendix-title em {
  font-style: normal;
  font-size: 11.5px;
  font-weight: 400;
  color: #909399;
}
.appendix-note {
  margin-top: 9px;
  font-size: 11.5px;
  color: #909399;
  line-height: 1.6;
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px 11px;
}

/* ── 规则沉淀 ── */
.rule-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.rule-stat { display: flex; gap: 9px; flex: 1; }
.rs {
  flex: 1;
  background: #f5f7fa;
  border-radius: 9px;
  padding: 8px 10px;
  text-align: center;
}
.rs b { display: block; font-size: 18px; color: #1f2d3d; line-height: 1.2; }
.rs span { font-size: 11px; color: #909399; }
.rs.warn b { color: #f0a64a; }
.rs.ok b { color: #10b981; }
.rule-tip {
  font-size: 11.5px;
  color: #909399;
  line-height: 1.6;
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px 11px;
  margin-bottom: 12px;
}
.rule-group { margin-bottom: 12px; }
.rule-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 7px;
}
.rg-name { font-size: 13px; font-weight: 700; color: #1f2d3d; }
.rg-count {
  font-size: 11px;
  background: #eef4ff;
  color: #2f6fed;
  padding: 0 7px;
  border-radius: 999px;
}
.rule-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 7px 10px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #ebeef5;
  margin-bottom: 5px;
  font-size: 12.5px;
}
.rule-row.done { background: #fafcff; }
.rule-text { flex: 1; color: #1f2d3d; line-height: 1.5; }
.rule-src {
  font-size: 11px;
  color: #909399;
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rule-flag { font-size: 11px; color: #f0a64a; flex-shrink: 0; }
.rule-row.done .rule-flag { color: #10b981; }

/* 关联表格 */
.filt { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.f {
  padding: 4px 10px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
}
.f.on { border-color: #2f6fed; color: #2f6fed; }
.rel-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.rel-table th {
  text-align: left;
  color: #64748b;
  font-weight: 600;
  font-size: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid #e4e7ed;
}
.rel-table td {
  padding: 9px 10px;
  border-bottom: 1px solid #ebeef5;
}
.ptag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  background: #ecf5ff;
  color: #409eff;
}
.link-btn {
  font-size: 12px;
  color: #2f6fed;
  text-decoration: none;
}
.empty-row { text-align: center; color: #909399; }

/* 自动区 */
.auto-status { display: flex; flex-direction: column; gap: 10px; }
.auto-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 8px;
}
.auto-label { color: #64748b; font-size: 13px; }
.auto-val { font-size: 13px; font-weight: 600; }
.auto-val.ok { color: #10b981; }
.auto-val.warn { color: #f0a64a; }
.note {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

/* ===== 产品圣经：全文展示卡片 ===== */
.bible-loading {
  text-align: center;
  padding: 40px;
  color: #909399;
  font-size: 14px;
}
.bible-full-content {
  padding: 24px 28px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(31, 45, 61, 0.04);
}

/* ===== Markdown 正文排版强化（v-html 内容须用 :deep 命中） ===== */
.bible-md {
  font-size: 13.5px;
  line-height: 1.75;
  color: #1f2d3d;
  word-break: break-word;
}
.bible-md :deep(h1) {
  font-size: 21px;
  font-weight: 700;
  color: #0f172a;
  margin: 4px 0 18px;
  padding-bottom: 10px;
  border-bottom: 2px solid #e8eefb;
  letter-spacing: 0.5px;
}
.bible-md :deep(h2) {
  font-size: 17px;
  font-weight: 700;
  color: #1e3a8a;
  margin: 26px 0 12px;
  padding: 6px 12px;
  background: linear-gradient(90deg, #eff5ff 0%, #ffffff 85%);
  border-left: 4px solid #2f6fed;
  border-radius: 0 6px 6px 0;
}
.bible-md :deep(h2:first-child) { margin-top: 4px; }
.bible-md :deep(h3) {
  font-size: 14.5px;
  font-weight: 600;
  color: #1f2d3d;
  margin: 18px 0 8px;
  padding-left: 10px;
  border-left: 3px solid #93c5fd;
}
.bible-md :deep(h4) {
  font-size: 13.5px;
  font-weight: 600;
  color: #374151;
  margin: 14px 0 6px;
}
.bible-md :deep(p) { margin: 8px 0; }
.bible-md :deep(strong) { color: #0f172a; font-weight: 600; }
.bible-md :deep(a) { color: #2f6fed; text-decoration: none; }
.bible-md :deep(a:hover) { text-decoration: underline; }
.bible-md :deep(ul), .bible-md :deep(ol) { padding-left: 22px; margin: 8px 0; }
.bible-md :deep(li) { margin: 4px 0; }
.bible-md :deep(li)::marker { color: #2f6fed; }
.bible-md :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  background: #f8fafc;
  border-left: 3px solid #cbd5e1;
  border-radius: 0 6px 6px 0;
  color: #475569;
}
.bible-md :deep(blockquote p) { margin: 4px 0; }
.bible-md :deep(code) {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  background: #f1f5f9;
  color: #b91c1c;
  padding: 1px 6px;
  border-radius: 4px;
}
.bible-md :deep(pre) {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
}
.bible-md :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: 12px;
}
.bible-md :deep(hr) {
  border: none;
  border-top: 1px dashed #e4e7ed;
  margin: 18px 0;
}
.bible-md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 12.5px;
  border-radius: 8px;
  overflow: hidden;
}
.bible-md :deep(th) {
  background: #eef4ff;
  color: #1e3a8a;
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  border: 1px solid #dbe6f8;
}
.bible-md :deep(td) {
  padding: 7px 12px;
  border: 1px solid #e8eef5;
  color: #374151;
}
.bible-md :deep(tr:nth-child(even) td) { background: #fafcff; }

/* ===== 编辑模式 ===== */
.bible-edit {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.edit-tip {
  font-size: 12px;
  color: #64748b;
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  padding: 6px 10px;
}
.bible-textarea {
  width: 100%;
  min-height: 260px;
  padding: 12px 14px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  font-size: 13px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  line-height: 1.6;
  resize: vertical;
  transition: border-color 0.2s;
}
.bible-textarea:focus {
  outline: none;
  border-color: #2f6fed;
  box-shadow: 0 0 0 2px rgba(47, 111, 237, 0.1);
}
.edit-preview {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}
.preview-label {
  padding: 6px 12px;
  background: #f5f7fa;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  border-bottom: 1px solid #e4e7ed;
}
.preview-content {
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.7;
  max-height: 360px;
  overflow-y: auto;
  background: #fff;
}
.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
