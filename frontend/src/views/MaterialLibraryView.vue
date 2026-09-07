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
        <el-button type="primary" @click="uploadVisible = true">
          <el-icon><Upload /></el-icon> 上传材料
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

        <div v-loading="loading" class="material-grid">
          <el-empty v-if="!loading && items.length === 0" description="暂无材料，点「汇聚同步」或「上传材料」" />
          <el-card v-for="m in items" :key="m.id" class="material-card" shadow="hover">
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

    <!-- 上传对话框 -->
    <el-dialog v-model="uploadVisible" title="上传材料" width="480px">
      <el-form label-width="80px">
        <el-form-item label="文件">
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            :on-change="onUploadChange"
            :on-remove="() => (uploadFile = null)"
            accept="*"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖入文件或 <em>点击选择</em></div>
          </el-upload>
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
          <el-input v-model="uploadForm.note" type="textarea" :rows="2" placeholder="可选，参与模糊搜索" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!uploadFile" :loading="uploading" @click="submitUpload">上传</el-button>
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
  uploadMaterial, getCategories, inlineMaterialUrl, downloadMaterialUrl,
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

const uploadVisible = ref(false)
const uploadFile = ref(null)
const uploading = ref(false)
const uploadForm = reactive({ category_id: null, note: '' })

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

function handleSearch() { page.value = 1; loadMaterials() }
function onPage(p) { page.value = p; loadMaterials() }
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
async function submitReassign() {
  try {
    await reassignMaterialCategory(reassignForm.id, reassignForm.category_id)
    ElMessage.success('分类已更新')
    reassignVisible.value = false
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

function onUploadChange(file) { uploadFile.value = file.raw }
async function submitUpload() {
  if (!uploadFile.value) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', uploadFile.value)
    if (uploadForm.category_id) fd.append('category_id', uploadForm.category_id)
    if (uploadForm.note) fd.append('note', uploadForm.note)
    const r = await uploadMaterial(fd)
    ElMessage.success(`已上传：${r.file_name}`)
    uploadVisible.value = false
    uploadFile.value = null
    uploadForm.category_id = null
    uploadForm.note = ''
    loadMaterials()
    loadCategories()
  } catch (e) { /* 忽略 */ }
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
</style>
