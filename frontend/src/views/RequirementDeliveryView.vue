<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <div class="page-title">需求与交付</div>
        <div class="page-sub">需求采集 → 团队评估 → 用户故事 → 分析说明书，一条主线闭环</div>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="openTicketDialog()">
          <el-icon><Plus /></el-icon> 新增开发工单
        </el-button>
      </div>
    </div>

    <!-- 主标签：需求 / 开发工单 -->
    <el-tabs v-model="activeTab" class="pm-tabs">
      <!-- ════════ 需求标签 ════════ -->
      <el-tab-pane label="需求" name="requirement">
        <div class="pm-table-wrap">
          <div class="table-toolbar">
            <el-input
              v-model="reqKeyword"
              placeholder="搜索需求编号 / 名称 / 提出人"
              style="width: 280px"
              clearable
              @keyup.enter="loadRequirements"
              @clear="loadRequirements"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="reqStatus" placeholder="跟踪状态" clearable style="width: 140px" @change="loadRequirements">
              <el-option label="建议中" value="proposed" />
              <el-option label="已采纳" value="accepted" />
              <el-option label="开发中" value="dev" />
              <el-option label="已关闭" value="closed" />
              <el-option label="暂停" value="paused" />
            </el-select>
            <el-select v-model="reqPriority" placeholder="优先级" clearable style="width: 120px" @change="loadRequirements">
              <el-option label="P0" value="P0" />
              <el-option label="P1" value="P1" />
              <el-option label="P2" value="P2" />
              <el-option label="P3" value="P3" />
            </el-select>
            <el-button @click="loadRequirements"><el-icon><Refresh /></el-icon> 刷新</el-button>
          </div>
          <el-table
            v-loading="reqLoading"
            :data="requirements"
            stripe
            class="req-table"
            @row-click="openWorkflow"
          >
            <el-table-column prop="req_id" label="需求编号" width="160" />
            <el-table-column prop="req_name" label="需求名称" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="link-text">{{ row.req_name || '（未命名）' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="proposer" label="提出人" width="100" />
            <el-table-column prop="system_name" label="涉及系统" width="130" show-overflow-tooltip />
            <el-table-column label="优先级" width="90" align="center">
              <template #default="{ row }">
                <span class="pm-tag" :class="priorityClass(row.ext?.priority || row.priority)">{{ row.ext?.priority || row.priority || 'P2' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="跟踪状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.ext?.status)">{{ statusLabel(row.ext?.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="工作量(人天)" width="110" align="center">
              <template #default="{ row }">
                <span class="font-mono">{{ row.workload || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openWorkflow(row)">工作流</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="table-footer">
            <span class="text-muted">共 {{ reqTotal }} 条</span>
          </div>
        </div>
      </el-tab-pane>

      <!-- ════════ 开发工单标签 ════════ -->
      <el-tab-pane label="开发工单" name="ticket">
        <div class="pm-table-wrap">
          <div class="table-toolbar">
            <el-input v-model="ticketKeyword" placeholder="搜索工单号 / 系统 / 开发团队" style="width: 280px" clearable @keyup.enter="loadTickets" @clear="loadTickets">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button @click="loadTickets"><el-icon><Refresh /></el-icon> 刷新</el-button>
          </div>
          <el-table v-loading="ticketLoading" :data="tickets" stripe>
            <el-table-column prop="ticket_no" label="工单号" width="170" />
            <el-table-column prop="req_id" label="关联需求" width="160" />
            <el-table-column prop="system_name" label="涉及系统" width="130" />
            <el-table-column prop="dev_team" label="开发团队" width="120" />
            <el-table-column prop="developer" label="开发负责人" width="110" />
            <el-table-column label="优先级" width="80" align="center">
              <template #default="{ row }"><span class="pm-tag" :class="priorityClass(row.priority)">{{ row.priority }}</span></template>
            </el-table-column>
            <el-table-column label="状态" width="110" align="center">
              <template #default="{ row }"><el-tag size="small" :type="ticketStatusType(row.status)">{{ ticketStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="进度" width="160">
              <template #default="{ row }">
                <el-progress :percentage="row.progress || 0" :stroke-width="8" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openTicketDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click.stop="removeTicket(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="table-footer"><span class="text-muted">共 {{ ticketTotal }} 条</span></div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- ════════ 4步工作流抽屉 ════════ -->
    <el-drawer v-model="wfVisible" size="78%" :title="null" destroy-on-close>
      <template #header>
        <div class="wf-head">
          <div>
            <div class="wf-req-id font-mono">{{ current.req_id }}</div>
            <div class="wf-req-name">{{ current.req_name || '（未命名需求）' }}</div>
          </div>
          <div class="flex gap-8">
            <el-tag size="small" :type="statusType(current.ext?.status)">{{ statusLabel(current.ext?.status) }}</el-tag>
            <el-tag size="small" :type="priorityType(current.ext?.priority)">{{ current.ext?.priority || 'P2' }}</el-tag>
          </div>
        </div>
      </template>

      <!-- 步骤指示 -->
      <div class="wf-steps">
        <div
          v-for="(s, i) in steps"
          :key="s.key"
          class="pm-step"
          :class="{ active: step === s.key, done: isStepDone(i) }"
          @click="step = s.key"
        >
          <div class="pm-step-dot">{{ isStepDone(i) ? '✓' : i + 1 }}</div>
          <div class="pm-step-label">{{ s.label }}</div>
          <div v-if="i < steps.length - 1" class="pm-step-line" :class="{ done: isStepDone(i) }"></div>
        </div>
      </div>

      <div class="wf-body">
        <!-- ───── 步骤1：需求采集 ───── -->
        <div v-show="step === 'collect'" class="wf-step-panel">
          <div class="bento-grid">
            <div class="card" style="grid-column: span 7">
              <div class="card-header"><span class="card-label">需求基本信息</span></div>
              <div class="card-body">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="来源工单号">{{ current.req_id }}</el-descriptions-item>
                  <el-descriptions-item label="提出人">{{ current.proposer || '—' }}</el-descriptions-item>
                  <el-descriptions-item label="提出时间">{{ current.propose_time || '—' }}</el-descriptions-item>
                  <el-descriptions-item label="期望版本">{{ current.ext?.version_required_date || '未设置' }}</el-descriptions-item>
                  <el-descriptions-item label="涉及系统">{{ current.system_name || '—' }}</el-descriptions-item>
                  <el-descriptions-item label="评估SA">{{ current.sa_name || '—' }}</el-descriptions-item>
                  <el-descriptions-item label="是否涉及开发">
                    <el-tag size="small" :type="current.is_involved ? 'warning' : 'info'">{{ current.is_involved ? '涉及开发' : '不涉及' }}</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="发送评估邮件">{{ current.send_datetime || '—' }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>

            <div class="card" style="grid-column: span 5">
              <div class="card-header"><span class="card-label">需求附件（统一文件夹）</span></div>
              <div class="card-body">
                <div class="folder-path">
                  <el-icon><Folder /></el-icon>
                  <code>{{ attachmentFolder }}</code>
                </div>
                <div class="attachment-list">
                  <div v-for="(f, idx) in attachments" :key="idx" class="attachment-item">
                    <el-icon><Document /></el-icon>
                    <span class="att-name">{{ f.name }}</span>
                    <span class="att-size text-muted">{{ f.size }}</span>
                    <el-button link type="primary" size="small" @click="downloadAttachment(f)">下载</el-button>
                    <el-button link type="danger" size="small" @click="attachments.splice(idx, 1)">删除</el-button>
                  </div>
                  <div v-if="!attachments.length" class="text-muted" style="padding: 8px 0">暂无附件</div>
                </div>
                <el-button class="mt-12" size="small" @click="addAttachment">
                  <el-icon><Upload /></el-icon> 上传附件
                </el-button>
                <div class="hint-text mt-8">分析说明书生成后将自动归入此文件夹。</div>
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header"><span class="card-label">需求背景</span></div>
              <div class="card-body">
                <p class="readonly-text">{{ current.background || '（暂无背景说明）' }}</p>
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header">
                <span class="card-label">原始需求描述</span>
              </div>
              <div class="card-body">
                <p class="readonly-text">{{ current.description || '（暂无描述）' }}</p>
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header">
                <span class="card-label">澄清后需求内容（用于生成用户故事）</span>
                <el-button size="small" type="primary" @click="saveClarification">保存澄清</el-button>
              </div>
              <div class="card-body">
                <el-input
                  v-model="clarification"
                  type="textarea"
                  :rows="5"
                  placeholder="录入经评审澄清后的最终需求内容…"
                />
                <div class="hint-text mt-8">澄清内容本地暂存，后端扩展持久化接口后自动落库。</div>
              </div>
            </div>
          </div>
        </div>

        <!-- ───── 步骤2：团队评估 ───── -->
        <div v-show="step === 'evaluate'" class="wf-step-panel">
          <div class="flex-between mb-16">
            <div class="pm-section-title" style="margin:0">按系统 / 团队评估</div>
            <el-button type="primary" size="small" @click="openEvalDialog()">
              <el-icon><Plus /></el-icon> 新增系统评估
            </el-button>
          </div>
          <div class="pm-table-wrap">
            <el-table :data="evaluations" v-loading="evalLoading" size="small" border>
              <el-table-column prop="system_name" label="涉及系统" width="140" />
              <el-table-column prop="sa_name" label="SA 负责人" width="110" />
              <el-table-column prop="workload" label="工作量(人天)" width="120" align="center" />
              <el-table-column prop="review_workload" label="复核工作量(人天)" width="140" align="center" />
              <el-table-column prop="opinion" label="评估意见 / 风险" min-width="200" show-overflow-tooltip />
              <el-table-column prop="dev_ticket_no" label="开发单号" width="150" show-overflow-tooltip />
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <span class="pm-tag" :class="row.review_workload != null ? 'green' : 'amber'">
                    {{ row.review_workload != null ? '已复核' : '评估中' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openEvalDialog(row)">编辑</el-button>
                  <el-button link type="danger" size="small" @click="removeEval(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="eval-summary mt-12">
            <div class="es-item"><span class="text-muted">初评总工作量</span><b class="font-mono">{{ totalWorkload }} 人天</b></div>
            <div class="es-item"><span class="text-muted">复核总工作量</span><b class="font-mono">{{ totalReview }} 人天</b></div>
            <div class="es-item"><span class="text-muted">评估系统数</span><b class="font-mono">{{ evaluations.length }}</b></div>
          </div>
        </div>

        <!-- ───── 步骤3：用户故事 ───── -->
        <div v-show="step === 'story'" class="wf-step-panel">
          <div class="bento-grid">
            <div class="card" style="grid-column: span 5">
              <div class="card-header"><span class="card-label">澄清后需求内容</span></div>
              <div class="card-body">
                <el-input v-model="clarification" type="textarea" :rows="10" />
                <el-button class="mt-12" size="small" type="primary" @click="generateStories">
                  <el-icon><MagicStick /></el-icon> 基于 DDD 生成用户故事
                </el-button>
              </div>
              <div class="card-header mt-16"><span class="card-label">DDD 领域视角</span></div>
              <div class="card-body">
                <div class="ddd-chips">
                  <span class="pm-tag blue">领域：政企需求交付</span>
                  <span class="pm-tag gray">子域：需求评估 / 工单履约</span>
                  <span class="pm-tag gray">聚合：需求-评估-工单</span>
                  <span class="pm-tag gray">实体：需求、系统评估、用户故事</span>
                </div>
              </div>
            </div>

            <div class="card" style="grid-column: span 7">
              <div class="card-header">
                <span class="card-label">用户故事（固定模板）</span>
                <el-button size="small" @click="addStory"><el-icon><Plus /></el-icon> 新增</el-button>
              </div>
              <div class="card-body">
                <div v-for="(st, i) in stories" :key="i" class="story-card" :class="{ finalized: st.finalized }">
                  <div class="story-head">
                    <input v-model="st.title" class="story-title-input" placeholder="故事标题" />
                    <el-switch v-model="st.finalized" active-text="已定稿" inactive-text="草稿" />
                    <el-button link type="danger" size="small" @click="stories.splice(i, 1)">删除</el-button>
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">故事描述</span>
                    <el-input v-model="st.desc" type="textarea" :rows="2" placeholder="作为…，我想要…，以便…" />
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">故事场景</span>
                    <el-input v-model="st.scene" type="textarea" :rows="2" placeholder="典型使用场景…" />
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">验收标准</span>
                    <div class="ac-list">
                      <div v-for="(ac, ai) in st.acceptance" :key="ai" class="ac-row">
                        <el-input v-model="st.acceptance[ai]" placeholder="验证***功能是否成功实现" />
                        <el-button link type="danger" size="small" @click="st.acceptance.splice(ai, 1)">×</el-button>
                      </div>
                      <el-button size="small" link type="primary" @click="st.acceptance.push('')">+ 新增验收标准</el-button>
                    </div>
                  </div>
                </div>
                <div v-if="!stories.length" class="text-muted" style="padding: 16px 0">点击左侧「生成用户故事」基于澄清内容自动产出。</div>
              </div>
            </div>
          </div>
        </div>

        <!-- ───── 步骤4：生成文档 ───── -->
        <div v-show="step === 'doc'" class="wf-step-panel">
          <div class="bento-grid">
            <div class="card" style="grid-column: span 5">
              <div class="card-header"><span class="card-label">生成配置</span></div>
              <div class="card-body">
                <div class="pm-field-label">Word 模板</div>
                <el-select v-model="docTemplate" class="w-full">
                  <el-option label="政企标准 · 需求分析说明书" value="std" />
                </el-select>
                <div class="pm-field-label mt-16">文件名</div>
                <el-input v-model="docFileName" placeholder="需求分析说明书" />
                <div class="pm-field-label mt-16">归档路径</div>
                <div class="folder-path"><el-icon><Folder /></el-icon><code>{{ docFolder }}</code></div>
                <el-button class="mt-16" type="primary" @click="generateDoc">
                  <el-icon><DocumentChecked /></el-icon> 生成并归档
                </el-button>
                <div class="hint-text mt-8">第 1/2/3 章自动填充，第 4/5 章复用模板。后端文档生成端点接入后落盘。</div>
              </div>
            </div>

            <div class="card" style="grid-column: span 7">
              <div class="card-header"><span class="card-label">章节填充策略</span></div>
              <div class="card-body">
                <div class="chapter-item auto"><span class="chapter-num">1</span><div><div style="font-weight:600">基本信息</div><div class="text-muted" style="font-size:11.5px">需求编号 / 提出人 / 系统 / 优先级</div></div><span class="chapter-status">自动填充</span></div>
                <div class="chapter-item auto"><span class="chapter-num">2</span><div><div style="font-weight:600">原始需求内容</div><div class="text-muted" style="font-size:11.5px">背景 / 描述 / 澄清内容</div></div><span class="chapter-status">自动填充</span></div>
                <div class="chapter-item auto"><span class="chapter-num">3</span><div><div style="font-weight:600">用户故事</div><div class="text-muted" style="font-size:11.5px">本需求下 {{ stories.length }} 条定稿故事</div></div><span class="chapter-status">自动填充</span></div>
                <div class="chapter-item reuse"><span class="chapter-num">4</span><div><div style="font-weight:600">需求检查项</div></div><span class="chapter-status">复用模板</span></div>
                <div class="chapter-item reuse"><span class="chapter-num">5</span><div><div style="font-weight:600">版本历史</div></div><span class="chapter-status">复用模板</span></div>
              </div>
              <div class="card-header mt-16"><span class="card-label">生成记录</span></div>
              <div class="card-body" style="padding-top:0">
                <div v-for="(g, i) in genHistory" :key="i" class="gen-item">
                  <el-icon><DocumentChecked /></el-icon>
                  <div class="gen-meta"><b>{{ g.file }}</b><div class="text-muted" style="font-size:11px">{{ g.time }} · {{ g.path }}</div></div>
                  <el-button link type="primary" size="small">下载</el-button>
                </div>
                <div v-if="!genHistory.length" class="text-muted">暂无生成记录</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- 团队评估弹层 -->
    <el-dialog v-model="evalDialog" :title="evalForm.id ? '编辑系统评估' : '新增系统评估'" width="520px">
      <el-form :model="evalForm" label-width="110px">
        <el-form-item label="涉及系统"><el-input v-model="evalForm.system_name" placeholder="如：生产运营平台" /></el-form-item>
        <el-form-item label="SA 负责人"><el-input v-model="evalForm.sa_name" placeholder="如：戴晓飞" /></el-form-item>
        <el-form-item label="工作量(人天)"><el-input-number v-model="evalForm.workload" :min="0" :step="0.5" style="width:100%" /></el-form-item>
        <el-form-item label="复核工作量(人天)"><el-input-number v-model="evalForm.review_workload" :min="0" :step="0.5" style="width:100%" /></el-form-item>
        <el-form-item label="评估意见"><el-input v-model="evalForm.opinion" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="开发单号"><el-input v-model="evalForm.dev_ticket_no" placeholder="可选" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="evalDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEval">保存</el-button>
      </template>
    </el-dialog>

    <!-- 开发工单弹层 -->
    <el-dialog v-model="ticketDialog" :title="ticketForm.id ? '编辑开发工单' : '新增开发工单'" width="560px">
      <el-form :model="ticketForm" label-width="110px">
        <el-form-item label="工单号"><el-input v-model="ticketForm.ticket_no" :disabled="!!ticketForm.id" placeholder="如：DEV-2026-0718" /></el-form-item>
        <el-form-item label="关联需求"><el-input v-model="ticketForm.req_id" placeholder="需求编号" /></el-form-item>
        <el-form-item label="涉及系统"><el-input v-model="ticketForm.system_name" /></el-form-item>
        <el-form-item label="开发团队"><el-input v-model="ticketForm.dev_team" /></el-form-item>
        <el-form-item label="开发负责人"><el-input v-model="ticketForm.developer" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="ticketForm.priority" style="width:100%">
            <el-option label="P0" value="P0" /><el-option label="P1" value="P1" /><el-option label="P2" value="P2" /><el-option label="P3" value="P3" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="ticketForm.status" style="width:100%">
            <el-option label="已创建" value="created" /><el-option label="设计已评审" value="design_reviewed" />
            <el-option label="开发完成" value="dev_completed" /><el-option label="测试完成" value="test_completed" />
            <el-option label="已上线" value="live" /><el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
        <el-form-item label="进度"><el-slider v-model="ticketForm.progress" :step="5" show-input /></el-form-item>
        <el-form-item label="描述"><el-input v-model="ticketForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ticketDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTicket">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getRequirements,
  getEvaluations, createEvaluation, updateEvaluation, deleteEvaluation,
} from '@/api/requirement'
import {
  getDevTickets, createDevTicket, updateDevTicket, deleteDevTicket,
} from '@/api/dev_ticket'

/* ─────────────── 需求标签 ─────────────── */
const activeTab = ref('requirement')
const reqKeyword = ref('')
const reqStatus = ref('')
const reqPriority = ref('')
const reqLoading = ref(false)
const requirements = ref([])
const reqTotal = ref(0)

async function loadRequirements() {
  reqLoading.value = true
  try {
    const res = await getRequirements({
      keyword: reqKeyword.value || undefined,
      status: reqStatus.value || undefined,
      priority: reqPriority.value || undefined,
      page: 1, page_size: 50,
    })
    requirements.value = res.items || []
    reqTotal.value = res.total || 0
  } finally {
    reqLoading.value = false
  }
}

/* ─────────────── 工单标签 ─────────────── */
const ticketKeyword = ref('')
const ticketLoading = ref(false)
const tickets = ref([])
const ticketTotal = ref(0)

async function loadTickets() {
  ticketLoading.value = true
  try {
    const res = await getDevTickets({ keyword: ticketKeyword.value || undefined, page: 1, page_size: 50 })
    tickets.value = res.items || []
    ticketTotal.value = res.total || 0
  } finally {
    ticketLoading.value = false
  }
}

/* ─────────────── 4步工作流抽屉 ─────────────── */
const steps = [
  { key: 'collect', label: '需求采集' },
  { key: 'evaluate', label: '团队评估' },
  { key: 'story', label: '用户故事' },
  { key: 'doc', label: '生成文档' },
]
const wfVisible = ref(false)
const step = ref('collect')
const current = ref({})
const clarification = ref('')
const attachments = ref([])
const evaluations = ref([])
const evalLoading = ref(false)
const stories = ref([])
const docTemplate = ref('std')
const docFileName = ref('')
const genHistory = ref([])

// 每需求本地工作流态（用户故事/澄清/附件，后端扩展前暂存）
const localStore = reactive({})

const attachmentFolder = computed(() => {
  const name = (current.value.req_name || 'requirement').replace(/[\\/:*?"<>|]/g, '_')
  return `D:\\项目\\知识图谱\\业务建设\\需求附件\\${current.value.req_id}_${name}\\`
})
const docFolder = computed(() => {
  const name = (current.value.req_name || 'requirement').replace(/[\\/:*?"<>|]/g, '_')
  return `D:\\项目\\知识图谱\\业务建设\\需求分析说明书\\${current.value.req_id}_${name}\\`
})
const totalWorkload = computed(() => evaluations.value.reduce((s, e) => s + (Number(e.workload) || 0), 0).toFixed(1))
const totalReview = computed(() => evaluations.value.reduce((s, e) => s + (Number(e.review_workload) || 0), 0).toFixed(1))

function isStepDone(i) {
  if (i === 0) return !!current.value.req_id
  if (i === 1) return evaluations.value.length > 0
  if (i === 2) return stories.value.length > 0
  if (i === 3) return genHistory.value.length > 0
  return false
}

async function openWorkflow(row) {
  current.value = row
  step.value = 'collect'
  clarification.value = row.clarification || ''
  docFileName.value = `关于${row.req_name || '需求'}的需求分析说明书`
  const key = row.req_id
  const cached = localStore[key] || {}
  attachments.value = cached.attachments || []
  stories.value = cached.stories || []
  genHistory.value = cached.genHistory || []
  wfVisible.value = true
  await loadEvaluations(key)
}

async function loadEvaluations(reqId) {
  evalLoading.value = true
  try {
    evaluations.value = await getEvaluations(reqId) || []
  } finally {
    evalLoading.value = false
  }
}

function cacheLocal() {
  localStore[current.value.req_id] = {
    attachments: attachments.value,
    stories: stories.value,
    genHistory: genHistory.value,
  }
}

function saveClarification() {
  // 后端 RequirementExtUpdate 暂不含 clarification 字段，先本地暂存
  current.value.clarification = clarification.value
  cacheLocal()
  ElMessage.success('澄清内容已暂存（待后端持久化）')
}

/* 附件（前端态） */
function addAttachment() {
  ElMessageBox.prompt('输入附件文件名', '上传附件', { inputValue: '附件.docx' })
    .then(({ value }) => {
      attachments.value.push({ name: value, size: '0.4 MB' })
      cacheLocal()
    }).catch(() => {})
}
function downloadAttachment(f) {
  ElMessage.info(`下载：${f.name}（后端附件端点接入后生效）`)
}

/* 评估弹层 */
const evalDialog = ref(false)
const evalForm = reactive({ id: null, system_name: '', sa_name: '', workload: 0, review_workload: null, opinion: '', dev_ticket_no: '' })
function openEvalDialog(row) {
  if (row) Object.assign(evalForm, { id: row.id, system_name: row.system_name, sa_name: row.sa_name, workload: row.workload, review_workload: row.review_workload, opinion: row.opinion, dev_ticket_no: row.dev_ticket_no })
  else Object.assign(evalForm, { id: null, system_name: '', sa_name: '', workload: 0, review_workload: null, opinion: '', dev_ticket_no: '' })
  evalDialog.value = true
}
async function saveEval() {
  const reqId = current.value.req_id
  if (evalForm.id) {
    await updateEvaluation(reqId, evalForm.id, { ...evalForm })
    ElMessage.success('评估已更新')
  } else {
    await createEvaluation(reqId, { sa_name: evalForm.sa_name, system_name: evalForm.system_name, workload: evalForm.workload, review_workload: evalForm.review_workload, opinion: evalForm.opinion, dev_ticket_no: evalForm.dev_ticket_no })
    ElMessage.success('评估已新增')
  }
  evalDialog.value = false
  await loadEvaluations(reqId)
}
async function removeEval(row) {
  await ElMessageBox.confirm(`确认删除「${row.system_name}」的评估？`, '提示', { type: 'warning' })
  await deleteEvaluation(current.value.req_id, row.id)
  ElMessage.success('已删除')
  await loadEvaluations(current.value.req_id)
}

/* 用户故事 */
function addStory() {
  stories.value.push({ title: '', desc: '', scene: '', acceptance: [''], finalized: false })
  cacheLocal()
}
function generateStories() {
  if (!clarification.value.trim()) {
    ElMessage.warning('请先填写澄清后需求内容')
    return
  }
  const base = clarification.value.slice(0, 20)
  stories.value = [
    { title: `查看${base}进度`, desc: `作为政企产品经理，我想要查看${base}的处理进度，以便及时跟进排期。`, scene: `进入需求详情页，切换至「用户故事」标签查看进度看板。`, acceptance: [`验证${base}进度展示功能是否成功实现`, `验证进度按系统维度拆分是否成功实现`], finalized: false },
    { title: `导出${base}清单`, desc: `作为运营人员，我想要导出${base}相关清单，以便线下跟进。`, scene: `在列表勾选目标需求，点击导出按钮。`, acceptance: [`验证${base}清单导出功能是否成功实现`, `验证导出字段完整性是否成功实现`], finalized: false },
  ]
  cacheLocal()
  ElMessage.success('已基于澄清内容生成用户故事')
}
watch(stories, cacheLocal, { deep: true })

/* 文档生成 */
function generateDoc() {
  const file = `${docFileName.value || '需求分析说明书'}.docx`
  genHistory.value.unshift({
    file,
    path: docFolder.value,
    time: new Date().toLocaleString('zh-CN'),
  })
  cacheLocal()
  ElMessage.success(`已生成并归档：${file}`)
}

/* 工单弹层 */
const ticketDialog = ref(false)
const ticketForm = reactive({ id: null, ticket_no: '', req_id: '', system_name: '', dev_team: '', developer: '', priority: 'P2', status: 'created', progress: 0, description: '' })
function openTicketDialog(row) {
  if (row) Object.assign(ticketForm, { ...row })
  else Object.assign(ticketForm, { id: null, ticket_no: '', req_id: current.value.req_id || '', system_name: '', dev_team: '', developer: '', priority: 'P2', status: 'created', progress: 0, description: '' })
  ticketDialog.value = true
}
async function saveTicket() {
  if (ticketForm.id) {
    await updateDevTicket(ticketForm.id, { ...ticketForm })
    ElMessage.success('工单已更新')
  } else {
    await createDevTicket({ ...ticketForm })
    ElMessage.success('工单已创建')
  }
  ticketDialog.value = false
  await loadTickets()
}
async function removeTicket(row) {
  await ElMessageBox.confirm(`确认删除工单 ${row.ticket_no}？`, '提示', { type: 'warning' })
  await deleteDevTicket(row.id)
  ElMessage.success('已删除')
  await loadTickets()
}

/* ─────────────── 工具 ─────────────── */
function priorityClass(p) {
  return { P0: 'red', P1: 'amber', P2: 'blue', P3: 'gray' }[p] || 'gray'
}
function statusType(s) {
  return { proposed: 'info', accepted: 'warning', dev: 'primary', closed: 'success', paused: 'info' }[s] || 'info'
}
function statusLabel(s) {
  return { proposed: '建议中', accepted: '已采纳', dev: '开发中', closed: '已关闭', paused: '暂停' }[s] || s || '建议中'
}
function priorityType(p) {
  return { P0: 'danger', P1: 'warning', P2: '', P3: 'info' }[p] || ''
}
function ticketStatusType(s) {
  return { created: 'info', design_reviewed: 'warning', dev_completed: 'primary', test_completed: 'primary', live: 'success', archived: 'info' }[s] || 'info'
}
function ticketStatusLabel(s) {
  return { created: '已创建', design_reviewed: '设计已评审', dev_completed: '开发完成', test_completed: '测试完成', live: '已上线', archived: '已归档' }[s] || s
}

loadRequirements()
loadTickets()
</script>

<style scoped>
.page-sub { font-size: 12.5px; color: var(--text-secondary); margin-top: 4px }
.pm-tabs { margin-top: 4px }
.table-toolbar { display: flex; gap: 10px; align-items: center; padding: 16px 20px; flex-wrap: wrap }
.table-footer { padding: 12px 20px; border-top: 1px solid var(--border-subtle) }
.link-text { color: var(--accent); cursor: pointer; font-weight: 500 }
.req-table :deep(.el-table__row) { cursor: pointer }

.wf-head { display: flex; align-items: center; justify-content: space-between; width: 100% }
.wf-req-id { font-size: 12px; color: var(--text-muted) }
.wf-req-name { font-size: 17px; font-weight: 700; color: var(--text-primary); margin-top: 2px }
.wf-steps { padding: 18px 24px; border-bottom: 1px solid var(--border-subtle) }
.wf-body { padding: 22px 24px 40px }
.wf-step-panel { animation: fadeIn .25s ease }
@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }

.readonly-text { font-size: 13.5px; line-height: 1.7; color: var(--text-secondary); white-space: pre-wrap; margin: 0 }
.folder-path { display: flex; align-items: center; gap: 8px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 8px 12px; font-size: 12px }
.folder-path code { color: var(--accent); font-family: var(--font-mono); word-break: break-all }
.attachment-list { margin-top: 10px }
.attachment-item { display: flex; align-items: center; gap: 8px; padding: 7px 0; border-bottom: 1px solid var(--border-subtle); font-size: 13px }
.att-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.att-size { font-size: 11px }
.hint-text { font-size: 11.5px; color: var(--text-muted) }

.eval-summary { display: flex; gap: 28px; padding: 14px 18px; background: var(--bg-app); border-radius: 10px }
.es-item { display: flex; flex-direction: column; gap: 2px }
.es-item b { font-size: 18px; color: var(--text-primary) }

.ddd-chips { display: flex; flex-wrap: wrap; gap: 8px }

.story-card { border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; margin-bottom: 14px; transition: all .2s }
.story-card.finalized { border-color: var(--success); background: var(--success-soft) }
.story-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px }
.story-title-input { flex: 1; border: none; border-bottom: 1px dashed var(--border); background: transparent; font-size: 14px; font-weight: 600; color: var(--text-primary); padding: 4px 0; outline: none }
.story-field { margin-bottom: 10px }
.story-field-label { font-size: 11.5px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .05em; display: block; margin-bottom: 5px }
.ac-list { display: flex; flex-direction: column; gap: 6px }
.ac-row { display: flex; align-items: center; gap: 6px }
.ac-row .el-input { flex: 1 }

.chapter-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 10px; margin-bottom: 8px }
.chapter-num { width: 26px; height: 26px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; flex-shrink: 0 }
.chapter-item.auto { background: var(--accent-soft) }
.chapter-item.auto .chapter-num { background: var(--accent); color: #fff }
.chapter-item.reuse .chapter-num { background: var(--border-subtle); color: var(--text-secondary) }
.chapter-status { margin-left: auto; font-size: 11.5px; font-weight: 600; padding: 2px 10px; border-radius: 999px }
.chapter-item.auto .chapter-status { background: #fff; color: var(--accent) }
.chapter-item.reuse .chapter-status { background: var(--border-subtle); color: var(--text-secondary) }

.gen-item { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle) }
.gen-meta { flex: 1; min-width: 0 }

.w-full { width: 100% }
</style>
