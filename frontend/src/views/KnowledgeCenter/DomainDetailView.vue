<template>
  <div class="domain-detail-view">
    <!-- 顶部栏（面包屑 + 操作按钮）由视图层保留；领域详情主体委托可复用组件 -->
    <div class="detail-topbar">
      <div class="detail-title">
        <span class="gtag" :style="panelGroupStyle(panelDetail?.domain_group)">{{ panelDetail?.domain_group }}</span>
        <span>{{ panelDetail?.domain_name || '领域详情' }}</span>
      </div>
      <div class="detail-breadcrumb">
        <router-link to="/knowledge-center/hub" class="bc-link">知识中心</router-link>
        <span class="bc-sep">/</span>
        <span class="bc-current">{{ panelDetail?.domain_name || code || '' }} · 领域详情</span>
      </div>
      <div class="detail-actions">
        <el-button v-if="!panelIsEditing" plain type="primary" @click="panelStartEdit">
          <el-icon><Edit /></el-icon>
          <span>编辑主笔记</span>
        </el-button>
        <template v-else>
          <el-button @click="panelCancelEdit">取消</el-button>
          <el-button type="success" :loading="panelSaving" @click="panelSaveAll">
            <el-icon><Check /></el-icon>
            <span>全部保存</span>
          </el-button>
        </template>
        <el-button plain :loading="panelSyncing" @click="panelSync">
          <el-icon><Refresh /></el-icon>
          <span>同步主笔记</span>
        </el-button>
        <el-button v-if="panelDetail?.obsidian_path" plain type="primary" @click="panelOpenObsidian">
          <el-icon><FolderOpened /></el-icon>
          <span>打开 Obsidian</span>
        </el-button>
      </div>
    </div>

    <!-- 详情主体：产品圣经/关联对象/时间线/自动区 + 左列结构卡片 -->
    <DomainDetailPanel ref="panelRef" :code="code" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DomainDetailPanel from './DomainDetailPanel.vue'

const route = useRoute()
const code = computed(() => route.params.code)

// panel ref only via template
const panelRef = null

const panelGroupStyle = (g) => {
  const meta = {
    '商客业务': { color: '#2f6fed', bg: 'rgba(47,111,237,.10)' },
    '系统平台': { color: '#06b6d4', bg: 'rgba(6,182,212,.10)' },
    '公共能力': { color: '#10b981', bg: 'rgba(16,185,129,.10)' },
    '通用': { color: '#8b5cf6', bg: 'rgba(139,92,246,.10)' },
  }
  const m = meta[g] || meta.通用
  return { color: m.color, background: m.bg }
}

// 代理至 DomainDetailPanel 暴露的能力
const panelDetail = computed(() => panelRef?.detail ?? {})
const panelIsEditing = computed(() => panelRef?.isEditing ?? false)
const panelSaving = computed(() => panelRef?.saving ?? false)
const panelSyncing = computed(() => panelRef?.syncing ?? false)
function panelStartEdit() { panelRef?.startEdit() }
function panelCancelEdit() { panelRef?.cancelEdit() }
function panelSaveAll() { panelRef?.saveAllChanges() }
function panelSync() { panelRef?.syncMainNote() }
function panelOpenObsidian() { panelRef?.openObsidian() }
</script>

<style scoped>
.domain-detail-view {
  padding: 16px 20px;
  background: #f5f7fa;
  min-height: 100%;
}
.detail-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}
.gtag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 600;
}
.detail-breadcrumb {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}
.bc-link { color: #2f6fed; text-decoration: none; }
.bc-sep { margin: 0 6px; }
.bc-current { color: #64748b; }
.detail-actions { display: flex; gap: 10px; }
</style>
