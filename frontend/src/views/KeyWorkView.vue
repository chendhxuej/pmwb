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
            <span class="pm-tag" :class="STATUS_MAP[row.status]?.tag">{{ STATUS_MAP[row.status]?.label }}</span>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <span class="pm-tag" :class="PRIORITY_MAP[row.priority]?.tag">{{ PRIORITY_MAP[row.priority]?.label }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="110" />
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
      size="860px"
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

      <el-tabs v-model="activeSection" class="drawer-tabs">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <div v-if="detail" class="sec-body">
            <div class="info-grid">
              <div class="info-item"><span class="pm-field-label">工作背景</span>{{ detail.background || '—' }}</div>
              <div class="info-item"><span class="pm-field-label">现状说明</span>{{ detail.current_status || '—' }}</div>
              <div class="info-item"><span class="pm-field-label">工作内容</span>{{ detail.content || '—' }}</div>
              <div class="info-item"><span class="pm-field-label">负责人</span>{{ detail.owner || '—' }}</div>
              <div class="info-item"><span class="pm-field-label">优先级</span>
                <span class="pm-tag" :class="PRIORITY_MAP[detail.priority]?.tag">{{ PRIORITY_MAP[detail.priority]?.label }}</span>
              </div>
              <div class="info-item"><span class="pm-field-label">生命周期状态</span>
                <span class="pm-tag" :class="STATUS_MAP[detail.status]?.tag">{{ STATUS_MAP[detail.status]?.label }}</span>
              </div>
              <div class="info-item"><span class="pm-field-label">计划完成时间</span>{{ detail.planned_finish_date || '—' }}</div>
              <div class="info-item"><span class="pm-field-label">进度</span>{{ detail.progress || 0 }}%</div>
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
            <el-table-column prop="division" label="分工说明" min-width="180" show-overflow-tooltip />
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
            <el-table-column prop="month" label="月份" width="120" />
            <el-table-column prop="content" label="计划内容" min-width="240" show-overflow-tooltip />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
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
            <el-table-column prop="week" label="周次" width="120" />
            <el-table-column prop="content" label="计划内容" min-width="240" show-overflow-tooltip />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
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
              :timestamp="p.progress_date"
              placement="top"
            >
              <div class="progress-item">
                <span>{{ p.content }}</span>
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
            <el-upload
              :show-file-list="false"
              :before-upload="handleDeliverableUpload"
              accept="*"
            >
              <el-button size="small" type="primary"><el-icon><Upload /></el-icon> 上传交付物</el-button>
            </el-upload>
          </div>
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
        <el-form-item label="负责人">
          <el-input v-model="basicForm.owner" placeholder="牵头人 / 负责人" />
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
        <el-form-item label="工作背景">
          <el-input v-model="basicForm.background" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="现状说明">
          <el-input v-model="basicForm.current_status" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="工作内容">
          <el-input v-model="basicForm.content" type="textarea" :rows="3" />
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
        <el-form-item label="姓名" required><el-input v-model="memberForm.name" /></el-form-item>
        <el-form-item label="角色"><el-input v-model="memberForm.role" /></el-form-item>
        <el-form-item label="分工"><el-input v-model="memberForm.division" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMember">确定</el-button>
      </template>
    </el-dialog>

    <!-- 月计划对话框 -->
    <el-dialog v-model="monthlyVisible" title="月度计划" width="480px">
      <el-form :model="monthlyForm" label-width="80px">
        <el-form-item label="月份" required><el-input v-model="monthlyForm.month" placeholder="如 2026-08" /></el-form-item>
        <el-form-item label="内容" required><el-input v-model="monthlyForm.content" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="monthlyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMonthly">确定</el-button>
      </template>
    </el-dialog>

    <!-- 周计划对话框 -->
    <el-dialog v-model="weeklyVisible" title="周计划" width="480px">
      <el-form :model="weeklyForm" label-width="80px">
        <el-form-item label="周次" required><el-input v-model="weeklyForm.week" placeholder="如 2026-W32" /></el-form-item>
        <el-form-item label="内容" required><el-input v-model="weeklyForm.content" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="weeklyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitWeekly">确定</el-button>
      </template>
    </el-dialog>

    <!-- 进展对话框 -->
    <el-dialog v-model="progressVisible" title="记录工作进展" width="520px">
      <el-form :model="progressForm" label-width="80px">
        <el-form-item label="日期"><el-date-picker v-model="progressForm.progress_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
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
        <el-form-item label="负责人"><el-input v-model="taskForm.assignee" /></el-form-item>
        <el-form-item label="截止"><el-date-picker v-model="taskForm.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="taskForm.status" style="width:100%">
            <el-option v-for="(v,k) in TASK_STATUS_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联">
          <el-select v-model="taskForm.link" style="width:100%">
            <el-option label="不关联" value="none" />
            <el-option label="关联里程碑" value="milestone" />
            <el-option label="关联月计划" value="monthly_plan" />
            <el-option label="关联周计划" value="weekly_plan" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTask">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as kwApi from '@/api/keywork.js'
import {
  CATEGORY_MAP, STATUS_MAP, PRIORITY_MAP, MS_STATUS_MAP, TASK_STATUS_MAP,
} from '@/api/keywork.js'

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
    title: '', category: 'hq_pilot', owner: '', priority: 'P2', status: 'planning',
    planned_finish_date: '', background: '', current_status: '', content: '',
  }
}

// ---------- 子表对话框状态 ----------
const goalVisible = ref(false)
const goalEditingId = ref(null)
const goalForm = ref({ indicator: '', target_value: '', current_value: '', unit: '', description: '' })

const milestoneVisible = ref(false)
const milestoneForm = ref({ name: '', due_date: '', status: 'pending', note: '' })

const memberVisible = ref(false)
const memberForm = ref({ name: '', role: '', division: '' })

const monthlyVisible = ref(false)
const monthlyForm = ref({ month: '', content: '' })

const weeklyVisible = ref(false)
const weeklyForm = ref({ week: '', content: '' })

const progressVisible = ref(false)
const progressForm = ref({ progress_date: '', content: '' })

const taskVisible = ref(false)
const taskForm = ref({ title: '', assignee: '', due_date: '', status: 'todo', link: 'none' })

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

// ---------- 详情 ----------
async function openDetail(row) {
  currentId.value = row.id
  drawerVisible.value = true
  await refreshDetail()
}

async function refreshDetail() {
  if (!currentId.value) return
  detail.value = await kwApi.getKeyWork(currentId.value)
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
    title: d.title, category: d.category, owner: d.owner || '', priority: d.priority,
    status: d.status, planned_finish_date: d.planned_finish_date || '',
    background: d.background || '', current_status: d.current_status || '', content: d.content || '',
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
  await kwApi.updateKeyWork(currentId.value, { goals })
  ElMessage.success('已保存目标')
  goalVisible.value = false
  await refreshDetail()
}

async function removeGoal(row) {
  const goals = (detail.value.goals || []).filter(g => g.id !== row.id)
  await kwApi.updateKeyWork(currentId.value, { goals })
  ElMessage.success('已删除')
  await refreshDetail()
}

// ---------- 验收标准 ----------
function openAcceptDialog() {
  ElMessageBox.prompt('输入一条验收标准', '新增验收标准', { inputType: 'textarea' })
    .then(async ({ value }) => {
      const acc = [...(detail.value.acceptance_criteria || []), value.trim()].filter(Boolean)
      await kwApi.updateKeyWork(currentId.value, { acceptance_criteria: acc })
      ElMessage.success('已添加')
      await refreshDetail()
    })
    .catch(() => {})
}

async function removeAccept(i) {
  const acc = [...(detail.value.acceptance_criteria || [])]
  acc.splice(i, 1)
  await kwApi.updateKeyWork(currentId.value, { acceptance_criteria: acc })
  await refreshDetail()
}

// ---------- 里程碑 ----------
function openMilestoneDialog() {
  milestoneForm.value = { name: '', due_date: '', status: 'pending', note: '' }
  milestoneVisible.value = true
}

async function submitMilestone() {
  if (!milestoneForm.value.name) { ElMessage.warning('请填写里程碑名称'); return }
  await kwApi.addMilestone(currentId.value, milestoneForm.value)
  ElMessage.success('已添加')
  milestoneVisible.value = false
  await refreshDetail()
}

async function changeMilestoneStatus(row, v) {
  await kwApi.updateMilestone(currentId.value, row.id, { status: v })
  await refreshDetail()
}

async function removeMilestone(row) {
  await kwApi.deleteMilestone(currentId.value, row.id)
  ElMessage.success('已删除')
  await refreshDetail()
}

// ---------- 成员 ----------
function openMemberDialog() {
  memberForm.value = { name: '', role: '', division: '' }
  memberVisible.value = true
}

async function submitMember() {
  if (!memberForm.value.name) { ElMessage.warning('请填写姓名'); return }
  await kwApi.addMember(currentId.value, memberForm.value)
  ElMessage.success('已添加')
  memberVisible.value = false
  await refreshDetail()
}

async function removeMember(row) {
  await kwApi.deleteMember(currentId.value, row.id)
  ElMessage.success('已删除')
  await refreshDetail()
}

// ---------- 月计划 ----------
function openMonthlyDialog() {
  monthlyForm.value = { month: '', content: '' }
  monthlyVisible.value = true
}

async function submitMonthly() {
  if (!monthlyForm.value.month || !monthlyForm.value.content) { ElMessage.warning('请填写月份与内容'); return }
  await kwApi.addMonthlyPlan(currentId.value, monthlyForm.value)
  ElMessage.success('已添加')
  monthlyVisible.value = false
  await refreshDetail()
}

async function removeMonthly(row) {
  await kwApi.deleteMonthlyPlan(currentId.value, row.id)
  ElMessage.success('已删除')
  await refreshDetail()
}

// ---------- 周计划 ----------
function openWeeklyDialog() {
  weeklyForm.value = { week: '', content: '' }
  weeklyVisible.value = true
}

async function submitWeekly() {
  if (!weeklyForm.value.week || !weeklyForm.value.content) { ElMessage.warning('请填写周次与内容'); return }
  await kwApi.addWeeklyPlan(currentId.value, weeklyForm.value)
  ElMessage.success('已添加')
  weeklyVisible.value = false
  await refreshDetail()
}

async function removeWeekly(row) {
  await kwApi.deleteWeeklyPlan(currentId.value, row.id)
  ElMessage.success('已删除')
  await refreshDetail()
}

// ---------- 进展 ----------
function openProgressDialog() {
  progressForm.value = { progress_date: '', content: '' }
  progressVisible.value = true
}

async function submitProgress() {
  if (!progressForm.value.content) { ElMessage.warning('请填写进展内容'); return }
  await kwApi.addProgress(currentId.value, progressForm.value)
  ElMessage.success('已记录')
  progressVisible.value = false
  await refreshDetail()
}

async function removeProgress(row) {
  await kwApi.deleteProgress(currentId.value, row.id)
  ElMessage.success('已删除')
  await refreshDetail()
}

// ---------- 成员待办 ----------
function openTaskDialog() {
  taskForm.value = { title: '', assignee: '', due_date: '', status: 'todo', link: 'none' }
  taskVisible.value = true
}

async function submitTask() {
  if (!taskForm.value.title) { ElMessage.warning('请填写任务'); return }
  await kwApi.addMemberTask(currentId.value, taskForm.value)
  ElMessage.success('已添加')
  taskVisible.value = false
  await refreshDetail()
}

async function changeTaskStatus(row, v) {
  await kwApi.updateMemberTask(currentId.value, row.id, { status: v })
  await refreshDetail()
}

async function removeTask(row) {
  await kwApi.deleteMemberTask(currentId.value, row.id)
  ElMessage.success('已删除')
  await refreshDetail()
}

// ---------- 交付物 ----------
async function handleDeliverableUpload(file) {
  await kwApi.uploadDeliverable(currentId.value, file)
  ElMessage.success('上传成功')
  await refreshDetail()
  return false
}

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
  await refreshDetail()
}

onMounted(() => {
  fetchList()
  fetchStats()
})
</script>

<style scoped>
.kpi-strip { margin-bottom: 4px; }
.table-toolbar { display: flex; gap: 10px; align-items: center; padding: 16px 20px; flex-wrap: wrap; }
.table-footer { padding: 12px 20px; border-top: 1px solid var(--border-subtle); display: flex; justify-content: flex-end; }
.drawer-tabs { padding: 0 8px; }
.sec-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.sec-body { padding: 4px 2px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 24px; }
.info-item { font-size: 13.5px; color: var(--text-primary); line-height: 1.6; }
.info-item .pm-field-label { margin-bottom: 2px; }
.accept-list { display: flex; flex-direction: column; gap: 8px; }
.accept-item { display: flex; align-items: center; gap: 10px; background: var(--bg-app); border: 1px solid var(--border-subtle); border-radius: 9px; padding: 8px 12px; }
.accept-idx { width: 22px; height: 22px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.accept-text { flex: 1; font-size: 13.5px; }
.progress-timeline { padding: 8px 4px; }
.progress-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 13.5px; }
.drawer-head-custom { display: flex; align-items: center; justify-content: space-between; width: 100%; padding-right: 24px; }
</style>
