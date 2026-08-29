<template>
  <div class="research-issue-view">
    <div class="page-head">
      <h2 class="page-title">一线调研</h2>
      <el-tag type="primary" effect="dark" size="large" round>调研工单</el-tag>
      <el-button type="primary" @click="openEntry" style="margin-left:auto">
        <el-icon><Plus /></el-icon><span>录入工单</span>
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="12" class="stats-row">
      <el-col :span="3">
        <el-card shadow="hover"><div class="stat-item"><div class="stat-value" v-countup="stats.total"></div><div class="stat-label">工单总数</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-pending"><div class="stat-item"><div class="stat-value" v-countup="stats.pending"></div><div class="stat-label">待处理</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-processing"><div class="stat-item"><div class="stat-value" v-countup="stats.processing"></div><div class="stat-label">处理中</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-verify"><div class="stat-item"><div class="stat-value" v-countup="stats.verify"></div><div class="stat-label">待验证</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-resolved"><div class="stat-item"><div class="stat-value" v-countup="stats.resolved"></div><div class="stat-label">已解决</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-closed"><div class="stat-item"><div class="stat-value" v-countup="stats.closed"></div><div class="stat-label">已关闭</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-overdue"><div class="stat-item"><div class="stat-value" v-countup="stats.overdue"></div><div class="stat-label">超期</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-loop"><div class="stat-item"><div class="stat-value">{{ stats.closed_loop_rate }}%</div><div class="stat-label">闭环率</div></div></el-card>
      </el-col>
    </el-row>

    <!-- 过滤栏 -->
    <div class="filter-bar">
      <el-select v-model="filterCity" clearable placeholder="地市" size="small" style="width:120px">
        <el-option v-for="c in CITY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
      </el-select>
      <el-select v-model="filterSubType" clearable placeholder="子类" size="small" style="width:120px">
        <el-option v-for="t in SUB_TYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <el-select v-model="filterStatus" clearable placeholder="状态" size="small" style="width:100px">
        <el-option v-for="s in STATUS_FLOW" :key="s.key" :label="s.label" :value="s.key" />
      </el-select>
      <el-select v-model="filterNature" clearable placeholder="问题性质" size="small" style="width:120px">
        <el-option v-for="n in NATURE_OPTIONS" :key="n.value" :label="n.label" :value="n.value" />
      </el-select>
      <EnlargeInput
        v-model="keyword"
        placeholder="搜索工单号 / 标题 / 负责人"
        clearable
        size="small"
        style="width: 260px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button size="small" @click="handleSearch">查询</el-button>
      <el-button size="small" @click="loadStats">刷新统计</el-button>
    </div>

    <!-- 工单列表 -->
    <el-table
      :data="tableData"
      v-loading="loading"
      stripe
      border
      class="wo-table"
    >
      <el-table-column prop="issue_no" label="工单编号" width="160" />
      <el-table-column prop="title" label="标题" min-width="380" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="iss-title" @click="openDetail(row)">{{ row.title }}</span>
        </template>
      </el-table-column>
      <el-table-column label="地市" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.city" size="small" type="info">{{ CITY_LABELS[row.city] || row.city }}</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="子类" width="100">
        <template #default="{ row }">
          <el-tag :type="subTypeTag(row.sub_type)" size="small">
            {{ SUB_TYPE_LABELS[row.sub_type] || row.sub_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="问题性质" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.issue_nature" :type="natureTag(row.issue_nature)" size="small">
            {{ NATURE_LABELS[row.issue_nature] || row.issue_nature }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="厂家责任人" width="170">
        <template #default="{ row }">
          <template v-if="row.vendor_handlers">
            <el-tag v-for="h in row.vendor_handlers.split(',').filter(Boolean)" :key="h" size="small" class="handler-tag">{{ h }}</el-tag>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <StatusBadge module="research" :value="row.status" :sensitive="row.is_overdue" />
        </template>
      </el-table-column>
      <el-table-column label="逾期" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.is_overdue" type="danger" size="small">逾期</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="反馈截止" width="130">
        <template #default="{ row }">
          {{ row.feedback_deadline ? String(row.feedback_deadline).slice(0, 10) : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="130">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-dropdown size="small" trigger="click" @command="(cmd) => changeStatus(row, cmd)">
              <el-button link type="primary" :loading="statusLoadingMap[row.id]">
                改状态<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="s in STATUS_OPTIONS"
                    :key="s.key"
                    :command="s.key"
                    :disabled="row.status === s.key"
                  >
                    <span :class="['status-dot', 'dot-' + s.key]"></span>{{ s.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-dropdown @command="(_cmd) => openSupervise(row, _cmd)">
              <el-button link type="warning">督办<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="urge">催办</el-dropdown-item>
                  <el-dropdown-item command="sync">同步通知</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <div class="wo-pager">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @size-change="loadData"
        @current-change="loadData"
      />
    </div>

    <!-- 工单详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      :title="'工单详情 · ' + (detailRow?.issue_no || '')"
      size="70%"
      destroy-on-close
    >
      <div v-loading="detailLoading" class="drawer-body-inner">
        <!-- 状态 stepper -->
        <div class="pm-steps detail-stepper">
          <template v-for="(s, idx) in STATUS_FLOW" :key="s.key">
            <div class="pm-step" :class="stepClass(idx)">
              <div class="pm-step-dot">{{ idx < currentIdx ? '✓' : idx + 1 }}</div>
              <div class="pm-step-label">{{ s.label }}</div>
            </div>
            <div v-if="idx < STATUS_FLOW.length - 1" class="pm-step-line" :class="{ done: idx < currentIdx }"></div>
          </template>
        </div>

        <!-- 基本信息 -->
        <div class="dt-sec">
          <div class="dt-sec-title">基本信息</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="地市">{{ CITY_LABELS[detailRow?.city] || detailRow?.city || '-' }}</el-descriptions-item>
            <el-descriptions-item label="子类">{{ SUB_TYPE_LABELS[detailRow?.sub_type] || detailRow?.sub_type || '-' }}</el-descriptions-item>
            <el-descriptions-item label="反馈人">{{ detailRow?.feedback_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{ detailRow?.feedback_phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="信息来源">{{ detailRow?.source || '-' }}</el-descriptions-item>
            <el-descriptions-item label="反馈截止日期">{{ detailRow?.feedback_deadline ? String(detailRow.feedback_deadline).slice(0, 10) : '—' }}</el-descriptions-item>
            <el-descriptions-item label="优先级/影响">{{ detailRow?.impact_level || '-' }}</el-descriptions-item>
            <el-descriptions-item label="业务领域">{{ detailRow?.domain_code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="逾期">
              <el-tag v-if="detailRow?.is_overdue" type="danger" size="small">已逾期</el-tag>
              <span v-else>正常</span>
            </el-descriptions-item>
            <el-descriptions-item label="关联需求">{{ detailRow?.related_req_id || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 情况说明 -->
        <div class="dt-sec">
          <div class="dt-sec-title">情况说明</div>
          <div class="dt-desc">{{ detailRow?.situation_desc || '—' }}</div>
        </div>

        <!-- 地市建议 -->
        <div class="dt-sec" v-if="detailRow?.city_suggestion">
          <div class="dt-sec-title">地市建议</div>
          <div class="dt-desc">{{ detailRow.city_suggestion }}</div>
        </div>

        <!-- 评估结果 -->
        <div class="dt-sec" v-if="detailRow?.assessment_result || detailRow?.issue_nature">
          <div class="dt-sec-title">评估结果</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="问题性质">
              <el-tag v-if="detailRow?.issue_nature" :type="natureTag(detailRow.issue_nature)" size="small">
                {{ NATURE_LABELS[detailRow.issue_nature] }}
              </el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="厂家责任人">
              <template v-if="detailRow?.vendor_handlers">
                <el-tag v-for="h in detailRow.vendor_handlers.split(',').filter(Boolean)" :key="h" size="small" class="handler-tag">{{ h }}</el-tag>
              </template>
              <span v-else>-</span>
            </el-descriptions-item>
          </el-descriptions>
          <div class="dt-desc" style="margin-top:12px">{{ detailRow?.assessment_result || '—' }}</div>
        </div>

        <!-- 解决方案 -->
        <div class="dt-sec" v-if="detailRow?.solution">
          <div class="dt-sec-title">解决方案</div>
          <div class="dt-desc">{{ detailRow.solution }}</div>
        </div>

        <!-- 正式反馈信息 -->
        <div class="dt-sec" v-if="detailRow?.official_feedback">
          <div class="dt-sec-title">正式反馈信息</div>
          <div class="dt-desc">{{ detailRow.official_feedback }}</div>
        </div>

        <!-- 关联工单 -->
        <div class="dt-sec" v-if="detailRow?.related_issue_id || detailRow?.related_meeting_id">
          <div class="dt-sec-title">关联工单</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="关联运营/调研工单">
              <a v-if="detailRow?.related_issue_id" href="#" @click.prevent="openRelatedResearch(detailRow.related_issue_id)">{{ detailRow.related_issue_id }}</a>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="关联会议">
              <a v-if="detailRow?.related_meeting_id" href="#" @click.prevent="openRelatedMeeting(detailRow.related_meeting_id)">{{ detailRow.related_meeting_id }}</a>
              <span v-else>-</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 案例信息 -->
        <div class="dt-sec" v-if="detailRow?.case_info">
          <div class="dt-sec-title">案例信息</div>
          <div class="dt-desc">{{ detailRow.case_info }}</div>
        </div>

        <!-- 备注 -->
        <div class="dt-sec" v-if="detailRow?.remark">
          <div class="dt-sec-title">备注</div>
          <div class="dt-desc">{{ detailRow.remark }}</div>
        </div>

        <!-- 附件 -->
        <div class="dt-sec" v-if="detailAttachments.length">
          <div class="dt-sec-title">附件</div>
          <div class="att-list">
            <div class="att-item" v-for="a in detailAttachments" :key="a.name">
              <el-icon><Document /></el-icon>
              <a class="att-link" :href="`/api/v1/research/issues/${detailRow?.id}/attachments/download?filename=${encodeURIComponent(a.name)}`" target="_blank">{{ a.name }}</a>
              <span class="att-size">{{ a.size }}</span>
            </div>
          </div>
        </div>

        <!-- 关联业务知识 -->
        <KnowledgeLinker
          v-if="detailRow?.id"
          source-type="research"
          :source-id="detailRow.id"
          :domain-code="detailRow.domain_code"
        />
        <div v-if="detailRow?.obsidian_path" class="dt-sec">
          <div class="dt-sec-title">已沉淀知识笔记</div>
          <div class="dt-link-row">
            <div class="lk-ico"><el-icon><Document /></el-icon></div>
            <div>
              <div class="dt-link-name">{{ noteTitle(detailRow.obsidian_path) }}</div>
              <div class="dt-link-meta">{{ detailRow.obsidian_path }}</div>
            </div>
          </div>
        </div>

        <!-- 邮件督办记录 -->
        <div class="dt-sec">
          <div class="dt-sec-title">邮件督办记录</div>
          <div class="email-log">
            <div v-for="(e, i) in supervisionList" :key="i" class="email-log-item">
              <div class="el-ico"><el-icon><Promotion /></el-icon></div>
              <div>
                <div class="email-log-to">收件：{{ e.to }}</div>
                <div class="email-log-time">{{ e.time }}</div>
                <div class="email-log-result">{{ e.result }}</div>
              </div>
            </div>
            <div v-if="!supervisionList.length" class="dt-link-meta">暂无督办邮件</div>
          </div>
          <div class="dt-link-meta" style="margin-top:6px;font-size:11px;color:var(--text-muted)">
            收件人通过「统一邮件中心」按姓名解析，不拼接邮箱地址
          </div>
        </div>
      </div>
      <template #footer>
        <div class="drawer-foot">
          <el-select v-model="nextStatus" size="small" class="w-s" placeholder="选择状态">
            <el-option v-for="s in STATUS_OPTIONS" :key="s.key" :label="s.label" :value="s.key" />
          </el-select>
          <el-button :loading="advanceLoading" :disabled="!nextStatus || nextStatus === detailRow?.status" @click="changeStatusFromDetail">
            <el-icon><RefreshRight /></el-icon><span>确认变更</span>
          </el-button>
          <el-button @click="openEditFromDetail"><el-icon><Edit /></el-icon><span>编辑</span></el-button>
          <el-dropdown @command="(cmd) => openSupervise(detailRow, cmd)">
            <el-button type="primary"><el-icon><Promotion /></el-icon><span>邮件督办</span><el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="urge">催办</el-dropdown-item>
                <el-dropdown-item command="sync">同步通知</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>
    </el-drawer>

    <!-- 录入 / 编辑弹窗 -->
    <el-dialog
      v-model="entryVisible"
      :title="isEdit ? '编辑调研工单' : '录入调研工单'"
      width="720px"
      destroy-on-close
      :before-close="handleEntryBeforeClose"
    >
      <el-form :model="form" label-width="100px" :rules="entryRules" ref="formRef">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="工单标题" prop="title">
              <EnlargeInput v-model="form.title" placeholder="简短描述问题或任务" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="子类" prop="sub_type">
              <el-select v-model="form.sub_type" style="width:100%">
                <el-option v-for="t in SUB_TYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="地市" prop="city">
              <el-select v-model="form.city" clearable style="width:100%">
                <el-option v-for="c in CITY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="问题性质">
              <el-select v-model="form.issue_nature" clearable style="width:100%">
                <el-option v-for="n in NATURE_OPTIONS" :key="n.value" :label="n.label" :value="n.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="基本情况">
          <EnlargeInput v-model="form.basic_info" type="textarea" :rows="2" placeholder="调研背景、对象、时间等基本情况" />
        </el-form-item>

        <el-form-item label="情况说明" prop="situation_desc">
          <EnlargeInput v-model="form.situation_desc" type="textarea" :rows="3" placeholder="调研中发现的具体问题及影响范围" />
        </el-form-item>

        <el-form-item label="地市建议">
          <EnlargeInput v-model="form.city_suggestion" type="textarea" :rows="2" placeholder="地市层面提出的建议或措施" />
        </el-form-item>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="反馈人">
              <el-input v-model="form.feedback_name" placeholder="反馈人姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="form.feedback_phone" placeholder="联系电话" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="案例信息">
          <EnlargeInput v-model="form.case_info" type="textarea" :rows="2" placeholder="典型案例描述" />
        </el-form-item>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="信息来源">
              <el-input v-model="form.source" placeholder="如：现场调研、电话访谈" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="反馈截止日期">
              <el-date-picker v-model="form.feedback_deadline" type="date" value-format="YYYY-MM-DD" placeholder="选填" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="厂家责任人">
              <StaffSelect v-model="form.vendor_handlers" multiple placeholder="从人员中台选择" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="业务管理员">
              <StaffSelect v-model="form.business_admin" multiple placeholder="从人员中台选择" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="评估结果">
          <EnlargeInput v-model="form.assessment_result" type="textarea" :rows="2" placeholder="对问题的定性评估结论" />
        </el-form-item>

        <el-form-item label="解决方案">
          <EnlargeInput v-model="form.solution" type="textarea" :rows="2" placeholder="拟采取的解决方案或整改措施" />
        </el-form-item>

        <el-form-item label="正式反馈">
          <EnlargeInput v-model="form.official_feedback" type="textarea" :rows="2" placeholder="正式反馈内容" />
        </el-form-item>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="版本计划">
              <el-input v-model="form.version_plan" placeholder="如：v2.6.0" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划完成">
              <el-date-picker v-model="form.go_live_date" type="date" value-format="YYYY-MM-DD" placeholder="选填" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="业务领域">
              <BusinessDomainSelect v-model="form.domain_code" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="form.impact_level" style="width:100%">
                <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="关联需求">
              <el-input v-model="form.related_req_id" placeholder="需求编号" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联会议">
              <el-input v-model="form.related_meeting_id" placeholder="会议ID（选填）" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <EnlargeInput v-model="form.remark" type="textarea" :rows="2" placeholder="其他补充说明" />
        </el-form-item>

        <el-form-item label="附件">
          <div ref="attachmentZone" class="att-block paste-attachment-zone" tabindex="0">
            <el-button size="small" :loading="attUploading || isPasting" @click="pickAttachment">+ 添加附件</el-button>
            <input ref="attInput" type="file" style="display:none" @change="onAttachmentPicked" />
            <div class="att-list" v-if="form.attachments.length">
              <div class="att-item" v-for="a in form.attachments" :key="a.name">
                <el-icon><Document /></el-icon>
                <span class="att-name" :title="a.name">{{ a.name }}</span>
                <span class="att-size">{{ a.size }}</span>
                <el-button link type="danger" size="small" :loading="attDeleting === a.name" @click="removeAttachment(a.name)">删除</el-button>
              </div>
            </div>
            <div class="att-hint" v-else>暂无附件，点击此区域后按 Ctrl+V 可粘贴截图/文件</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleEntryBeforeClose(() => { entryVisible = false })">取消</el-button>
        <el-button type="primary" :loading="entryLoading" @click="submitEntry">确定</el-button>
      </template>
    </el-dialog>

    <!-- 统一邮件弹窗 -->
    <MailComposeDialog
      v-model="mailDialogVisible"
      :title="mailDialogTitle"
      :default-to="mailDialogTo"
      :default-subject="mailDialogSubject"
      :default-body="mailDialogBody"
      :scene="mailDialogScene"
      :variables="mailDialogVariables"
      value-key="email"
      @success="recordSupervise"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Edit, Promotion, RefreshRight, Document, ArrowDown } from '@element-plus/icons-vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import KnowledgeLinker from '@/components/Common/KnowledgeLinker.vue'
import BusinessDomainSelect from '@/components/Common/BusinessDomainSelect.vue'
import { researchApi } from '@/api/research'
import { formatDateTime } from '@/utils/format'
import request from '@/api/request'
import { useDrawerDraft } from '@/composables/useDrawerDraft'
import { usePasteUpload } from '@/composables/usePasteUpload.js'

// ---- 常量定义 ----
const CITY_OPTIONS = [
  { value: 'nanjing', label: '南京' },
  { value: 'suzhou', label: '苏州' },
  { value: 'wuxi', label: '无锡' },
  { value: 'changzhou', label: '常州' },
  { value: 'zhenjiang', label: '镇江' },
  { value: 'yangzhou', label: '扬州' },
  { value: 'taizhou', label: '泰州' },
  { value: 'nantong', label: '南通' },
  { value: 'yancheng', label: '盐城' },
  { value: 'huaian', label: '淮安' },
  { value: 'suqian', label: '宿迁' },
  { value: 'xuzhou', label: '徐州' },
  { value: 'lianyungang', label: '连云港' },
]
const CITY_LABELS = Object.fromEntries(CITY_OPTIONS.map((c) => [c.value, c.label]))

const SUB_TYPE_OPTIONS = [
  { value: 'leader_research', label: '领导调研' },
  { value: 'frontline_station', label: '一线驻点' },
]
const SUB_TYPE_LABELS = Object.fromEntries(SUB_TYPE_OPTIONS.map((t) => [t.value, t.label]))

const NATURE_OPTIONS = [
  { value: 'bug', label: 'BUG' },
  { value: 'optimization', label: '优化' },
  { value: 'invalid', label: '非有效问题' },
]
const NATURE_LABELS = Object.fromEntries(NATURE_OPTIONS.map((n) => [n.value, n.label]))

const PRIORITY_OPTIONS = [
  { value: 'P0', label: '严重' },
  { value: 'P1', label: '高' },
  { value: 'P2', label: '中' },
  { value: 'P3', label: '低' },
]

const STATUS_FLOW = [
  { key: 'pending', label: '待处理' },
  { key: 'processing', label: '处理中' },
  { key: 'verify', label: '验证中' },
  { key: 'resolved', label: '已解决' },
  { key: 'closed', label: '已关闭' },
]
const STATUS_OPTIONS = [
  ...STATUS_FLOW,
  { key: 'suspended', label: '已挂起' },
]
const statusBadgeOptions = {
  pending: { label: '待处理', type: 'danger' },
  processing: { label: '处理中', type: 'warning' },
  verify: { label: '验证中', type: 'primary' },
  resolved: { label: '已解决', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
  suspended: { label: '已挂起', type: 'info' },
}

const subTypeTag = (val) => val === 'leader_research' ? 'primary' : 'success'
const natureTag = (val) => {
  if (val === 'bug') return 'danger'
  if (val === 'optimization') return 'warning'
  return 'info'
}

// ---- 列表 / 统计 ----
const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')

const filterCity = ref('')
const filterSubType = ref('')
const filterStatus = ref('')
const filterNature = ref('')

const stats = reactive({
  total: 0, pending: 0, processing: 0, verify: 0, resolved: 0, closed: 0,
  overdue: 0, closed_loop_rate: 0,
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await researchApi.listIssues({
      keyword: keyword.value || undefined,
      city: filterCity.value || undefined,
      sub_type: filterSubType.value || undefined,
      status: filterStatus.value || undefined,
      issue_nature: filterNature.value || undefined,
      page: pagination.page,
      page_size: pagination.page_size,
    })
    tableData.value = res.items || []
    pagination.total = res.total || 0
  } catch (e) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await researchApi.getStats()
    Object.assign(stats, {
      total: res.total || 0, pending: res.pending || 0, processing: res.processing || 0,
      verify: res.verify || 0, resolved: res.resolved || 0, closed: res.closed || 0,
      overdue: res.overdue || 0, closed_loop_rate: res.closed_loop_rate || 0,
    })
  } catch (e) {
    ElMessage.error('加载统计失败')
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

// ---- 详情抽屉 ----
const detailVisible = ref(false)
const detailRow = ref(null)
const detailLoading = ref(false)
const advanceLoading = ref(false)
const nextStatus = ref('')
const currentIdx = computed(() => STATUS_FLOW.findIndex((s) => s.key === detailRow.value?.status))
const stepClass = (idx) => (idx < currentIdx.value ? 'done' : idx === currentIdx.value ? 'active' : '')

const supervisionRecords = reactive({})
const supervisionList = computed(() => (detailRow.value && supervisionRecords[detailRow.value.id]) || [])
const detailAttachments = computed(() => parseAttachments(detailRow.value?.attachments))

const noteTitle = (path) => (path || '').split('/').pop().replace(/\.md$/, '') || path

const openDetail = async (row) => {
  detailRow.value = row
  nextStatus.value = row?.status || ''
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await researchApi.getIssue(row.id)
    detailRow.value = res
    nextStatus.value = res.status || ''
  } catch (e) {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

const refreshDetail = async () => {
  if (!detailRow.value?.id) return
  try {
    const res = await researchApi.getIssue(detailRow.value.id)
    detailRow.value = res
  } catch (e) { /* 保留旧值 */ }
}

const changeStatusFromDetail = async () => {
  if (!detailRow.value || !nextStatus.value || nextStatus.value === detailRow.value.status) return
  advanceLoading.value = true
  try {
    await researchApi.updateStatus(detailRow.value.id, nextStatus.value)
    ElMessage.success('状态已更新')
    await refreshDetail()
    nextStatus.value = detailRow.value?.status || ''
    loadData(); loadStats()
  } catch (e) {
    ElMessage.error('状态更新失败')
  } finally {
    advanceLoading.value = false
  }
}

// ---- 列表快速改状态 ----
const statusLoadingMap = ref({})
const changeStatus = async (row, status) => {
  if (!row || row.status === status) return
  statusLoadingMap.value[row.id] = true
  try {
    await researchApi.updateStatus(row.id, status)
    ElMessage.success('状态已更新')
    loadData(); loadStats()
    if (detailVisible.value && detailRow.value?.id === row.id) {
      await refreshDetail()
      nextStatus.value = detailRow.value?.status || ''
    }
  } catch (e) {
    ElMessage.error('状态更新失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    delete statusLoadingMap.value[row.id]
  }
}

// ---- 关联跳转 ----
const openRelatedResearch = async (issueId) => {
  try {
    const res = await researchApi.getIssue(issueId)
    detailRow.value = res
    nextStatus.value = res.status || ''
  } catch (e) {
    ElMessage.error('加载关联工单失败')
  }
}

const openRelatedMeeting = (meetingId) => {
  // 跳转至会议列表并定位到对应会议（二期扩展）
  window.open(`/meeting/list?meetingId=${meetingId}`, '_self')
}

// ---- 录入 / 编辑 ----
const entryVisible = ref(false)
const isEdit = ref(false)
const entryLoading = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null, issue_no: '', title: '', sub_type: 'leader_research', status: 'pending',
  city: '', basic_info: '', situation_desc: '', city_suggestion: '',
  feedback_name: '', feedback_phone: '', case_info: '',
  source: '', feedback_deadline: '', remark: '',
  vendor_handlers: [], business_admin: [],
  assessment_result: '', issue_nature: '', solution: '',
  related_req_id: '', related_issue_id: null, related_meeting_id: null,
  version_plan: '', official_feedback: '',
  domain_code: '', impact_level: 'P2', go_live_date: '',
  attachments: [],
})

const {
  restoreDraft: restoreEntryDraft,
  clearDraft: clearEntryDraft,
  handleBeforeClose: handleEntryBeforeClose,
} = useDrawerDraft('research-entry', form, {
  keySuffix: () => form.id ?? 'new',
  onBeforeClose() {
    if (entryLoading.value) return false
  },
})

const entryRules = {
  title: [{ required: true, message: '请输入工单标题', trigger: 'blur' }],
  sub_type: [{ required: true, message: '请选择子类', trigger: 'change' }],
  situation_desc: [{ required: true, message: '请输入情况说明', trigger: 'blur' }],
  vendor_handlers: [{ required: true, type: 'array', min: 1, message: '请至少选择一名厂家责任人', trigger: 'change' }],
}

const generateIssueNo = () => {
  const d = new Date()
  const ds = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
  return `RES-${ds}-${Math.floor(Math.random() * 900 + 100)}`
}

const openEntry = () => {
  isEdit.value = false
  Object.assign(form, {
    id: null, issue_no: '', title: '', sub_type: 'leader_research', status: 'pending',
    city: '', basic_info: '', situation_desc: '', city_suggestion: '',
    feedback_name: '', feedback_phone: '', case_info: '',
    source: '', feedback_deadline: '', remark: '',
    vendor_handlers: [], business_admin: [],
    assessment_result: '', issue_nature: '', solution: '',
    related_req_id: '', related_issue_id: null, related_meeting_id: null,
    version_plan: '', official_feedback: '',
    domain_code: '', impact_level: 'P2', go_live_date: '',
    attachments: [],
  })
  if (restoreEntryDraft()) ElMessage.info('已恢复上次未保存的草稿')
  entryVisible.value = true
}

const openEditFromDetail = async () => {
  if (!detailRow.value) return
  isEdit.value = true
  Object.assign(form, {
    id: detailRow.value.id,
    issue_no: detailRow.value.issue_no,
    title: detailRow.value.title,
    sub_type: detailRow.value.sub_type || 'leader_research',
    status: detailRow.value.status,
    city: detailRow.value.city || '',
    basic_info: detailRow.value.basic_info || '',
    situation_desc: detailRow.value.situation_desc || '',
    city_suggestion: detailRow.value.city_suggestion || '',
    feedback_name: detailRow.value.feedback_name || '',
    feedback_phone: detailRow.value.feedback_phone || '',
    case_info: detailRow.value.case_info || '',
    source: detailRow.value.source || '',
    feedback_deadline: detailRow.value.feedback_deadline || '',
    remark: detailRow.value.remark || '',
    vendor_handlers: (detailRow.value.vendor_handlers || '').split(',').filter(Boolean),
    business_admin: (detailRow.value.business_admin || '').split(',').filter(Boolean),
    assessment_result: detailRow.value.assessment_result || '',
    issue_nature: detailRow.value.issue_nature || '',
    solution: detailRow.value.solution || '',
    related_req_id: detailRow.value.related_req_id || '',
    related_issue_id: detailRow.value.related_issue_id || null,
    related_meeting_id: detailRow.value.related_meeting_id || null,
    version_plan: detailRow.value.version_plan || '',
    official_feedback: detailRow.value.official_feedback || '',
    domain_code: detailRow.value.domain_code || '',
    impact_level: detailRow.value.impact_level || 'P2',
    go_live_date: detailRow.value.go_live_date || '',
    attachments: parseAttachments(detailRow.value.attachments),
  })
  if (restoreEntryDraft()) ElMessage.info('已恢复上次未保存的草稿')
  entryVisible.value = true
}

const submitEntry = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    const payload = {
      issue_no: form.issue_no || generateIssueNo(),
      title: form.title.trim(),
      sub_type: form.sub_type,
      status: 'pending',
      city: form.city || null,
      basic_info: (form.basic_info || '').trim() || null,
      situation_desc: form.situation_desc.trim(),
      city_suggestion: (form.city_suggestion || '').trim() || null,
      feedback_name: form.feedback_name || null,
      feedback_phone: form.feedback_phone || null,
      case_info: (form.case_info || '').trim() || null,
      source: form.source || null,
      feedback_deadline: form.feedback_deadline || null,
      remark: (form.remark || '').trim() || null,
      vendor_handlers: (form.vendor_handlers || []).join(','),
      business_admin: (form.business_admin || []).join(','),
      assessment_result: (form.assessment_result || '').trim() || null,
      issue_nature: form.issue_nature || null,
      solution: (form.solution || '').trim() || null,
      related_req_id: form.related_req_id || null,
      related_issue_id: form.related_issue_id || null,
      related_meeting_id: form.related_meeting_id || null,
      version_plan: form.version_plan || null,
      official_feedback: (form.official_feedback || '').trim() || null,
      domain_code: form.domain_code || null,
      impact_level: form.impact_level,
      go_live_date: form.go_live_date || null,
    }
    entryLoading.value = true
    try {
      let newId
      if (isEdit.value && form.id) {
        await researchApi.updateIssue(form.id, payload)
        newId = form.id
        ElMessage.success('更新成功')
      } else {
        const res = await researchApi.createIssue(payload)
        newId = res?.id
        ElMessage.success('创建成功')
      }
      clearEntryDraft()
      entryVisible.value = false
      loadData(); loadStats()
      if (detailVisible.value) refreshDetail()
    } catch (e) {
      ElMessage.error('操作失败：' + (e?.response?.data?.message || e.message || '未知错误'))
    } finally {
      entryLoading.value = false
    }
  })
}

// ---- 附件管理 ----
const attInput = ref(null)
const attachmentZone = ref(null)
const attUploading = ref(false)
const attDeleting = ref('')

function parseAttachments(raw) {
  if (!raw) return []
  try {
    const d = JSON.parse(raw)
    return Array.isArray(d) ? d : []
  } catch (e) {
    return []
  }
}

const pickAttachment = () => attInput.value && attInput.value.click()

const onAttachmentPicked = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  if (!form.id) {
    ElMessage.warning('请先保存工单后再上传附件')
    e.target.value = ''
    return
  }
  attUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await request.post(`/research/issues/${form.id}/attachments/upload`, fd)
    form.attachments = res.data || []
    ElMessage.success('附件已上传')
  } catch (err) {
    ElMessage.error('上传失败：' + (err?.response?.data?.message || err.message || '未知错误'))
  } finally {
    attUploading.value = false
    e.target.value = ''
  }
}

const removeAttachment = async (name) => {
  if (!form.id) return
  attDeleting.value = name
  try {
    const res = await request.post(`/research/issues/${form.id}/attachments/delete?filename=${encodeURIComponent(name)}`)
    form.attachments = res.data || []
    ElMessage.success('已删除')
  } catch (err) {
    ElMessage.error('删除失败：' + (err?.response?.data?.message || err.message || '未知错误'))
  } finally {
    attDeleting.value = ''
  }
}

const { isPasting } = usePasteUpload({
  targetRef: attachmentZone,
  enabled: computed(() => entryVisible.value),
  onFiles: async (files) => {
    if (!form.id) {
      ElMessage.warning('请先保存工单后再上传附件')
      return
    }
    attUploading.value = true
    try {
      for (const file of files) {
        const fd = new FormData()
        fd.append('file', file)
        const res = await request.post(`/research/issues/${form.id}/attachments/upload`, fd)
        form.attachments = res.data || []
      }
      ElMessage.success(`已粘贴上传 ${files.length} 个附件`)
    } catch (err) {
      ElMessage.error('粘贴上传失败：' + (err?.response?.data?.message || err.message || '未知错误'))
      throw err
    } finally {
      attUploading.value = false
    }
  },
})

// ---- 统一邮件弹窗 ----
const mailDialogVisible = ref(false)
const mailDialogTitle = ref('发送督办邮件')
const mailDialogTo = ref([])
const mailDialogSubject = ref('')
const mailDialogBody = ref('')
const mailDialogScene = ref('research_urge')
const mailDialogVariables = ref({})
const _researchIssue = ref(null)

const buildResearchSuperviseBody = (row, scene = 'urge') => {
  const natureLabel = row.issue_nature ? (NATURE_LABELS[row.issue_nature] || row.issue_nature) : ''
  const cityLabel = row.city ? (CITY_LABELS[row.city] || row.city) : ''
  return [
    scene === 'urge' ? '## 催办通知' : '## 工单进展同步',
    '',
    '| 字段 | 内容 |',
    '|------|------|',
    `| 工单编号 | ${row.issue_no || row.id || ''} |`,
    `| 标题 | ${row.title || ''} |`,
    `| 地市 | ${cityLabel || ''} |`,
    `| 子类 | ${SUB_TYPE_LABELS[row.sub_type] || row.sub_type || ''} |`,
    `| 问题性质 | ${natureLabel || ''} |`,
    `| 厂家责任人 | ${row.vendor_handlers || ''} |`,
    `| 计划完成日期 | ${row.go_live_date || ''} |`,
    `| 当前状态 | ${statusBadgeOptions[row.status]?.label || row.status || ''} |`,
    '',
    '### 情况说明',
    row.situation_desc || '（无）',
    '',
    '---',
    scene === 'urge'
      ? '请尽快处理该调研工单，如有疑问请及时沟通。'
      : '请知悉该调研工单最新进展，如有疑问请及时沟通。',
  ].join('\n')
}

const openSupervise = (row, scene = 'urge') => {
  if (!row) return
  _researchIssue.value = row
  mailDialogTitle.value = scene === 'urge' ? '发送催办邮件' : '发送同步通知'
  mailDialogTo.value = (row.vendor_handlers || '').split(',').filter(Boolean)
  mailDialogSubject.value = (scene === 'urge' ? '催办：' : '同步：') + (row.title || row.issue_no || '')
  mailDialogVariables.value = {
    no: row.issue_no || String(row.id || ''),
    title: row.title || '',
    city: CITY_LABELS[row.city] || row.city || '',
    subType: SUB_TYPE_LABELS[row.sub_type] || row.sub_type || '',
    nature: NATURE_LABELS[row.issue_nature] || row.issue_nature || '',
    vendorHandler: row.vendor_handlers || '',
    resolveDate: row.go_live_date || '',
    status: statusBadgeOptions[row.status]?.label || row.status || '',
    description: row.situation_desc || '（无）',
  }
  mailDialogBody.value = buildResearchSuperviseBody(row, scene)
  mailDialogScene.value = scene === 'sync' ? 'research_sync' : 'research_urge'
  mailDialogVisible.value = true
}

const recordSupervise = () => {
  const issue = _researchIssue.value
  if (!issue?.id) return
  const rec = {
    to: (issue.vendor_handlers || '').split(',').filter(Boolean).join('、'),
    time: formatDateTime(new Date()),
    result: '已送达（统一邮件中心）',
  }
  if (!supervisionRecords[issue.id]) supervisionRecords[issue.id] = []
  supervisionRecords[issue.id].push(rec)
}

onMounted(async () => {
  await loadData()
  loadStats()
})
</script>

<style scoped>
.research-issue-view { padding: 20px; }
.page-head { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0; }

.stats-row { margin-bottom: 18px; }
.stat-item { text-align: center; padding: 10px 0; }
.stat-value { font-size: 26px; font-weight: 700; color: #303133; }
.stat-label { font-size: 13px; color: #606266; margin-top: 6px; }
.status-pending .stat-value { color: #f56c6c; }
.status-processing .stat-value { color: #e6a23c; }
.status-verify .stat-value { color: #409eff; }
.status-resolved .stat-value { color: #67c23a; }
.status-closed .stat-value { color: #909399; }
.status-overdue .stat-value { color: #f56c6c; }
.status-loop .stat-value { color: #409eff; }

.filter-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }

.wo-table { margin-top: 4px; }
.iss-title { font-weight: 600; color: var(--text-primary); cursor: pointer; }
.iss-title:hover { color: var(--accent); }
.handler-tag { margin: 0 4px 4px 0; }
.wo-pager { display: flex; justify-content: flex-end; margin-top: 16px; }

.row-actions { display: flex; align-items: center; gap: 4px; flex-wrap: nowrap; white-space: nowrap; }

.att-block { display: flex; flex-direction: column; gap: 8px; }
.att-list { display: flex; flex-direction: column; gap: 6px; }
.att-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--surface); }
.att-item .el-icon { color: var(--accent); }
.att-name { flex: 1; font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.att-link { flex: 1; font-size: 13px; color: var(--accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-decoration: none; }
.att-link:hover { text-decoration: underline; }
.att-size { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.att-hint { font-size: 12px; color: var(--text-muted); }
.paste-attachment-zone { outline: none; border-radius: 4px; transition: box-shadow 0.2s, background-color 0.2s; padding: 8px; margin: -8px; }
.paste-attachment-zone:focus-visible { box-shadow: 0 0 0 2px var(--el-color-primary-light-5); background-color: var(--el-fill-color-light) }

.drawer-body-inner { padding: 4px 4px 8px; }
.detail-stepper { padding: 4px 0 18px; }
.dt-sec { border-top: 1px solid var(--border-subtle); padding: 18px 4px; }
.dt-sec-title { font-size: 13px; font-weight: 700; color: var(--text-secondary); margin-bottom: 14px; }
.dt-desc { font-size: 13.5px; line-height: 1.75; color: var(--text-secondary); background: var(--border-subtle); border-radius: 11px; padding: 14px 16px; }
.dt-link-row { display: flex; align-items: center; gap: 10px; padding: 11px 13px; border: 1px solid var(--border-subtle); border-radius: 9px; margin-bottom: 8px; }
.lk-ico { width: 30px; height: 30px; border-radius: 8px; background: var(--warning-soft); color: var(--warning); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.dt-link-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.dt-link-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; word-break: break-all; }
.email-log { display: flex; flex-direction: column; gap: 8px; }
.email-log-item { display: flex; align-items: flex-start; gap: 10px; padding: 11px 13px; background: var(--info-soft); border-radius: 9px; }
.el-ico { width: 26px; height: 26px; border-radius: 7px; background: var(--info); color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 13px; }
.email-log-to { font-size: 12.5px; font-weight: 600; color: var(--text-primary); }
.email-log-time { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.email-log-result { font-size: 11px; color: var(--success); font-weight: 600; }
.drawer-foot { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }
.dot-pending { background: #f56c6c; }
.dot-processing { background: #e6a23c; }
.dot-verify { background: #409eff; }
.dot-resolved { background: #67c23a; }
.dot-closed { background: #909399; }
.dot-suspended { background: #909399; }
</style>
