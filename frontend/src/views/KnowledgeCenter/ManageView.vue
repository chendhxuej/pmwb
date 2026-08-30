<template>
  <div class="manage-view">
    <div class="manage-header">
      <div class="manage-titles">
        <h3 class="manage-title">领域管理</h3>
        <span class="manage-subtitle">页面化同步创建业务领域与 vault 主笔记</span>
      </div>
    </div>

    <div class="manage-grid">
      <div class="manage-card">
        <div class="card-head">
          <el-icon><Plus /></el-icon>
          <span>新增业务子领域（一键同步 vault）</span>
        </div>
        <el-form :model="form" label-position="top" @submit.prevent>
          <el-form-item label="类别（4 选 1，决定分目录）">
            <el-select v-model="form.domain_group" placeholder="选择业务分组" style="width: 100%">
              <el-option label="商客业务" value="商客业务" />
              <el-option label="系统平台" value="系统平台" />
              <el-option label="公共能力" value="公共能力" />
              <el-option label="通用" value="通用" />
            </el-select>
          </el-form-item>
          <el-form-item label="领域名称">
            <el-input v-model="form.domain_name" placeholder="如：商客安防" />
          </el-form-item>
          <el-form-item label="领域编码（domain_code）">
            <el-input v-model="form.domain_code" placeholder="如：cj-security" />
          </el-form-item>
          <el-form-item label="匹配关键词（逗号分隔，用于智能推荐）">
            <el-input v-model="form.match_keywords" placeholder="如：安防,监控,摄像头" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="syncing" @click="runSync">
              同步创建（建目录+主笔记+回写路径）
            </el-button>
            <el-button @click="$router.push('/knowledge-center/hub')">返回总览</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="manage-card">
        <div class="card-head">
          <el-icon><SetUp /></el-icon>
          <span>同步创建流程</span>
        </div>
        <div class="steps">
          <div class="step" :class="{ done: stepDone >= 1 }">
            <div class="step-num">1</div>
            <div class="step-tx">校验参数<div class="step-sd">类别 / 名称 / 编码 合法、编码未占用</div></div>
          </div>
          <div class="step" :class="{ done: stepDone >= 2 }">
            <div class="step-num">2</div>
            <div class="step-tx">计算 vault 路径<div class="step-sd">01-业务知识/{类别}/{名称}/ （走权威源）</div></div>
          </div>
          <div class="step" :class="{ done: stepDone >= 3 }">
            <div class="step-num">3</div>
            <div class="step-tx">建目录<div class="step-sd">按 Obsidian 权威路径建业务知识目录</div></div>
          </div>
          <div class="step" :class="{ done: stepDone >= 4 }">
            <div class="step-num">4</div>
            <div class="step-tx">生成主笔记（套模板）<div class="step-sd">frontmatter + 人工区占位 + 自动区预留</div></div>
          </div>
          <div class="step" :class="{ done: stepDone >= 5 }">
            <div class="step-num">5</div>
            <div class="step-tx">回写 DB + 索引<div class="step-sd">vault_path / obsidian_path 落库，立即可见</div></div>
          </div>
        </div>
        <div v-if="syncResult" class="sync-result">{{ syncResult }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Plus, SetUp } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { basicDataApi } from '@/api/basicData'
import { knowledgeApi } from '@/api/knowledge'

const form = ref({
  domain_group: '商客业务',
  domain_name: '',
  domain_code: '',
  match_keywords: '',
  enabled: true,
})
const syncing = ref(false)
const stepDone = ref(0)
const syncResult = ref('')

async function runSync() {
  if (!form.value.domain_name || !form.value.domain_code) {
    ElMessage.warning('请填写领域名称和编码')
    return
  }
  syncing.value = true
  stepDone.value = 1
  syncResult.value = ''
  try {
    const payload = {
      domain_code: form.value.domain_code,
      domain_name: form.value.domain_name,
      domain_group: form.value.domain_group,
      match_keywords: form.value.match_keywords,
      enabled: true,
    }
    const res = await basicDataApi.createBusinessDomain(payload)
    if (res.data && res.data.code === 0) {
      stepDone.value = 3
      ElMessage.success('领域已创建，开始生成主笔记')
      try {
        const mainRes = await knowledgeApi.createMainNote(form.value.domain_code)
        if (mainRes.data && mainRes.data.code === 0) {
          stepDone.value = 5
          syncResult.value = `成功：${form.value.domain_name} 已创建并生成主笔记。`
          ElMessage.success('主笔记生成成功')
        } else {
          stepDone.value = 3
          syncResult.value = `领域已创建，但主笔记生成失败：${mainRes.data?.message || ''}`
        }
      } catch (e) {
        stepDone.value = 3
        syncResult.value = `领域已创建，主笔记生成异常：${e.message}`
      }
    } else {
      ElMessage.error(res.data?.message || '创建失败')
    }
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    syncing.value = false
  }
}
</script>

<style scoped>
.manage-view { padding: 16px 20px; height: 100%; overflow: auto; background: #f5f7fa; }
.manage-header { margin-bottom: 16px; }
.manage-titles { display: flex; flex-direction: column; gap: 4px; }
.manage-title { font-size: 18px; font-weight: 700; margin: 0; color: #1d2129; }
.manage-subtitle { font-size: 13px; color: #86909c; }
.manage-grid {
  display: grid; grid-template-columns: 1.1fr .9fr; gap: 16px;
}
.manage-card {
  background: #fff; border: 1px solid #e5e6eb; border-radius: 12px;
  padding: 18px; box-shadow: 0 2px 12px rgba(0,0,0,.04);
}
.card-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 700; color: #1d2129;
  margin-bottom: 18px;
}
.steps { display: flex; flex-direction: column; gap: 0; }
.step {
  display: flex; gap: 12px; padding: 10px 0; align-items: flex-start;
}
.step-num {
  width: 24px; height: 24px; border-radius: 50%;
  background: #e5e6eb; color: #86909c;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; flex: none;
}
.step.done .step-num { background: #3fb950; color: #fff; }
.step-tx { font-size: 13px; color: #1d2129; }
.step-sd { color: #86909c; font-size: 12px; margin-top: 2px; }
.sync-result {
  margin-top: 12px; padding: 10px 12px;
  background: #f2f5ff; border-radius: 8px;
  font-size: 13px; color: #1d2129;
}
</style>
