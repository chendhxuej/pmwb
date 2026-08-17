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
            <EnlargeInput
              v-model="reqKeyword"
              placeholder="搜索需求编号 / 名称 / 提出人"
              class="w-m"
              clearable
              @keyup.enter="handleReqSearch"
              @clear="handleReqSearch"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </EnlargeInput>
            <el-select v-model="reqStatus" placeholder="跟踪状态" clearable class="w-s" @change="handleReqSearch">
              <el-option label="建议中" value="proposed" />
              <el-option label="已采纳" value="accepted" />
              <el-option label="开发中" value="dev" />
              <el-option label="已上线" value="closed" />
              <el-option label="暂停" value="paused" />
            </el-select>
            <el-select v-model="reqPriority" placeholder="优先级" clearable class="w-xs" @change="handleReqSearch">
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
                <StatusBadge module="requirement_delivery" :value="row.ext?.status" />
              </template>
            </el-table-column>
            <el-table-column label="工作量(人天)" width="110" align="center">
              <template #default="{ row }">
                <span class="font-mono">{{ row.eval_workload != null ? row.eval_workload : '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="dev_ticket_no" label="开发单号" width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="170" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openReqDialog(row)">编辑</el-button>
                <el-dropdown @command="(cmd) => openSupervise(row, cmd)">
                  <el-button link type="warning" size="small">督办<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="urge">催办</el-dropdown-item>
                      <el-dropdown-item command="sync">同步通知</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
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

      <!-- ════════ 用户故事标签（全局检索） ════════ -->
      <el-tab-pane label="用户故事" name="story">
        <div class="pm-table-wrap">
          <div class="table-toolbar">
            <EnlargeInput
              v-model="usKeyword"
              placeholder="模糊搜索：标题 / 描述 / 场景 / 验收标准 / 业务规则 / 需求编号 / 需求名称（空格分词）"
              class="w-xl"
              clearable
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </EnlargeInput>
            <el-select v-model="usFinalized" placeholder="定稿状态" clearable class="w-s" @change="handleStorySearch">
              <el-option label="全部" value="" />
              <el-option label="草稿" :value="0" />
              <el-option label="已定稿" :value="1" />
            </el-select>
            <el-button @click="loadStorySearch"><el-icon><Refresh /></el-icon> 刷新</el-button>
            <span class="text-muted" style="margin-left:auto;font-size:12px">默认全局展示，按创建时间倒序</span>
          </div>
          <el-table
            v-loading="usLoading"
            :data="usList"
            stripe
            scrollbar-always-on
            @row-click="openStoryDetail"
          >
            <el-table-column prop="req_id" label="需求编号" width="140" show-overflow-tooltip />
            <el-table-column prop="req_name" label="需求名称" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ row.req_name || '（未命名）' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="seq" label="序号" width="64" align="center">
              <template #default="{ row }"><span class="story-seq">US{{ row.seq }}</span></template>
            </el-table-column>
            <el-table-column prop="title" label="故事标题" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="link-text">{{ row.title || '（无标题）' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="desc" label="故事描述" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="text-muted">{{ row.desc || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="定稿状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.finalized ? 'success' : 'info'">{{ row.finalized ? '已定稿' : '草稿' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="150" align="center">
              <template #default="{ row }">
                <span class="text-muted">{{ formatDateTime(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openStoryDetail(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="table-footer">
            <span class="text-muted">共 {{ usTotal }} 条</span>
            <el-pagination
              v-model:current-page="usPage"
              v-model:page-size="usPageSize"
              :total="usTotal"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              small
              background
              @size-change="loadStorySearch"
              @current-change="loadStorySearch"
            />
          </div>
        </div>
      </el-tab-pane>

      <!-- ════════ 开发工单标签 ════════ -->
      <el-tab-pane label="开发工单" name="ticket">
        <div class="pm-table-wrap">
          <div class="table-toolbar">
            <EnlargeInput v-model="ticketKeyword" placeholder="搜索工单号 / 系统 / 开发团队" class="w-m" clearable @keyup.enter="handleTicketSearch" @clear="handleTicketSearch">
              <template #prefix><el-icon><Search /></el-icon></template>
            </EnlargeInput>
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
              <template #default="{ row }"><StatusBadge module="requirement_version" :value="row.status" /></template>
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

    <!-- 统一邮件弹窗（督办：催办 / 同步通知） -->
    <MailComposeDialog
      v-model="mailDialogVisible"
      :title="mailDialogTitle"
      :default-to="mailDialogTo"
      :default-subject="mailDialogSubject"
      :default-body="mailDialogBody"
      :scene="mailDialogScene"
      :variables="mailDialogVariables"
      value-key="email"
    />

    <!-- ════════ 4步工作流抽屉 ════════ -->
    <el-drawer v-model="wfVisible" size="70%" :title="null" destroy-on-close>
      <template #header>
        <div class="wf-head">
          <div>
            <div class="wf-req-id font-mono">{{ current.req_id }}</div>
            <div class="wf-req-name">{{ current.req_name || '（未命名需求）' }}</div>
          </div>
          <div class="flex gap-8">
            <StatusBadge module="requirement_delivery" :value="current.ext?.status" />
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
                      <el-form-item label="需求名称"><EnlargeInput v-model="current.req_name" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="涉及系统"><EnlargeInput v-model="current.system_name" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="评估 SA"><EnlargeInput v-model="current.sa_name" /></el-form-item>
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
                          <el-option label="开发中" value="dev" /><el-option label="已上线" value="closed" />
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
                      <el-form-item label="实际上线日">
                        <el-date-picker v-model="current.delivered_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="需求实际交付/上线日期" />
                      </el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="开发单号">
                        <EnlargeInput v-model="current.dev_ticket_no" placeholder="需求级开发单号，如 DEV-2026-001" />
                      </el-form-item>
                    </div>
                    <div style="grid-column: span 12">
                      <el-form-item label="负责人备忘"><EnlargeInput v-model="current.owner_note" type="textarea" :rows="2" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="个人标签"><EnlargeInput v-model="current.tags" placeholder="逗号分隔" /></el-form-item>
                    </div>
                    <div style="grid-column: span 6">
                      <el-form-item label="个人备注"><EnlargeInput v-model="current.personal_note" type="textarea" :rows="2" /></el-form-item>
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
                  <div v-if="!attachments.length" class="empty-hint">暂无文件，可上传附件或生成说明书</div>
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
                <EnlargeInput v-model="current.background" type="textarea" :rows="4" placeholder="可覆盖原始背景…" />
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
                <span class="card-label">原始需求描述</span>
                <el-button size="small" type="primary" @click="saveDetail">保存</el-button>
              </div>
              <div class="card-body">
                <EnlargeInput v-model="current.description" type="textarea" :rows="4" placeholder="可覆盖原始描述…" />
              </div>
            </div>

            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
                <span class="card-label">澄清后需求内容（用于生成用户故事）</span>
                <el-button size="small" type="primary" @click="saveClarification">保存澄清</el-button>
              </div>
              <div class="card-body">
                <EnlargeInput
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
                <EnlargeInput v-model="clarification" type="textarea" :rows="10" placeholder="在此梳理、澄清需求内容，作为用户故事生成的输入…" />
              </div>

              <!-- 生成策略选择器 -->
              <div class="card-header" style="border-top:1px solid var(--border-subtle);padding-top:16px">
                <span class="card-label">生成策略</span>
                <span v-if="llmChecking" style="font-size:11px;color:var(--text-muted)">检测中…</span>
              </div>
              <div class="card-body">
                <div class="strategy-selector">
                  <div
                    class="strategy-card"
                    :class="{ active: selectedStrategy === 'rules_v2' }"
                    @click="selectedStrategy = 'rules_v2'"
                  >
                    <div class="sc-icon sc-icon-merge">⚡</div>
                    <div class="sc-body">
                      <div class="sc-title">合并生成 <span class="sc-badge">推荐</span></div>
                      <div class="sc-desc">同角色同场景自动合并，秒级出结果</div>
                    </div>
                    <div class="sc-check" v-if="selectedStrategy === 'rules_v2'">✓</div>
                  </div>

                  <div
                    class="strategy-card"
                    :class="{
                      active: selectedStrategy === 'llm',
                      disabled: !llmStatus.reachable,
                    }"
                    @click="llmStatus.reachable && (selectedStrategy = 'llm')"
                  >
                    <div class="sc-icon sc-icon-ai">🤖</div>
                    <div class="sc-body">
                      <div class="sc-title">
                        Kimi 智能拆分
                        <span v-if="llmChecking" class="sc-badge sc-badge-info">检测中</span>
                        <span v-else-if="!llmStatus.enabled" class="sc-badge sc-badge-off">未配置</span>
                        <span v-else-if="llmStatus.reachable" class="sc-badge sc-badge-on">已连接</span>
                        <span v-else class="sc-badge sc-badge-off">API 不可用</span>
                      </div>
                      <div class="sc-desc">
                        AI 理解角色/场景/闭环，约 30 秒
                      </div>
                      <div
                        v-if="!llmChecking && llmStatus.enabled && !llmStatus.reachable && llmStatus.error"
                        class="sc-error"
                        :title="llmStatus.error"
                      >⚠ {{ llmErrorHint }}</div>
                    </div>
                    <div class="sc-check" v-if="selectedStrategy === 'llm'">✓</div>
                  </div>

                  <div
                    class="strategy-card"
                    :class="{ active: selectedStrategy === 'rules_v1' }"
                    @click="selectedStrategy = 'rules_v1'"
                  >
                    <div class="sc-icon sc-icon-old">📐</div>
                    <div class="sc-body">
                      <div class="sc-title">按工作量拆分 <span class="sc-badge sc-badge-old">旧版</span></div>
                      <div class="sc-desc">按人天机械拆分，不推荐新需求使用</div>
                    </div>
                    <div class="sc-check" v-if="selectedStrategy === 'rules_v1'">✓</div>
                  </div>
                </div>

                <div
                  v-if="!llmChecking && llmStatus.enabled && !llmStatus.reachable"
                  class="strategy-warn"
                >
                  <span class="sw-icon">⚠️</span>
                  <span>Kimi 暂时不可用{{ llmStatus.error ? '：' + llmErrorHint : '' }}。可改用「合并生成」秒级出结果，或前往「大模型管理」配置可用的 API Key。</span>
                </div>

                <el-button
                  class="mt-12 w-full"
                  type="primary"
                  :loading="storyGenLoading"
                  :disabled="!clarification.trim()"
                  @click="generateStories(selectedStrategy)"
                >
                  <template v-if="storyGenLoading">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    {{ selectedStrategy === 'llm' ? `Kimi 正在分析需求… ${storyGenElapsed}s` : `正在生成… ${storyGenElapsed}s` }}
                  </template>
                  <template v-else>
                    <el-icon><MagicStick /></el-icon>
                    {{ selectedStrategy === 'llm' ? 'Kimi 智能生成用户故事' : selectedStrategy === 'rules_v1' ? '按工作量生成用户故事' : '生成用户故事' }}
                  </template>
                </el-button>
              </div>

              <div class="card-header" style="border-top:1px solid var(--border-subtle);padding-top:16px"><span class="card-label">DDD 领域视角</span></div>
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
                <span class="card-label">用户故事</span>
                <span v-if="strategyLabel" class="pm-tag gray ml-8" style="font-size: 11px">{{ strategyLabel }} · {{ stories.length }} 条</span>
                <div class="flex gap-8" style="margin-left:auto">
                  <template v-if="stories.length && !storiesConfirmed">
                    <el-badge :value="stories.length" :max="99" class="confirm-badge">
                      <el-button size="small" type="success" @click="confirmStories">
                        <el-icon><CircleCheck /></el-icon> 确认落库
                      </el-button>
                    </el-badge>
                  </template>
                  <template v-else-if="storiesConfirmed">
                    <el-tag type="success" size="small" effect="plain">✓ 已保存 {{ stories.length }} 条</el-tag>
                  </template>
                  <el-button size="small" @click="addStory"><el-icon><Plus /></el-icon> 新增</el-button>
                </div>
              </div>
              <div class="card-body">

                <!-- 生成中遮罩 -->
                <div v-if="storyGenLoading" class="story-loading-overlay">
                  <el-icon class="is-loading" :size="28"><Loading /></el-icon>
                  <p>{{ selectedStrategy === 'llm' ? 'Kimi 正在分析需求内容，识别角色/场景/闭环…' : '正在生成用户故事…' }}</p>
                  <p class="story-loading-hint">{{ selectedStrategy === 'llm' ? 'Kimi 带推理能力，通常需要 20-40 秒，请耐心等待' : '预计 1-3 秒完成' }}</p>
                </div>

                <!-- 未生成提示 -->
                <div v-if="!storyGenLoading && !stories.length && !storiesConfirmed" class="story-empty">
                  <p>👈 在左侧填写澄清内容，选择生成策略后点击「生成用户故事」</p>
                </div>

                <!-- 待确认提示条 -->
                <div v-if="!storyGenLoading && stories.length && !storiesConfirmed" class="story-pending-bar">
                  ⚠️ 已生成 <b>{{ stories.length }}</b> 条用户故事，请预览确认后点击右上角「确认落库」保存到数据库
                </div>
                <div v-if="!storyGenLoading" v-for="(st, i) in stories" :key="i" class="story-card" :class="{ finalized: st.finalized }">
                  <div class="story-head">
                    <span class="story-seq">US{{ i + 1 }}</span>
                    <EnlargeInput v-model="st.title" class="story-title-enlarge" placeholder="故事标题" />
                    <el-switch v-model="st.finalized" active-text="已定稿" inactive-text="草稿" />
                    <el-button link type="danger" size="small" @click="stories.splice(i, 1)">删除</el-button>
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">故事描述</span>
                    <EnlargeInput v-model="st.desc" type="textarea" :autosize="{ minRows: 3, maxRows: 14 }" placeholder="作为…，我想要…，以便…" />
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">故事场景</span>
                    <EnlargeInput v-model="st.scene" type="textarea" :autosize="{ minRows: 3, maxRows: 14 }" placeholder="典型使用场景…" />
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">验收标准</span>
                    <div class="ac-list">
                      <div v-for="(ac, ai) in st.acceptance" :key="ai" class="ac-row">
                        <EnlargeInput v-model="st.acceptance[ai]" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }" placeholder="验证***功能是否成功实现" />
                        <el-button link type="danger" size="small" @click="st.acceptance.splice(ai, 1)">×</el-button>
                      </div>
                      <el-button size="small" link type="primary" @click="st.acceptance.push('')">+ 新增验收标准</el-button>
                    </div>
                  </div>
                  <div class="story-field">
                    <span class="story-field-label">业务规则（每条一栏，可空，生成文档时每种子下将落规则表）</span>
                    <el-button
                      size="small"
                      link
                      type="primary"
                      :disabled="!st.id || !(st.rules || []).length"
                      :loading="st._sed"
                      @click="sedimentStoryRules(st)"
                    >沉淀业务规则到主笔记</el-button>
                    <div class="ac-list">
                      <div v-for="(r, ri) in (st.rules || [])" :key="ri" class="ac-row">
                        <EnlargeInput v-model="st.rules[ri]" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }" placeholder="提炼本故事的业务规则…" />
                        <el-button link type="danger" size="small" @click="st.rules.splice(ri, 1)">×</el-button>
                      </div>
                      <el-button size="small" link type="primary" @click="(st.rules || (st.rules = [])).push('')">+ 新增业务规则</el-button>
                    </div>
                  </div>
                </div>
                <div v-if="!stories.length" class="text-muted" style="padding: 16px 0">点击上方「合并生成」基于澄清内容自动产出用户故事（预览模式，需确认后落库）。</div>
                <div v-else-if="!storiesConfirmed" class="text-muted" style="padding: 8px 16px; background: #fff8e1; border-radius: 4px; margin-top: 8px">
                  ⚠ 用户故事已生成但尚未确认落库，请预览内容无误后点击「确认落库」保存。
                </div>
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
                <EnlargeInput v-model="docFileName" placeholder="需求分析说明书" />
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
                <div v-if="!genHistory.length" class="empty-hint">暂无生成记录</div>
              </div>
            </div>
          </div>
        </div>

        <!-- ───── 知识沉淀 ───── -->
        <div class="wf-step-panel" v-if="current.req_id">
          <div class="bento-grid">
            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
                <span class="card-label">知识沉淀与业务知识关联</span>
                <div class="flex gap-8">
                  <el-button
                    v-if="isRequirementClosed(current)"
                    size="small"
                    :type="current.ext?.manual_archived ? 'info' : 'success'"
                    :loading="archiving"
                    @click="archiveManual(current)"
                  >{{ current.ext?.manual_archived ? '已归档操作手册' : '归档操作手册到业务知识' }}</el-button>
                  <el-button size="small" type="primary" :loading="sedimenting" @click="sedimentRequirement">
                    沉淀需求为知识笔记
                  </el-button>
                </div>
              </div>
              <div class="card-body">
                <el-form label-width="84px" label-position="left" class="mb-12">
                  <el-form-item label="业务领域">
                    <BusinessDomainSelect v-model="domainCode" @change="saveDomainCode" />
                  </el-form-item>
                </el-form>
                <KnowledgeLinker
                  source-type="requirement"
                  :source-id="current.req_id"
                  :domain-code="current.ext?.domain_code"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- ════════ 用户故事只读详情抽屉 ════════ -->
    <el-drawer v-model="usDetailVisible" size="70%" :title="null" destroy-on-close>
      <template #header>
        <div class="wf-head">
          <div>
            <div class="wf-req-id font-mono">{{ usDetail.req_id }} · US{{ usDetail.seq }}</div>
            <div class="wf-req-name">{{ usDetail.req_name || '（未命名需求）' }}</div>
          </div>
          <div class="flex gap-8">
            <el-tag size="small" :type="usDetail.finalized ? 'success' : 'info'">{{ usDetail.finalized ? '已定稿' : '草稿' }}</el-tag>
            <el-button size="small" type="primary" @click="openSourceRequirement(usDetail)">
              <el-icon><TopRight /></el-icon> 跳转原需求
            </el-button>
          </div>
        </div>
      </template>
      <div class="us-detail">
        <div class="us-block">
          <div class="us-label">故事标题</div>
          <div class="us-value" v-html="highlight(usDetail.title)"></div>
        </div>
        <div class="us-block">
          <div class="us-label">故事描述</div>
          <div class="us-value pre" v-html="highlight(usDetail.desc)"></div>
        </div>
        <div class="us-block">
          <div class="us-label">故事场景</div>
          <div class="us-value pre" v-html="highlight(usDetail.scene)"></div>
        </div>
        <div class="us-block">
          <div class="us-label">验收标准</div>
          <ol v-if="(usDetail.acceptance || []).length" class="us-ol">
            <li v-for="(ac, i) in usDetail.acceptance" :key="i" v-html="highlight(ac)"></li>
          </ol>
          <div v-else class="text-muted">—</div>
        </div>
        <div class="us-block">
          <div class="us-label">业务规则</div>
          <ol v-if="(usDetail.rules || []).length" class="us-ol">
            <li v-for="(r, i) in usDetail.rules" :key="i" v-html="highlight(r)"></li>
          </ol>
          <div v-else class="text-muted">—</div>
        </div>
        <div class="us-block">
          <div class="us-label">创建时间</div>
          <div class="us-value">{{ formatDateTime(usDetail.created_at) }}</div>
        </div>
        <div class="hint-text">此处为只读视图；如需修改，请点「跳转原需求」在需求工作流的「用户故事」步中编辑。</div>
      </div>
    </el-drawer>

    <!-- 团队评估弹层 -->
    <el-dialog v-model="evalDialog" :title="evalForm.id ? '编辑系统评估' : '新增系统评估'" width="520px">
      <el-form :model="evalForm" label-width="110px">
        <el-form-item label="涉及系统"><EnlargeInput v-model="evalForm.system_name" placeholder="如：生产运营平台" /></el-form-item>
        <el-form-item label="SA 负责人"><StaffSelect v-model="evalForm.sa_name" placeholder="如：戴晓飞" /></el-form-item>
        <el-form-item label="工作量(人天)"><el-input-number v-model="evalForm.workload" :min="0" :step="0.5" style="width:100%" /></el-form-item>
        <el-form-item label="复核工作量(人天)"><el-input-number v-model="evalForm.review_workload" :min="0" :step="0.5" style="width:100%" /></el-form-item>
        <el-form-item label="评估意见"><EnlargeInput v-model="evalForm.opinion" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="开发单号"><EnlargeInput v-model="evalForm.dev_ticket_no" placeholder="可选" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="evalDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEval">保存</el-button>
      </template>
    </el-dialog>

    <!-- 需求编辑弹层 -->
    <el-dialog v-model="reqDialog" title="编辑需求跟踪信息" width="560px">
      <el-form :model="reqForm" label-width="110px">
        <el-form-item label="需求名称"><EnlargeInput v-model="reqForm.req_name" placeholder="覆盖 sent_emails 原始名称" /></el-form-item>
        <el-form-item label="涉及系统"><EnlargeInput v-model="reqForm.system_name" placeholder="覆盖原始系统" /></el-form-item>
        <el-form-item label="SA"><StaffSelect v-model="reqForm.sa_name" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="reqForm.priority" style="width:100%">
            <el-option label="P0" value="P0" /><el-option label="P1" value="P1" />
            <el-option label="P2" value="P2" /><el-option label="P3" value="P3" />
          </el-select>
        </el-form-item>
        <el-form-item label="跟踪状态">
          <el-select v-model="reqForm.status" style="width:100%">
            <el-option label="建议中" value="proposed" /><el-option label="已采纳" value="accepted" />
            <el-option label="开发中" value="dev" /><el-option label="已上线" value="closed" />
            <el-option label="暂停" value="paused" />
          </el-select>
        </el-form-item>
        <el-form-item label="期望版本日"><el-date-picker v-model="reqForm.version_required_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="选择日期" /></el-form-item>
        <el-form-item label="实际上线日"><el-date-picker v-model="reqForm.delivered_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="需求实际交付/上线日期" /></el-form-item>
        <el-form-item label="需求背景"><EnlargeInput v-model="reqForm.background" type="textarea" :rows="3" placeholder="覆盖原始背景" /></el-form-item>
        <el-form-item label="需求描述"><EnlargeInput v-model="reqForm.description" type="textarea" :rows="3" placeholder="覆盖原始描述" /></el-form-item>
        <el-form-item label="澄清内容"><EnlargeInput v-model="reqForm.clarification" type="textarea" :rows="3" placeholder="经评审后的澄清内容" /></el-form-item>
        <el-form-item label="负责人备忘"><EnlargeInput v-model="reqForm.owner_note" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="个人标签"><EnlargeInput v-model="reqForm.tags" placeholder="逗号分隔" /></el-form-item>
        <el-form-item label="个人备注"><EnlargeInput v-model="reqForm.personal_note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reqDialog = false">取消</el-button>
        <el-button type="primary" @click="saveReq">保存</el-button>
      </template>
    </el-dialog>

    <!-- 开发工单弹层 -->
    <el-dialog v-model="ticketDialog" :title="ticketForm.id ? '编辑开发工单' : '新增开发工单'" width="560px">
      <el-form :model="ticketForm" label-width="110px">
        <el-form-item label="工单号"><EnlargeInput v-model="ticketForm.ticket_no" :disabled="!!ticketForm.id" placeholder="如：DEV-2026-0718" /></el-form-item>
        <el-form-item label="关联需求"><EnlargeInput v-model="ticketForm.req_id" placeholder="需求编号" /></el-form-item>
        <el-form-item label="涉及系统"><EnlargeInput v-model="ticketForm.system_name" /></el-form-item>
        <el-form-item label="开发团队"><EnlargeInput v-model="ticketForm.dev_team" /></el-form-item>
        <el-form-item label="开发负责人"><StaffSelect v-model="ticketForm.developer" /></el-form-item>
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
        <el-form-item label="上线时间"><el-date-picker v-model="ticketForm.go_live_date" type="date" value-format="YYYY-MM-DD" placeholder="实际上线/计划上线日期" style="width:100%" /></el-form-item>
        <el-form-item label="进度"><el-slider v-model="ticketForm.progress" :step="5" show-input /></el-form-item>
        <el-form-item label="描述"><EnlargeInput v-model="ticketForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ticketDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTicket">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDate, formatDateTime } from '@/utils/format'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import KnowledgeLinker from '@/components/Common/KnowledgeLinker.vue'
import BusinessDomainSelect from '@/components/Common/BusinessDomainSelect.vue'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api/knowledge.js'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import {
  getRequirements, getRequirement, updateRequirement, deleteRequirement,
  getEvaluations, createEvaluation, updateEvaluation, deleteEvaluation,
  initRequirementFolder, listRequirementAttachments, uploadRequirementAttachment,
  deleteRequirementAttachment, generateUserStories, getUserStories, saveUserStories,
  generateRequirementDoc, searchUserStories, getLlmStatus,
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
  delivered_date: '',
  dev_ticket_no: '',
  background: '',
  description: '',
  clarification: '',
  owner_note: '',
  tags: '',
  personal_note: '',
})
// ---- 统一邮件弹窗（督办：催办 / 同步通知，走 MailComposeDialog 统一组件） ----
const mailDialogVisible = ref(false)
const mailDialogTitle = ref('发送督办邮件')
const mailDialogTo = ref([])
const mailDialogSubject = ref('')
const mailDialogBody = ref('')
const mailDialogScene = ref('supervise_urge')
// T-E：supervise_urge/sync 模板变量（复用工单 7 变量：no/title/category/handler/resolveDate/status/description）
const mailDialogVariables = ref({})

function buildReqSuperviseBody(row, scene = 'urge') {
  return [
    scene === 'urge' ? '## 需求催办通知' : '## 需求进展同步',
    '',
    '| 字段 | 内容 |',
    '|------|------|',
    `| 需求编号 | ${row.req_id || ''} |`,
    `| 需求名称 | ${row.req_name || row.title || ''} |`,
    `| SA | ${row.sa_name || ''} |`,
    `| 负责人 | ${row.owner || ''} |`,
    `| 优先级 | ${row.ext?.priority || 'P2'} |`,
    `| 当前状态 | ${row.ext?.status || ''} |`,
    `| 期望上线月份 | ${row.ext?.version_required_date || ''} |`,
    '',
    '### 需求描述',
    row.description || row.background || '（无）',
    '',
    '---',
    scene === 'urge'
      ? '请尽快评估/处理该需求，如有疑问请及时沟通。'
      : '请知悉该需求最新进展，如有疑问请及时沟通。',
  ].join('\n')
}

function openSupervise(row, scene = 'urge') {
  if (!row) return
  mailDialogTitle.value = scene === 'urge' ? '发送催办邮件' : '发送同步通知'
  mailDialogTo.value = String(row.sa_name || row.owner || row.proposer || '').split(',').filter(Boolean)
  mailDialogSubject.value = (scene === 'urge' ? '催办：' : '同步：') + (row.req_name || row.req_id || '')
  // T-E：模板变量——正文由 3210 supervise_urge/sync 模板渲染，字段按需求语义映射
  mailDialogVariables.value = {
    no: row.req_id || '',
    title: row.req_name || row.title || '',
    category: row.system_name || '需求',
    handler: row.owner || row.sa_name || '',
    resolveDate: row.ext?.version_required_date || row.ext?.delivered_date || '',
    status: row.ext?.status || row.status || '',
    description: row.description || row.background || '（无）',
  }
  mailDialogBody.value = buildReqSuperviseBody(row, scene)
  mailDialogScene.value = scene === 'sync' ? 'supervise_sync' : 'supervise_urge'
  mailDialogVisible.value = true
}

function openReqDialog(row) {
  Object.assign(reqForm, {
    req_id: row.req_id,
    req_name: row.req_name || '',
    system_name: row.system_name || '',
    sa_name: row.sa_name || '',
    priority: row.ext?.priority || 'P2',
    status: row.ext?.status || 'proposed',
    version_required_date: row.ext?.version_required_date || '',
    delivered_date: row.ext?.delivered_date || '',
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
      current.value.delivered_date = res.ext?.delivered_date || ''
      current.value.dev_ticket_no = res.dev_ticket_no || ''
      current.value.owner_note = res.ext?.owner_note || ''
      current.value.tags = res.ext?.tags || ''
      current.value.personal_note = res.ext?.personal_note || ''
    }
  } catch (e) { /* ignore */ }
}

/* ─────────────── 用户故事标签（全局检索） ─────────────── */
const usKeyword = ref('')
const usFinalized = ref('')
const usLoading = ref(false)
const usList = ref([])
const usTotal = ref(0)
const usPage = ref(1)
const usPageSize = ref(20)
let usDebounce = null

async function loadStorySearch() {
  usLoading.value = true
  try {
    const res = await searchUserStories({
      keyword: usKeyword.value.trim(),
      finalized: usFinalized.value,
      page: usPage.value,
      pageSize: usPageSize.value,
    })
    usList.value = res.items || []
    usTotal.value = res.total || 0
  } finally {
    usLoading.value = false
  }
}

function handleStorySearch() {
  usPage.value = 1
  loadStorySearch()
}

// 输入即查（防抖 300ms）
watch(usKeyword, () => {
  if (usDebounce) clearTimeout(usDebounce)
  usDebounce = setTimeout(() => {
    usPage.value = 1
    loadStorySearch()
  }, 300)
})

// 首次进入用户故事标签时懒加载
watch(activeTab, (v) => {
  if (v === 'story' && !usList.value.length && !usLoading.value) {
    loadStorySearch()
  }
})

/* 用户故事只读详情 */
const usDetailVisible = ref(false)
const usDetail = ref({})
function openStoryDetail(row) {
  usDetail.value = { ...row }
  usDetailVisible.value = true
}

// 高亮命中关键词（先转义 HTML，再包裹 <mark>）
function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
function highlight(text) {
  const safe = escapeHtml(text)
  const words = usKeyword.value.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return safe
  const escapeReg = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${words.map(escapeReg).join('|')})`, 'gi')
  return safe.replace(re, '<mark class="us-hl">$1</mark>')
}

// 跳转原需求（打开工作流并定位到「用户故事」步）
async function openSourceRequirement(row) {
  try {
    const res = await getRequirement(row.req_id)
    if (!res) {
      ElMessage.warning('未找到原需求记录')
      return
    }
    usDetailVisible.value = false
    await openWorkflow(res)
    step.value = 'story'
  } catch (e) {
    ElMessage.error('跳转失败')
  }
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
const domainCode = ref('')
watch(current, (c) => { domainCode.value = c?.ext?.domain_code || '' }, { immediate: true })
async function saveDomainCode() {
  if (!current.value.req_id) return
  try {
    await updateRequirement(current.value.req_id, { domain_code: domainCode.value || null })
    if (current.value.ext) current.value.ext.domain_code = domainCode.value
    ElMessage.success('业务领域已保存')
  } catch (e) {
    ElMessage.error('保存业务领域失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}
const clarification = ref('')
const attachments = ref([])
const evaluations = ref([])
const evalLoading = ref(false)
const stories = ref([])
const strategyLabel = ref('')
const storiesConfirmed = ref(false)
const llmStatus = ref({ enabled: false, provider: '', model: '', reachable: false, error: null })
const llmChecking = ref(false)
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
  current.value.delivered_date = row.ext?.delivered_date || ''
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
    storiesConfirmed.value = stories.value.length > 0
  } catch (err) {
    stories.value = []
    storiesConfirmed.value = false
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

/* 沉淀需求为知识笔记 */
const sedimenting = ref(false)
async function sedimentRequirement() {
  if (!current.value.req_id) return
  sedimenting.value = true
  try {
    const res = await knowledgeApi.sedimentRequirement(current.value.req_id, true)
    ElMessage.success('需求已沉淀为知识笔记：' + (res.obsidian_path || ''))
  } catch (e) {
    ElMessage.error('沉淀失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    sedimenting.value = false
  }
}

/* kc-2-3：操作手册归档 + 规则沉淀状态判定 */
const archiving = ref(false)
function isRequirementClosed(req) {
  return (req?.ext?.status || req?.status) === 'closed'
}
async function archiveManual(req) {
  if (!req?.req_id) return
  archiving.value = true
  try {
    const res = await knowledgeApi.archiveRequirementManual(req.req_id)
    const data = res?.data || {}
    const n = data.archived?.length || 0
    ElMessage.success(`操作手册已归档 ${n} 个${data.main_note ? '，主笔记：' + data.main_note : ''}`)
    await refreshCurrent(req.req_id)
  } catch (e) {
    ElMessage.error('归档失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    archiving.value = false
  }
}


/* 沉淀用户故事业务规则到对应领域主笔记的「场景规则」子笔记 */
async function sedimentStoryRules(st) {
  if (!current.value?.req_id) {
    ElMessage.warning('请先确认落库用户故事再沉淀')
    return
  }
  if (!st.rules || !st.rules.length) {
    ElMessage.warning('该故事暂无业务规则可沉淀')
    return
  }
  st._sed = true
  try {
    await knowledgeApi.sedimentRequirementRules(current.value.req_id)
    ElMessage.success('用户故事业务规则已沉淀到对应领域主笔记的「场景规则」子笔记')
  } catch (e) {
    ElMessage.error('沉淀失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    st._sed = false
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
      delivered_date: current.value.delivered_date || null,
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

/* 用户故事生成 */
const selectedStrategy = ref('rules_v2')         // 当前选中的策略
const storyGenLoading = ref(false)                // 生成中
const storyGenElapsed = ref(0)                    // 已耗时（秒）
let _storyGenTimer = null                         // 耗时计时器

const llmProviderLabel = computed(() => {
  const p = llmStatus.value.provider
  const map = { kimi: 'Kimi', ollama: 'Ollama', openai: 'OpenAI', deepseek: 'DeepSeek' }
  return map[p] || p || 'AI'
})
async function checkLlmStatus() {
  llmChecking.value = true
  try {
    const res = await getLlmStatus()
    llmStatus.value = res
  } catch {
    llmStatus.value = { enabled: false, provider: '', model: '', reachable: false, error: null }
  } finally {
    llmChecking.value = false
  }
}
const llmErrorHint = computed(() => {
  const e = llmStatus.value.error || ''
  if (!e) return ''
  // 去掉超长英文 URL，保留中文关键信息，过长截断
  const zh = e.replace(/https?:\/\/\S+/g, '').replace(/\s+/g, ' ').trim()
  const base = zh || e
  return base.length > 90 ? base.slice(0, 90) + '…' : base
})
function addStory() {
  stories.value.push({ title: '', desc: '', scene: '', acceptance: [''], rules: [], finalized: false })
  storiesConfirmed.value = false
}
function _startGenTimer() {
  storyGenElapsed.value = 0
  _storyGenTimer = setInterval(() => { storyGenElapsed.value++ }, 1000)
}
function _stopGenTimer() {
  if (_storyGenTimer) { clearInterval(_storyGenTimer); _storyGenTimer = null }
}
async function generateStories(strategy = 'rules_v2') {
  if (!clarification.value.trim()) {
    ElMessage.warning('请先填写澄清后需求内容')
    return
  }
  storyGenLoading.value = true
  _startGenTimer()
  try {
    const res = await generateUserStories(current.value.req_id, clarification.value, strategy)
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
    storiesConfirmed.value = false
    const labelMap = { rules_v2: '合并优先', rules_v1: '按工作量拆分', rules_v2_fallback: '合并优先', llm: 'Kimi 智能拆分' }
    strategyLabel.value = labelMap[res.strategy_used] || res.strategy_used || ''
    ElMessage.success(`已生成 ${stories.value.length} 条用户故事（${strategyLabel.value}），请预览后点击「确认落库」保存`)
  } catch (err) {
    ElMessage.error('生成失败，请重试')
  } finally {
    _stopGenTimer()
    storyGenLoading.value = false
  }
}
async function confirmStories() {
  if (!stories.value.length) return
  try {
    await saveUserStories(current.value.req_id, stories.value.map((s, i) => ({
      ...s, seq: i + 1,
    })))
    storiesConfirmed.value = true
    ElMessage.success(`已保存 ${stories.value.length} 条用户故事到数据库`)
  } catch {
    ElMessage.error('保存失败，请重试')
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
const ticketForm = reactive({ id: null, ticket_no: '', req_id: '', system_name: '', dev_team: '', developer: '', priority: 'P2', status: 'created', progress: 0, go_live_date: '', description: '' })
function openTicketDialog(row) {
  if (row) Object.assign(ticketForm, { ...row, go_live_date: row.go_live_date || '' })
  else Object.assign(ticketForm, { id: null, ticket_no: '', req_id: current.value.req_id || '', system_name: '', dev_team: '', developer: '', priority: 'P2', status: 'created', progress: 0, go_live_date: '', description: '' })
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
  return { proposed: '建议中', accepted: '已采纳', dev: '开发中', closed: '已上线', paused: '暂停' }[s] || s || '建议中'
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

const route = useRoute()

/* 深链定位 */
function applyDeepLink() {
  const q = route.query
  if (q.ticket) {
    const row = tickets.value.find((t) => t.ticket_no === q.ticket)
    if (row) { openTicketDialog(row); }
  } else if (q.req) {
    const row = requirements.value.find((t) => t.req_id === q.req)
    if (row) { openReqDialog(row); }
  }
}

onMounted(async () => {
  await loadRequirements()
  await loadTickets()
  applyDeepLink()
  checkLlmStatus()  // 后台检测 Kimi/LLM 状态，不阻塞主流程
})

onBeforeUnmount(() => {
  _stopGenTimer()
})
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
.story-title-enlarge { flex: 1; min-width: 0 }
.story-title-enlarge :deep(.el-input__wrapper) {
  background: transparent;
  box-shadow: none;
  border: none;
  border-bottom: 1px dashed var(--border);
  border-radius: 0;
  padding: 4px 26px 4px 0;
}
.story-title-enlarge :deep(.el-input__inner) {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0;
}
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

/* ── 生成策略选择器 ── */
.strategy-selector { display: flex; flex-direction: column; gap: 8px }
.strategy-card {
  display: flex; align-items: center; gap: 12px; padding: 10px 14px;
  border: 2px solid var(--border-subtle); border-radius: 10px;
  cursor: pointer; transition: all .2s; position: relative;
}
.strategy-card:hover { border-color: var(--border); background: var(--bg-app) }
.strategy-card.active { border-color: var(--accent); background: var(--accent-soft) }
.strategy-card.disabled { opacity: .45; cursor: not-allowed; background: var(--bg-app) }
.strategy-card.disabled:hover { border-color: var(--border-subtle) }
.sc-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0 }
.sc-icon-merge { background: #e6f4ff; color: #1677ff }
.sc-icon-ai { background: #f0e6ff; color: #722ed1 }
.sc-icon-old { background: #f5f5f5; color: #999 }
.sc-body { flex: 1; min-width: 0 }
.sc-title { font-size: 13px; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 6px }
.sc-desc { font-size: 11.5px; color: var(--text-muted); margin-top: 2px }
.sc-badge { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 999px; line-height: 1.5 }
.sc-badge { background: var(--accent-soft); color: var(--accent) }
.sc-badge-on { background: #e6ffe6; color: #389e0d }
.sc-badge-off { background: #fff2e8; color: #d48806 }
.sc-badge-old { background: #f5f5f5; color: #999 }
.sc-badge-info { background: #e6f4ff; color: #1677ff }
.sc-check { width: 22px; height: 22px; border-radius: 50%; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0 }
.sc-error { font-size: 11px; color: #cf1322; margin-top: 4px; line-height: 1.45; word-break: break-word }
.strategy-warn {
  display: flex; align-items: flex-start; gap: 6px;
  margin-top: 10px; padding: 8px 10px; border-radius: 8px;
  background: #fff7e6; border: 1px solid #ffd591; color: #ad6800;
  font-size: 12px; line-height: 1.55;
}
.strategy-warn .sw-icon { flex-shrink: 0; font-size: 14px; line-height: 1.4 }

/* ── 生成中 & 空状态 ── */
.story-loading-overlay {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 40px 20px; color: var(--text-secondary);
}
.story-loading-overlay p { margin: 8px 0 0; font-size: 14px }
.story-loading-hint { font-size: 12px !important; color: var(--text-muted) !important }
.story-empty { padding: 40px 20px; text-align: center; color: var(--text-muted); font-size: 13px }
.story-pending-bar {
  background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px;
  padding: 10px 14px; margin-bottom: 14px; font-size: 12.5px; color: #8c6d00
}
.confirm-badge :deep(.el-badge__content) { margin-top: 2px }

/* 用户故事只读详情 */
.us-detail { padding: 4px 24px 32px }
.us-block { margin-bottom: 18px }
.us-label { font-size: 11.5px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px }
.us-value { font-size: 13.5px; line-height: 1.7; color: var(--text-primary) }
.us-value.pre { white-space: pre-wrap }
.us-ol { margin: 0; padding-left: 20px; font-size: 13.5px; line-height: 1.8; color: var(--text-primary) }
.us-ol li { margin-bottom: 4px }
:deep(.us-hl) { background: var(--accent-soft); color: var(--accent); border-radius: 3px; padding: 0 2px; font-weight: 600 }
</style>
