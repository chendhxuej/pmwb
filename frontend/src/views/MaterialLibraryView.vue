<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <div class="page-title">业务资料库</div>
        <div class="page-sub">汇总展示各业务模块材料，支持在线预览、下载与模糊检索；手工上传材料统一归档</div>
      </div>
      <div class="page-actions">
        <el-button @click="handleSync">
          <el-icon><Refresh /></el-icon> 汇聚同步
        </el-button>
        <el-button type="primary" @click="openUpload">
          <el-icon><Upload /></el-icon> 批量上传
        </el-button>
      </div>
    </div>

    <div class="material-layout">
      <!-- 左侧：分类树 -->
      <aside class="material-aside">
        <div class="aside-head">
          <span>材料分类</span>
          <el-button link type="primary" size="small" @click="categoryManageVisible = true">
            <el-icon><Setting /></el-icon> 管理
          </el-button>
        </div>
        <el-tree
          ref="treeRef"
          class="material-tree"
          :data="treeData"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          :expand-on-click-node="false"
          highlight-current
          default-expand-all
          @node-click="onTreeNodeClick"
        >
          <template #default="{ node, data }">
            <span class="tree-node">
              <span>{{ data.name }}</span>
              <span class="tree-count">{{ data.material_count }}</span>
            </span>
          </template>
        </el-tree>
      </aside>

      <!-- 右侧：筛选 + 列表 -->
      <section class="material-main">
        <div class="table-toolbar">
          <el-input
            v-model="keyword"
            placeholder="搜索文件名 / 备注 / 标签 / 来源单号"
            clearable
            style="width: 280px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="sourceType" placeholder="来源" clearable style="width: 150px" @change="handleSearch">
            <el-option v-for="s in sourceStats" :key="s.source_type" :label="`${s.label} (${s.count})`" :value="s.source_type" />
          </el-select>
          <el-select v-model="fileExt" placeholder="类型" clearable style="width: 130px" @change="handleSearch">
            <el-option v-for="e in extOptions" :key="e" :label="extLabel(e)" :value="e" />
          </el-select>
          <el-button @click="handleSearch"><el-icon><Refresh /></el-icon> 刷新</el-button>
        </div>

        <!-- 批量操作条：选中任意卡片后出现 -->
        <div v-if="selectedIds.length" class="batch-bar">
          <span class="batch-count">已选 {{ selectedIds.length }} 项</span>
          <el-button size="small" link type="primary" @click="toggleSelectAll">
            {{ allCurrentSelected ? '取消全选本页' : '全选本页' }}
          </el-button>
          <el-button size="small" type="primary" @click="openBatchReassign">
            <el-icon><FolderOpened /></el-icon> 批量改分类
          </el-button>
          <el-button size="small" type="danger" @click="handleBatchDelete">
            <el-icon><Delete /></el-icon> 批量删除索引
          </el-button>
          <el-button size="small" link @click="selectedIds = []">取消选择</el-button>
        </div>

        <div v-loading="loading" class="material-grid">
          <el-empty v-if="!loading && items.length === 0" description="暂无材料，点「汇聚同步」或「批量上传」" />
          <el-card v-for="m in items" :key="m.id" class="material-card" shadow="hover"
                   :class="{ 'is-selected': selectedIds.includes(m.id) }">
            <el-checkbox
              class="mc-check"
              :model-value="selectedIds.includes(m.id)"
              @change="(v) => toggleSelect(m.id, v)"
            />
            <div class="mc-top">
              <el-icon class="mc-icon" :style="{ color: extColor(m.file_ext) }">
                <component :is="extIcon(m.file_ext)" />
              </el-icon>
              <div class="mc-name" :title="m.file_name">{{ m.file_name }}</div>
            </div>
            <div class="mc-meta">
              <el-tag size="small" effect="plain">{{ m.source_label }}</el-tag>
              <span class="mc-size">{{ m.file_size_human || '—' }}</span>
            </div>
            <div class="mc-sub">
              <span v-if="m.category_name" class="mc-cat">{{ m.category_name }}</span>
              <span v-if="m.source_title" class="mc-src" :title="m.source_title">{{ m.source_title }}</span>
            </div>
            <div class="mc-actions">
              <el-button v-if="m.can_preview" link type="primary" size="small" @click="openPreview(m)">
                <el-icon><View /></el-icon> 预览
              </el-button>
              <el-button link type="primary" size="small" @click="doDownload(m)">
                <el-icon><Download /></el-icon> 下载
              </el-button>
              <el-button link size="small" @click="openReassign(m)">
                <el-icon><FolderOpened /></el-icon> 分类
              </el-button>
              <el-button link type="danger" size="small" @click="handleDelete(m)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </el-card>
        </div>

        <el-pagination
          v-if="total > 0"
          class="material-pager"
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPage"
        />
      </section>
    </div>

    <!-- 预览抽屉 -->
    <el-drawer v-model="previewVisible" :title="previewTitle" size="60%" destroy-on-close>
      <div v-loading="previewLoading" class="preview-body">
        <template v-if="previewData">
          <div v-if="previewData.mode === 'html'" class="preview-html" v-html="previewData.html" />
          <pre v-else-if="previewData.mode === 'text'" class="preview-text">{{ previewData.text }}</pre>
          <iframe v-else-if="previewData.mode === 'stream'" :src="inlineMaterialUrl(previewId)" class="preview-iframe" />
          <el-result v-else icon="warning" title="暂不支持在线预览" :sub-title="previewData.reason">
            <template #extra>
              <el-button type="primary" @click="doDownloadById(previewId)">下载查看</el-button>
            </template>
          </el-result>
        </template>
      </div>
    </el-drawer>

    <!-- 改分类对话框 -->
    <el-dialog v-model="reassignVisible" title="调整分类" width="420px">
      <el-form label-width="80px">
        <el-form-item label="选择分类">
          <el-tree-select
            v-model="reassignForm.category_id"
            :data="treeData"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            value-key="id"
            placeholder="不分类"
            clearable
            check-strictly
            default-expand-all
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReassign">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量上传对话框 -->
    <el-dialog v-model="uploadVisible" title="批量上传材料" width="560px" @closed="resetUploadForm">
      <el-form label-width="80px">
        <el-form-item label="文件">
          <el-upload
            ref="uploaderRef"
            drag
            multiple
            :auto-upload="false"
            :limit="50"
            :on-change="syncUploadList"
            :on-remove="syncUploadList"
            :on-exceed="onUploadExceed"
            accept="*"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖入多个文件或 <em>点击选择</em>（单次最多 50 个）</div>
          </el-upload>
          <div v-if="uploadRawList.length" class="upload-tip">
            已选 {{ uploadRawList.length }} 个文件，将统一归入下方分类
          </div>
        </el-form-item>
        <el-form-item label="归类">
          <el-tree-select
            v-model="uploadForm.category_id"
            :data="treeData"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            value-key="id"
            placeholder="不分类"
            clearable
            check-strictly
            default-expand-all
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="uploadForm.note" type="textarea" :rows="2" placeholder="可选，批量同写，参与模糊搜索" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!uploadRawList.length" :loading="uploading" @click="submitUpload">
          上传{{ uploadRawList.length ? ` (${uploadRawList.length})` : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 分类管理 -->
    <MaterialCategoryManage v-model="categoryManageVisible" @saved="onCategorySaved" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getMaterials, syncMaterials, previewMaterial, reassignMaterialCategory, deleteMaterial,
  checkUploadConflict, batchUploadMaterials, batchReassignCategory, batchDeleteMaterials,
  getCategories, inlineMaterialUrl, downloadMaterialUrl,
} from '@/api/material.js'
import MaterialCategoryManage from '@/views/MaterialCategoryManage.vue'

const keyword = ref('')
const sourceType = ref('')
const fileExt = ref('')
const categoryId = ref(null)
const page = ref(1)
const pageSize = ref(24)
const total = ref(0)
const items = ref([])
const loading = ref(false)
const sourceStats = ref([])
const categories = ref([])

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewData = ref(null)
const previewId = ref(null)
const previewTitle = ref('')

const reassignVisible = ref(false)
const reassignForm = reactive({ id: null, category_id: null })

const uploaderRef = ref(null)
const uploadRawList = ref([]) // 选中的原生 File 列表
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadForm = reactive({ category_id: null, note: '' })

const selectedIds = ref([]) // 卡片多选
const BATCH_CHUNK = 5 // 每批 5 个文件串行上传，规避 request 全局 120s 超时

const categoryManageVisible = ref(false)

const EXT_ICON = {
  xlsx: 'Grid', xlsm: 'Grid', csv: 'Grid', xls: 'Grid',
  docx: 'Document', doc: 'Document',
  pptx: 'Presentation', ppt: 'Presentation',
  pdf: 'Files', zip: 'Folder', rar: 'Folder', '7z': 'Folder',
  png: 'Picture', jpg: 'Picture', jpeg: 'Picture', gif: 'Picture', bmp: 'Picture', webp: 'Picture',
  txt: 'Memo', md: 'Memo', log: 'Memo', json: 'Memo', xml: 'Memo',
  htm: 'Link', html: 'Link',
  default: 'Files',
}
const EXT_COLOR = {
  xlsx: '#1d8e3b', csv: '#1d8e3b', xlsm: '#1d8e3b', xls: '#1d8e3b',
  docx: '#2b579a', doc: '#2b579a',
  pptx: '#d24726', ppt: '#d24726',
  pdf: '#c0392b', zip: '#b9770e', rar: '#b9770e', '7z:': '#b9770e',
  png: '#16a085', jpg: '#16a085', jpeg: '#16a085', gif: '#16a085', bmp: '#16a085', webp: '#16a085',
  txt: '#607d8b', md: '#607d8b', log: '#607d8b', json: '#607d8b', xml: '#607d8b',
  htm: '#8e44ad', html: '#8e44ad',
}
function extIcon(e) { return EXT_ICON[e] || EXT_ICON.default }
function extColor(e) { return EXT_COLOR[e] || '#909399' }
function extLabel(e) {
  const map = { xlsx: 'Excel', xlsm: 'Excel', csv: 'CSV', xls: 'Excel', docx: 'Word', doc: 'Word', pptx: 'PPT', ppt: 'PPT', pdf: 'PDF', zip: '压缩包', rar: '压缩包', '7z': '压缩包', png: '图片', jpg: '图片', jpeg: '图片', gif: '图片', bmp: '图片', webp: '图片', txt: '文本', md: 'Markdown', log: '文本', json: 'JSON', xml: 'XML', htm: '网页', html: '网页' }
  return map[e] || (e ? e.toUpperCase() : '其他')
}

function buildTree(list) {
  const map = {}
  list.forEach((c) => (map[c.id] = { ...c, children: [] }))
  const roots = []
  list.forEach((c) => {
    if (c.parent_id && map[c.parent_id]) map[c.parent_id].children.push(map[c.id])
    else roots.push(map[c.id])
  })
  roots.sort((a, b) => a.sort_order - b.sort_order)
  const sortRec = (nodes) => nodes.sort((a, b) => a.sort_order - b.sort_order) || nodes.forEach((n) => sortRec(n.children))
  sortRec(roots)
  return [{ id: 0, name: '全部分类', material_count: total.value, children: roots }]
}
const treeData = computed(() => buildTree(categories.value))

async function loadCategories() {
  try {
    const data = await getCategories()
    categories.value = data || []
  } catch (e) { /* 忽略 */ }
}
async function loadMaterials() {
  loading.value = true
  try {
    const data = await getMaterials({
      keyword: keyword.value || undefined,
      source_type: sourceType.value || undefined,
      category_id: categoryId.value || undefined,
      file_ext: fileExt.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.items || []
    total.value = data.total || 0
    sourceStats.value = data.source_stats || []
  } catch (e) { /* 忽略 */ }
  finally { loading.value = false }
}
const extOptions = computed(() => {
  const set = new Set()
  items.value.forEach((m) => m.file_ext && set.add(m.file_ext))
  return Array.from(set)
})

function handleSearch() { page.value = 1; selectedIds.value = []; loadMaterials() }
function onPage(p) { page.value = p; selectedIds.value = []; loadMaterials() }
function onTreeNodeClick(node) {
  categoryId.value = node.id === 0 ? null : node.id
  handleSearch()
}

async function handleSync() {
  try {
    const r = await syncMaterials()
    const added = r.added ?? 0
    ElMessage.success(`汇聚完成，新增 ${added} 条（库内共 ${r.total ?? 0} 条）`)
    loadMaterials()
    loadCategories()
  } catch (e) { /* 忽略 */ }
}

async function openPreview(m) {
  previewId.value = m.id
  previewTitle.value = m.file_name
  previewVisible.value = true
  previewLoading.value = true
  previewData.value = null
  try {
    const data = await previewMaterial(m.id)
    previewData.value = data
  } catch (e) {
    previewData.value = { mode: 'unsupported', reason: '预览失败，请下载查看' }
  } finally { previewLoading.value = false }
}
function doDownload(m) { doDownloadById(m.id) }
function doDownloadById(id) {
  const a = document.createElement('a')
  a.href = downloadMaterialUrl(id)
  a.target = '_blank'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
function openReassign(m) {
  reassignForm.id = m.id
  reassignForm.category_id = m.category_id
  reassignVisible.value = true
}
// 批量模式：id 置 null，复用同一个对话框
function openBatchReassign() {
  if (!selectedIds.value.length) return
  reassignForm.id = null
  reassignForm.category_id = null
  reassignVisible.value = true
}
async function submitReassign() {
  try {
    if (reassignForm.id != null) {
      await reassignMaterialCategory(reassignForm.id, reassignForm.category_id)
    } else {
      const r = await batchReassignCategory(selectedIds.value, reassignForm.category_id)
      if (r?.not_found?.length) ElMessage.warning(`${r.updated} 个已更新，${r.not_found.length} 个未找到（可能已被删除）`)
    }
    ElMessage.success('分类已更新')
    reassignVisible.value = false
    selectedIds.value = []
    loadMaterials()
    loadCategories()
  } catch (e) { /* 忽略 */ }
}
function handleDelete(m) {
  ElMessageBox.confirm(`确定删除「${m.file_name}」的索引吗？（仅取消登记，不删物理文件）`, '提示', {
    type: 'warning',
  }).then(async () => {
    await deleteMaterial(m.id, false)
    ElMessage.success('已删除索引')
    loadMaterials()
    loadCategories()
  }).catch(() => {})
}

// ---------- 卡片多选 ----------
const allCurrentSelected = computed(
  () => items.value.length > 0 && selectedIds.value.length >= items.value.length
)
function toggleSelect(id, val) {
  if (val) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  }
}
function toggleSelectAll() {
  selectedIds.value = allCurrentSelected.value ? [] : items.value.map((m) => m.id)
}
function handleBatchDelete() {
  if (!selectedIds.value.length) return
  ElMessageBox.confirm(
    `确定删除选中的 ${selectedIds.value.length} 个材料索引吗？（仅取消登记，不删物理文件）`,
    '批量删除索引',
    { type: 'warning' }
  ).then(async () => {
    const r = await batchDeleteMaterials(selectedIds.value, false)
    if (r?.not_found?.length) ElMessage.warning(`${r.deleted} 个已删除，${r.not_found.length} 个未找到`)
    ElMessage.success('已删除索引')
    selectedIds.value = []
    loadMaterials()
    loadCategories()
  }).catch(() => {})
}

// 打开上传弹窗：自动带入左侧树当前选中的分类（「全部分类」=0 视为未分类）
function openUpload() {
  uploadForm.category_id = categoryId.value && categoryId.value !== 0 ? categoryId.value : null
  uploadVisible.value = true
}
// el-upload 的 on-change/on-remove 第二参数即当前全部待传文件（官方签名），比 ref 稳定
function syncUploadList(_file, uploadFiles) {
  uploadRawList.value = (uploadFiles || []).map((f) => f.raw).filter(Boolean)
}
function onUploadExceed(files) {
  ElMessage.warning(`单次最多 50 个文件，当前选择了 ${uploadRawList.value.length + files.length} 个`)
}
function resetUploadForm() {
  uploadRawList.value = []
  uploadForm.category_id = null
  uploadForm.note = ''
  uploaderRef.value?.clearFiles()
}

async function submitUpload() {
  const files = uploadRawList.value
  if (!files.length) return
  uploading.value = true
  try {
    // 1) 重名预检 → 二次确认（确认=仍上传副本 force；取消/关闭=默认跳过 skip）
    let dupAction = 'skip'
    try {
      const checkRes = await checkUploadConflict({
        category_id: uploadForm.category_id,
        file_names: files.map((f) => f.name),
      })
      const conflicts = checkRes?.conflicts || []
      if (conflicts.length) {
        const names = conflicts.map((c) => c.file_name).join('、')
        try {
          await ElMessageBox.confirm(
            `分类下已存在同名文件 ${conflicts.length} 个：${names}。将跳过这些文件；如确需保留副本，请点「仍然上传」。`,
            '发现重名文件',
            { confirmButtonText: '仍然上传', cancelButtonText: '跳过(默认)',
              type: 'warning', distinguishCancelAndClose: true }
          )
          dupAction = 'force'
        } catch (e) {
          dupAction = 'skip' // 取消或关闭 → 默认跳过
        }
      }
    } catch (e) { /* 预检失败不阻塞，上传端点内还会兜底 */ }

    // 2) 分块串行上传，合并结果
    const all = []
    for (let i = 0; i < files.length; i += BATCH_CHUNK) {
      const chunk = files.slice(i, i + BATCH_CHUNK)
      const fd = new FormData()
      chunk.forEach((f) => fd.append('files', f))
      if (uploadForm.category_id) fd.append('category_id', uploadForm.category_id)
      if (uploadForm.note) fd.append('note', uploadForm.note)
      fd.append('dup_action', dupAction)
      const r = await batchUploadMaterials(fd)
      all.push(...(r?.results || []))
    }

    // 3) 汇总提示
    const ok = all.filter((x) => x.status === 'success').length
    const skip = all.filter((x) => x.status === 'skipped').length
    const failed = all.filter((x) => x.status === 'failed')
    let msg = `上传完成：成功 ${ok} 个`
    if (skip) msg += `，跳过 ${skip} 个`
    if (failed.length) {
      msg += `，失败 ${failed.length} 个。失败详情：${failed.map((f) => `${f.file_name}（${f.reason}）`).join('；')}`
      ElMessage.warning(msg)
    } else {
      ElMessage.success(msg)
    }
    uploadVisible.value = false
    resetUploadForm()
    loadMaterials()
    loadCategories()
  } catch (e) { /* 拦截器已提示 */ }
  finally { uploading.value = false }
}

function onCategorySaved() { loadCategories() }

onMounted(() => { loadMaterials(); loadCategories() })
</script>

<style scoped>
.material-layout { display: flex; gap: 16px; align-items: flex-start; }
.material-aside {
  width: 220px; flex: 0 0 220px;
  background: var(--el-fill-color-blank, #fff);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px; padding: 12px;
  position: sticky; top: 12px;
}
.aside-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; margin-bottom: 8px; }
.material-tree { --el-tree-node-hover-bg-color: var(--el-fill-color-light); }
.tree-node { display: flex; justify-content: space-between; width: 100%; align-items: center; }
.tree-count { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px; }
.material-main { flex: 1; min-width: 0; }
.table-toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.material-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px; min-height: 200px;
}
.material-card { border-radius: 10px; }
.mc-top { display: flex; gap: 10px; align-items: flex-start; }
.mc-icon { font-size: 26px; flex: 0 0 26px; margin-top: 2px; }
.mc-name { font-weight: 600; font-size: 14px; line-height: 1.4; word-break: break-all;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.mc-meta { display: flex; align-items: center; gap: 8px; margin: 10px 0 6px; }
.mc-size { color: var(--el-text-color-secondary); font-size: 12px; }
.mc-sub { font-size: 12px; color: var(--el-text-color-secondary); min-height: 18px; }
.mc-cat { color: var(--el-color-primary); margin-right: 8px; }
.mc-src { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mc-actions { display: flex; gap: 2px; margin-top: 8px; border-top: 1px solid var(--el-border-color-lighter); padding-top: 6px; }
.material-pager { margin-top: 16px; justify-content: flex-end; display: flex; }
.preview-body { height: 100%; }
.preview-html { height: 100%; overflow: auto; }
.preview-text { white-space: pre-wrap; word-break: break-all; font-family: monospace; font-size: 13px;
  background: var(--el-fill-color-light); padding: 12px; border-radius: 8px; max-height: 100%; overflow: auto; }
.preview-iframe { width: 100%; height: 100%; border: none; }

/* ---------- 卡片多选 / 批量操作条 ---------- */
.batch-bar {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 10px; padding: 6px 12px;
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 8px;
}
.batch-count { font-size: 13px; color: var(--el-color-primary); font-weight: 600; }
.material-card { position: relative; }
.material-card.is-selected { border-color: var(--el-color-primary); box-shadow: 0 0 0 1px var(--el-color-primary-light-5); }
.mc-check { position: absolute; top: 6px; right: 6px; z-index: 1; height: 16px; }
.upload-tip { margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
</style>
