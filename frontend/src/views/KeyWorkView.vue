<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <div class="page-title">重点工作</div>
        <div class="page-sub">总部试点 · 年度任务 · 专题工作 — 全周期闭环管理</div>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新建重点工作
        </el-button>
      </div>
    </div>

    <!-- KPI 概览 -->
    <div class="bento-grid kpi-strip">
      <section class="card kpi-card">
        <div class="kpi-num blue">{{ stats.by_status ? totalCount : 0 }}</div>
        <div class="kpi-label">重点工作总数</div>
      </section>
      <section class="card kpi-card">
        <div class="kpi-num">{{ stats.by_status?.in_progress || 0 }}</div>
        <div class="kpi-label">进行中</div>
      </section>
      <section class="card kpi-card">
        <div class="kpi-num green">{{ stats.by_status?.completed || 0 }}</div>
        <div class="kpi-label">已完成</div>
      </section>
      <section class="card kpi-card">
        <div class="kpi-num red">{{ stats.overdue_member_tasks || 0 }}</div>
        <div class="kpi-label">超期成员待办</div>
      </section>
    </div>

    <!-- 分类 Tab + 工具栏 -->
    <div class="pm-table-wrap mt-16">
      <el-tabs v-model="activeCategory" class="pm-tabs" @tab-change="handleCategoryChange">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="总部试点" name="hq_pilot" />
        <el-tab-pane label="年度任务" name="annual_task" />
        <el-tab-pane label="专题工作" name="special_topic" />
      </el-tabs>
      <div class="table-toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索工作编号 / 标题 / 负责人"
          style="width: 280px"
          clearable
          @keyup.enter="fetchList"
          @clear="fetchList"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 140px" @change="fetchList">
          <el-option v-for="(v, k) in STATUS_MAP" :key="k" :label="v.label" :value="k" />
        </el-select>
        <el-button @click="fetchList"><el-icon><Refresh /></el-icon> 刷新</el-button>
        <el-button @click="handleDownloadTemplate"><el-icon><Download /></el-icon> 下载模版</el-button>
        <el-button type="success" @click="triggerImport"><el-icon><Upload /></el-icon> 导入</el-button>
        <input ref="importFileRef" type="file" accept=".xlsx" style="display:none" @change="handleImportFile" />
      </div>

      <el-table
        v-loading="loading"
        :data="list"
        stripe
        border
        style="width: 100%"
        @row-click="openDetail"
      >
        <el-table-column prop="work_no" label="工作编号" width="150" />
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="分类" width="110">
          <template #default="{ row }">
            <span class="pm-tag" :class="CATEGORY_MAP[row.category]?.tag">{{ CATEGORY_MAP[row.category]?.label }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusBadge module="keywork" :value="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <span class="pm-tag" :class="PRIORITY_MAP[row.priority]?.tag">{{ PRIORITY_MAP[row.priority]?.label }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="110" />
        <el-table-column prop="created_at" label="创建时间" width="130">
          <template #default="{ row }">{{ row.created_at ? String(row.created_at).slice(0, 10) : '—' }}</template>
        </el-table-column>
        <el-table-column prop="planned_finish_date" label="计划完成" width="130" />
        <el-table-column label="进度" width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDetail(row)">查看</el-button>
            <el-button link type="danger" @click.stop="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="detail?.title || '重点工作详情'"
      size="70%"
      :before-close="closeDrawer"
    >
      <template #header>
        <div class="drawer-head-custom">
          <div>
            <div class="pm-drawer-title">{{ detail?.title }}</div>
            <div class="text-muted" style="font-size: 12px; margin-top: 2px">
              {{ detail?.work_no }} ·
              <span class="pm-tag" :class="CATEGORY_MAP[detail?.category]?.tag">{{ CATEGORY_MAP[detail?.category]?.label }}</span>
            </div>
          </div>
          <el-button size="small" @click="openBasicEdit"><el-icon><Edit /></el-icon> 编辑基本信息</el-button>
        </div>
      </template>

      <el-tabs v-model="activeSection" class="drawer-tabs" @tab-change="handleSectionChange">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <div v-if="detail" class="sec-body">
            <!-- 工作概述：大段文本字段，垂直串行独占整行 -->
            <div class="pm-section-title">工作概述</div>
            <div class="info-stack">
              <div class="info-item info-block">
                <span class="pm-field-label">工作背景</span>
                <div class="info-text">{{ detail.background || '—' }}</div>
              </div>
              <div class="info-item info-block">
                <span class="pm-field-label">现状说明</span>
                <div class="info-text">{{ detail.current_status || '—' }}</div>
              </div>
              <div class="info-item info-block">
                <span class="pm-field-label">工作内容</span>
                <div class="info-text">{{ detail.content || '—' }}</div>
              </div>
              <div class="info-item info-block">
                <span class="pm-field-label">工作价值</span>
                <div class="info-text">{{ detail.work_value || '—' }}</div>
              </div>
            </div>
            <!-- 执行属性：短字段两列并排 -->
            <div class="pm-section-title" style="margin-top: 20px">执行属性</div>
            <div class="info-grid-compact">
              <div class="info-item"><span class="pm-field-label">负责人</span>{{ detail.owner || '—' }}</div>
              <div class="info-item"><span class="pm-field-label">优先级</span>
                <span class="pm-tag" :class="PRIORITY_MAP[detail.priority]?.tag">{{ PRIORITY_MAP[detail.priority]?.label }}</span>
              </div>
              <div class="info-item"><span class="pm-field-label">生命周期状态</span>
                <StatusBadge module="keywork" :value="detail.status" />
              </div>
              <div class="info-item"><span class="pm-field-label">计划完成时间</span>{{ detail.planned_finish_date || '—' }}</div>
            </div>
            <!-- 进度可视化 -->
            <div class="info-item info-progress">
              <span class="pm-field-label">进度</span>
              <el-progress :percentage="detail.progress || 0" :stroke-width="8" :show-text="true" style="max-width: 320px" />
            </div>
          </div>
        </el-tab-pane>

        <!-- 工作目标 -->
        <el-tab-pane label="工作目标" name="goals">
          <div class="sec-head">
            <span class="pm-section-title">工作目标 / 指标</span>
            <el-button size="small" type="primary" @click="openGoalDialog()"><el-icon><Plus /></el-icon> 新增目标</el-button>
          </div>
          <el-table :data="detail?.goals || []" border stripe size="small">
            <el-table-column prop="seq" label="序号" width="60" />
            <el-table-column prop="indicator" label="指标" min-width="120" />
            <el-table-column prop="target_value" label="目标值" width="110" />
            <el-table-column prop="current_value" label="当前值" width="110" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openGoalDialog(row)">编辑</el-button>
                <el-button link type="danger" @click="removeGoal(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 验收标准 -->
        <el-tab-pane label="验收标准" name="accept">
          <div class="sec-head">
            <span class="pm-section-title">验收标准</span>
            <el-button size="small" type="primary" @click="openAcceptDialog()"><el-icon><Plus /></el-icon> 新增标准</el-button>
          </div>
          <div v-if="(detail?.acceptance_criteria || []).length" class="accept-list">
            <div v-for="(item, i) in detail.acceptance_criteria" :key="i" class="accept-item">
              <span class="accept-idx">{{ i + 1 }}</span>
              <span class="accept-text">{{ item }}</span>
              <el-button link type="danger" size="small" @click="removeAccept(i)"><el-icon><Delete /></el-icon></el-button>
            </div>
          </div>
          <div v-else class="text-muted" style="padding: 12px 0">暂无验收标准</div>
        </el-tab-pane>

        <!-- 里程碑 -->
        <el-tab-pane label="里程碑" name="milestone">
          <div class="sec-head">
            <span class="pm-section-title">任务里程碑</span>
            <el-button size="small" type="primary" @click="openMilestoneDialog()"><el-icon><Plus /></el-icon> 新增里程碑</el-button>
          </div>
          <el-table :data="detail?.milestones || []" border stripe size="small">
            <el-table-column prop="name" label="里程碑" min-width="160" />
            <el-table-column prop="due_date" label="计划完成" width="130" />
            <el-table-column label="状态" width="140">
              <template #default="{ row }">
                <el-select :model-value="row.status" size="small" style="width: 110px"
                  @change="(v) => changeMilestoneStatus(row, v)">
                  <el-option v-for="(v, k) in MS_STATUS_MAP" :key="k" :label="v.label" :value="k" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column prop="note" label="说明" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click="removeMilestone(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 团队分工 -->
        <el-tab-pane label="团队分工" name="member">
          <div class="sec-head">
            <span class="pm-section-title">团队成员及分工</span>
            <el-button size="small" type="primary" @click="openMemberDialog()"><el-icon><Plus /></el-icon> 添加成员</el-button>
          </div>
          <el-table :data="detail?.members || []" border stripe size="small">
            <el-table-column prop="name" label="姓名" width="120" />
            <el-table-column prop="role" label="角色" width="140" />
            <el-table-column prop="division_desc" label="分工说明" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click="removeMember(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 月度计划 -->
        <el-tab-pane label="月度计划" name="monthly">
          <div class="sec-head">
            <span class="pm-section-title">月度计划</span>
            <el-button size="small" type="primary" @click="openMonthlyDialog()"><el-icon><Plus /></el-icon> 新增月计划</el-button>
          </div>
          <el-table :data="detail?.monthly_plans || []" border stripe size="small">
            <el-table-column prop="month" label="月份" width="110" />
            <el-table-column prop="task_date" label="创建日期" width="110" />
            <el-table-column prop="title" label="任务标题" min-width="140" show-overflow-tooltip />
            <el-table-column prop="content" label="任务描述" min-width="180" show-overflow-tooltip />
            <el-table-column prop="assignee" label="责任人" width="100" />
            <el-table-column prop="due_date" label="计划完成" width="110" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-select :model-value="row.status" size="small" style="width: 100px"
                  @change="(v) => changeMonthlyStatus(row, v)">
                  <el-option v-for="(v, k) in PLAN_STATUS_MAP" :key="k" :label="v.label" :value="k" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openMonthlyDialog(row)">编辑</el-button>
                <el-button link type="danger" @click="removeMonthly(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 周计划 -->
        <el-tab-pane label="周计划" name="weekly">
          <div class="sec-head">
            <span class="pm-section-title">周计划</span>
            <el-button size="small" type="primary" @click="openWeeklyDialog()"><el-icon><Plus /></el-icon> 新增周计划</el-button>
          </div>
          <el-table :data="detail?.weekly_plans || []" border stripe size="small">
            <el-table-column prop="week" label="周次" width="110" />
            <el-table-column prop="task_date" label="创建日期" width="110" />
            <el-table-column prop="title" label="任务标题" min-width="140" show-overflow-tooltip />
            <el-table-column prop="content" label="任务描述" min-width="180" show-overflow-tooltip />
            <el-table-column prop="assignee" label="责任人" width="100" />
            <el-table-column prop="due_date" label="计划完成" width="110" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-select :model-value="row.status" size="small" style="width: 100px"
                  @change="(v) => changeWeeklyStatus(row, v)">
                  <el-option v-for="(v, k) in PLAN_STATUS_MAP" :key="k" :label="v.label" :value="k" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openWeeklyDialog(row)">编辑</el-button>
                <el-button link type="danger" @click="removeWeekly(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 工作进展 -->
        <el-tab-pane label="工作进展" name="progress">
          <div class="sec-head">
            <span class="pm-section-title">工作进展日志</span>
            <el-button size="small" type="primary" @click="openProgressDialog()"><el-icon><Plus /></el-icon> 记录进展</el-button>
          </div>
          <el-timeline class="progress-timeline">
            <el-timeline-item
              v-for="p in (detail?.progresses || [])"
              :key="p.id"
              :timestamp="p.record_date"
              placement="top"
            >
              <div class="progress-item">
                <div>
                  <div>{{ p.content }}</div>
                  <div class="text-muted" style="font-size: 12px; margin-top: 4px">
                    {{ p.reporter ? '汇报人：' + p.reporter : '' }}{{ p.created_at ? (p.reporter ? ' · ' : '') + String(p.created_at).slice(0, 10) : '' }}
                  </div>
                </div>
                <el-button link type="danger" size="small" @click="removeProgress(p)"><el-icon><Delete /></el-icon></el-button>
              </div>
            </el-timeline-item>
          </el-timeline>
          <div v-if="!(detail?.progresses || []).length" class="text-muted" style="padding: 12px 0">暂无进展记录</div>
        </el-tab-pane>

        <!-- 成员待办 -->
        <el-tab-pane label="成员待办" name="task">
          <div class="sec-head">
            <span class="pm-section-title">成员代办任务</span>
            <el-button size="small" type="primary" @click="openTaskDialog()"><el-icon><Plus /></el-icon> 新增待办</el-button>
          </div>
          <el-table :data="detail?.member_tasks || []" border stripe size="small">
            <el-table-column prop="title" label="任务" min-width="180" show-overflow-tooltip />
            <el-table-column prop="assignee" label="负责人" width="100" />
            <el-table-column prop="due_date" label="截止" width="120" />
            <el-table-column label="状态" width="140">
              <template #default="{ row }">
                <el-select :model-value="row.status" size="small" style="width: 110px"
                  @change="(v) => changeTaskStatus(row, v)">
                  <el-option v-for="(v, k) in TASK_STATUS_MAP" :key="k" :label="v.label" :value="k" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click="removeTask(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 交付物 -->
        <el-tab-pane label="交付物" name="deliverable">
          <div class="sec-head">
            <span class="pm-section-title">任务交付物管理</span>
            <div
              ref="deliverableZone"
              class="paste-upload-inline"
              tabindex="0"
            >
              <el-upload
                :show-file-list="false"
                :before-upload="handleDeliverableUpload"
                accept="*"
              >
                <el-button size="small" type="primary" :loading="isPasting"><el-icon><Upload /></el-icon> 上传交付物</el-button>
              </el-upload>
            </div>
          </div>
          <div class="paste-hint">点击上方按钮上传，或点击按钮区域后按 Ctrl+V 粘贴截图/文件</div>
          <el-table :data="detail?.deliverables || []" border stripe size="small">
            <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
            <el-table-column prop="file_size" label="大小(字节)" width="110" />
            <el-table-column prop="uploaded_by" label="上传人" width="100" />
            <el-table-column prop="created_at" label="上传时间" width="170" />
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="downloadDeliverable(row)">下载</el-button>
                <el-button link type="danger" @click="removeDeliverable(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 周反馈 -->
        <el-tab-pane label="周反馈" name="feedback">
          <div class="sec-head" style="flex-wrap: wrap; gap: 8px">
            <span class="pm-section-title">在途工单周反馈（负责人牵头汇总）</span>
            <div style="display: flex; align-items: center; gap: 8px; margin-left: auto">
              <el-date-picker
                v-model="feedbackWeek"
                type="week"
                format="YYYY-Www"
                value-format="YYYY-Www"
                :clearable="false"
                style="width: 140px"
                @change="loadWeeklyFeedback"
              />
              <el-button size="small" @click="openFeedbackMail">
                <el-icon><Message /></el-icon> 预览并发送反馈请求
              </el-button>
            </div>
          </div>

          <div v-if="feedbackGroups.length" class="feedback-list">
            <div v-for="g in feedbackGroups" :key="g.assignee" class="feedback-card">
              <div class="feedback-card-head" @click="toggleFeedbackCard(g)">
                <div style="display: flex; flex-direction: column; gap: 4px">
                  <div style="display: flex; align-items: center; gap: 8px">
                    <span class="feedback-assignee">负责人：{{ g.assignee }}</span>
                    <span v-if="g.feedback" class="pm-tag" style="background: var(--success-bg, #f0f9eb); color: var(--success, #67c23a)">
                      已反馈 {{ (g.feedback.feedback_date || '').slice(0, 10) }}
                    </span>
                    <span v-else class="pm-tag gray">负责人未反馈</span>
                  </div>
                  <span class="feedback-hint">牵头线下收集团队进展，统一汇总后录入归档</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px">
                  <span v-if="g.feedback" class="text-muted" style="font-size: 12px">进度 {{ g.feedback.progress || 0 }}%</span>
                  <el-button link type="primary" size="small" @click.stop="toggleFeedbackCard(g)">
                    {{ isExpanded(g) ? '收起' : (g.feedback ? '查看/编辑' : '填写反馈') }}
                  </el-button>
                </div>
              </div>

              <div v-if="isExpanded(g)" class="feedback-card-body">
                <el-form label-position="top" size="small">
                  <el-collapse v-model="g._activePanels">
                    <!-- A. 上周回顾 -->
                    <el-collapse-item title="A. 上周回顾（只读）" name="lastWeek">
                      <div v-if="lastWeekFeedback" class="feedback-last-week">
                        <div class="info-block">
                          <div class="info-label">上周计划（{{ lastWeekFeedback.week }}）</div>
                          <div class="info-text">{{ lastWeekFeedback.next_summary || '（上周未填写下周计划）' }}</div>
                        </div>
                        <div v-if="lastWeekFeedback.item_updates?.length" class="info-block">
                          <div class="info-label">上周计划子项当前状态</div>
                          <div class="feedback-items">
                            <div v-for="u in lastWeekFeedback.item_updates" :key="u.type + '-' + u.id" class="feedback-item-row">
                              <span>{{ lastWeekItemLabel(u) }}</span>
                              <span class="pm-tag" :class="(PLAN_STATUS_MAP[lastWeekItemStatus(u)] || {}).tag">
                                {{ (PLAN_STATUS_MAP[lastWeekItemStatus(u)] || { label: lastWeekItemStatus(u) }).label }}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div v-else class="text-muted">暂无上周反馈记录</div>
                    </el-collapse-item>

                    <!-- B. 月计划 -->
                    <el-collapse-item title="B. 月计划" name="monthly">
                      <div v-if="g.monthly_items.length" class="feedback-items">
                        <el-checkbox
                          v-for="it in g.monthly_items"
                          :key="'m-' + it.id"
                          :model-value="isItemChecked(g, it)"
                          @change="(v) => toggleItemChecked(g, it, v)"
                        >
                          <span style="margin-right: 6px">{{ itemLabel(it) }}</span>
                          <span class="pm-tag" :class="(PLAN_STATUS_MAP[it.status] || {}).tag">{{ (PLAN_STATUS_MAP[it.status] || { label: it.status }).label }}</span>
                        </el-checkbox>
                      </div>
                      <div v-else class="text-muted">暂无关联网月计划</div>
                      <template v-if="isMonthEnd">
                        <el-form-item label="本月月总结" class="feedback-textarea-item">
                          <el-input v-model="g._form.monthly_summary" type="textarea" :rows="3" placeholder="汇总本月完成情况、关键成果、偏差说明" />
                        </el-form-item>
                        <el-form-item label="下月重点 / 下月月计划草案" class="feedback-textarea-item">
                          <el-input v-model="g._form.next_month_summary" type="textarea" :rows="3" placeholder="下月重点工作或拟制定的月计划" />
                        </el-form-item>
                      </template>
                    </el-collapse-item>

                    <!-- C. 周计划 -->
                    <el-collapse-item title="C. 周计划" name="weekly">
                      <div v-if="g.weekly_items.length" class="feedback-items">
                        <el-checkbox
                          v-for="it in g.weekly_items"
                          :key="'w-' + it.id"
                          :model-value="isItemChecked(g, it)"
                          @change="(v) => toggleItemChecked(g, it, v)"
                        >
                          <span style="margin-right: 6px">{{ itemLabel(it) }}</span>
                          <span class="pm-tag" :class="(PLAN_STATUS_MAP[it.status] || {}).tag">{{ (PLAN_STATUS_MAP[it.status] || { label: it.status }).label }}</span>
                        </el-checkbox>
                      </div>
                      <div v-else class="text-muted">暂无关联周计划</div>
                      <el-form-item label="下周新的工作计划" class="feedback-textarea-item">
                        <el-input v-model="g._form.next_summary" type="textarea" :rows="3" placeholder="反馈下周计划开展的重点工作" />
                      </el-form-item>
                    </el-collapse-item>

                    <!-- D. 成员待办 -->
                    <el-collapse-item title="D. 成员待办（进展 + 新增）" name="memberTask">
                      <el-table v-if="g.task_items.length" :data="g.task_items" border stripe size="small" class="feedback-task-table">
                        <el-table-column prop="label" label="任务" min-width="140" show-overflow-tooltip />
                        <el-table-column prop="assignee" label="负责人" width="90" />
                        <el-table-column label="状态" width="130">
                          <template #default="{ row }">
                            <el-select :model-value="taskNote(g, row).status || row.status" size="small" style="width: 110px" @change="(v) => setTaskStatus(g, row, v)">
                              <el-option v-for="(v, k) in TASK_STATUS_MAP" :key="k" :label="v.label" :value="k" />
                            </el-select>
                          </template>
                        </el-table-column>
                        <el-table-column label="进展说明" min-width="160">
                          <template #default="{ row }">
                            <el-input v-model="taskNote(g, row).note" type="textarea" :rows="1" placeholder="填写进展" size="small" @blur="ensureTaskNote(g, row)" />
                          </template>
                        </el-table-column>
                      </el-table>
                      <div v-else class="text-muted">当前无未完成的成员待办</div>

                      <div class="feedback-new-task">
                        <div class="feedback-section-subtitle">新增成员任务</div>
                        <div class="feedback-new-task-form">
                          <el-input v-model="newTaskForm.title" size="small" placeholder="任务标题" style="flex: 1" />
                          <StaffSelect v-model="newTaskForm.assignee" style="width: 120px" />
                          <el-date-picker v-model="newTaskForm.due_date" type="date" value-format="YYYY-MM-DD" placeholder="截止日" size="small" style="width: 130px" />
                          <el-button size="small" @click="addNewTask(g)"><el-icon><Plus /></el-icon>添加</el-button>
                        </div>
                        <div v-if="g._form.new_tasks.length" class="feedback-new-task-list">
                          <div v-for="(t, idx) in g._form.new_tasks" :key="idx" class="feedback-new-task-row">
                            <span>{{ t.title }}</span>
                            <span class="text-muted">{{ t.assignee || '未指派' }} {{ t.due_date ? '· ' + t.due_date : '' }}</span>
                            <el-button link type="danger" size="small" @click="removeNewTask(g, idx)">删除</el-button>
                          </div>
                        </div>
                      </div>
                    </el-collapse-item>

                    <!-- E. 交付物 -->
                    <el-collapse-item title="E. 交付物材料" name="deliverable">
                      <el-upload
                        :show-file-list="false"
                        :before-upload="(file) => handleFeedbackDeliverableUpload(file, g)"
                        accept="*"
                      >
                        <el-button size="small" type="primary"><el-icon><Upload /></el-icon> 上传交付物</el-button>
                      </el-upload>
                      <div v-if="!g._form.deliverable_ids.length" class="text-muted" style="margin-top: 8px">本周暂无关联交付物</div>
                      <div v-else class="feedback-deliverable-list">
                        <div v-for="d in feedbackDeliverables.filter(x => g._form.deliverable_ids.includes(x.id))" :key="d.id" class="feedback-deliverable-row">
                          <el-icon><Document /></el-icon>
                          <span class="feedback-deliverable-name" :title="d.original_name || d.file_name">{{ d.original_name || d.file_name }}</span>
                          <el-button link type="danger" size="small" @click="removeFeedbackDeliverable(g, d)">移除</el-button>
                        </div>
                      </div>
                    </el-collapse-item>

                    <!-- F. 风险/求助 -->
                    <el-collapse-item title="F. 风险/求助" name="risk">
                      <el-form-item label="风险、阻塞或需协调事项">
                        <el-input v-model="g._form.risk_note" type="textarea" :rows="3" placeholder="请填写需要同步给管理员的异常或求助" />
                      </el-form-item>
                    </el-collapse-item>

                    <!-- G. 整体进度 & 本周完成 -->
                    <el-collapse-item title="G. 整体进度 & 本周完成" name="summary">
                      <el-form-item label="整体进度">
                        <div style="display: flex; align-items: center; gap: 12px; width: 100%">
                          <el-slider v-model="g._form.progress" :min="0" :max="100" style="flex: 1" />
                          <span style="width: 42px; text-align: right; font-size: 13px">{{ g._form.progress || 0 }}%</span>
                        </div>
                      </el-form-item>
                      <el-form-item label="本周完成摘要">
                        <el-input v-model="g._form.done_summary" type="textarea" :rows="3" placeholder="汇总本周完成的关键事项" />
                      </el-form-item>
                      <div class="feedback-card-actions">
                        <el-button type="primary" size="small" :loading="submittingAssignees.includes(g.assignee)" @click="submitFeedback(g)">
                          提交负责人周反馈
                        </el-button>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </el-form>
              </div>
            </div>
          </div>
          <div v-else class="text-muted" style="padding: 16px 0">该工单未设置负责人，无法生成周反馈工作单</div>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>

    <!-- 新建 / 编辑基本信息 对话框 -->
    <el-dialog v-model="basicVisible" :title="basicIsEdit ? '编辑基本信息' : '新建重点工作'" width="640px">
      <el-form :model="basicForm" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="basicForm.title" placeholder="工作标题" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="basicForm.category" style="width: 100%">
            <el-option v-for="(v, k) in CATEGORY_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务领域">
          <BusinessDomainSelect v-model="basicForm.domain_code" />
        </el-form-item>
        <el-form-item label="负责人">
          <StaffSelect v-model="basicForm.owner" placeholder="牵头人 / 负责人" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="basicForm.priority" style="width: 100%">
            <el-option v-for="(v, k) in PRIORITY_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="basicForm.status" style="width: 100%">
            <el-option v-for="(v, k) in STATUS_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划完成">
          <el-date-picker v-model="basicForm.planned_finish_date" type="date" value-format="YYYY-MM-DD" placeholder="计划完成时间" style="width: 100%" />
        </el-form-item>
        <el-form-item label="工作进度">
          <div style="display: flex; align-items: center; gap: 12px; width: 100%">
            <el-slider v-model="basicForm.progress" :min="0" :max="100" :step="1" style="flex: 1" />
            <span style="width: 42px; text-align: right; font-size: 13px; color: var(--text-primary)">{{ basicForm.progress || 0 }}%</span>
          </div>
        </el-form-item>
        <el-form-item label="工作背景">
          <el-input v-model="basicForm.background" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="现状说明">
          <el-input v-model="basicForm.current_status" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="工作内容">
          <el-input v-model="basicForm.content" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="工作价值">
          <el-input v-model="basicForm.work_value" type="textarea" :rows="3" placeholder="专题工作做完后的收获、收益或价值" />
        </el-form-item>
        <el-form-item label="验收标准">
          <el-input v-model="acceptText" type="textarea" :rows="3" placeholder="每行一条验收标准" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="basicVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBasic">确定</el-button>
      </template>
    </el-dialog>

    <!-- 目标对话框 -->
    <el-dialog v-model="goalVisible" title="工作目标" width="520px">
      <el-form :model="goalForm" label-width="80px">
        <el-form-item label="指标"><el-input v-model="goalForm.indicator" /></el-form-item>
        <el-form-item label="目标值"><el-input v-model="goalForm.target_value" /></el-form-item>
        <el-form-item label="当前值"><el-input v-model="goalForm.current_value" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="goalForm.unit" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="goalForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="goalVisible = false">取消</el-button>
        <el-button type="primary" @click="submitGoal">确定</el-button>
      </template>
    </el-dialog>

    <!-- 里程碑对话框 -->
    <el-dialog v-model="milestoneVisible" title="任务里程碑" width="520px">
      <el-form :model="milestoneForm" label-width="90px">
        <el-form-item label="里程碑" required><el-input v-model="milestoneForm.name" /></el-form-item>
        <el-form-item label="计划完成"><el-date-picker v-model="milestoneForm.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="milestoneForm.status" style="width:100%">
            <el-option v-for="(v,k) in MS_STATUS_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明"><el-input v-model="milestoneForm.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="milestoneVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMilestone">确定</el-button>
      </template>
    </el-dialog>

    <!-- 成员对话框 -->
    <el-dialog v-model="memberVisible" title="团队成员" width="480px">
      <el-form :model="memberForm" label-width="80px">
        <el-form-item label="姓名" required><StaffSelect v-model="memberForm.name" /></el-form-item>
        <el-form-item label="角色"><el-input v-model="memberForm.role" /></el-form-item>
        <el-form-item label="分工"><el-input v-model="memberForm.division_desc" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMember">确定</el-button>
      </template>
    </el-dialog>

    <!-- 月计划对话框 -->
    <el-dialog v-model="monthlyVisible" :title="monthlyEditingId ? '编辑月度计划' : '新增月度计划'" width="560px">
      <el-form :model="monthlyForm" label-width="100px">
        <el-form-item label="月份" required><el-input v-model="monthlyForm.month" placeholder="如 2026-08" /></el-form-item>
        <el-form-item label="创建日期"><el-date-picker v-model="monthlyForm.task_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="任务标题"><el-input v-model="monthlyForm.title" /></el-form-item>
        <el-form-item label="任务描述"><el-input v-model="monthlyForm.content" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="责任人"><StaffSelect v-model="monthlyForm.assignee" /></el-form-item>
        <el-form-item label="计划完成"><el-date-picker v-model="monthlyForm.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="monthlyForm.status" style="width:100%">
            <el-option v-for="(v,k) in PLAN_STATUS_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="monthlyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMonthly">确定</el-button>
      </template>
    </el-dialog>

    <!-- 周计划对话框 -->
    <el-dialog v-model="weeklyVisible" :title="weeklyEditingId ? '编辑周计划' : '新增周计划'" width="560px">
      <el-form :model="weeklyForm" label-width="100px">
        <el-form-item label="周次" required><el-input v-model="weeklyForm.week" placeholder="如 2026-W32" /></el-form-item>
        <el-form-item label="创建日期"><el-date-picker v-model="weeklyForm.task_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="任务标题"><el-input v-model="weeklyForm.title" /></el-form-item>
        <el-form-item label="任务描述"><el-input v-model="weeklyForm.content" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="责任人"><StaffSelect v-model="weeklyForm.assignee" /></el-form-item>
        <el-form-item label="计划完成"><el-date-picker v-model="weeklyForm.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="weeklyForm.status" style="width:100%">
            <el-option v-for="(v,k) in PLAN_STATUS_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="weeklyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitWeekly">确定</el-button>
      </template>
    </el-dialog>

    <!-- 进展对话框 -->
    <el-dialog v-model="progressVisible" title="记录工作进展" width="520px">
      <el-form :model="progressForm" label-width="80px">
        <el-form-item label="日期"><el-date-picker v-model="progressForm.record_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="内容" required><el-input v-model="progressForm.content" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="progressVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProgress">确定</el-button>
      </template>
    </el-dialog>

    <!-- 成员待办对话框 -->
    <el-dialog v-model="taskVisible" title="成员待办" width="520px">
      <el-form :model="taskForm" label-width="80px">
        <el-form-item label="任务" required><el-input v-model="taskForm.title" /></el-form-item>
        <el-form-item label="负责人"><StaffSelect v-model="taskForm.assignee" /></el-form-item>
        <el-form-item label="截止"><el-date-picker v-model="taskForm.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="taskForm.status" style="width:100%">
            <el-option v-for="(v,k) in TASK_STATUS_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联">
          <el-select v-model="taskForm.link_type" style="width:100%">
            <el-option label="不关联" value="none" />
            <el-option label="关联里程碑" value="milestone" />
            <el-option label="关联月计划" value="monthly_plan" />
            <el-option label="关联周计划" value="weekly_plan" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="taskForm.link_type !== 'none'" label="关联对象">
          <el-select v-model="taskForm.link_id" style="width:100%" placeholder="选择关联对象">
            <el-option v-for="opt in taskLinkOptions" :key="opt.id" :label="opt.label" :value="opt.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTask">确定</el-button>
      </template>
    </el-dialog>
  </div>

  <!-- 周反馈邮件预览弹窗（负责人牵头制） -->
  <MailComposeDialog
    v-model="mailDialogVisible"
    :title="mailDialogTitle"
    :scene="mailDialogScene"
    :variables="mailDialogVariables"
    :default-to="mailDialogTo"
    :default-cc="mailDialogCc"
    :default-subject="mailDialogSubject"
    :default-body="mailDialogBody"
    value-key="email"
    @success="handleFeedbackMailSuccess"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as kwApi from '@/api/keywork.js'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import BusinessDomainSelect from '@/components/Common/BusinessDomainSelect.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import { usePasteUpload } from '@/composables/usePasteUpload.js'
import {
  CATEGORY_MAP, STATUS_MAP, PRIORITY_MAP, MS_STATUS_MAP, TASK_STATUS_MAP, PLAN_STATUS_MAP,
} from '@/api/keywork.js'

const route = useRoute()

// ---------- 列表状态 ----------
const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const activeCategory = ref('all')
const keyword = ref('')
const statusFilter = ref('')
const stats = ref({ by_status: {}, overdue_member_tasks: 0, upcoming_milestones: 0, total_member_tasks: 0, done_member_tasks: 0 })

const totalCount = computed(() => {
  const b = stats.value.by_category || {}
  return Object.values(b).reduce((a, c) => a + (c || 0), 0)
})

// ---------- 抽屉 / 详情 ----------
const drawerVisible = ref(false)
const currentId = ref(null)
const detail = ref(null)
const activeSection = ref('basic')

// ---------- 基本信息 对话框 ----------
const basicVisible = ref(false)
const basicIsEdit = ref(false)
const basicForm = ref(blankMain())
const acceptText = ref('')

function blankMain() {
  return {
    title: '', category: 'hq_pilot', domain_code: '', owner: '', priority: 'P2', status: 'planning',
    planned_finish_date: '', progress: 0, background: '', current_status: '', content: '', work_value: '',
  }
}

// ---------- 子表对话框状态 ----------
const goalVisible = ref(false)
const goalEditingId = ref(null)
const goalForm = ref({ indicator: '', target_value: '', current_value: '', unit: '', description: '' })

const milestoneVisible = ref(false)
const milestoneForm = ref({ name: '', due_date: '', status: 'not_started', note: '' })

const memberVisible = ref(false)
const memberForm = ref({ name: '', role: '', division_desc: '' })

const monthlyVisible = ref(false)
const monthlyEditingId = ref(null)
const monthlyForm = ref({ month: '', task_date: '', title: '', content: '', assignee: '', due_date: '', status: 'not_started' })

const weeklyVisible = ref(false)
const weeklyEditingId = ref(null)
const weeklyForm = ref({ week: '', task_date: '', title: '', content: '', assignee: '', due_date: '', status: 'not_started' })

const progressVisible = ref(false)
const progressForm = ref({ record_date: '', content: '' })

const taskVisible = ref(false)
const taskForm = ref({ title: '', assignee: '', due_date: '', status: 'not_started', link_type: 'none', link_id: null })

// 待办关联对象候选：按关联类型从当前工单子表取
const taskLinkOptions = computed(() => {
  const t = taskForm.value.link_type
  const d = detail.value
  if (!d) return []
  if (t === 'milestone') return (d.milestones || []).map((m) => ({ id: m.id, label: m.name || `里程碑#${m.id}` }))
  if (t === 'monthly_plan') {
    return (d.monthly_plans || []).map((p) => ({
      id: p.id, label: `${p.month} ${p.title || (p.content || '').slice(0, 20) || ''}`.trim(),
    }))
  }
  if (t === 'weekly_plan') {
    return (d.weekly_plans || []).map((p) => ({
      id: p.id, label: `${p.week} ${p.title || (p.content || '').slice(0, 20) || ''}`.trim(),
    }))
  }
  return []
})

// ---------- 周反馈（在途工单增量更新） ----------
const feedbackWeek = ref(currentIsoWeek())
const feedbackGroups = ref([])
const expandedAssignees = ref([])
const submittingAssignees = ref([])

// 邮件预览弹窗（负责人牵头制）
const mailDialogVisible = ref(false)
const mailDialogTitle = ref('发送周反馈请求')
const mailDialogTo = ref([])
const mailDialogCc = ref([])
const mailDialogSubject = ref('')
const mailDialogBody = ref('')
const mailDialogScene = ref('keywork_feedback')
const mailDialogVariables = ref({})
const mailDialogContext = ref({})

/** 用 feedbackGroups 真实数据构建周反馈邮件正文（Markdown） */
function buildFeedbackMailBody(g) {
  const week = feedbackWeek.value
  const kw = detail.value
  const title = kw?.title || ''
  const workNo = kw?.work_no || ''
  const lines = []

  // 头部
  lines.push(`【重点工作周反馈】${title}（${workNo}）- ${week} 周`)
  lines.push('')
  lines.push(`负责人：${g.assignee}`)
  lines.push('')

  // 一、本周工作进展反馈
  lines.push('## 一、本周工作进展反馈')
  lines.push('')

  // 1、月计划完成情况（仅月底显示）
  if (isMonthEnd.value) {
    lines.push('### 1、月计划完成情况（月底反馈）')
    if (g.monthly_items.length) {
      for (const it of g.monthly_items) {
        const checked = isItemChecked(g, it)
        lines.push(`- ${checked ? '✅' : '⬜'} ${itemLabel(it)}（${it.status || '—'}）`)
      }
    } else {
      lines.push('- （无关联月计划）')
    }
    lines.push('')
  }

  // 2、周计划完成情况反馈
  lines.push('### 2、周计划完成情况反馈')
  if (g.weekly_items.length) {
    for (const it of g.weekly_items) {
      const checked = isItemChecked(g, it)
      lines.push(`- ${checked ? '✅' : '⬜'} ${itemLabel(it)}（${it.status || '—'}）`)
    }
  } else {
    lines.push('- （暂无关联周计划）')
  }
  lines.push('')

  // 二、下周工作计划
  lines.push('## 二、下周工作计划')
  lines.push('')

  // 下月计划（仅月底显示）
  if (isMonthEnd.value) {
    lines.push('### 下月计划（月底反馈）')
    if (g._form.next_month_summary) {
      lines.push(g._form.next_month_summary)
    } else {
      lines.push('- （待填写）')
    }
    lines.push('')
  }

  // 下周计划
  lines.push('### 下周计划')
  if (g._form.next_summary) {
    lines.push(g._form.next_summary)
  } else {
    lines.push('- （待填写）')
  }
  lines.push('')

  // 三、成员待办管理
  lines.push('## 三、成员待办管理')
  lines.push('')
  const hasTasks = g.task_items.length || g._form.new_tasks.length
  if (hasTasks) {
    if (g.task_items.length) {
      for (const t of g.task_items) {
        const note = taskNote(g, t)
        const assignee = t.assignee || '未指派'
        const statusLabel = note.status ? (TASK_STATUS_MAP[note.status]?.label || note.status) : (t.status ? (TASK_STATUS_MAP[t.status]?.label || t.status) : '—')
        const noteText = note.note || t.note || ''
        lines.push(`- **${t.label || t.title || '（未命名）'}** — ${assignee} | ${statusLabel} | ${noteText || '（无进展说明）'}`)
      }
    }
    if (g._form.new_tasks.length) {
      lines.push('')
      lines.push('#### 新增成员任务')
      for (const t of g._form.new_tasks) {
        lines.push(`- ${t.title} — ${t.assignee || '未指派'} ${t.due_date ? '· ' + t.due_date : ''}`)
      }
    }
  } else {
    lines.push('- （暂无在途成员待办）')
  }
  lines.push('')

  // 四、风险 / 求助事件
  lines.push('## 四、风险 / 求助事件')
  if (g._form.risk_note) {
    lines.push(g._form.risk_note)
  } else {
    lines.push('- （无）')
  }
  lines.push('')

  // 整体进度
  lines.push(`**专题工作整体进度：${g._form.progress || 0}%**`)
  lines.push('')

  // 底部提示
  lines.push('反馈方式：直接回复本邮件，或线下同步给管理员在 PMWB「重点工作」详情页周反馈页签录入归档。')

  return lines.join('\n')
}

/** 打开周反馈邮件预览弹窗 */
function openFeedbackMailDialog(g, owner, week, title, workNo) {
  const body = buildFeedbackMailBody(g)
  mailDialogTo.value = [owner]
  mailDialogCc.value = []
  mailDialogSubject.value = `【周反馈请求】${title} - ${week} 周`
  mailDialogBody.value = body
  mailDialogScene.value = 'keywork_feedback'
  mailDialogVariables.value = {
    week,
    work_no: workNo,
    title,
    assignee: owner,
    body,
  }
  mailDialogContext.value = {}
  mailDialogVisible.value = true
}
const lastWeekFeedback = ref(null)
const isMonthEnd = ref(false)
const currentMonth = ref('')
const feedbackDeliverables = ref([])
const newTaskForm = ref({ title: '', assignee: '', due_date: '', note: '' })

/** 当前 ISO 周次 YYYY-Www（周一为一周起点） */
function currentIsoWeek() {
  const now = new Date()
  const day = (now.getDay() + 6) % 7
  // 挪到本周周四（ISO 年份以周四所在年为准）
  const thursday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - day + 3)
  const jan4 = new Date(thursday.getFullYear(), 0, 4)
  const jan4Iso = (jan4.getDay() + 6) % 7 + 1 // 1=周一 ... 7=周日
  const diffDays = Math.round((thursday - jan4) / 86400000)
  const week = Math.ceil((diffDays + jan4Iso) / 7)
  return `${thursday.getFullYear()}-W${String(week).padStart(2, '0')}`
}

function isExpanded(g) {
  return expandedAssignees.value.includes(g.assignee)
}

function toggleFeedbackCard(g) {
  const i = expandedAssignees.value.indexOf(g.assignee)
  if (i >= 0) expandedAssignees.value.splice(i, 1)
  else expandedAssignees.value.push(g.assignee)
}

/** 加载周反馈：台账 + 工作单（上周回顾/月计划/周计划/成员待办/交付物） */
async function loadWeeklyFeedback() {
  if (!currentId.value || !feedbackWeek.value) return
  try {
    const [ledger, form] = await Promise.all([
      kwApi.listWeeklyFeedbacks(currentId.value, feedbackWeek.value),
      kwApi.getWeeklyFeedbackForm(currentId.value, feedbackWeek.value),
    ])
    lastWeekFeedback.value = form.last_week_feedback || null
    isMonthEnd.value = !!form.is_month_end
    currentMonth.value = form.current_month || ''
    feedbackDeliverables.value = detail.value?.deliverables || []
    feedbackGroups.value = (form.groups || []).map((g) => {
      const fb = g.feedback || (ledger.items || []).find((i) => i.assignee === g.assignee) || null
      return {
        assignee: g.assignee,
        monthly_items: g.monthly_items || [],
        weekly_items: g.weekly_items || [],
        task_items: g.task_items || [],
        feedback: fb,
        _activePanels: ['summary', 'monthly', 'weekly', 'memberTask'],
        _form: {
          week: feedbackWeek.value,
          assignee: g.assignee,
          source: fb?.source || 'manual',
          feedback_date: fb?.feedback_date || new Date().toISOString().slice(0, 10),
          done_summary: fb?.done_summary || '',
          next_summary: fb?.next_summary || '',
          monthly_summary: fb?.monthly_summary || '',
          next_month_summary: fb?.next_month_summary || '',
          risk_note: fb?.risk_note || '',
          progress: fb?.progress ?? 0,
          item_updates: fb?.item_updates || [],
          member_task_notes: fb?.member_task_notes || [],
          new_tasks: [],
          deliverable_ids: fb?.deliverable_ids || [],
        },
      }
    })
  } catch (e) {
    ElMessage.error('加载周反馈失败：' + (e?.message || e))
  }
}

function isItemChecked(g, it) {
  return (g._form.item_updates || []).some((u) => u.type === it.type && u.id === it.id)
}

function toggleItemChecked(g, it, checked) {
  const updates = g._form.item_updates || []
  const i = updates.findIndex((u) => u.type === it.type && u.id === it.id)
  if (checked) {
    if (i < 0) updates.push({ type: it.type, id: it.id, status: 'completed' })
  } else if (i >= 0) {
    updates.splice(i, 1)
  }
}

function itemLabel(it) {
  const title = it.label || it.title || it.content || ''
  const typeName = { monthly: '月计划', weekly: '周计划', task: '成员待办' }[it.type] || it.type
  const suffix = it.assignee ? `（${it.assignee}）` : ''
  return `【${typeName}】${(title || '').slice(0, 40)}${suffix}`
}

function _findCurrentItem(u) {
  const g = feedbackGroups.value[0]
  if (!g) return null
  const list = u.type === 'monthly' ? g.monthly_items : u.type === 'weekly' ? g.weekly_items : g.task_items
  return list.find((it) => it.id === u.id) || null
}

function lastWeekItemLabel(u) {
  const it = _findCurrentItem(u)
  return it ? itemLabel(it) : `【${u.type}】#${u.id}`
}

function lastWeekItemStatus(u) {
  const it = _findCurrentItem(u)
  return it ? it.status : u.status
}

function taskNote(g, row) {
  const notes = g._form.member_task_notes || []
  let n = notes.find((x) => x.task_id === row.id)
  if (!n) {
    n = { task_id: row.id, note: row.note || '', status: row.status }
    notes.push(n)
  }
  return n
}

function ensureTaskNote(g, row) {
  taskNote(g, row) // 只保证对象存在；blur 时已经双向绑定
}

function setTaskStatus(g, row, status) {
  const n = taskNote(g, row)
  n.status = status
}

function addNewTask(g) {
  const t = newTaskForm.value
  if (!t.title.trim()) {
    ElMessage.warning('请输入新任务标题')
    return
  }
  g._form.new_tasks.push({
    title: t.title.trim(),
    assignee: t.assignee || '',
    due_date: t.due_date || null,
    note: t.note || '',
    status: 'not_started',
    link_type: 'none',
    link_id: null,
  })
  newTaskForm.value = { title: '', assignee: '', due_date: '', note: '' }
}

function removeNewTask(g, idx) {
  g._form.new_tasks.splice(idx, 1)
}

async function handleFeedbackDeliverableUpload(file, g) {
  try {
    const data = await kwApi.uploadDeliverable(currentId.value, file)
    g._form.deliverable_ids.push(data.id)
    feedbackDeliverables.value.push(data)
    ElMessage.success('交付物已上传')
    await refreshDetail({ silent: true })
  } catch (e) {
    ElMessage.error('上传失败：' + (e?.message || e))
  }
  return false
}

function removeFeedbackDeliverable(g, d) {
  const ids = g._form.deliverable_ids
  const i = ids.indexOf(d.id)
  if (i >= 0) ids.splice(i, 1)
  const list = feedbackDeliverables.value
  const j = list.findIndex((x) => x.id === d.id)
  if (j >= 0) list.splice(j, 1)
}

/** 提交单个负责人的周反馈（幂等 upsert） */
async function submitFeedback(g) {
  if (!g._form.assignee) return
  submittingAssignees.value.push(g.assignee)
  try {
    await kwApi.submitWeeklyFeedback(currentId.value, { ...g._form })
    ElMessage.success(`「${g.assignee}」负责人周反馈已归档`)
    await loadWeeklyFeedback()
    refreshDetail({ silent: true }) // 子项状态被批量更新，静默兜底保持一致
  } catch (e) {
    ElMessage.error('提交失败：' + (e?.message || e))
  } finally {
    const i = submittingAssignees.value.indexOf(g.assignee)
    if (i >= 0) submittingAssignees.value.splice(i, 1)
  }
}

/** 发送周反馈请求邮件（只发给负责人）— 改为预览确认后发送 */
async function openFeedbackMail() {
  if (!currentId.value) return
  const g = feedbackGroups.value[0]
  if (!g?.assignee) {
    ElMessage.warning('该工单未设置负责人')
    return
  }
  const kw = detail.value
  openFeedbackMailDialog(g, g.assignee, feedbackWeek.value, kw.title, kw.work_no)
}

/** 邮件预览弹窗确认发送回调 */
function handleFeedbackMailSuccess() {
  mailDialogVisible.value = false
  ElMessage.success('周反馈请求邮件已发送')
}

// ---------- 数据获取 ----------
async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (activeCategory.value !== 'all') params.category = activeCategory.value
    if (keyword.value) params.keyword = keyword.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await kwApi.listKeyWorks(params)
    list.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    stats.value = await kwApi.getKeyWorkStats()
  } catch (e) { /* 忽略 */ }
}

function handleCategoryChange() {
  page.value = 1
  fetchList()
}

/** 抽屉页签切换：进入「周反馈」时按当前周加载卡片流 */
function handleSectionChange(name) {
  if (name === 'feedback') loadWeeklyFeedback()
}

// ---------- 详情 ----------
let detailSeq = 0 // 竞态保护：连续操作时仅应用最后一次详情响应

async function openDetail(row) {
  currentId.value = row.id
  drawerVisible.value = true
  await refreshDetail()
}

/**
 * 刷新详情。
 * @param {object} opts
 *   - silent: true 表示静默兜底（本地已即时更新，失败不打扰用户）
 * 竞态保护：多次并发请求时仅最后一次结果生效，避免旧响应覆盖新数据。
 */
async function refreshDetail(opts = {}) {
  if (!currentId.value) return
  const { silent = false } = opts
  const seq = ++detailSeq
  try {
    const data = await kwApi.getKeyWork(currentId.value)
    if (seq === detailSeq) detail.value = data
  } catch (e) {
    if (!silent) ElMessage.error('刷新详情失败：' + (e?.message || e))
  }
}

/** 子表操作成功后：本地即时更新（秒级可见）+ 后台静默兜底保持一致 */
function localPatch(mutator) {
  if (!detail.value) return
  mutator(detail.value)
}

function patchAppend(listKey, row) {
  localPatch((d) => {
    if (!d[listKey]) d[listKey] = []
    d[listKey].push(row)
  })
}

function patchReplace(listKey, row) {
  localPatch((d) => {
    const arr = d[listKey] || []
    const i = arr.findIndex((x) => x.id === row.id)
    if (i >= 0) arr.splice(i, 1, row)
  })
}

function patchRemove(listKey, id) {
  localPatch((d) => {
    const arr = d[listKey] || []
    const i = arr.findIndex((x) => x.id === id)
    if (i >= 0) arr.splice(i, 1)
  })
}

function closeDrawer(done) {
  drawerVisible.value = false
  currentId.value = null
  detail.value = null
  if (done) done()
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.title}」？该操作将级联删除全部子表数据。`, '删除确认', { type: 'warning' })
  } catch (e) { return }
  await kwApi.deleteKeyWork(row.id)
  ElMessage.success('已删除')
  fetchList()
  fetchStats()
}

// ---------- 基本信息 提交 ----------
function openCreate() {
  basicIsEdit.value = false
  basicForm.value = blankMain()
  acceptText.value = ''
  basicVisible.value = true
}

function openBasicEdit() {
  if (!detail.value) return
  basicIsEdit.value = true
  const d = detail.value
  basicForm.value = {
    ...blankMain(),
    title: d.title, category: d.category, domain_code: d.domain_code || '', owner: d.owner || '', priority: d.priority,
    status: d.status, planned_finish_date: d.planned_finish_date || '', progress: d.progress ?? 0,
    background: d.background || '', current_status: d.current_status || '', content: d.content || '', work_value: d.work_value || '',
  }
  acceptText.value = (d.acceptance_criteria || []).join('\n')
  basicVisible.value = true
}

async function submitBasic() {
  if (!basicForm.value.title) { ElMessage.warning('请填写标题'); return }
  const acceptance = acceptText.value.split('\n').map(s => s.trim()).filter(Boolean)
  const payload = { ...basicForm.value, acceptance_criteria: acceptance }
  if (basicIsEdit.value) {
    await kwApi.updateKeyWork(currentId.value, payload)
    ElMessage.success('已更新')
    await refreshDetail()
  } else {
    const created = await kwApi.createKeyWork(payload)
    ElMessage.success('已创建')
    currentId.value = created.id
    drawerVisible.value = true
    await refreshDetail()
    fetchStats()
  }
  basicVisible.value = false
  fetchList()
}

// ---------- 目标 ----------
function openGoalDialog(row) {
  if (row) {
    goalEditingId.value = row.id
    goalForm.value = { indicator: row.indicator || '', target_value: row.target_value || '', current_value: row.current_value || '', unit: row.unit || '', description: row.description || '' }
  } else {
    goalEditingId.value = null
    goalForm.value = { indicator: '', target_value: '', current_value: '', unit: '', description: '' }
  }
  goalVisible.value = true
}

async function submitGoal() {
  const goals = [...(detail.value.goals || []).filter(g => g.id !== goalEditingId.value)]
  goals.push({ ...goalForm.value })
  const res = await kwApi.updateKeyWork(currentId.value, { goals })
  ElMessage.success('已保存目标')
  goalVisible.value = false
  detailSeq++ // 使进行中的旧详情响应失效
  detail.value = res
}

async function removeGoal(row) {
  const goals = (detail.value.goals || []).filter(g => g.id !== row.id)
  const res = await kwApi.updateKeyWork(currentId.value, { goals })
  ElMessage.success('已删除')
  detailSeq++
  detail.value = res
}

// ---------- 验收标准 ----------
function openAcceptDialog() {
  ElMessageBox.prompt('输入一条验收标准', '新增验收标准', { inputType: 'textarea' })
    .then(async ({ value }) => {
      const acc = [...(detail.value.acceptance_criteria || []), value.trim()].filter(Boolean)
      const res = await kwApi.updateKeyWork(currentId.value, { acceptance_criteria: acc })
      ElMessage.success('已添加')
      detailSeq++
      detail.value = res
    })
    .catch(() => {})
}

async function removeAccept(i) {
  const acc = [...(detail.value.acceptance_criteria || [])]
  acc.splice(i, 1)
  const res = await kwApi.updateKeyWork(currentId.value, { acceptance_criteria: acc })
  detailSeq++
  detail.value = res
}

// ---------- 里程碑 ----------
function openMilestoneDialog() {
  milestoneForm.value = { name: '', due_date: '', status: 'not_started', note: '' }
  milestoneVisible.value = true
}

async function submitMilestone() {
  if (!milestoneForm.value.name) { ElMessage.warning('请填写里程碑名称'); return }
  const row = await kwApi.addMilestone(currentId.value, milestoneForm.value)
  ElMessage.success('已添加')
  milestoneVisible.value = false
  patchAppend('milestones', row)
  await refreshDetail({ silent: true })
}

async function changeMilestoneStatus(row, v) {
  const updated = await kwApi.updateMilestone(currentId.value, row.id, { status: v })
  patchReplace('milestones', updated)
  await refreshDetail({ silent: true })
}

async function removeMilestone(row) {
  await kwApi.deleteMilestone(currentId.value, row.id)
  ElMessage.success('已删除')
  patchRemove('milestones', row.id)
  await refreshDetail({ silent: true })
}

// ---------- 成员 ----------
function openMemberDialog() {
  memberForm.value = { name: '', role: '', division_desc: '' }
  memberVisible.value = true
}

async function submitMember() {
  if (!memberForm.value.name) { ElMessage.warning('请填写姓名'); return }
  const row = await kwApi.addMember(currentId.value, memberForm.value)
  ElMessage.success('已添加')
  memberVisible.value = false
  patchAppend('members', row)
  await refreshDetail({ silent: true })
}

async function removeMember(row) {
  await kwApi.deleteMember(currentId.value, row.id)
  ElMessage.success('已删除')
  patchRemove('members', row.id)
  await refreshDetail({ silent: true })
}

// ---------- 月计划 ----------
function openMonthlyDialog(row) {
  if (row) {
    monthlyEditingId.value = row.id
    monthlyForm.value = {
      month: row.month || '',
      task_date: row.task_date || '',
      title: row.title || '',
      content: row.content || '',
      assignee: row.assignee || '',
      due_date: row.due_date || '',
      status: row.status || 'not_started',
    }
  } else {
    monthlyEditingId.value = null
    monthlyForm.value = { month: '', task_date: '', title: '', content: '', assignee: '', due_date: '', status: 'not_started' }
  }
  monthlyVisible.value = true
}

async function submitMonthly() {
  if (!monthlyForm.value.month) { ElMessage.warning('请填写月份'); return }
  const payload = { ...monthlyForm.value }
  if (monthlyEditingId.value) {
    const updated = await kwApi.updateMonthlyPlan(currentId.value, monthlyEditingId.value, payload)
    ElMessage.success('已更新月度计划')
    patchReplace('monthly_plans', updated)
  } else {
    const row = await kwApi.addMonthlyPlan(currentId.value, payload)
    ElMessage.success('已添加月度计划')
    patchAppend('monthly_plans', row)
  }
  monthlyVisible.value = false
  await refreshDetail({ silent: true })
}

async function changeMonthlyStatus(row, v) {
  const updated = await kwApi.updateMonthlyPlan(currentId.value, row.id, { status: v })
  patchReplace('monthly_plans', updated)
  await refreshDetail({ silent: true })
}

async function removeMonthly(row) {
  await kwApi.deleteMonthlyPlan(currentId.value, row.id)
  ElMessage.success('已删除')
  patchRemove('monthly_plans', row.id)
  await refreshDetail({ silent: true })
}

// ---------- 周计划 ----------
function openWeeklyDialog(row) {
  if (row) {
    weeklyEditingId.value = row.id
    weeklyForm.value = {
      week: row.week || '',
      task_date: row.task_date || '',
      title: row.title || '',
      content: row.content || '',
      assignee: row.assignee || '',
      due_date: row.due_date || '',
      status: row.status || 'not_started',
    }
  } else {
    weeklyEditingId.value = null
    weeklyForm.value = { week: '', task_date: '', title: '', content: '', assignee: '', due_date: '', status: 'not_started' }
  }
  weeklyVisible.value = true
}

async function submitWeekly() {
  if (!weeklyForm.value.week) { ElMessage.warning('请填写周次'); return }
  const payload = { ...weeklyForm.value }
  if (weeklyEditingId.value) {
    const updated = await kwApi.updateWeeklyPlan(currentId.value, weeklyEditingId.value, payload)
    ElMessage.success('已更新周计划')
    patchReplace('weekly_plans', updated)
  } else {
    const row = await kwApi.addWeeklyPlan(currentId.value, payload)
    ElMessage.success('已添加周计划')
    patchAppend('weekly_plans', row)
  }
  weeklyVisible.value = false
  await refreshDetail({ silent: true })
}

async function changeWeeklyStatus(row, v) {
  const updated = await kwApi.updateWeeklyPlan(currentId.value, row.id, { status: v })
  patchReplace('weekly_plans', updated)
  await refreshDetail({ silent: true })
}

async function removeWeekly(row) {
  await kwApi.deleteWeeklyPlan(currentId.value, row.id)
  ElMessage.success('已删除')
  patchRemove('weekly_plans', row.id)
  await refreshDetail({ silent: true })
}

// ---------- 进展 ----------
function openProgressDialog() {
  progressForm.value = { progress_date: '', content: '' }
  progressVisible.value = true
}

async function submitProgress() {
  if (!progressForm.value.content) { ElMessage.warning('请填写进展内容'); return }
  const row = await kwApi.addProgress(currentId.value, progressForm.value)
  ElMessage.success('已记录')
  progressVisible.value = false
  patchAppend('progresses', row)
  await refreshDetail({ silent: true })
}

async function removeProgress(row) {
  await kwApi.deleteProgress(currentId.value, row.id)
  ElMessage.success('已删除')
  patchRemove('progresses', row.id)
  await refreshDetail({ silent: true })
}

// ---------- 成员待办 ----------
function openTaskDialog() {
  taskForm.value = { title: '', assignee: '', due_date: '', status: 'not_started', link_type: 'none', link_id: null }
  taskVisible.value = true
}

async function submitTask() {
  if (!taskForm.value.title) { ElMessage.warning('请填写任务'); return }
  const row = await kwApi.addMemberTask(currentId.value, taskForm.value)
  ElMessage.success('已添加')
  taskVisible.value = false
  patchAppend('member_tasks', row)
  await refreshDetail({ silent: true })
}

async function changeTaskStatus(row, v) {
  const updated = await kwApi.updateMemberTask(currentId.value, row.id, { status: v })
  patchReplace('member_tasks', updated)
  await refreshDetail({ silent: true })
}

async function removeTask(row) {
  await kwApi.deleteMemberTask(currentId.value, row.id)
  ElMessage.success('已删除')
  patchRemove('member_tasks', row.id)
  await refreshDetail({ silent: true })
}

// ---------- 交付物 ----------
const deliverableZone = ref(null)

async function handleDeliverableUpload(file) {
  const data = await kwApi.uploadDeliverable(currentId.value, file)
  ElMessage.success('上传成功')
  patchAppend('deliverables', data)
  await refreshDetail({ silent: true })
  return false
}

const { isPasting } = usePasteUpload({
  targetRef: deliverableZone,
  enabled: computed(() => drawerVisible.value && activeSection.value === 'deliverable'),
  onFiles: async (files) => {
    for (const file of files) {
      try {
        await kwApi.uploadDeliverable(currentId.value, file)
      } catch (err) {
        ElMessage.error(`${file.name} 上传失败`)
        throw err
      }
    }
    ElMessage.success(`已粘贴上传 ${files.length} 个交付物`)
    await refreshDetail({ silent: true })
  },
})

async function downloadDeliverable(row) {
  const blob = await kwApi.downloadDeliverable(currentId.value, row.id)
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = row.file_name || 'download'
  a.click()
  window.URL.revokeObjectURL(url)
}

async function removeDeliverable(row) {
  await kwApi.deleteDeliverable(currentId.value, row.id)
  ElMessage.success('已删除')
  patchRemove('deliverables', row.id)
  await refreshDetail({ silent: true })
}

// ── 模版下载 / Excel 导入 ──
const importFileRef = ref(null)

function triggerImport() {
  importFileRef.value?.click()
}

async function handleDownloadTemplate() {
  try {
    const blob = await kwApi.downloadKeyworkTemplate()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '重点工作导入模版.xlsx'
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载模版失败：' + (e?.message || e))
  }
}

async function handleImportFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const res = await kwApi.importKeyWorks(file)
    const data = res || {}
    if (data.ok) {
      ElMessage.success(`导入成功：共 ${data.imported ?? data.total} 条重点工作`)
      fetchList()
      fetchStats()
    } else {
      const errs = (data.errors || []).slice(0, 5).map((x) => `行${x.row}:${x.message}`).join('；')
      ElMessage.warning('导入校验未通过：' + (errs || '请检查模版格式'))
    }
  } catch (err) {
    ElMessage.error('导入失败：' + (err?.message || err))
  } finally {
    e.target.value = ''
  }
}

onMounted(async () => {
  fetchList()
  fetchStats()
  // 深链：?id=task-{id} / ?id=milestone-{id}
  const deepLinkId = route.query.id
  if (deepLinkId) {
    const match = String(deepLinkId).match(/^(task|milestone)-(\d+)$/)
    if (match) {
      const [, type, childId] = match
      try {
        const res = await kwApi.findKeyWorkByChild(type, childId)
        const kwId = res?.key_work_id  // 拦截器已解包，res 直接为 data.data
        if (kwId) {
          const detail = await kwApi.getKeyWork(kwId)
          if (detail) await openDetail(detail)
        }
      } catch { /* 深链降级静默 */ }
    }
  }
})
</script>

<style scoped>
.kpi-strip { margin-bottom: 4px; }
.table-toolbar { display: flex; gap: 10px; align-items: center; padding: 16px 20px; flex-wrap: wrap; }
.table-footer { padding: 12px 20px; border-top: 1px solid var(--border-subtle); display: flex; justify-content: flex-end; }
.drawer-tabs { padding: 0 8px; }
.sec-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.paste-upload-inline { outline: none; border-radius: 4px; transition: box-shadow 0.2s, background-color 0.2s; padding: 4px; margin: -4px; }
.paste-upload-inline:focus-visible { box-shadow: 0 0 0 2px var(--el-color-primary-light-5); background-color: var(--el-fill-color-light) }
.paste-hint { font-size: 11.5px; color: var(--text-muted); margin-bottom: 10px; margin-top: -6px; }
.sec-body { padding: 4px 2px; }
/* 长文本字段：垂直串行，独占整行 */
.info-stack { display: flex; flex-direction: column; gap: 18px; }
.info-block .info-text { font-size: 13.5px; color: var(--text-primary); line-height: 1.75; white-space: pre-wrap; word-break: break-word; }
/* 短字段：两列并排网格 */
.info-grid-compact { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 24px; margin-bottom: 18px; }
.info-item { font-size: 13.5px; color: var(--text-primary); line-height: 1.6; }
.info-item .pm-field-label { margin-bottom: 4px; }
.info-progress { margin-top: 4px; }
.accept-list { display: flex; flex-direction: column; gap: 8px; }
.accept-item { display: flex; align-items: center; gap: 10px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: 9px; padding: 8px 12px; }
.accept-idx { width: 22px; height: 22px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.accept-text { flex: 1; font-size: 13.5px; }
.progress-timeline { padding: 8px 4px; }
.progress-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 13.5px; }
.drawer-head-custom { display: flex; align-items: center; justify-content: space-between; width: 100%; padding-right: 24px; }
/* 周反馈卡片流 */
.feedback-list { display: flex; flex-direction: column; gap: 10px; }
.feedback-card { border: 1px solid var(--border-subtle); border-radius: 10px; background: var(--bg-app); overflow: hidden; }
.feedback-card-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; cursor: pointer; transition: background-color 0.2s; }
.feedback-card-head:hover { background: var(--el-fill-color-light); }
.feedback-assignee { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.feedback-hint { font-size: 12px; color: var(--text-muted); line-height: 1.4; }
.feedback-card-body { border-top: 1px dashed var(--border-subtle); padding: 12px 14px 4px; }
.feedback-card-actions { display: flex; justify-content: flex-end; padding-bottom: 10px; }
.feedback-items { display: flex; flex-direction: column; gap: 6px; }
.feedback-items .el-checkbox { margin-right: 0; height: auto; white-space: normal; }
.feedback-item-row { display: flex; align-items: center; gap: 8px; font-size: 13px; }
/* 周反馈折叠面板 */
.feedback-card-body .el-collapse-item__header { font-size: 13px; font-weight: 500; }
.feedback-last-week { display: flex; flex-direction: column; gap: 10px; }
.feedback-last-week .info-label { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
.feedback-last-week .info-text { font-size: 13px; color: var(--text-primary); line-height: 1.6; white-space: pre-wrap; }
.feedback-textarea-item { margin-top: 12px; }
.feedback-section-subtitle { font-size: 13px; font-weight: 500; color: var(--text-primary); margin: 12px 0 8px; }
/* 成员任务 */
.feedback-task-table { margin-bottom: 10px; }
.feedback-new-task-form { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.feedback-new-task-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.feedback-new-task-row { display: flex; align-items: center; gap: 8px; font-size: 13px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 6px 10px; }
/* 交付物 */
.feedback-deliverable-list { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
.feedback-deliverable-row { display: flex; align-items: center; gap: 8px; font-size: 13px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 6px 10px; }
.feedback-deliverable-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
