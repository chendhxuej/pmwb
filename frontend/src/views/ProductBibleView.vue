<template>
  <div class="product-bible">
    <div class="pb-header">
      <div class="pb-title-row">
        <h2 class="page-title">产品圣经</h2>
        <el-radio-group v-model="activeKey" @change="loadBible" size="default">
          <el-radio-button v-for="b in catalog" :key="b.key" :value="b.key">
            {{ b.name }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <el-card v-if="meta.title" class="meta-card" shadow="never">
        <div class="meta-item">
          <span class="meta-label">业务线</span><span class="meta-value">{{ meta.name }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">文档</span><span class="meta-value">{{ meta.title }}</span>
        </div>
        <div class="meta-item" v-if="meta.updated_at">
          <span class="meta-label">更新日期</span><span class="meta-value">{{ meta.updated_at }}</span>
        </div>
      </el-card>
    </div>

    <div class="pb-body" v-loading="loading">
      <aside class="pb-toc">
        <div class="toc-title">目录</div>
        <ul class="toc-list">
          <li
            v-for="item in toc"
            :key="item.id"
            :class="['toc-item', `toc-level-${item.level}`, { active: activeToc === item.id }]"
            @click="scrollTo(item.id)"
          >
            {{ item.text }}
          </li>
        </ul>
      </aside>

      <main class="pb-content">
        <MarkdownRender :content="markdown" @toc="onToc" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { productBibleApi } from '@/api/productBible'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'

const catalog = ref([])
const activeKey = ref('')
const loading = ref(false)
const markdown = ref('')
const toc = ref([])
const activeToc = ref('')

const meta = reactive({
  name: '',
  title: '',
  updated_at: '',
})

let observer = null

const loadCatalog = async () => {
  try {
    const res = await productBibleApi.getCatalog()
    catalog.value = res || []
    if (!activeKey.value && catalog.value.length) {
      activeKey.value = catalog.value[0].key
      await loadBible(activeKey.value)
    }
  } catch (e) {
    ElMessage.error('加载业务目录失败')
  }
}

const loadBible = async (key) => {
  if (!key) return
  loading.value = true
  try {
    const res = await productBibleApi.getBible(key)
    meta.name = res.name
    meta.title = res.title
    meta.updated_at = res.updated_at
    markdown.value = res.markdown
  } catch (e) {
    ElMessage.error('加载产品圣经内容失败')
    markdown.value = ''
  } finally {
    loading.value = false
  }
}

const onToc = async (list) => {
  toc.value = list || []
  activeToc.value = toc.value.length ? toc.value[0].id : ''
  await nextTick()
  setupSpy()
}

const scrollTo = (id) => {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const setupSpy = () => {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) activeToc.value = e.target.id
      })
    },
    { rootMargin: '-80px 0px -65% 0px', threshold: 0 }
  )
  toc.value.forEach((t) => {
    const el = document.getElementById(t.id)
    if (el) observer.observe(el)
  })
}

onMounted(loadCatalog)
onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.product-bible {
  padding: 20px 24px;
  height: 100%;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
}

.pb-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}

.meta-card {
  margin-bottom: 16px;
  background: #f8fafc;
}

.meta-card :deep(.el-card__body) {
  display: flex;
  gap: 32px;
  padding: 14px 18px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 14px;
}

.meta-label {
  color: #909399;
  font-size: 13px;
}

.meta-value {
  color: #303133;
  font-weight: 600;
}

.pb-body {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.pb-toc {
  width: 240px;
  flex: 0 0 240px;
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 140px);
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 10px;
}

.toc-title {
  font-size: 13px;
  font-weight: 600;
  color: #909399;
  padding: 0 8px 10px;
  border-bottom: 1px solid #f0f2f5;
  margin-bottom: 8px;
}

.toc-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.toc-item {
  padding: 6px 8px;
  font-size: 13.5px;
  color: #606266;
  cursor: pointer;
  border-radius: 6px;
  line-height: 1.5;
  transition: all 0.15s;
}

.toc-item:hover {
  background: #f0f7ff;
  color: #409eff;
}

.toc-level-3 {
  padding-left: 22px;
  font-size: 13px;
}

.toc-item.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}

.pb-content {
  flex: 1;
  min-width: 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 28px 32px;
  min-height: 60vh;
}

@media (max-width: 900px) {
  .pb-toc {
    display: none;
  }
}
</style>
