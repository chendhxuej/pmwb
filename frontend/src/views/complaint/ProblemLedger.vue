<template>
  <div class="problem-ledger">
    <PageHeader title="共性问题台账" :subtitle="subTitle">
      <template #actions>
        <el-button :icon="MagicStick" :loading="scanning" @click="doScan(false)">扫描候选（预览）</el-button>
        <el-button :icon="Promotion" :disabled="!urgeCnt" @click="doProblemsUrge">
          问题督办（{{ urgeCnt }}）
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">手工立问题</el-button>
      </template>
    </PageHeader>

    <!-- KPI 区 -->
    <div class="pm-stat-grid pm-stat-grid--5">
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">待确认候选</span></div>
        <div class="pm-stat__val" :class="kpi.candidate ? 'is-warning' : 'is-success'">{{ kpi.candidate }}</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">在办问题</span></div>
        <div class="pm-stat__val" :class="kpi.inflight ? 'is-accent' : 'is-success'">{{ kpi.inflight }}<span class="pm-stat__unit">个</span></div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">待闭环建议</span></div>
        <div class="pm-stat__val" :class="suggestions.length ? 'is-success' : ''">{{ suggestions.length }}<span class="pm-stat__unit">条</span></div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">长期未闭环</span></div>
        <div class="pm-stat__val" :class="kpi.longRunning ? 'is-danger' : 'is-success'">{{ kpi.longRunning }}</div>
        <div class="pm-stat__sub">在办 ≥12 周</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">闭环后复发</span></div>
        <div class="pm-stat__val" :class="kpi.reopen ? 'is-danger' : 'is-success'">{{ kpi.reopen }}</div>
        <div class="pm-stat__sub">待重开</div>
      </div>
    </div>

    <!-- 闭环建议 -->
    <el-alert v-if="suggestions.length" type="success" :closable="false" class="sug-alert">
      <template #title>
        {{ suggestions.length }} 个问题满足闭环条件（关联措施全部验证有效且连续零复发），请人工确认闭环
      </template>
      <div v-for="s in suggestions" :key="s.problem_no" class="sug-line">
        <b>{{ s.problem_no }}</b> {{ s.title }}（{{ s.reason }}）
        <el-button size="small" type="success" text @click="doClose(s)">确认闭环</el-button>
      </div>
    </el-alert>

    <!-- 台账：默认只展示「已复核、未闭环」的问题；候选独立页签（2026-11-04 收窄） -->
    <section class="card">
      <el-tabs v-model="activeTab" class="ledger-tabs">
        <el-tab-pane :label="`在办问题（已复核未闭环 · ${inflightRows.length}）`" name="open">
          <div class="tab-bar">
            <el-select v-model="statusFilter" clearable size="small" style="width: 150px" placeholder="全部在办状态">
              <el-option v-for="s in inflightStatusDefs" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-select v-model="statWeek" size="small" style="width: 148px" @change="load"
              placeholder="观察周">
              <el-option v-for="w in weekOptions" :key="w" :label="w === latestWeek ? `${w}（最新）` : w" :value="w" />
            </el-select>
            <span class="tab-hint">
              「增量」= 所选周该问题新增投诉单量；「累计」= 截至所选周的单量总和。点表头可切换增量/累计排序
            </span>
          </div>
          <el-table ref="pmTbl2" v-loading="loading" :data="filteredRows" size="default" border stripe
            :default-sort="{ prop: 'week_delta', order: 'descending' }" @sort-change="onSortChange">
            <el-table-column prop="problem_no" label="问题编号" width="146">
              <template #default="{ row }"><b>{{ row.problem_no }}</b></template>
            </el-table-column>
            <el-table-column prop="title" label="问题（根因摘要）" min-width="230" show-overflow-tooltip />
            <el-table-column prop="module_problem_id" label="归因锚点" width="132">
              <template #default="{ row }">
                <el-tag v-if="row.module_problem_id" type="success" size="small" effect="plain">模块·{{ row.module_problem_id }}</el-tag>
                <span v-else>{{ row.rootcause_no || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="92" align="center">
              <template #default="{ row }">
                <el-tag :type="statusTone(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="week_delta" label="增量" width="104" align="center" sortable="custom">
              <template #default="{ row }">
                <span class="delta-num" :class="{ hot: row.week_delta >= 3 }">{{ row.week_delta ?? 0 }}</span>
                <span class="col-unit">单</span>
              </template>
            </el-table-column>
            <el-table-column prop="cum_total" label="累计" width="104" align="center" sortable="custom">
              <template #default="{ row }">
                <span class="cum-num">{{ row.cum_total ?? 0 }}</span><span class="col-unit">单</span>
              </template>
            </el-table-column>
            <el-table-column label="措施" width="96" align="center">
              <template #default="{ row }">
                <span :class="{ 'no-action': !row.action_cnt }">{{ row.effective_cnt ?? 0 }} / {{ row.action_cnt }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="owner" label="责任人" width="92" show-overflow-tooltip />
            <el-table-column label="操作" width="150" fixed="right" align="center">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="openDetail(row)">详情</el-button>
                <el-button size="small" type="primary" text @click="openIssueForRow(row)">建工单</el-button>
                <el-dropdown v-if="nextTargets(row.status).length" trigger="click"
                  @command="(cmd) => doTransition(row, cmd)">
                  <el-button size="small" text class="more-btn">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-for="t in nextTargets(row.status)" :key="t.value" :command="t">
                        {{ t.label }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!inflightRows.length" description="暂无在办问题——去「待确认候选」把 AI 识别的问题确认入账" :image-size="60" />
        </el-tab-pane>

        <el-tab-pane :label="`待确认候选（${candidates.length}）`" name="candidate">
          <div class="tab-bar">
            <span class="tab-hint">候选来源：<b>主要投诉点</b>（闭集模块问题，零 LLM）+ 旧根因簇扫描；<b>确认入账</b>后才进入台账、才能挂措施</span>
          </div>
          <el-table ref="pmTbl1" v-if="candidates.length" :data="candidates" size="default" border>
          <el-table-column prop="problem_no" label="编号" width="150">
            <template #default="{ row }"><b>{{ row.problem_no }}</b></template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
          <el-table-column prop="category_l2" label="场景" min-width="130" show-overflow-tooltip />
          <el-table-column label="归因锚点" width="150">
            <template #default="{ row }">
              <el-tag v-if="row.module_problem_id" type="success" size="small" effect="plain">模块·{{ row.module_problem_id }}</el-tag>
              <span v-else>{{ row.rootcause_no || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="命中规则" width="180">
            <template #default="{ row }">
              <el-tag v-for="h in ruleHits(row.rule_hits)" :key="h" size="small" class="rule-tag" type="warning">{{ h }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="证据摘要" min-width="200">
            <template #default="{ row }">{{ evidenceBrief(row.evidence) }}</template>
          </el-table-column>
          <el-table-column prop="week_cnt" label="当周单量" width="90" align="center" />
          <el-table-column label="操作" width="196" fixed="right" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" text @click="doConfirmOpen(row)">入账</el-button>
              <el-button size="small" text @click="openMerge(row)">合并</el-button>
              <el-button size="small" text type="danger" @click="doIgnore(row)">忽略</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无待确认候选（每周导入分析后自动生成）" :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </section>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="detail?.problem_no || '问题详情'" size="62%">
      <div v-if="detail" class="detail-body">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="标题" :span="2">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="场景">{{ detail.category_l2 }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTone(detail.status)" size="small">{{ statusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="责任人">{{ detail.owner || '—' }}</el-descriptions-item>
          <el-descriptions-item label="首见/末见周">{{ detail.first_week }} / {{ detail.last_week || '—' }}</el-descriptions-item>
          <el-descriptions-item label="当周/累计单量">{{ detail.week_cnt }} / {{ detail.total_cnt }}</el-descriptions-item>
          <el-descriptions-item label="复发">{{ detail.recur_cnt }} 单（连续 {{ detail.recur_weeks }} 周）</el-descriptions-item>
          <el-descriptions-item label="连续零复发">{{ detail.quiet_weeks }} 周</el-descriptions-item>
          <el-descriptions-item label="闭环结论">{{ detail.conclusion || '—' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="sec-title">命中规则与证据</h4>
        <div class="ev-line">
          <el-tag v-for="h in ruleHits(detail.rule_hits)" :key="h" size="small" type="warning" class="rule-tag">{{ h }}</el-tag>
          <span class="ev-text">{{ evidenceBrief(detail.evidence) }}</span>
        </div>

        <h4 class="sec-title">
          关联投诉工单（{{ detailTicketTotal }} 单）
          <el-button v-if="detailTicketTotal > detailTickets.length" size="small" text type="primary"
            @click="ticketDrillVisible = true">查看全部</el-button>
        </h4>
        <el-table v-if="detailTickets.length" :data="detailTickets" size="small" border>
          <!-- 老大 2026-11-04：明细要能看出「这单怎么核查」，处理信息与 AI 分析必须直达；
               工单号/时间等运维字段弱化（窄列、灰字） -->
          <el-table-column prop="ticket_no" label="工单号" width="118">
            <template #default="{ row }"><span class="mono text-muted">{{ row.ticket_no }}</span></template>
          </el-table-column>
          <el-table-column prop="content" label="投诉内容" min-width="190" show-overflow-tooltip />
          <el-table-column label="核查过程（处理信息）" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.solution_history">{{ row.solution_history }}</span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="AI 分析总结" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.root_cause">{{ row.root_cause }}</span>
              <span v-else class="text-muted">待分析</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80" />
          <el-table-column label="已知/新增" width="88" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.known_flag === 1" size="small" type="warning">已知</el-tag>
              <el-tag v-else-if="row.known_flag === 0" size="small" type="danger">新增</el-tag>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="该问题下暂无关联工单" :image-size="48" />

        <h4 class="sec-title">周度轨迹（根因簇单量）</h4>
        <ChartLine v-if="trajectory.length" :x-data="trajectory.map(t => t.week)" height="200px"
          :series="[{ name: '周单量', type: 'line', data: trajectory.map(t => t.cnt) }]" />
        <el-empty v-else description="暂无轨迹数据" :image-size="48" />

        <h4 class="sec-title">
          关联措施（{{ detail.actions.length }}）
          <el-button type="primary" size="small" :icon="Plus" @click="openIssueDialog">建立运营工单</el-button>
        </h4>
        <el-table ref="pmTbl3" :data="detail.actions" size="small" border>
          <el-table-column prop="action_no" label="措施编号" width="140">
            <template #default="{ row }">
              <b>{{ row.action_no }}</b>
              <el-tag v-if="row.is_primary" size="small" type="primary" class="rule-tag">主</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="140" show-overflow-tooltip />
          <el-table-column prop="owner" label="责任人" width="90" />
          <el-table-column label="状态" width="96" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="actionTone(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关联工单" width="130">
            <template #default="{ row }">{{ row.issue_no || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="danger" @click="doUnlink(row)">解除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="link-row">
          <el-select v-model="linkActionNo" filterable clearable size="small" placeholder="选择措施关联到该问题" style="width: 320px">
            <el-option v-for="a in linkableActions" :key="a.action_no"
              :label="`${a.action_no} ${a.title}`" :value="a.action_no" />
          </el-select>
          <el-button size="small" type="primary" :disabled="!linkActionNo" @click="doLink">关联</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 关联工单下钻（问题详情内「查看全部」） -->
    <TicketDrillDrawer v-model="ticketDrillVisible"
      :filters="drillFilters" :title="`${detail?.problem_no || ''} 关联投诉工单`" />

    <!-- 建立运营工单（自动生成措施 + 工单，双向联动） -->
    <el-dialog v-model="issueVisible" title="建立运营工单" width="560px">
      <el-form label-width="92px" size="default">
        <el-form-item label="所属问题">
          <span class="mono">{{ detail?.problem_no }}</span>
          <span class="text-muted" style="margin-left:8px">{{ detail?.title }}</span>
        </el-form-item>
        <el-form-item label="问题场景" required>
          <el-select v-model="issueForm.l2" filterable placeholder="选择二级场景（措施口径）" style="width: 100%">
            <el-option v-for="c in l2Catalog" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="工单标题" required>
          <el-input v-model="issueForm.title" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="责任人" required>
          <el-input v-model="issueForm.owner" placeholder="多负责人用逗号分隔" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="issueForm.due_date" type="date" value-format="YYYY-MM-DD"
            placeholder="要求完成日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="代入工单明细">
          <el-select v-model="issueForm.context_weeks" style="width: 100%" @change="reloadIssueContext">
            <el-option :value="1" label="当周投诉工单（默认）" />
            <el-option :value="4" label="近 4 周" />
            <el-option :value="8" label="近 8 周" />
            <el-option :value="26" label="全周期" />
          </el-select>
        </el-form-item>
        <el-form-item label="情况说明" required>
          <el-input v-model="issueForm.desc" type="textarea" :rows="5" maxlength="2000" show-word-limit
            placeholder="已按问题自动生成总结，可直接修改或补充您想说明的内容" />
        </el-form-item>
        <el-form-item label="工单明细">
          <div v-if="ctxTickets.length" class="ctx-tickets">
            <div class="ctx-title">
              将代入 {{ ctxTickets.length }} 条投诉工单明细
              <span class="text-muted">（随工单存档，接收人按表格核查；周期切换后自动更新）</span>
            </div>
            <el-table :data="ctxTickets" size="small" border max-height="240">
              <el-table-column prop="ticket_no" label="工单号" width="140">
                <template #default="{ row }"><span class="mono text-muted">{{ row.ticket_no }}</span></template>
              </el-table-column>
              <el-table-column prop="day" label="日期" width="92" />
              <el-table-column prop="content" label="投诉内容" min-width="170" show-overflow-tooltip />
              <el-table-column prop="solution_history" label="核查过程" min-width="150" show-overflow-tooltip>
                <template #default="{ row }">{{ row.solution_history || '待核查' }}</template>
              </el-table-column>
              <el-table-column prop="root_cause" label="AI 分析" min-width="150" show-overflow-tooltip>
                <template #default="{ row }">{{ row.root_cause || '待分析' }}</template>
              </el-table-column>
            </el-table>
          </div>
          <div v-else class="text-muted">所选周期内暂无关联投诉工单，将只代入问题说明</div>
        </el-form-item>
        <el-form-item label="验收标准" required>
          <el-input v-model="issueForm.acceptance" type="textarea" :rows="2"
            placeholder="可验证，如：上线后连续 3 周该簇周单量降至 3 单以下" />
        </el-form-item>
      </el-form>
      <div class="gl-tip">
        提交后自动生成「改进措施 + 运营工单」并双向关联本问题。情况说明已按问题自动总结（可编辑补充），
        投诉工单明细按表格随工单存档，并在催办/同步邮件中以表格形式发送。工单状态流转自动回写措施状态，
        措施生效后按簇周单量自动验证压降。
      </div>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveIssue">创建并关联</el-button>
      </template>
    </el-dialog>

    <!-- 入账对话框 -->
    <el-dialog v-model="openVisible" title="候选入账（置为待处置）" width="440px">
      <el-form label-width="88px" size="default">
        <el-form-item label="问题">{{ openRow?.problem_no }}</el-form-item>
        <el-form-item label="责任人" required>
          <el-input v-model="openOwner" placeholder="多负责人用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="openVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveOpen">确认入账</el-button>
      </template>
    </el-dialog>

    <!-- 合并对话框 -->
    <el-dialog v-model="mergeVisible" title="合并候选到在办问题" width="480px">
      <el-form label-width="88px" size="default">
        <el-form-item label="候选">{{ mergeRow?.problem_no }}（{{ mergeRow?.title }}）</el-form-item>
        <el-form-item label="合并目标" required>
          <el-select v-model="mergeTarget" filterable placeholder="选择目标问题" style="width: 100%">
            <el-option v-for="p in mergeTargets" :key="p.problem_no"
              :label="`${p.problem_no} ${p.title}（${statusLabel(p.status)}）`" :value="p.problem_no" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="gl-tip">合并后候选工单归因与计数并入目标，候选置为「已合并」。</div>
      <template #footer>
        <el-button @click="mergeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveMerge">确认合并</el-button>
      </template>
    </el-dialog>

    <!-- 手工立问题 -->
    <el-dialog v-model="createVisible" title="手工立问题" width="480px">
      <el-form label-width="88px" size="default">
        <el-form-item label="场景" required>
          <el-select v-model="createForm.category_l2" filterable placeholder="二级问题场景" style="width: 100%">
            <el-option v-for="c in l2Options" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" />
        </el-form-item>
        <el-form-item label="责任人">
          <el-input v-model="createForm.owner" placeholder="留空则先入候选，多负责人逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 问题督办 -->
    <el-dialog v-model="urgeVisible" title="客诉共性问题督办" width="520px">
      <el-alert type="info" :closable="false" show-icon class="gl-tip">
        对在办问题下的超期措施按责任人聚合发送督办（复用客诉措施督办场景）。先预览，确认后真发。
      </el-alert>
      <div v-for="r in urgeResults" :key="r.owner" class="urge-line">
        <b>{{ r.owner }}</b>：
        <template v-if="r.skipped"><span class="warn">{{ r.skipped }}</span></template>
        <template v-else>
          {{ r.task_cnt }} 项 → {{ r.to }}
          <el-tag :type="r.dry_run ? 'info' : 'success'" size="small">
            {{ r.dry_run ? 'dry_run 已落库' : '已发送' }}
          </el-tag>
        </template>
      </div>
      <template #footer>
        <el-button @click="urgeVisible = false">关闭</el-button>
        <el-button v-if="!urgeDone" :loading="urging" @click="doProblemsUrge(false)">预览（dry_run）</el-button>
        <el-button v-if="urgeDone" type="danger" :loading="urging" @click="doProblemsUrge(true)">确认真发</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Plus, Promotion, ArrowDown } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import ChartLine from '@/components/Charts/ChartLine.vue'
import TicketDrillDrawer from './components/TicketDrillDrawer.vue'
import { complaintApi } from '@/api/complaint'
import { domainStatuses, allowedNext } from '@/constants/statusConfig'

const DOMAIN = 'complaint_problem'
const RULE_NAMES = { batch_cluster: 'R1批量簇', surge: 'R3环比激增', top_scene: 'R2场景TOP', recur: 'R4复发', manual: '人工' }
const SOURCE_NAMES = {
  rootcause_batch: '批量成簇',
  surge: '环比激增',
  recur: '复发',
  manual: '手工',
  // 兼容历史数据里的旧口径值
  batch_cluster: '批量簇',
  top_scene: '场景TOP',
}

const loading = ref(false)
const saving = ref(false)
const scanning = ref(false)
const rows = ref([])
const suggestions = ref([])
const allActions = ref([])
const statusFilter = ref('')
const activeTab = ref('open')

const detailVisible = ref(false)
const detail = ref(null)
const trajectory = ref([])
const linkActionNo = ref('')

// 详情页「关联投诉工单」与「建立运营工单」
const detailTickets = ref([])
const detailTicketTotal = ref(0)
const ticketDrillVisible = ref(false)
const drillFilters = ref({})
const issueVisible = ref(false)
const issueForm = ref({ l2: '', title: '', owner: '', due_date: '', acceptance: '', context_weeks: 1, desc: '' })
const ctxTickets = ref([])
const ctxLoading = ref(false)

function ctxDescPrefix() {
  return detail.value ? `由共性问题 ${detail.value.problem_no} 发起：${detail.value.title}` : ''
}

// 拉取代入上下文：summary 预填情况说明（可编辑），tickets 预览表格
async function reloadIssueContext() {
  if (!detail.value) return
  ctxLoading.value = true
  try {
    const r = await complaintApi.getIssueContext(detail.value.problem_no, issueForm.value.context_weeks || 1)
    ctxTickets.value = r.tickets || []
    issueForm.value.desc = ctxDescPrefix() + (r.summary ? `\n\n${r.summary}` : '')
  } catch (e) {
    ctxTickets.value = []
    issueForm.value.desc = ctxDescPrefix()
  } finally { ctxLoading.value = false }
}
const l2Catalog = ref([])

const openVisible = ref(false)
const openRow = ref(null)
const openOwner = ref('')
const mergeVisible = ref(false)
const mergeRow = ref(null)
const mergeTarget = ref('')
const createVisible = ref(false)
const createForm = ref({ category_l2: '', title: '', owner: '' })
const urgeVisible = ref(false)
const urgeResults = ref([])
const urgeDone = ref(false)
const urging = ref(false)

const statusDefs = computed(() => domainStatuses(DOMAIN))
const statusMap = computed(() => {
  const m = {}
  for (const s of statusDefs.value) m[s.value] = s
  return m
})

const subTitle = computed(() => {
  const inflight = rows.value.filter(r => ['open', 'resolving'].includes(r.status)).length
  return `共 ${rows.value.length} 个问题（在办 ${inflight}）｜闭环流程：周分析 → 台账确认 → 措施跟踪 → 周验证 → 闭环确认`
})

const candidates = computed(() => rows.value.filter(r => r.status === 'candidate'))
const inflightRows = computed(() => rows.value.filter(r => ['open', 'resolving'].includes(r.status)))
const inflightStatusDefs = computed(() => statusDefs.value.filter(s => ['open', 'resolving'].includes(s.value)))

// ── 观察周与排序（2026-11-04：按指定周看问题表现，默认增量倒序） ──
const statWeek = ref('')
const latestWeek = ref('')
const weekOptions = ref([])
const sortState = ref({ prop: 'week_delta', order: 'descending' })

function onSortChange({ prop, order }) {
  // 只允许增量/累计排序；取消排序回默认（增量倒序）
  sortState.value = order && ['week_delta', 'cum_total'].includes(prop)
    ? { prop, order }
    : { prop: 'week_delta', order: 'descending' }
}

// 台账主列表**只展示在办**（已复核、未闭环）——候选走页签，不混在台账里
const filteredRows = computed(() => {
  let r = statusFilter.value
    ? inflightRows.value.filter(x => x.status === statusFilter.value)
    : inflightRows.value
  const { prop, order } = sortState.value
  if (order) {
    const dir = order === 'descending' ? -1 : 1
    // 主键相同再看另一维度，保证排序稳定可解释
    const alt = prop === 'week_delta' ? 'cum_total' : 'week_delta'
    r = [...r].sort((a, b) => {
      const d = ((a[prop] || 0) - (b[prop] || 0)) * dir
      return d !== 0 ? d : ((a[alt] || 0) - (b[alt] || 0)) * dir
    })
  }
  return r
})

const kpi = computed(() => ({
  candidate: candidates.value.length,
  inflight: rows.value.filter(r => ['open', 'resolving'].includes(r.status)).length,
  longRunning: rows.value.filter(r => r.active_weeks >= 12 && ['open', 'resolving'].includes(r.status)).length,
  reopen: rows.value.filter(r => r.reopen_flag).length,
}))

const urgeCnt = computed(() => kpi.value.reopen + kpi.value.longRunning)

const mergeTargets = computed(() =>
  rows.value.filter(r => ['open', 'resolving'].includes(r.status) && r.problem_no !== mergeRow.value?.problem_no)
)

const l2Options = computed(() =>
  [...new Set(rows.value.map(r => r.category_l2).filter(Boolean))]
)

const linkableActions = computed(() =>
  allActions.value.filter(a => !['cancelled'].includes(a.status))
)

function statusLabel(v) { return statusMap.value[v]?.label || v }
function statusTone(v) {
  const t = statusMap.value[v]?.tone || 'info'
  return { danger: 'danger', warning: 'warning', primary: 'primary', success: 'success', info: 'info', neutral: 'info' }[t] || 'info'
}
function actionTone(v) {
  return { effective: 'success', ineffective: 'danger', verifying: 'primary', in_progress: 'warning', planned: 'info', cancelled: 'info' }[v] || 'info'
}
function nextTargets(current) {
  return allowedNext(DOMAIN, current).map(v => ({ value: v, label: statusLabel(v) }))
}
function ruleHits(v) {
  return (v || '').split(',').filter(Boolean).map(h => RULE_NAMES[h] || h)
}
function sourceLabel(v) { return SOURCE_NAMES[v] || v }
function evidenceBrief(v) {
  if (!v) return '—'
  try {
    const ev = typeof v === 'string' ? JSON.parse(v) : v
    if (ev.weeks) {
      const last = ev.weeks[ev.weeks.length - 1] || {}
      return evidenceBrief(JSON.stringify(last))
    }
    const parts = []
    if (ev.max_day_cnt) parts.push(`单日峰值 ${ev.max_day_cnt} 单`)
    if (ev.wow != null) parts.push(`环比 +${ev.wow}%`)
    if (ev.rank) parts.push(`场景第 ${ev.rank} 位`)
    if (ev.recur_cnt) parts.push(`复发 ${ev.recur_cnt} 单`)
    if (ev.cnt) parts.push(`累计 ${ev.cnt} 单`)
    if (ev.active_weeks) parts.push(`活跃 ${ev.active_weeks} 周`)
    if (ev.sample_tickets && ev.sample_tickets.length) parts.push(`样本 ${ev.sample_tickets.length} 单`)
    return parts.join('；') || '—'
  } catch (e) { return '—' }
}

async function loadWeeks() {
  try {
    const r = await complaintApi.listWeeks(20)
    weekOptions.value = r?.weeks || []
    latestWeek.value = r?.latest || (weekOptions.value[0] || '')
    if (!statWeek.value) statWeek.value = latestWeek.value
  } catch (e) { weekOptions.value = [] }
}

async function load() {
  loading.value = true
  try {
    if (!weekOptions.value.length) await loadWeeks()
    // 分两次拉（在办 / 候选）：单次 200 上限，混拉会被分页截断丢候选
    const [openData, candData] = await Promise.all([
      complaintApi.listProblems({
        page_size: 200, status: 'open,resolving',
        stat_week: statWeek.value || undefined, sort: 'delta_desc',
      }),
      complaintApi.listProblems({ page_size: 200, status: 'candidate' }),
    ])
    rows.value = [...(openData?.items || []), ...(candData?.items || [])]
    try {
      const sug = await complaintApi.closureSuggestions()
      suggestions.value = sug?.items || []
    } catch (e) { suggestions.value = [] }
  } catch (e) {
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function doScan(dryRun) {
  scanning.value = true
  try {
    const r = await complaintApi.scanProblems(null, dryRun)
    const txt = `候选新建 ${r.created.length}，归并更新 ${r.updated.length}，待重开 ${r.reopen.length}`
    if (dryRun || !r.created.length) {
      ElMessage.info(`扫描完成：${txt}${dryRun ? '（预览未落库）' : ''}`)
    } else {
      ElMessage.success(`扫描完成：${txt}`)
    }
    load()
  } catch (e) { /* request 已提示 */ } finally {
    scanning.value = false
  }
}

function doConfirmOpen(row) {
  openRow.value = row
  openOwner.value = row.owner || ''
  openVisible.value = true
}

async function saveOpen() {
  if (!openOwner.value.trim()) {
    ElMessage.warning('入账必须指定责任人')
    return
  }
  saving.value = true
  try {
    await complaintApi.confirmProblem(openRow.value.problem_no, {
      decision: 'open', owner: openOwner.value.trim(),
    })
    ElMessage.success(`${openRow.value.problem_no} 已入账`)
    openVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

function openMerge(row) {
  mergeRow.value = row
  mergeTarget.value = ''
  mergeVisible.value = true
}

async function saveMerge() {
  if (!mergeTarget.value) {
    ElMessage.warning('请选择合并目标')
    return
  }
  saving.value = true
  try {
    await complaintApi.confirmProblem(mergeRow.value.problem_no, {
      decision: 'merge', merged_into: mergeTarget.value,
    })
    ElMessage.success(`已合并至 ${mergeTarget.value}`)
    mergeVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

async function doIgnore(row) {
  try {
    await ElMessageBox.confirm(`确认忽略 ${row.problem_no}？忽略后可反悔（重新入账）。`, '忽略候选', { type: 'warning' })
  } catch (e) { return }
  try {
    await complaintApi.confirmProblem(row.problem_no, { decision: 'ignore' })
    ElMessage.success('已忽略')
    load()
  } catch (e) { /* request 已提示 */ }
}

// 列表行直接建运营工单：不打开详情抽屉，用行数据做轻量上下文（详情在提交后自动补全）
async function openIssueForRow(row) {
  if (!row) return
  detail.value = { ...row }
  trajectory.value = []
  await openIssueDialog()
}

async function doTransition(row, t) {
  const payload = {}
  if (t.value === 'open' && !row.owner) {
    ElMessage.warning('进入待处置须先指定责任人（入账时填写）')
    return
  }
  if (t.value === 'closed') {
    let conclusion
    try {
      ({ value: conclusion } = await ElMessageBox.prompt(
        `确认闭环 ${row.problem_no}？请填写闭环结论（必填）`, '闭环确认',
        { type: 'success', inputPlaceholder: '如：措施生效后连续 3 周零复发，问题闭环' }
      ))
    } catch (e) { return }
    if (!conclusion || !conclusion.trim()) {
      ElMessage.warning('闭环结论必填')
      return
    }
    payload.conclusion = conclusion.trim()
  }
  try {
    await ElMessageBox.confirm(`确认将 ${row.problem_no} 置为「${t.label}」？`, '状态流转', { type: 'warning' })
  } catch (e) { return }
  try {
    await complaintApi.changeProblemStatus(row.problem_no, { status: t.value, ...payload })
    ElMessage.success(`已置为「${t.label}」`)
    load()
  } catch (e) { /* request 已提示 */ }
}

async function doClose(s) {
  let conclusion = ''
  try {
    ({ value: conclusion } = await ElMessageBox.prompt(
      `确认闭环 ${s.problem_no}？请填写闭环结论（必填）`, '闭环确认',
      { type: 'success', inputPlaceholder: s.reason }
    ))
  } catch (e) { return }
  if (!conclusion || !conclusion.trim()) {
    ElMessage.warning('闭环结论必填')
    return
  }
  try {
    await complaintApi.changeProblemStatus(s.problem_no, { status: 'closed', conclusion: conclusion.trim() })
    ElMessage.success(`${s.problem_no} 已闭环`)
    load()
  } catch (e) { /* request 已提示 */ }
}

async function openDetail(row) {
  try {
    detail.value = await complaintApi.getProblem(row.problem_no)
    trajectory.value = detail.value.trajectory || []
    // 关联投诉工单：按问题覆盖的根因簇拉（一个问题可纳多簇）
    await loadDetailTickets()
    if (!allActions.value.length) {
      allActions.value = await complaintApi.listActions()
    }
    linkActionNo.value = ''
    detailVisible.value = true
  } catch (e) { /* request 已提示 */ }
}

function problemRcNos() {
  const raw = detail.value?.rootcause_nos || detail.value?.rootcause_no || ''
  return String(raw).split(',').map(s => s.trim()).filter(Boolean)
}

async function loadDetailTickets() {
  // 归因锚点选路：优先闭集模块问题（L2 主要投诉点），否则根因簇，再否则按问题编号
  if (detail.value?.module_problem_id) {
    drillFilters.value = { module_problem_id: detail.value.module_problem_id }
  } else {
    const rcs = problemRcNos()
    drillFilters.value = rcs.length ? { rootcause_no: rcs.join(',') } : { problem_no: detail.value?.problem_no }
  }
  try {
    const t = await complaintApi.listTickets({ ...drillFilters.value, page: 1, page_size: 8 })
    detailTickets.value = t?.items || []
    detailTicketTotal.value = t?.total || 0
  } catch (e) {
    detailTickets.value = []
    detailTicketTotal.value = 0
  }
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}

async function openIssueDialog() {
  if (!detail.value) return
  if (!l2Catalog.value.length) {
    try {
      const cats = await complaintApi.listCategories()
      l2Catalog.value = (Array.isArray(cats) ? cats : [])
        .filter(c => c.level === 2 && c.enabled)
        .map(c => c.name)
    } catch (e) { l2Catalog.value = [] }
  }
  const due = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10)
  issueForm.value = {
    l2: detail.value.category_l2 || '',
    title: detail.value.title || '',
    owner: detail.value.owner || '',
    due_date: due,
    acceptance: '',
    context_weeks: 1,
    desc: '',
  }
  ctxTickets.value = []
  issueVisible.value = true
  await reloadIssueContext()
}

async function saveIssue() {
  const f = issueForm.value
  if (!f.l2) return ElMessage.warning('请选择问题场景')
  if (!f.title.trim()) return ElMessage.warning('请填写工单标题')
  if (!f.owner.trim()) return ElMessage.warning('请指定责任人')
  if (!f.desc.trim()) return ElMessage.warning('情况说明必填（可修改自动总结后提交）')
  if (!f.acceptance.trim()) return ElMessage.warning('验收标准必填（可验证才算闭环）')
  saving.value = true
  try {
    const r = await complaintApi.createAction({
      l2: f.l2,
      title: f.title.trim(),
      owner: f.owner.trim(),
      due_date: f.due_date || null,
      acceptance: f.acceptance.trim(),
      desc: f.desc.trim(),
      create_issue: true,
      problem_nos: [detail.value.problem_no],
      context_weeks: f.context_weeks || 1,
      context_tickets: JSON.stringify(ctxTickets.value || []),
    })
    ElMessage.success(`已创建措施 ${r.action_no}，运营工单 ${r.issue_no || '已生成'}`)
    issueVisible.value = false
    // 重新拉详情（措施与工单已联动回写）
    detail.value = await complaintApi.getProblem(detail.value.problem_no)
    trajectory.value = detail.value.trajectory || []
    await loadDetailTickets()
    allActions.value = await complaintApi.listActions()
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

async function doLink() {
  if (!linkActionNo.value || !detail.value) return
  try {
    const r = await complaintApi.linkProblemAction(detail.value.problem_no, {
      action_no: linkActionNo.value,
    })
    if (r.warning) ElMessage.warning(r.warning)
    else ElMessage.success('已关联')
    detail.value = await complaintApi.getProblem(detail.value.problem_no)
    detail.value.trajectory = trajectory.value
    load()
  } catch (e) { /* request 已提示 */ }
}

async function doUnlink(linkRow) {
  try {
    await ElMessageBox.confirm(`解除 ${linkRow.action_no} 与该问题的关联？`, '解除关联', { type: 'warning' })
  } catch (e) { return }
  try {
    await complaintApi.unlinkProblemAction(detail.value.problem_no, linkRow.action_no)
    ElMessage.success('已解除')
    detail.value = await complaintApi.getProblem(detail.value.problem_no)
    detail.value.trajectory = trajectory.value
    load()
  } catch (e) { /* request 已提示 */ }
}

function openCreate() {
  createForm.value = { category_l2: '', title: '', owner: '' }
  createVisible.value = true
}

async function saveCreate() {
  if (!createForm.value.category_l2 || !createForm.value.title.trim()) {
    ElMessage.warning('场景与标题必填')
    return
  }
  saving.value = true
  try {
    await complaintApi.createProblem({ ...createForm.value, title: createForm.value.title.trim() })
    ElMessage.success('问题已创建')
    createVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

function doProblemsUrge(confirmSend) {
  if (!confirmSend) {
    urgeResults.value = []
    urgeDone.value = false
    urgeVisible.value = true
  }
  urging.value = true
  complaintApi.problemsUrge({ confirm_send: !!confirmSend })
    .then(data => {
      if (data.skipped && !confirmSend) {
        ElMessage.info(data.skipped)
        urgeVisible.value = false
        return
      }
      urgeResults.value = data.sent || []
      if (confirmSend) {
        ElMessage.success('问题督办邮件已发送')
        urgeVisible.value = false
      } else {
        urgeDone.value = true
      }
    })
    .catch(() => { /* request 已提示 */ })
    .finally(() => { urging.value = false })
}

onMounted(load)
</script>

<style scoped>
.problem-ledger {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sug-alert {
  margin-bottom: 0;
}
.sug-line {
  font-size: 12.5px;
  padding: 4px 0;
}
.rule-tag {
  margin-right: 4px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sec-title {
  font-size: 13.5px;
  margin: 8px 0 2px;
  color: var(--text-secondary);
}
.ev-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12.5px;
}
.ev-text {
  color: var(--text-secondary);
}
.link-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.gl-tip {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}
.urge-line {
  font-size: 12.5px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}
.urge-line .warn {
  color: var(--warning);
}
.tab-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.tab-hint {
  font-size: 12px;
  color: var(--text-muted);
}
.ledger-tabs {
  padding: 0 2px;
}
.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace);
  font-size: 12px;
}
/* 区块标题右侧的操作按钮：与标题基线对齐 */
.sec-title .el-button {
  margin-left: 8px;
  vertical-align: baseline;
}
/* 建单对话框：代入工单明细预览 */
.ctx-tickets {
  width: 100%;
}
.ctx-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
/* 台账增量/累计两列（2026-11-04 拆分口径） */
.delta-num {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}
.delta-num.hot {
  color: var(--danger, #c0392b);
}
.cum-num {
  font-size: 13px;
  color: var(--text-secondary);
}
.col-unit {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: 2px;
}
.no-action {
  color: var(--text-muted);
}
.more-btn {
  padding-left: 4px;
  padding-right: 4px;
}
</style>
