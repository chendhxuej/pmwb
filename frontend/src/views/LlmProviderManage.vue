<template>
  <div class="llm-manage-page">
    <div class="page-header">
      <div class="page-title">大模型管理</div>
      <div class="page-actions">
        <el-button type="primary" :icon="Plus" @click="openCreate">新增模型</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert type="info" :closable="false" show-icon class="hint">
      <template #title>多模型管理</template>
      <div class="hint-body">
        配置多个大模型提供方（Kimi / 腾讯混元 / TokenHub / DeepSeek / OpenAI 兼容等），AI总结生成时按「主用→优先级」自动 fallback；
        全部不可用时降级为规则模板并在报告页提示。API Key 仅本机存储、界面脱敏。
      </div>
    </el-alert>

    <el-table :data="list" v-loading="loading" border stripe style="width: 100%">
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="类型" width="150">
        <template #default="{ row }">{{ typeLabel(row.provider_type) }}</template>
      </el-table-column>
      <el-table-column prop="model" label="模型" min-width="160" />
      <el-table-column label="主用" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success">主用</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-switch v-model="row.is_enabled" @change="() => toggleEnabled(row)" />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="140">
        <template #default="{ row }">
          <el-tag v-if="testResults[row.id]?.reachable" type="success">可达</el-tag>
          <el-tooltip v-else-if="testResults[row.id] && !testResults[row.id].reachable" :content="testResults[row.id].error || '不可达'">
            <el-tag type="danger">不可达</el-tag>
          </el-tooltip>
          <el-tooltip v-else-if="row.last_error" :content="row.last_error">
            <el-tag type="danger">不可用</el-tag>
          </el-tooltip>
          <el-tag v-else type="info">未测试</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :loading="testingId === row.id" @click="doTest(row)">测试</el-button>
          <el-button v-if="!row.is_default" link type="success" @click="doSetDefault(row)">设主用</el-button>
          <el-button link type="warning" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="doDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模型' : '新增模型'" width="560px">
      <el-form label-width="110px" :model="form">
        <el-form-item label="名称">
          <EnlargeInput v-model="form.name" placeholder="如：默认Kimi / 腾讯混元" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.provider_type" style="width: 100%" @change="onTypeChange">
            <el-option v-for="(v, k) in presets" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="Base URL">
          <EnlargeInput v-model="form.base_url" placeholder="OpenAI 兼容端点，如 https://api.hunyuan.cloud.tencent.com/v1" />
        </el-form-item>
        <el-form-item label="模型">
          <EnlargeInput v-model="form.model" placeholder="如 hunyuan-turbos-latest / kimi-k2.6 / hy3" />
        </el-form-item>
        <el-form-item label="API Key">
          <EnlargeInput
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="留空或填 *** 表示不修改（已有密钥保留）"
          />
        </el-form-item>
        <el-form-item label="温度">
          <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="最大 Token">
          <el-input-number v-model="form.max_tokens" :min="256" :max="32768" :step="256" />
        </el-form-item>
        <el-form-item label="超时(秒)">
          <el-input-number v-model="form.timeout" :min="10" :max="600" :step="10" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="999" />
          <span class="form-tip">数值越小越优先（主用优先于优先级）</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
        <el-form-item label="设为主用">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  listLlmProviders, getLlmProviderPresets, createLlmProvider,
  updateLlmProvider, deleteLlmProvider, setDefaultLlmProvider, testLlmProvider,
} from '@/api/llmProvider'

const list = ref([])
const presets = ref({})
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const testingId = ref(null)
const testResults = reactive({})

const emptyForm = () => ({
  name: '', provider_type: 'hunyuan', base_url: '', model: '',
  api_key: '', temperature: 0.3, max_tokens: 4096, timeout: 120,
  priority: 0, is_enabled: true, is_default: false,
})
const form = reactive(emptyForm())

function typeLabel(k) {
  return presets.value[k]?.label || k
}

async function load() {
  loading.value = true
  try {
    const [providers, presetData] = await Promise.all([listLlmProviders(), getLlmProviderPresets()])
    list.value = providers || []
    presets.value = presetData || {}
  } catch (e) {
    ElMessage.error('加载大模型列表失败')
  } finally {
    loading.value = false
  }
}

function onTypeChange(k) {
  const p = presets.value[k]
  if (p) {
    form.base_url = p.base_url || ''
    form.model = p.model || ''
  }
}

function openCreate() {
  Object.assign(form, emptyForm())
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    name: row.name,
    provider_type: row.provider_type,
    base_url: row.base_url,
    model: row.model,
    api_key: '***', // 脱敏占位，保存时表示不修改
    temperature: row.temperature ?? 0.3,
    max_tokens: row.max_tokens ?? 4096,
    timeout: row.timeout ?? 120,
    priority: row.priority ?? 0,
    is_enabled: row.is_enabled,
    is_default: row.is_default,
  })
  editingId.value = row.id
  dialogVisible.value = true
}

async function save() {
  if (!form.name || !form.base_url || !form.model) {
    ElMessage.warning('请填写名称、Base URL 与模型')
    return
  }
  saving.value = true
  try {
    const payload = { ...form }
    if (!payload.api_key || payload.api_key === '***') payload.api_key = '***'
    if (editingId.value) {
      await updateLlmProvider(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createLlmProvider(payload)
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row) {
  try {
    await updateLlmProvider(row.id, {
      name: row.name, provider_type: row.provider_type, base_url: row.base_url,
      model: row.model, api_key: '***', temperature: row.temperature,
      max_tokens: row.max_tokens, timeout: row.timeout, priority: row.priority,
      is_enabled: row.is_enabled, is_default: row.is_default,
    })
  } catch (e) {
    ElMessage.error('切换启用失败')
    row.is_enabled = !row.is_enabled
  }
}

async function doSetDefault(row) {
  try {
    await setDefaultLlmProvider(row.id)
    ElMessage.success(`已将「${row.name}」设为主用`)
    await load()
  } catch (e) {
    ElMessage.error('设置主用失败')
  }
}

async function doTest(row) {
  testingId.value = row.id
  try {
    const r = await testLlmProvider(row.id)
    testResults[row.id] = { reachable: !!r.reachable, error: r.error || '' }
    if (r.reachable) ElMessage.success(`「${row.name}」连通正常`)
    else ElMessage.warning(`「${row.name}」不可达：${r.error || ''}`)
    await load()
  } catch (e) {
    ElMessage.error('测试失败：' + (e?.message || '未知错误'))
  } finally {
    testingId.value = null
  }
}

async function doDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除大模型「${row.name}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteLlmProvider(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.llm-manage-page { padding: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 600; }
.hint { margin-bottom: 16px; }
.hint-body { font-size: 13px; line-height: 1.6; color: var(--el-text-color-regular); }
.form-tip { margin-left: 10px; font-size: 12px; color: #909399; }
</style>
