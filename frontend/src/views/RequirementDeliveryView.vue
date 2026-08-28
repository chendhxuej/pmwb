<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <div class="page-title">需求与交付</div>
        <div class="page-sub">需求采集 → 团队评估 → 用户故事 → 分析说明书 → 启动开发 → 生产部署，全流程闭环</div>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="openActiveOptDialog()">
          <el-icon><Plus /></el-icon> 新增主动优化
        </el-button>
      </div>
    </div>

    <!-- 主标签：需求 / 开发工单 -->
    <el-tabs v-model="activeTab" class="pm-tabs">
      <!-- ════════ 需求标签 ════════ -->
      <el-tab-pane label="需求" name="requirement">
        <div class="pm-table-wrap">
          <div class="stat-cards">
            <div class="stat-card">
              <div class="stat-label">需求总数</div>
              <div class="stat-num">{{ reqStats.total || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">建议中</div>
              <div class="stat-num">{{ reqStats.proposed || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">已采纳</div>
              <div class="stat-num warning">{{ reqStats.accepted || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">开发中</div>
              <div class="stat-num primary">{{ reqStats.dev || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">已上线</div>
              <div class="stat-num success">{{ reqStats.closed || 0 }}</div>
            </div>
          </div>
          <div class="table-toolbar">
            <EnlargeInput
              v-model="reqKeyword"
              placeholder="搜索需求编号 / 名称 / 提出人"
              style="width: 260px"
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
          <div class="stat-cards">
            <div class="stat-card">
              <div class="stat-label">故事总数</div>
              <div class="stat-num">{{ usStats.total || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">已定稿</div>
              <div class="stat-num success">{{ usStats.finalized || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">草稿</div>
              <div class="stat-num">{{ usStats.draft || 0 }}</div>
            </div>
          </div>
          <div class="table-toolbar">
            <EnlargeInput
              v-model="usKeyword"
              placeholder="模糊搜索：标题 / 描述 / 场景 / 验收标准 / 业务规则 / 需求编号 / 需求名称（空格分词）"
              style="width: 420px"
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

      <!-- ════════ 主动优化标签 ════════ -->
      <el-tab-pane label="主动优化" name="active_opt">
        <div class="pm-table-wrap">
          <div class="stat-cards">
            <div class="stat-card">
              <div class="stat-label">工单总数</div>
              <div class="stat-num">{{ activeOptStats.total || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">待评估</div>
              <div class="stat-num" :class="{ warn: (activeOptStats.pending || 0) > 0 }">{{ activeOptStats.pending || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">已采纳</div>
              <div class="stat-num success">{{ activeOptStats.adopted || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">不采纳</div>
              <div class="stat-num muted">{{ activeOptStats.rejected || 0 }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">高优先级(P0/P1)</div>
              <div class="stat-num danger">{{ (activeOptStats.p0 || 0) + (activeOptStats.p1 || 0) }}</div>
            </div>
          </div>
          <div class="table-toolbar">
            <EnlargeInput v-model="activeOptKeyword" placeholder="搜索标题 / 现状 / 建议 / 管理员 / 需求文号" style="width: 320px" clearable @keyup.enter="handleActiveOptSearch" @clear="handleActiveOptSearch">
              <template #prefix><el-icon><Search /></el-icon></template>
            </EnlargeInput>
            <el-select v-model="activeOptStatus" placeholder="评估状态" clearable class="w-s" @change="handleActiveOptSearch">
              <el-option label="待评估" value="pending" />
              <el-option label="已采纳" value="adopted" />
              <el-option label="不采纳" value="rejected" />
            </el-select>
            <el-select v-model="activeOptPriority" placeholder="优先级" clearable class="w-xs" @change="handleActiveOptSearch">
              <el-option label="P0" value="P0" />
              <el-option label="P1" value="P1" />
              <el-option label="P2" value="P2" />
              <el-option label="P3" value="P3" />
            </el-select>
            <el-button @click="loadActiveOpts"><el-icon><Refresh /></el-icon> 刷新</el-button>
          </div>
          <el-table v-loading="activeOptLoading" :data="activeOpts" stripe scrollbar-always-on row-class-name="req-table">
            <el-table-column label="优先级" width="70" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="priorityType(row.priority)" effect="dark">{{ row.priority || 'P2' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="工单标题" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="link-text" @click.stop="openActiveOptDetail(row)">{{ row.title || '（未命名）' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="现状描述" width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="text-muted" style="font-size: 12.5px">{{ row.current_situation || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="优化建议" width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="text-muted" style="font-size: 12.5px">{{ row.suggestion || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="admin_name" label="业务管理员" width="90" align="center" />
            <el-table-column label="评估状态" width="88" align="center">
              <template #default="{ row }"><StatusBadge module="active_optimization" :value="row.status" /></template>
            </el-table-column>
            <el-table-column label="关联需求" width="150" show-overflow-tooltip align="center">
              <template #default="{ row }">
                <span class="text-muted">{{ row.req_id || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="100" align="center">
              <template #default="{ row }">
                <span class="text-muted">{{ formatDate(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openActiveOptDialog(row)">编辑</el-button>
                <el-button link type="warning" size="small" @click.stop="openActiveOptMail(row, 'urge')">催办</el-button>
                <el-button link type="info" size="small" @click.stop="openActiveOptMail(row, 'sync')">同步</el-button>
                <el-button link type="danger" size="small" @click.stop="removeActiveOpt(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="table-footer">
            <span class="text-muted">共 {{ activeOptTotal }} 条</span>
            <el-pagination
              v-model:current-page="activeOptPage"
              v-model:page-size="activeOptPageSize"
              :total="activeOptTotal"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              small
              background
              @size-change="loadActiveOpts"
              @current-change="loadActiveOpts"
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

    <!-- ════════ 6步工作流抽屉 ════════ -->
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

      <!-- 步骤指示（双击步骤时间可修正） -->
      <div class="wf-steps">
        <div
          v-for="(s, i) in steps"
          :key="s.key"
          class="pm-step"
          :class="{ active: step === s.key, done: isStepDone(i) }"
          @click="step = s.key"
          @dblclick="openStageTimeEdit(s)"
          :title="'双击修正「' + s.label + '」环节时间'"
        >
          <div class="pm-step-dot">{{ isStepDone(i) ? '✓' : i + 1 }}</div>
          <div class="pm-step-meta">
            <div class="pm-step-label">{{ s.label }}</div>
            <div class="pm-step-time">
              <div v-for="(ln, li) in stageTimeLines(s.key)" :key="li" class="pm-step-time-line">{{ ln }}</div>
            </div>
          </div>
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

            <div
              ref="attachmentZone"
              class="card paste-attachment-zone"
              style="grid-column: span 5"
              tabindex="0"
            >
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
                <div class="hint-text mt-8">附件与生成文档统一归档在「需求分析说明书」文件夹；点击上方区域后按 Ctrl+V 可粘贴截图/文件。</div>
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
                      disabled: !llmStatus.available,
                    }"
                    @click="llmStatus.available && (selectedStrategy = 'llm')"
                  >
                    <div class="sc-icon sc-icon-ai">🤖</div>
                    <div class="sc-body">
                      <div class="sc-title">
                        AI智能生成
                        <span v-if="llmChecking" class="sc-badge sc-badge-info">检测中</span>
                        <span v-else-if="!llmStatus.available" class="sc-badge sc-badge-off">未启用</span>
                        <span v-else-if="llmStatus.available" class="sc-badge sc-badge-on">已连接</span>
                        <span v-else class="sc-badge sc-badge-off">未连接</span>
                      </div>
                      <div class="sc-desc">
                        AI 理解角色/场景/闭环，约 30 秒
                      </div>
                      <div
                        v-if="!llmChecking && !llmStatus.available && llmStatus.notice"
                        class="sc-error"
                        :title="llmStatus.notice"
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
                  v-if="!llmChecking && !llmStatus.available"
                  class="strategy-warn"
                >
                  <span class="sw-icon">⚠️</span>
                  <span>AI 中心暂无可用的统一大模型{{ llmStatus.notice ? '：' + llmErrorHint : '' }}。可改用「合并生成」秒级出结果，或前往「大模型管理」配置并启用一个。</span>
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
                    {{ selectedStrategy === 'llm' ? `AI 正在分析需求… ${storyGenElapsed}s` : `正在生成… ${storyGenElapsed}s` }}
                  </template>
                  <template v-else>
                    <el-icon><MagicStick /></el-icon>
                    {{ selectedStrategy === 'llm' ? 'AI智能生成用户故事' : selectedStrategy === 'rules_v1' ? '按工作量生成用户故事' : '生成用户故事' }}
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
                  <p>{{ selectedStrategy === 'llm' ? 'AI 正在分析需求内容，识别角色/场景/闭环…' : '正在生成用户故事…' }}</p>
                  <p class="story-loading-hint">{{ selectedStrategy === 'llm' ? 'AI 带推理能力，通常需要 20-40 秒，请耐心等待' : '预计 1-3 秒完成' }}</p>
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

        <!-- ───── 步骤5：启动开发 ───── -->
        <div v-show="step === 'dev'" class="wf-step-panel">
          <div class="bento-grid">
            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
                <span class="card-label">开发事件记录（时间线倒序）</span>
                <el-button size="small" type="primary" @click="openDevEventDialog()">
                  <el-icon><Plus /></el-icon> 新增开发事件
                </el-button>
              </div>
              <div class="card-body">
                <div v-if="devEvents.length" class="dev-event-timeline">
                  <div v-for="ev in devEvents" :key="ev.id" class="dev-event-item">
                    <div class="dev-event-axis">
                      <div class="dev-event-dot" :class="devEventTypeClass(ev.event_type)"></div>
                      <div v-if="ev !== devEvents[devEvents.length - 1]" class="dev-event-line"></div>
                    </div>
                    <div class="dev-event-content">
                      <div class="dev-event-head">
                        <el-tag size="small" :type="devEventTypeTag(ev.event_type)">{{ ev.event_type_label }}</el-tag>
                        <b class="dev-event-title">{{ ev.title }}</b>
                        <span class="dev-event-time text-muted">{{ ev.event_time }}</span>
                        <div class="flex gap-4" style="margin-left:auto">
                          <el-button link type="primary" size="small" @click="openDevEventDialog(ev)">编辑</el-button>
                          <el-button link type="danger" size="small" @click="removeDevEvent(ev)">删除</el-button>
                        </div>
                      </div>
                      <div v-if="ev.content" class="dev-event-detail pre">{{ ev.content }}</div>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-hint">
                  暂无开发事件。跟踪状态切为「开发中」时会自动记录一条「启动开发」事件；也可点击右上角手动新增。
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ───── 步骤6：生产部署 ───── -->
        <div v-show="step === 'deploy'" class="wf-step-panel">
          <div class="bento-grid">
            <div class="card" style="grid-column: span 12">
              <div class="card-header flex-between">
                <span class="card-label">操作手册（按系统区分 · 在线浏览 / 下载）</span>
                <div class="flex gap-8">
                  <el-select v-model="manualUploadSystem" placeholder="选择系统" style="width: 220px" size="small">
                    <el-option v-for="sys in manualSystems" :key="sys.system_name" :label="sys.system_name" :value="sys.system_name" />
                  </el-select>
                  <input
                    ref="manualFileInput"
                    type="file"
                    style="display:none"
                    accept=".pdf,.doc,.docx,.xls,.xlsx,.pptx,.zip"
                    @change="handleManualFileChange"
                  />
                  <el-button size="small" type="success" :loading="uploadingManual" @click="triggerManualUpload">
                    <el-icon><Upload /></el-icon> 上传操作手册
                  </el-button>
                  <el-button
                    size="small"
                    :type="current.ext?.manual_archived ? 'info' : 'primary'"
                    :loading="archiving"
                    @click="archiveManual(current)"
                  >{{ current.ext?.manual_archived ? '重新归档操作手册' : '归档操作手册到业务知识' }}</el-button>
                </div>
              </div>
              <div class="card-body">
                <div class="hint-text mb-12">手册按「系统 + 团队」归属：系统选项来自本需求团队评估记录，同一系统一份手册，重复上传将替换；无手册的系统显示「暂无操作手册」。</div>
                <div v-for="sys in manualSystems" :key="sys.system_name" class="manual-system-block">
                  <div class="manual-system-head">
                    <el-icon><Monitor /></el-icon>
                    <b>{{ sys.system_name }}</b>
                    <span class="text-muted" style="font-size:12px">SA：{{ sys.sa_name || '—' }}</span>
                    <el-tag v-if="sys.manual" size="small" type="success" style="margin-left:8px">有手册</el-tag>
                    <el-tag v-else size="small" type="info" style="margin-left:8px">暂无操作手册</el-tag>
                  </div>
                  <div v-if="sys.manual" class="manual-item">
                    <el-icon><Document /></el-icon>
                    <div class="gen-meta">
                      <b>{{ sys.manual.file_name }}</b>
                      <div class="text-muted" style="font-size:11px">{{ sys.manual.created_at }} · {{ fmtSize(sys.manual.size) }}</div>
                    </div>
                    <el-button v-if="canPreview(sys.manual.file_name)" link type="primary" size="small" @click="openManualPreview(sys)">在线浏览</el-button>
                    <el-button link type="primary" size="small" @click="downloadManual(sys)">下载</el-button>
                    <el-button link type="danger" size="small" @click="removeManual(sys)">删除</el-button>
                  </div>
                  <div v-else class="manual-item empty">
                    <span class="text-muted">该团队暂无「{{ sys.system_name }}」操作手册</span>
                    <el-button link type="primary" size="small" @click="manualUploadSystem = sys.system_name; triggerManualUpload()">去上传</el-button>
                  </div>
                </div>
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
                <el-button size="small" type="primary" :loading="sedimenting" @click="sedimentRequirement">
                  沉淀需求为知识笔记
                </el-button>
              </div>
              <div class="card-body">
                <el-form label-width="84px" label-position="left" class="mb-12">
                  <el-form-item label="业务领域">
                    <BusinessDomainSelect v-model="domainCode" @change="saveDomainCode" />
                  </el-form-item>
                </el-form>

                <div class="hint-text mb-12">操作手册在「生产部署」环节上传后自动归档到业务知识；此处负责沉淀需求为知识笔记并与业务领域关联。</div>

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

    <!-- 环节时间修正弹窗 -->
    <el-dialog v-model="stageTimeDialog" :title="'修正「' + stageTimeForm.label + '」环节时间'" width="420px">
      <el-form :model="stageTimeForm" label-width="90px">
        <el-form-item label="进入时间">
          <el-date-picker v-model="stageTimeForm.entered_at" type="datetime" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm" style="width:100%" placeholder="该环节进入时间" />
        </el-form-item>
        <el-form-item label="完成时间">
          <el-date-picker v-model="stageTimeForm.left_at" type="datetime" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm" style="width:100%" placeholder="该环节完成时间（当前环节留空）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stageTimeDialog = false">取消</el-button>
        <el-button type="primary" @click="saveStageTime">保存</el-button>
      </template>
    </el-dialog>

    <!-- 开发事件弹窗 -->
    <el-dialog v-model="devEventDialog" :title="devEventForm.id ? '编辑开发事件' : '新增开发事件'" width="520px">
      <el-form :model="devEventForm" label-width="90px">
        <el-form-item label="事件类型">
          <el-select v-model="devEventForm.event_type" style="width:100%">
            <el-option v-for="(label, key) in devEventTypes" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="发生时间">
          <el-date-picker v-model="devEventForm.event_time" type="datetime" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm" style="width:100%" placeholder="默认当前时间" />
        </el-form-item>
        <el-form-item label="事件标题"><EnlargeInput v-model="devEventForm.title" placeholder="如：完成联调提测、版本发布到测试环境" /></el-form-item>
        <el-form-item label="事件详情"><EnlargeInput v-model="devEventForm.content" type="textarea" :rows="3" placeholder="补充说明（可选）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="devEventDialog = false">取消</el-button>
        <el-button type="primary" @click="saveDevEvent">保存</el-button>
      </template>
    </el-dialog>

    <!-- 操作手册在线预览弹窗 -->
    <el-dialog v-model="manualPreviewVisible" title="操作手册预览" width="80%" top="4vh">
      <div v-loading="manualPreviewLoading" class="manual-preview-box">
        <iframe v-if="manualPreviewUrl" :src="manualPreviewUrl" class="manual-preview-frame"></iframe>
        <div v-else class="empty-hint">该格式暂不支持在线预览，请下载后查看</div>
      </div>
      <template #footer>
        <el-button @click="manualPreviewVisible = false">关闭</el-button>
        <el-button type="primary" @click="downloadManual(manualPreviewSys)">下载</el-button>
      </template>
    </el-dialog>

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

    <!-- 主动优化弹层 -->
    <el-dialog v-model="activeOptDialog" :title="activeOptForm.id ? '编辑主动优化' : '新增主动优化'" width="600px">
      <el-form :model="activeOptForm" label-width="110px">
        <el-form-item label="工单标题"><EnlargeInput v-model="activeOptForm.title" placeholder="简洁描述优化方向" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="activeOptForm.priority" style="width:100%">
            <el-option label="P0" value="P0" />
            <el-option label="P1" value="P1" />
            <el-option label="P2" value="P2" />
            <el-option label="P3" value="P3" />
          </el-select>
        </el-form-item>
        <el-form-item label="现状描述"><EnlargeInput v-model="activeOptForm.current_situation" type="textarea" :rows="3" placeholder="当前业务痛点或低效环节" /></el-form-item>
        <el-form-item label="优化建议"><EnlargeInput v-model="activeOptForm.suggestion" type="textarea" :rows="3" placeholder="具体优化思路或措施" /></el-form-item>
        <el-form-item label="业务管理员"><StaffSelect v-model="activeOptForm.admin_name" /></el-form-item>
        <el-form-item label="评估状态">
          <el-select v-model="activeOptForm.status" style="width:100%">
            <el-option label="待评估" value="pending" />
            <el-option label="已采纳" value="adopted" />
            <el-option label="不采纳" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联需求">
          <el-select
            v-model="activeOptForm.req_id"
            filterable
            remote
            reserve-keyword
            clearable
            placeholder="输入需求文号/名称搜索并选择"
            :remote-method="searchLinkedReq"
            :loading="reqSearchLoading"
            style="width: 100%"
          >
            <el-option
              v-for="r in linkedReqOptions"
              :key="r.req_id"
              :label="`${r.req_name || '未命名需求'}（${r.req_id}）`"
              :value="r.req_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注说明"><EnlargeInput v-model="activeOptForm.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="activeOptDialog = false">取消</el-button>
        <el-button type="primary" @click="saveActiveOpt">保存</el-button>
      </template>
    </el-dialog>

    <!-- ════════ 主动优化详情抽屉 ════════ -->
    <el-drawer v-model="activeOptDetailVisible" size="70%" :title="null" destroy-on-close>
      <template #header>
        <div class="wf-head">
          <div>
            <div class="wf-req-id font-mono">#{{ activeOptDetail.id }}</div>
            <div class="wf-req-name">{{ activeOptDetail.title || '（未命名）' }}</div>
          </div>
          <div class="flex gap-8">
            <StatusBadge module="active_optimization" :value="activeOptDetail.status" />
            <el-tag size="small" :type="priorityType(activeOptDetail.priority)">{{ activeOptDetail.priority || 'P2' }}</el-tag>
          </div>
        </div>
      </template>
      <div class="us-detail">
        <div class="us-block">
          <div class="us-label">现状描述</div>
          <div class="us-value pre">{{ activeOptDetail.current_situation || '—' }}</div>
        </div>
        <div class="us-block">
          <div class="us-label">优化建议</div>
          <div class="us-value pre">{{ activeOptDetail.suggestion || '—' }}</div>
        </div>
        <div class="us-block">
          <div class="us-label">业务管理员</div>
          <div class="us-value">{{ activeOptDetail.admin_name || '—' }}</div>
        </div>
        <div class="us-block">
          <div class="us-label">关联需求</div>
          <div class="us-value font-mono">{{ activeOptDetail.req_id || '—' }}</div>
        </div>
        <div class="us-block">
          <div class="us-label">备注说明</div>
          <div class="us-value pre">{{ activeOptDetail.note || '—' }}</div>
        </div>
        <div class="us-block">
          <div class="us-label">创建时间</div>
          <div class="us-value">{{ formatDateTime(activeOptDetail.created_at) }}</div>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-10">
          <el-button @click="activeOptDetailVisible = false">关闭</el-button>
          <el-button type="primary" @click="openActiveOptDialog(activeOptDetail)">编辑</el-button>
          <el-button type="warning" @click="openActiveOptMail(activeOptDetail, 'urge')">催办</el-button>
          <el-button type="info" @click="openActiveOptMail(activeOptDetail, 'sync')">同步</el-button>
        </div>
      </template>
    </el-drawer>
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
import { usePasteUpload } from '@/composables/usePasteUpload.js'
import {
  getRequirements, getRequirement, updateRequirement, deleteRequirement,
  getRequirementStats,
  getEvaluations, createEvaluation, updateEvaluation, deleteEvaluation,
  initRequirementFolder, listRequirementAttachments, uploadRequirementAttachment,
  deleteRequirementAttachment, generateUserStories, getUserStories,
  saveUserStories, generateRequirementDoc, searchUserStories, getLlmStatus, getUserStoryStats,
  getStageLogs, updateStageLog, listDevEvents, createDevEvent, updateDevEvent, deleteDevEvent,
  listManuals, uploadManual, deleteManual, downloadManualUrl, previewManualUrl,
} from '@/api/requirement'
import {
  getActiveOptimizations, getActiveOptimizationStats, createActiveOptimization, updateActiveOptimization, deleteActiveOptimization,
} from '@/api/active_optimization'

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
const reqStats = ref({})

async function loadRequirements() {
  reqLoading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([
      getRequirements({
        keyword: reqKeyword.value || undefined,
        status: reqStatus.value || undefined,
        priority: reqPriority.value || undefined,
        page: reqPage.value,
        page_size: reqPageSize.value,
      }),
      getRequirementStats(),
    ])
    requirements.value = listRes.items || []
    reqTotal.value = listRes.total || 0
    reqStats.value = statsRes || {}
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
    `| 当前状态 | ${statusLabel(row.ext?.status || row.status) || (row.ext?.status || row.status || '')} |`,
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
    status: statusLabel(row.ext?.status || row.status) || (row.ext?.status || row.status || ''),
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
const usStats = ref({})
let usDebounce = null

async function loadStorySearch() {
  usLoading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([
      searchUserStories({
        keyword: usKeyword.value.trim(),
        finalized: usFinalized.value,
        page: usPage.value,
        pageSize: usPageSize.value,
      }),
      getUserStoryStats(),
    ])
    usList.value = listRes.items || []
    usTotal.value = listRes.total || 0
    usStats.value = statsRes || {}
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

// 首次进入用户故事 / 主动优化标签时懒加载
watch(activeTab, (v) => {
  if (v === 'story' && !usList.value.length && !usLoading.value) {
    loadStorySearch()
  }
  if (v === 'active_opt' && !activeOpts.value.length && !activeOptLoading.value) {
    loadActiveOpts()
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

/* ─────────────── 主动优化标签 ─────────────── */
const activeOptKeyword = ref('')
const activeOptStatus = ref('')
const activeOptPriority = ref('')
const activeOptLoading = ref(false)
const activeOpts = ref([])
const activeOptTotal = ref(0)
const activeOptPage = ref(1)
const activeOptPageSize = ref(20)
const activeOptStats = ref({})

async function loadActiveOpts() {
  activeOptLoading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([
      getActiveOptimizations({
        keyword: activeOptKeyword.value || undefined,
        status: activeOptStatus.value || undefined,
        priority: activeOptPriority.value || undefined,
        page: activeOptPage.value,
        page_size: activeOptPageSize.value,
      }),
      getActiveOptimizationStats(),
    ])
    activeOpts.value = listRes.items || []
    activeOptTotal.value = listRes.total || 0
    activeOptStats.value = statsRes || {}
  } catch (e) {
    console.error('[主动优化] 加载失败:', e)
  } finally {
    activeOptLoading.value = false
  }
}

function handleActiveOptSearch() {
  activeOptPage.value = 1
  loadActiveOpts()
}

/* ─────────────── 6步工作流抽屉 ─────────────── */
const steps = [
  { key: 'collect', label: '需求采集' },
  { key: 'evaluate', label: '团队评估' },
  { key: 'story', label: '用户故事' },
  { key: 'doc', label: '生成文档' },
  { key: 'dev', label: '启动开发' },
  { key: 'deploy', label: '生产部署' },
]
const wfVisible = ref(false)
const step = ref('collect')
const current = ref({})

/* ── 环节时间日志 ── */
const stageLogs = ref([])
const stageTimeDialog = ref(false)
const stageTimeForm = reactive({ stage: '', label: '', entered_at: '', left_at: '' })
async function loadStageLogs(reqId) {
  try {
    const res = await getStageLogs(reqId)
    stageLogs.value = res?.stages || []
  } catch (e) {
    stageLogs.value = []
  }
}
function fmtMiniDt(v) {
  if (!v) return ''
  const s = String(v).slice(0, 16).replace('T', ' ')
  return s.length >= 10 ? s.slice(5) : s
}
function stageTimeLines(stageKey) {
  const s = stageLogs.value.find((x) => x.stage === stageKey)
  if (!s) return []
  const lines = []
  if (s.entered_at) lines.push(fmtMiniDt(s.entered_at) + ' 进入')
  if (s.left_at) lines.push(fmtMiniDt(s.left_at) + ' 完成')
  else if (s.entered_at) {
    const days = calcStayDays(s.entered_at)
    lines.push('已停留 ' + (days > 0 ? days + ' 天' : '今天'))
  }
  return lines
}
function calcStayDays(v) {
  if (!v) return 0
  const t = new Date(String(v).replace('T', ' ').replace(/-/g, '/'))
  if (isNaN(t.getTime())) return 0
  return Math.max(0, Math.floor((Date.now() - t.getTime()) / 86400000))
}
function openStageTimeEdit(s) {
  const rec = stageLogs.value.find((x) => x.stage === s.key)
  stageTimeForm.stage = s.key
  stageTimeForm.label = s.label
  stageTimeForm.entered_at = rec?.entered_at || ''
  stageTimeForm.left_at = rec?.left_at || ''
  stageTimeDialog.value = true
}
async function saveStageTime() {
  try {
    await updateStageLog(current.value.req_id, stageTimeForm.stage, {
      entered_at: stageTimeForm.entered_at || null,
      left_at: stageTimeForm.left_at || null,
    })
    ElMessage.success('环节时间已修正')
    stageTimeDialog.value = false
    await loadStageLogs(current.value.req_id)
  } catch (e) {
    ElMessage.error('修正失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}

/* ── 开发事件 ── */
const devEventTypes = {
  dev_start: '开发启动',
  joint_test: '联调提测',
  test: '测试',
  bugfix: '缺陷修复',
  release_ready: '上线准备',
  other: '其他',
}
const devEvents = ref([])
const devEventDialog = ref(false)
const devEventForm = reactive({ id: 0, event_type: 'dev_start', event_time: '', title: '', content: '' })
async function loadDevEvents(reqId) {
  try {
    devEvents.value = (await listDevEvents(reqId)) || []
  } catch (e) {
    devEvents.value = []
  }
}
function openDevEventDialog(ev) {
  if (ev?.id) {
    devEventForm.id = ev.id
    devEventForm.event_type = ev.event_type || 'other'
    devEventForm.event_time = ev.event_time || ''
    devEventForm.title = ev.title || ''
    devEventForm.content = ev.content || ''
  } else {
    devEventForm.id = 0
    devEventForm.event_type = 'dev_start'
    devEventForm.event_time = ''
    devEventForm.title = ''
    devEventForm.content = ''
  }
  devEventDialog.value = true
}
async function saveDevEvent() {
  if (!devEventForm.title.trim()) {
    ElMessage.warning('请填写事件标题')
    return
  }
  const payload = {
    event_type: devEventForm.event_type,
    event_time: devEventForm.event_time || null,
    title: devEventForm.title.trim(),
    content: devEventForm.content || '',
  }
  try {
    if (devEventForm.id) {
      await updateDevEvent(current.value.req_id, devEventForm.id, payload)
      ElMessage.success('开发事件已更新')
    } else {
      await createDevEvent(current.value.req_id, payload)
      ElMessage.success('开发事件已记录')
    }
    devEventDialog.value = false
    await loadDevEvents(current.value.req_id)
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}
async function removeDevEvent(ev) {
  try {
    await ElMessageBox.confirm(`确认删除开发事件「${ev.title}」？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteDevEvent(current.value.req_id, ev.id)
    ElMessage.success('已删除')
    await loadDevEvents(current.value.req_id)
  } catch (e) {
    ElMessage.error('删除失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}
function devEventTypeClass(type) {
  const map = { dev_start: 'ev-dev', joint_test: 'ev-test', test: 'ev-test', bugfix: 'ev-bug', release_ready: 'ev-rel', other: 'ev-other' }
  return map[type] || 'ev-other'
}
function devEventTypeTag(type) {
  const map = { dev_start: 'primary', joint_test: 'warning', test: 'warning', bugfix: 'danger', release_ready: 'success', other: 'info' }
  return map[type] || 'info'
}

/* ── 操作手册（按系统） ── */
const manualSystems = ref([])
const manualUploadSystem = ref('')
const uploadingManual = ref(false)
const manualFileInput = ref(null)
const manualPreviewVisible = ref(false)
const manualPreviewLoading = ref(false)
const manualPreviewUrl = ref('')
const manualPreviewSys = ref(null)
async function loadManuals(reqId) {
  try {
    const res = await listManuals(reqId)
    manualSystems.value = res?.systems || []
    if (!manualUploadSystem.value && manualSystems.value.length) {
      manualUploadSystem.value = manualSystems.value[0].system_name
    }
  } catch (e) {
    manualSystems.value = []
  }
}
function triggerManualUpload() {
  if (!manualUploadSystem.value) {
    ElMessage.warning('请先选择系统')
    return
  }
  manualFileInput.value?.click()
}
async function handleManualFileChange(e) {
  const file = e.target.files?.[0]
  if (!file || !current.value?.req_id) return
  if (!manualUploadSystem.value) {
    ElMessage.warning('请先选择系统')
    if (manualFileInput.value) manualFileInput.value.value = ''
    return
  }
  uploadingManual.value = true
  try {
    await uploadManual(current.value.req_id, file, manualUploadSystem.value)
    ElMessage.success(`「${manualUploadSystem.value}」操作手册已上传`)
    await loadManuals(current.value.req_id)
    // 合二为一：上传即归档（业务上不会出现"只上传不归档"）。未设业务领域时温和提示。
    if (!current.value.ext?.domain_code) {
      ElMessage.warning('已上传。该需求尚未设置业务领域，无法自动归档；请先在下方选择业务领域，再点击「归档操作手册到业务知识」')
    } else {
      await archiveManual(current.value)
    }
  } catch (err) {
    ElMessage.error('上传失败：' + (err?.response?.data?.message || err.message || '未知错误'))
  } finally {
    uploadingManual.value = false
    if (manualFileInput.value) manualFileInput.value.value = ''
  }
}
async function removeManual(sys) {
  const m = sys?.manual
  if (!m?.id) return
  try {
    await ElMessageBox.confirm(`确认删除「${sys.system_name}」的操作手册「${m.file_name}」？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteManual(current.value.req_id, m.id)
    ElMessage.success('已删除')
    await loadManuals(current.value.req_id)
  } catch (e) {
    ElMessage.error('删除失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}
function canPreview(fileName) {
  const ext = String(fileName || '').split('.').pop().toLowerCase()
  return ['pdf', 'docx'].includes(ext)
}
function openManualPreview(sys) {
  const m = sys?.manual
  if (!m?.id) return
  manualPreviewSys.value = sys
  manualPreviewLoading.value = true
  manualPreviewVisible.value = true
  manualPreviewUrl.value = ''
  // 预取预览 HTML（docx 转 html 耗时，先加载提示）
  setTimeout(() => {
    manualPreviewUrl.value = previewManualUrl(current.value.req_id, m.id)
    manualPreviewLoading.value = false
  }, 50)
}
function downloadManual(sys) {
  const m = sys?.manual
  if (!m?.id) return
  const a = document.createElement('a')
  a.href = downloadManualUrl(current.value.req_id, m.id)
  a.download = m.file_name
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
function fmtSize(v) {
  if (!v) return ''
  const n = Number(v)
  if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB'
  if (n >= 1024) return (n / 1024).toFixed(1) + ' KB'
  return n + ' B'
}
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
const llmStatus = ref({ available: false, provider_name: '', provider_count: 0, notice: '' })
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
  const key = steps[i]?.key
  if (key === 'collect') return !!current.value.req_id
  if (key === 'evaluate') return evaluations.value.length > 0
  if (key === 'story') return stories.value.length > 0
  if (key === 'doc') return genHistory.value.length > 0
  if (key === 'dev') return devEvents.value.length > 0
  if (key === 'deploy') return !!current.value.delivered_date
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
  await Promise.all([loadStageLogs(key), loadDevEvents(key), loadManuals(key)])
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

/* kc-2-3：操作手册归档到业务知识 */
const archiving = ref(false)
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
const attachmentZone = ref(null)
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

usePasteUpload({
  targetRef: attachmentZone,
  enabled: computed(() => wfVisible.value),
  onFiles: async (files) => {
    for (const file of files) {
      try {
        await uploadRequirementAttachment(current.value.req_id, file)
      } catch (err) {
        ElMessage.error(`${file.name} 上传失败`)
        throw err
      }
    }
    const list = await listRequirementAttachments(current.value.req_id)
    attachments.value = list || []
    ElMessage.success(`已粘贴上传 ${files.length} 个文件`)
  },
})
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
  const p = llmStatus.value.provider_name
  return p || 'AI'
})
async function checkLlmStatus() {
  llmChecking.value = true
  try {
    const res = await getLlmStatus()
    llmStatus.value = res
  } catch {
    llmStatus.value = { available: false, provider_name: '', provider_count: 0, notice: '' }
  } finally {
    llmChecking.value = false
  }
}
const llmErrorHint = computed(() => {
  const e = llmStatus.value.notice || ''
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
    const labelMap = { rules_v2: '合并优先', rules_v1: '按工作量拆分', rules_v2_fallback: '合并优先', llm: 'AI智能生成' }
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

/* 主动优化弹层 */
const activeOptDialog = ref(false)
const activeOptForm = reactive({
  id: null,
  title: '',
  priority: 'P2',
  current_situation: '',
  suggestion: '',
  admin_name: '',
  status: 'pending',
  req_id: '',
  note: '',
})
function openActiveOptDialog(row) {
  if (row) {
    Object.assign(activeOptForm, { priority: 'P2', ...row })
  } else {
    Object.assign(activeOptForm, {
      id: null,
      title: '',
      priority: 'P2',
      current_situation: '',
      suggestion: '',
      admin_name: '',
      status: 'pending',
      req_id: current.value.req_id || '',
      note: '',
    })
  }
  activeOptDialog.value = true
  // 预载关联需求可选项（确保当前已选值可显示，并带需求名称）
  searchLinkedReq(activeOptForm.req_id || '').then(async () => {
    if (activeOptForm.req_id && !linkedReqOptions.value.some((r) => r.req_id === activeOptForm.req_id)) {
      let name = ''
      try {
        const res = await getRequirement(activeOptForm.req_id)
        name = (res && res.req_name) || ''
      } catch (e) {
        /* 忽略，仅展示文号 */
      }
      linkedReqOptions.value.unshift({ req_id: activeOptForm.req_id, req_name: name })
    }
  })
}

/* 关联需求：远端搜索需求工单 */
const linkedReqOptions = ref([])
const reqSearchLoading = ref(false)
async function searchLinkedReq(keyword) {
  reqSearchLoading.value = true
  try {
    const res = await getRequirements({ keyword: keyword || undefined, page: 1, page_size: 50 })
    linkedReqOptions.value = res.items || []
  } catch (e) {
    linkedReqOptions.value = []
  } finally {
    reqSearchLoading.value = false
  }
}

/* 主动优化详情抽屉 */
const activeOptDetailVisible = ref(false)
const activeOptDetail = ref({})
function openActiveOptDetail(row) {
  activeOptDetail.value = { ...row }
  activeOptDetailVisible.value = true
}
async function saveActiveOpt() {
  if (!activeOptForm.title.trim()) {
    ElMessage.warning('请填写工单标题')
    return
  }
  const payload = { ...activeOptForm }
  if (activeOptForm.id) {
    await updateActiveOptimization(activeOptForm.id, payload)
    ElMessage.success('主动优化已更新')
  } else {
    await createActiveOptimization(payload)
    ElMessage.success('主动优化已创建')
  }
  activeOptDialog.value = false
  await loadActiveOpts()
  // 若抽屉正展示同一工单，同步刷新其详情
  if (activeOptDetailVisible.value && activeOptDetail.value?.id && activeOptForm.id === activeOptDetail.value.id) {
    activeOptDetail.value = { ...activeOptForm }
  }
}
async function removeActiveOpt(row) {
  await ElMessageBox.confirm(`确认删除主动优化「${row.title}」？`, '提示', { type: 'warning' })
  await deleteActiveOptimization(row.id)
  ElMessage.success('已删除')
  await loadActiveOpts()
}

/* 主动优化邮件：催办 / 同步 */
function openActiveOptMail(row, scene) {
  if (!row) return
  mailDialogTitle.value = scene === 'urge' ? '催办：主动优化建议' : '同步：主动优化建议'
  mailDialogTo.value = String(row.admin_name || '').split(',').filter(Boolean)
  mailDialogSubject.value = (scene === 'urge' ? '催办：' : '同步：') + (row.title || row.req_id || '主动优化建议')
  mailDialogVariables.value = {
    title: row.title || '',
    status: row.status || 'pending',
    status_label: activeOptStatusLabel(row.status),
    admin_name: row.admin_name || '',
    req_id: row.req_id || '',
    current_situation: row.current_situation || '（无）',
    suggestion: row.suggestion || '（无）',
    note: row.note || '（无）',
    scene_label: scene === 'urge' ? '催办' : '同步',
    body: '',
  }
  mailDialogBody.value = buildActiveOptMailBody(row, scene)
  mailDialogScene.value = scene === 'urge' ? 'active_optimization_urge' : 'active_optimization_sync'
  mailDialogVisible.value = true
}
function buildActiveOptMailBody(row, scene) {
  const lines = [
    scene === 'urge' ? '## 主动优化建议催办' : '## 主动优化建议同步',
    '',
    '| 字段 | 内容 |',
    '|------|------|',
    `| 工单标题 | ${row.title || ''} |`,
    `| 优先级 | ${row.priority || 'P2'} |`,
    `| 评估状态 | ${activeOptStatusLabel(row.status)} |`,
    `| 业务管理员 | ${row.admin_name || ''} |`,
    `| 关联需求 | ${row.req_id || ''} |`,
    '',
    '### 现状描述',
    row.current_situation || '（无）',
    '',
    '### 优化建议',
    row.suggestion || '（无）',
    '',
  ]
  if (row.note) {
    lines.push('### 备注说明')
    lines.push(row.note)
    lines.push('')
  }
  lines.push(scene === 'urge' ? '请尽快评估并反馈处理意见，谢谢。' : '请知悉以上优化建议的最新状态。')
  return lines.join('\n')
}
function activeOptStatusLabel(s) {
  return { pending: '待评估', adopted: '已采纳', rejected: '不采纳' }[s] || s || '待评估'
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
const route = useRoute()

/* 深链定位 */
function applyDeepLink() {
  const q = route.query
  if (q.req) {
    const row = requirements.value.find((t) => t.req_id === q.req)
    if (row) { openReqDialog(row); }
  } else if (q.activeOpt) {
    activeTab.value = 'active_opt'
    loadActiveOpts().then(() => {
      const row = activeOpts.value.find((t) => String(t.id) === String(q.activeOpt))
      if (row) { openActiveOptDialog(row); }
    })
  }
}

onMounted(async () => {
  await loadRequirements()
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
.stat-cards { display: flex; gap: 12px; padding: 16px 20px 0; flex-wrap: wrap }
.stat-card { background: var(--bg-card, var(--el-bg-color)); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 14px 18px; min-width: 110px; flex: 1; display: flex; flex-direction: column; gap: 6px; transition: box-shadow .2s }
.stat-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.04) }
.stat-label { font-size: 12px; color: var(--text-muted); font-weight: 500 }
.stat-num { font-size: 22px; font-weight: 700; color: var(--text-primary); line-height: 1 }
.stat-num.success { color: var(--success, #67c23a) }
.stat-num.warning { color: var(--warning, #e6a23c) }
.stat-num.primary { color: var(--accent, #409eff) }
.stat-num.danger { color: var(--danger, #f56c6c) }
.stat-num.muted { color: var(--text-muted) }
.stat-num.warn { color: var(--warning, #e6a23c) }
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
.pm-step-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; align-items: flex-start }
.pm-step-time { font-size: 10px; color: var(--text-muted); line-height: 1.45; white-space: normal; word-break: break-all; min-height: 29px; display: flex; flex-direction: column; justify-content: center }
.pm-step-time-line { line-height: 1.45 }
.pm-step.active .pm-step-time { color: var(--accent); opacity: .85 }
.pm-step-line { flex: 1; height: 2px; background: var(--border-subtle); margin: 0 10px; min-width: 20px }
.pm-step-line.done { background: var(--success) }
.wf-body { padding: 22px 24px 40px }
.wf-step-panel { animation: fadeIn .25s ease }
@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }

/* 开发事件时间线 */
.dev-event-timeline { display: flex; flex-direction: column; gap: 0 }
.dev-event-item { display: flex; gap: 14px }
.dev-event-axis { display: flex; flex-direction: column; align-items: center; width: 14px; flex-shrink: 0 }
.dev-event-dot { width: 12px; height: 12px; border-radius: 50%; margin-top: 6px; border: 2px solid var(--border) }
.dev-event-dot.ev-dev { background: var(--accent); border-color: var(--accent) }
.dev-event-dot.ev-test { background: var(--warning); border-color: var(--warning) }
.dev-event-dot.ev-bug { background: var(--danger); border-color: var(--danger) }
.dev-event-dot.ev-rel { background: var(--success); border-color: var(--success) }
.dev-event-dot.ev-other { background: var(--text-muted); border-color: var(--text-muted) }
.dev-event-line { flex: 1; width: 2px; background: var(--border-subtle); min-height: 18px; margin: 4px 0 }
.dev-event-content { flex: 1; min-width: 0; padding-bottom: 18px }
.dev-event-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap }
.dev-event-title { font-size: 13.5px; color: var(--text-primary) }
.dev-event-time { font-size: 11.5px }
.dev-event-detail { margin-top: 6px; font-size: 12.5px; color: var(--text-secondary); line-height: 1.6; background: var(--bg-app); border-radius: 8px; padding: 8px 12px }

/* 操作手册（按系统） */
.manual-system-block { border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; margin-bottom: 12px }
.manual-system-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px }
.manual-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: var(--bg-app); border-radius: 8px; font-size: 13px }
.manual-item.empty { color: var(--text-muted); font-size: 12.5px }
.manual-preview-box { height: 68vh; border: 1px solid var(--border-subtle); border-radius: 8px; overflow: hidden; background: #fff }
.manual-preview-frame { width: 100%; height: 100%; border: none }
.empty-hint { padding: 18px 0; text-align: center; color: var(--text-muted); font-size: 12.5px }

.readonly-text { font-size: 13.5px; line-height: 1.7; color: var(--text-secondary); white-space: pre-wrap; margin: 0 }
.folder-path { display: flex; align-items: center; gap: 8px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 8px 12px; font-size: 12px }
.folder-path code { color: var(--accent); font-family: var(--font-mono); word-break: break-all }
.attachment-list { margin-top: 10px }
.attachment-item { display: flex; align-items: center; gap: 8px; padding: 7px 0; border-bottom: 1px solid var(--border-subtle); font-size: 13px }
.att-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.att-size { font-size: 11px }
.hint-text { font-size: 11.5px; color: var(--text-muted) }
.paste-attachment-zone { outline: none; transition: box-shadow 0.2s, background-color 0.2s }
.paste-attachment-zone:focus-visible { box-shadow: 0 0 0 2px var(--el-color-primary-light-5); background-color: var(--el-fill-color-light) }

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
