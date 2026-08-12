<template>
  <div class="sediment-panel">
    <div class="sp-header">
      <h3 class="sp-title">沉淀向导</h3>
      <span class="sp-hint">将需求/会议/运营工单中的知识沉淀到 Obsidian 业务知识库</span>
    </div>

    <!-- 三种沉淀入口 -->
    <div class="sp-cards">
      <!-- 需求沉淀 -->
      <div class="sp-card" @click="goRequirement">
        <div class="sp-card-icon" style="background: var(--accent-soft); color: var(--accent)">
          <el-icon :size="28"><Document /></el-icon>
        </div>
        <div class="sp-card-body">
          <div class="sp-card-title">需求 → 知识笔记</div>
          <div class="sp-card-desc">将需求自动生成业务知识笔记，含用户故事、规则、交付物归档</div>
        </div>
        <el-button type="primary" size="small" plain>去沉淀</el-button>
      </div>

      <!-- 会议沉淀 -->
      <div class="sp-card" @click="goMeeting">
        <div class="sp-card-icon" style="background: #f3edff; color: #7c3aed">
          <el-icon :size="28"><Calendar /></el-icon>
        </div>
        <div class="sp-card-body">
          <div class="sp-card-title">会议 → 知识笔记</div>
          <div class="sp-card-desc">将会议纪要沉淀为业务知识笔记，关联到对应业务领域</div>
        </div>
        <el-button type="primary" size="small" plain>去沉淀</el-button>
      </div>

      <!-- 运营工单沉淀 -->
      <div class="sp-card" @click="goOperation">
        <div class="sp-card-icon" style="background: var(--warning-soft); color: var(--warning)">
          <el-icon :size="28"><Warning /></el-icon>
        </div>
        <div class="sp-card-body">
          <div class="sp-card-title">运营工单 → 场景规则</div>
          <div class="sp-card-desc">将运营工单的结构化经验追加到主笔记「场景规则」子笔记</div>
        </div>
        <el-button type="primary" size="small" plain>去沉淀</el-button>
      </div>
    </div>

    <!-- 快捷操作：最近沉淀 -->
    <div class="sp-recent">
      <div class="sp-section-title">快捷操作</div>
      <div class="sp-quick">
        <el-button size="small" @click="ensureNotes">确保全部主笔记</el-button>
        <el-button size="small" @click="syncVault">从 Vault 同步</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Document, Calendar, Warning } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { knowledgeApi } from '@/api/knowledge.js'

const router = useRouter()

const goRequirement = () => router.push('/requirement-delivery')
const goMeeting = () => router.push('/meeting/list')
const goOperation = () => router.push('/operation/overview')

const ensureNotes = async () => {
  try {
    await knowledgeApi.ensureMainNotes()
    ElMessage.success('已确保所有领域主笔记')
  } catch {
    ElMessage.error('操作失败')
  }
}

const syncVault = async () => {
  try {
    const res = await knowledgeApi.syncFromVault({ force: false })
    ElMessage.success(`同步完成: ${res?.synced || 0} 条`)
  } catch {
    ElMessage.error('同步失败')
  }
}
</script>

<style scoped>
.sediment-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.sp-header {
  /* header */
}
.sp-title {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 700;
}
.sp-hint {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin-top: 4px;
}
.sp-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sp-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.sp-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-card);
}
.sp-card-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sp-card-body {
  flex: 1;
  min-width: 0;
}
.sp-card-title {
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--text-primary);
}
.sp-card-desc {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  margin-top: 2px;
  line-height: 1.5;
}
.sp-recent {
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
}
.sp-section-title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.sp-quick {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
