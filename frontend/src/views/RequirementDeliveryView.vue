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
              @keyup.enter="handleReqSearch"
              @clear="handleReqSearch"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="reqStatus" placeholder="跟踪状态" clearable style="width: 140px" @change="handleReqSearch">
              <el-option label="建议中" value="proposed" />
              <el-option label="已采纳" value="accepted" />
              <el-option label="开发中" value="dev" />
              <el-option label="已关闭" value="closed" />
              <el-option label="暂停" value="paused" />
            </el-select>
            <el-select v-model="reqPriority" placeholder="优先级" clearable style="width: 120px" @change="handleReqSearch">
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
            scrollbar-always-on
            @row-click="openWorkflow"
          >
            <el-table-column prop="req_id" label="需求编号" width="150" show-overflow-tooltip />
            <el-table-column prop="req_name" label="需求名称" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="link-text">{{ row.req_name || '（未命名）' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="proposer" label="提出人" width="90" />
            <el-table-column label="录入时间" width="105" align="center">
              <template #default="{ row }">
                <span class="text-muted">{{ formatDate(row.created_at || row.send_datetime || row.propose_time) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="eval_systems" label="涉及系统" width="140" show-overflow-tooltip />
            <el-table-column label="优先级" width="70" align="center">
              <template #default="{ row }">
                <span class="pm-tag" :class="priorityClass(row.ext?.priority || row.priority)">{{ row.ext?.priority || row.priority || 'P2' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="跟踪状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.ext?.status)">{{ statusLabel(row.ext?.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="工作量(人天)" width="110" align="center">
              <template #default="{ row }">
                <span class="font-mono">{{ row.eval_workload != null ? row.eval_workload : '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="dev_ticket_no" label="开发单号" width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="120" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openReqDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click.stop="removeReq(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="table-footer">
            <span class="text-muted">共 {{ reqTotal }} 条</span>
            <el-pagination
              v-model:current-page="reqPage"
              v-model:page-size="reqPageSize"
              :total="reqTotal"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              small
              background
              @size-change="loadRequirements"
              @current-change="loadRequirements"
            />
          </div>
        </div>
      </el-tab-pane>

      <!-- ════════ 开发工单标签 ════════ -->
      <el-tab-pane label="开发工单" name="ticket">
        <div class="pm-table-wrap">
          <div class="table-toolbar">
            <el-input v-model="ticketKeyword" placeholder="搜索工单号 / 系统 / 开发团队" style="width: 280px" clearable @keyup.enter="handleTicketSearch" @clear="handleTicketSearch">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button @click="loadTickets"><el-icon><Refresh /></el-icon> 刷新</el-button>
          </div>
          <el-table v-loading="ticketLoading" :data="tickets" stripe scrollbar-always-on>
            <el-table-column prop="ticket_no" label="工单号" width="150" show-overflow-tooltip />
            <el-table-column prop="req_id" label="关联需求" width="140" show-overflow-tooltip />
            <el-table-column prop="system_name" label="涉及系统" width="110" show-overflow-tooltip />
            <el-table-column prop="dev_team" label="开发团队" width="100" show-overflow-tooltip />
            <el-table-column prop="developer" label="开发负责人" width="100" />
            <el-table-column label="优先级" width="70" align="center">
              <template #default="{ row }"><span class="pm-tag" :class="priorityClass(row.priority)">{{ row.priority }}</span></template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }"><el-tag size="small" :type="ticketStatusType(row.status)">{{ ticketStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="进度" width="140">
              <template #default="{ row }">
                <el-progress :percentage="row.progress || 0" :stroke-width="8" />
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="105" align="center">
              <template #default="{ row }">
                <span class="text-muted">{{ formatDate(row.created_at || row.send_datetime) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openTicketDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click.stop="removeTicket(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="table-footer">
            <span class="text-muted">共 {{ ticketTotal }} 条</span>
            <el-pagination
              v-model:current-page="ticketPage"
              v-model:page-size="ticketPageSize"
              :total="ticketTotal"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              small
              background
              @size-change="loadTickets"
              @current-change="loadTickets"
            />
          </div>
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
              <div class="card-header flex-between">
                <span class="card-label">需求基本信息（可直接修改）</span>
                <el-button size="small" type="primary" @click="saveDetail">保存</el-button>
              </div>
              <div class="card-body">
                <el-form :model="current" label-width="100px" size="small">
                  <div class="bento-grid" style="gap: 8px">
                    <div style="grid-column: span 6">
                      <el-form-item label="需求名称"><el-input v-model="current.req_name" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="涉及系统"><el-input v-model="current.system_name" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="评估 SA"><el-input v-model="current.sa_name" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="优先级">
                        <el-select v-model="current.priority" style="width:100%">
                          <el-option label="P0" value="P0" /><el-option label="P1" value="P1" />
                          <el-option label="P2" value="P2" /><el-option label="P3" value="P3" />
                        </el-select>
                      </el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="跟踪状态">
                        <el-select v-model="current.status" style="width:100%">
                          <el-option label="建议中" value="proposed" /><el-option label="已采纳" value="accepted" />
                          <el-option label="开发中" value="dev" /><el-option label="已关闭" value="closed" />
                          <el-option label="暂停" value="paused" />
                        </el-select>
                      </el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="期望版本日">
                        <el-date-picker v-model="current.version_required_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="选择日期" />
                      </el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="开发单号">
                        <el-input v-model="current.dev_ticket_no" placeholder="需求级开发单号，如 DEV-2026-001" />
                      </el-form-item>
                    </div>
                    <div style="grid-column: span 12">
                      <el-form-item label="负责人备忘"><el-input v-model="current.owner_note" type="textarea" :rows="2" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="个人标签"><el-input v-model="current.tags" placeholder="逗号分隔" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="个人备注"><el-input v-model="current.personal_note" type="textarea" :rows="2" /></el-form-item>
                    </div>
                  </div>
                </el-form>
              </div>
            </div>

            <div class="card" style="grid-column: span 5">
              <div class="card-header"><span class="card-label">需求分析说明书文件夹</span></div>
              <div class="card-body">
                <div class="folder-path">
                  <el-icon><Folder /></el-icon>
                  <code>{{ folder || '（打开需求后初始化）' }}</code>
                </div>
                <div class="attachment-list">
                  <div v-for="(f, idx) in attachments" :key="idx" class="attachment-item">
                    <el-icon><Document /></el-icon>
                    <span class="att-name">{{ f.name }}</span>
                    <span class="att-size text-muted">{{ f.size }}</span>
                    <el-button link type="primary" size="small" @click="downloadAttachment(f)">下载</el-button>
                    <el-button link type="danger" size="small" @click="removeAttachment(f)">删除</el-button>
                  </div>
                  <div v-if="!attachments.length" class="text-muted" style="padding: 8px 0">暂无文件，可上传附件或生成说明书</div>
                </div>
                <input ref="fileInput" type="file" style="display:none" @change="handleFileChange" />
                <el-button class="mt-12" size="small" @click="triggerUpload">
                  <el-icon><Upload /></el-icon> 上传文件
                </el-button>
                <div class="hint-text mt-8">附件与生成文档统一归档在「需求分析说明书」文件夹。</div>
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
                <span class="card-label">需求背景</span>
                <el-button size="small" type="primary" @click="saveDetail">保存</el-button>
              </div>
              <div class="card-body">
                <el-input v-model="current.background" type="textarea" :rows="4" placeholder="可覆盖原始背景…" />
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
                <span class="card-label">原始需求描述</span>
                <el-button size="small" type="primary" @click="saveDetail">保存</el-button>
              </div>
              <div class="card-body">
                <el-input v-model="current.description" type="textarea" :rows="4" placeholder="可覆盖原始描述…" />
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
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
                <div class="hint-text mt-8">澄清内容已接入后端持久化。</div>
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
                  <span class="pm-tag blue">领域：{{ dddView.domain }}</span>
                  <span class="pm-tag gray">子域：{{ dddView.subdomain }}</span>
                  <span class="pm-tag gray">聚合：{{ dddView.aggregate }}</span>
                  <span class="pm-tag gray">实体：{{ dddView.entity }}</span>
                </div>
              </div>
            </div>

            <div class="card" style="grid-column: span 7">
              <div class="card-header">
                <span class="card-label">用户故事（固定模板）</span>
                <div class="flex gap-8">
                  <el-button size="small" type="primary" @click="saveStories">保存</el-button>
                  <el-button size="small" @click="addStory"><el-icon><Plus /></el-icon> 新增</el-button>
                </div>
              </div>
              <div class="card-body">
                <div v-for="(st, i) in stories" :key="i" class="story-card" :class="{ finalized: st.finalized }">
                  <div class="story-head">
                    <span class="story-seq">US{{ i + 1 }}</span>
                    <input v-model="st.title" class="story-title-input" placeholder="故事标题" />
                    <el-switch v-model="st.finalized" active-text="已定稿" inactive-text="草稿" />
                    <el-button link type="danger" size="small" @click="stories.splice(i, 1)">删除</el-button>
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">故事描述</span>
                    <el-input v-model="st.desc" type="textarea" :autosize="{ minRows: 3, maxRows: 14 }" placeholder="作为…，我想要…，以便…" />
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">故事场景</span>
                    <el-input v-model="st.scene" type="textarea" :autosize="{ minRows: 3, maxRows: 14 }" placeholder="典型使用场景…" />
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">验收标准</span>
                    <div class="ac-list">
                      <div v-for="(ac, ai) in st.acceptance" :key="ai" class="ac-row">
                        <el-input v-model="st.acceptance[ai]" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }" placeholder="验证***功能是否成功实现" />
                        <el-button link type="danger" size="small" @click="st.acceptance.splice(ai, 1)">×</el-button>
                      </div>
                      <el-button size="small" link type="primary" @click="st.acceptance.push('')">+ 新增验收标准</el-button>
                    </div>
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">业务规则（每条一栏，可空，生成文档时每种子下将落规则表）</span>
                    <div class="ac-list">
                      <div v-for="(r, ri) in (st.rules || [])" :key="ri" class="ac-row">
                        <el-input v-model="st.rules[ri]" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }" placeholder="提炼本故事的业务规则…" />
                        <el-button link type="danger" size="small" @click="st.rules.splice(ri, 1)">×</el-button>
                      </div>
                      <el-button size="small" link type="primary" @click="(st.rules || (st.rules = [])).push('')">+ 新增业务规则</el-button>
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
                <div class="folder-path"><el-icon><Folder /></el-icon><code>{{ folder }}</code></div>
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
                  <el-button link type="primary" size="small" @click="openGen(g)">打开</el-button>
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

    <!-- 需求编辑弹层 -->
    <el-dialog v-model="reqDialog" title="编辑需求跟踪信息" width="560px">
      <el-form :model="reqForm" label-width="110px">
        <el-form-item label="需求名称"><el-input v-model="reqForm.req_name" placeholder="覆盖 sent_emails 原始名称" /></el-form-item>
        <el-form-item label="涉及系统"><el-input v-model="reqForm.system_name" placeholder="覆盖原始系统" /></el-form-item>
        <el-form-item label="SA"><el-input v-model="reqForm.sa_name" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="reqForm.priority" style="width:100%">
            <el-option label="P0" value="P0" /><el-option label="P1" value="P1" />
            <el-option label="P2" value="P2" /><el-option label="P3" value="P3" />
          </el-select>
        </el-form-item>
        <el-form-item label="跟踪状态">
          <el-select v-model="reqForm.status" style="width:100%">
            <el-option label="建议中" value="proposed" /><el-option label="已采纳" value="accepted" />
            <el-option label="开发中" value="dev" /><el-option label="已关闭" value="closed" />
            <el-option label="暂停" value="paused" />
          </el-select>
        </el-form-item>
        <el-form-item label="期望版本日"><el-date-picker v-model="reqForm.version_required_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="选择日期" /></el-form-item>
        <el-form-item label="需求背景"><el-input v-model="reqForm.background" type="textarea" :rows="3" placeholder="覆盖原始背景" /></el-form-item>
        <el-form-item label="需求描述"><el-input v-model="reqForm.description" type="textarea" :rows="3" placeholder="覆盖原始描述" /></el-form-item>
        <el-form-item label="澄清内容"><el-input v-model="reqForm.clarification" type="textarea" :rows="3" placeholder="经评审后的澄清内容" /></el-form-item>
        <el-form-item label="负责人备忘"><el-input v-model="reqForm.owner_note" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="个人标签"><el-input v-model="reqForm.tags" placeholder="逗号分隔" /></el-form-item>
        <el-form-item label="个人备注"><el-input v-model="reqForm.personal_note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reqDialog = false">取消</el-button>
        <el-button type="primary" @click="saveReq">保存</el-button>
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
import { formatDate } from '@/utils/format'
import {
  getRequirements, getRequirement, updateRequirement, deleteRequirement,
  getEvaluations, createEvaluation, updateEvaluation, deleteEvaluation,
  initRequirementFolder, listRequirementAttachments, uploadRequirementAttachment,
  deleteRequirementAttachment, generateUserStories, getUserStories, saveUserStories, generateRequirementDoc,
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
const reqPage = ref(1)
const reqPageSize = ref(20)

async function loadRequirements() {
  reqLoading.value = true
  try {
    const res = await getRequirements({
      keyword: reqKeyword.value || undefined,
      status: reqStatus.value || undefined,
      priority: reqPriority.value || undefined,
      page: reqPage.value,
      page_size: reqPageSize.value,
    })
    requirements.value = res.items || []
    reqTotal.value = res.total || 0
  } finally {
    reqLoading.value = false
  }
}

function handleReqSearch() {
  reqPage.value = 1
  loadRequirements()
}

/* 需求编辑/删除 */
const reqDialog = ref(false)
const reqForm = reactive({
  req_id: '',
  req_name: '',
  system_name: '',
  sa_name: '',
  priority: 'P2',
  status: 'proposed',
  version_required_date: '',
  dev_ticket_no: '',
  background: '',
  description: '',
  clarification: '',
  owner_note: '',
  tags: '',
  personal_note: '',
})
function openReqDialog(row) {
  Object.assign(reqForm, {
    req_id: row.req_id,
    req_name: row.req_name || '',
    system_name: row.system_name || '',
    sa_name: row.sa_name || '',
    priority: row.ext?.priority || 'P2',
    status: row.ext?.status || 'proposed',
    version_required_date: row.ext?.version_required_date || '',
    dev_ticket_no: row.dev_ticket_no || '',
    background: row.background || '',
    description: row.description || '',
    clarification: row.clarification || '',
    owner_note: row.ext?.owner_note || '',
    tags: row.ext?.tags || '',
    personal_note: row.ext?.personal_note || '',
  })
  reqDialog.value = true
}
async function saveReq() {
  const payload = { ...reqForm }
  await updateRequirement(reqForm.req_id, payload)
  ElMessage.success('需求信息已保存')
  reqDialog.value = false
  await loadRequirements()
  // 若当前正在看工作流，同步刷新 current
  if (current.value.req_id === reqForm.req_id) {
    await refreshCurrent(reqForm.req_id)
  }
}
async function removeReq(row) {
  await ElMessageBox.confirm(`确认删除需求 ${row.req_id} 的工作台数据？（只读源数据保留）`, '提示', { type: 'warning' })
  await deleteRequirement(row.req_id)
  ElMessage.success('已删除')
  await loadRequirements()
}
async function refreshCurrent(reqId) {
  try {
    const res = await getRequirement(reqId)
    if (res) {
      current.value = res
      current.value.priority = res.ext?.priority || 'P2'
      current.value.status = res.ext?.status || 'proposed'
      current.value.version_required_date = res.ext?.version_required_date || ''
      current.value.dev_ticket_no = res.dev_ticket_no || ''
      current.value.owner_note = res.ext?.owner_note || ''
      current.value.tags = res.ext?.tags || ''
      current.value.personal_note = res.ext?.personal_note || ''
    }
  } catch (e) { /* ignore */ }
}

/* ─────────────── 工单标签 ─────────────── */
const ticketKeyword = ref('')
const ticketLoading = ref(false)
const tickets = ref([])
const ticketTotal = ref(0)
const ticketPage = ref(1)
const ticketPageSize = ref(20)

async function loadTickets() {
  ticketLoading.value = true
  try {
    const res = await getDevTickets({
      keyword: ticketKeyword.value || undefined,
      page: ticketPage.value,
      page_size: ticketPageSize.value,
    })
    tickets.value = res.items || []
    ticketTotal.value = res.total || 0
  } finally {
    ticketLoading.value = false
  }
}

function handleTicketSearch() {
  ticketPage.value = 1
  loadTickets()
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
const dddView = ref({ domain: '政企需求交付', subdomain: '需求评估与履约', aggregate: '需求-评估-交付', entity: '需求、用户故事、开发工单' })

// 真实路径（来自后端 init-folder）
const folder = ref('')

// 生成文档历史本地暂存
const localStore = reactive({})
function cacheLocal() {
  localStore[current.value.req_id] = { genHistory: genHistory.value }
}

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
  // 把 ext 跟踪字段铺平到 current，方便表单直接绑定
  current.value.priority = row.ext?.priority || 'P2'
  current.value.status = row.ext?.status || 'proposed'
  current.value.version_required_date = row.ext?.version_required_date || ''
  current.value.dev_ticket_no = row.dev_ticket_no || ''
  current.value.owner_note = row.ext?.owner_note || ''
  current.value.tags = row.ext?.tags || ''
  current.value.personal_note = row.ext?.personal_note || ''
  clarification.value = row.clarification || ''
  docFileName.value = `关于${row.req_name || '需求'}的需求分析说明书`
  const key = row.req_id
  const cached = localStore[key] || {}
  stories.value = cached.stories || []
  genHistory.value = cached.genHistory || []
  wfVisible.value = true
  // 真实创建/读取需求文件夹，并拉取真实附件列表
  try {
    const res = await initRequirementFolder(key)
    folder.value = res.folder || ''
    attachments.value = res.attachments || []
  } catch (e) {
    folder.value = ''
    attachments.value = []
  }
  await loadEvaluations(key)
  await loadStories(key)
}

async function loadEvaluations(reqId) {
  evalLoading.value = true
  try {
    evaluations.value = await getEvaluations(reqId) || []
  } finally {
    evalLoading.value = false
  }
}

async function loadStories(reqId) {
  try {
    const res = await getUserStories(reqId)
    stories.value = (res.stories || []).map((s) => ({
      id: s.id,
      seq: s.seq,
      title: s.title,
      desc: s.desc,
      scene: s.scene,
      acceptance: s.acceptance && s.acceptance.length ? s.acceptance : [''],
      rules: s.rules && s.rules.length ? s.rules : [],
      finalized: s.finalized,
    }))
  } catch (err) {
    stories.value = []
  }
}

async function saveStories() {
  try {
    const payload = stories.value.map((s, idx) => ({
      seq: s.seq || idx + 1,
      title: s.title,
      desc: s.desc,
      scene: s.scene,
      acceptance: s.acceptance || [],
      rules: s.rules || [],
      finalized: s.finalized,
    }))
    await saveUserStories(current.value.req_id, payload)
    ElMessage.success('用户故事已保存')
  } catch (err) {
    ElMessage.error('保存失败')
  }
}

async function saveClarification() {
  try {
    await updateRequirement(current.value.req_id, { clarification: clarification.value })
    current.value.clarification = clarification.value
    ElMessage.success('澄清内容已保存')
  } catch (err) {
    ElMessage.error('保存失败')
  }
}

async function saveDetail() {
  try {
    const payload = {
      req_name: current.value.req_name,
      system_name: current.value.system_name,
      sa_name: current.value.sa_name,
      priority: current.value.priority,
      status: current.value.status,
      version_required_date: current.value.version_required_date || null,
      dev_ticket_no: current.value.dev_ticket_no || '',
      owner_note: current.value.owner_note,
      tags: current.value.tags,
      personal_note: current.value.personal_note,
      background: current.value.background,
      description: current.value.description,
    }
    await updateRequirement(current.value.req_id, payload)
    ElMessage.success('需求信息已保存')
    await refreshCurrent(current.value.req_id)
  } catch (err) {
    ElMessage.error('保存失败')
  }
}

/* 附件（真实端点：上传 / 下载 / 删除） */
const fileInput = ref(null)
function triggerUpload() {
  fileInput.value?.click()
}
async function handleFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    await uploadRequirementAttachment(current.value.req_id, file)
    const list = await listRequirementAttachments(current.value.req_id)
    attachments.value = list || []
    ElMessage.success(`已上传：${file.name}`)
  } catch (err) {
    ElMessage.error('上传失败')
  } finally {
    e.target.value = ''
  }
}
function downloadAttachment(f) {
  const url = `/api/v1/requirements/${current.value.req_id}/delivery/attachments/download?filename=${encodeURIComponent(f.name)}`
  window.open(url, '_blank')
}
function openGen(g) {
  if (g.url) window.open(g.url)
}
async function removeAttachment(f) {
  try {
    await deleteRequirementAttachment(current.value.req_id, f.name)
    attachments.value = attachments.value.filter((x) => x.name !== f.name)
    ElMessage.success('已删除')
  } catch (err) {
    ElMessage.error('删除失败')
  }
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

/* 用户故事（真实端点：基于 DDD 生成固定 4 段模板，落库） */
function addStory() {
  stories.value.push({ title: '', desc: '', scene: '', acceptance: [''], rules: [], finalized: false })
}
async function generateStories() {
  if (!clarification.value.trim()) {
    ElMessage.warning('请先填写澄清后需求内容')
    return
  }
  try {
    const res = await generateUserStories(current.value.req_id, clarification.value)
    dddView.value = res.ddd || dddView.value
    stories.value = (res.stories || []).map((s) => ({
      id: s.id,
      seq: s.seq,
      title: s.title,
      desc: s.desc,
      scene: s.scene,
      acceptance: s.acceptance && s.acceptance.length ? s.acceptance : [''],
      rules: s.rules && s.rules.length ? s.rules : [],
      finalized: false,
    }))
    ElMessage.success(`已基于工作量(约20人天/故事)生成 ${stories.value.length} 条用户故事并落库`)
  } catch (err) {
    ElMessage.error('生成失败，请重试')
  }
}

/* 文档生成（真实端点：按固定模板生成 docx 并落盘） */
async function generateDoc() {
  if (!stories.value.length) {
    ElMessage.warning('请先生成用户故事')
    return
  }
  try {
    const res = await generateRequirementDoc(
      current.value.req_id,
      stories.value.map((s) => ({ title: s.title, desc: s.desc, scene: s.scene, acceptance: s.acceptance, rules: s.rules || [], seq: s.seq })),
      clarification.value,
    )
    genHistory.value.unshift({
      file: res.file,
      path: res.path,
      time: new Date().toLocaleString('zh-CN'),
      url: res.url,
    })
    cacheLocal()
    ElMessage.success(`已生成并归档：${res.file}`)
    // 刷新附件列表（说明书包归档在 doc 目录，这里仅提示路径）
  } catch (err) {
    ElMessage.error('生成失败，请重试')
  }
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
.wf-steps { display: flex; align-items: center; padding: 18px 24px; border-bottom: 1px solid var(--border-subtle); gap: 8px }
.pm-step { display: flex; align-items: center; gap: 8px; cursor: pointer; flex: 1; min-width: 0 }
.pm-step-dot { width: 26px; height: 26px; border-radius: 50%; background: var(--bg-app); border: 2px solid var(--border); color: var(--text-secondary); font-size: 12px; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0 }
.pm-step.active .pm-step-dot { background: var(--accent); border-color: var(--accent); color: #fff }
.pm-step.done .pm-step-dot { background: var(--success); border-color: var(--success); color: #fff }
.pm-step-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); white-space: nowrap }
.pm-step.active .pm-step-label { color: var(--accent) }
.pm-step-line { flex: 1; height: 2px; background: var(--border-subtle); margin: 0 10px; min-width: 20px }
.pm-step-line.done { background: var(--success) }
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
.story-seq { font-size: 11px; font-weight: 700; color: var(--accent); background: var(--accent-soft); border-radius: 6px; padding: 2px 8px; flex-shrink: 0; white-space: nowrap }
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
