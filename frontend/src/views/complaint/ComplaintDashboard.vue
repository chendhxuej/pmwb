<template>
  <div class="complaint-dashboard">
    <PageHeader title="投诉现状分析" :subtitle="subTitle">
      <template #actions>
        <el-select v-if="weekOptions.length" v-model="selectedWeek" style="width: 168px" @change="onWeekChange">
          <el-option v-for="w in weekOptions" :key="w" :label="weekLabel(w)" :value="w" />
        </el-select>
        <el-button :icon="Upload" type="primary" plain @click="uploadVisible = true">上传工单数据</el-button>
        <el-tooltip :content="reportTip" placement="bottom">
          <el-button :icon="Download" :disabled="!metrics.week" @click="openReport">
            周报 {{ metrics.week || '' }}<span v-if="reportStale" class="stale-dot">· 数据已更新</span>
          </el-button>
        </el-tooltip>
        <el-tooltip content="保存 HTML 文件（含全周期投诉全貌，内联图表可离线打开）" placement="bottom">
          <el-button class="report-html-download" :icon="Document" :disabled="!metrics.week"
                     :loading="reportDownloading" @click="downloadReportHtml">
            下载 HTML
          </el-button>
        </el-tooltip>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 整体投诉全貌（2026-11-11）：进入页面第一屏即可判断全貌 / 重点问题 / 异常波动。
         独立组件，下钻复用本页唯一的 TicketDrillDrawer；下方周维度区块原样不动。 -->
    <OverallOverview :data="overall" @drill="drill" />

    <!-- 主要投诉点速览（新闭集 · 与「主要投诉点」页同源，定位系统改造落点） -->
    <section class="card mp-overview">
      <div class="card-header">
        <h3>主要投诉点（功能模块问题 · 闭集）</h3>
        <span class="hint">上方 KPI 为全周期累计；下方 TOP 为所选周单量（vL2 闭集字典）</span>
        <el-button class="ml-auto" size="small" type="primary" plain @click="goModuleProblemPage">查看完整主要投诉点 →</el-button>
      </div>
      <div class="card-body">
        <div class="pm-stat-grid pm-stat-grid--5">
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">总工单</span></div>
            <div class="pm-stat__val">{{ mpSummary.total_tickets ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">缺陷已归集</span></div>
            <div class="pm-stat__val is-accent">{{ mpSummary.defect_classified ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">缺陷类数</span></div>
            <div class="pm-stat__val">{{ mpSummary.defect_classes ?? 0 }}<span class="pm-stat__unit">个</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">未归类</span></div>
            <div class="pm-stat__val" :class="(mpSummary.unclassified || 0) ? 'is-warning' : 'is-success'">{{ mpSummary.unclassified ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
          <div class="pm-stat">
            <div class="pm-stat__top"><span class="pm-stat__label">咨询类（隔离）</span></div>
            <div class="pm-stat__val is-muted">{{ mpSummary.consult ?? 0 }}<span class="pm-stat__unit">单</span></div>
          </div>
        </div>
        <div class="mp-top">
          <div class="mp-top__title">TOP 缺陷类（{{ metrics.week || '所选周' }} 单量，点击下钻该周工单）</div>
          <div class="mp-top__list">
            <div v-for="(c, i) in mpTop" :key="c.module_problem_id" class="mp-top__item"
                 @click="drill({ week: metrics.week, module_problem_id: c.module_problem_id }, '主要投诉点·' + c.name)">
              <span class="mp-rank">{{ i + 1 }}</span>
              <span class="mp-name" :title="c.name">{{ c.name }}</span>
              <span class="mp-cnt">{{ c.week_cnt ?? 0 }} 单</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div v-if="metrics.week" v-loading="loading" class="dashboard-body">
      <!-- 一、本周概览与波动 -->
      <section class="card">
        <div class="card-header">
          <h3>一、本周概览与波动</h3>
          <span class="hint">区间 {{ metrics.range }}</span>
        </div>
        <div class="card-body">
          <div class="pm-stat-grid pm-stat-grid--6">
            <div class="pm-stat is-clickable" title="点击下钻本周工单" @click="drill({ week: metrics.week }, '本周新增投诉工单')">
              <div class="pm-stat__top"><span class="pm-stat__label">本周新增</span></div>
              <div class="pm-stat__val is-accent">{{ metrics.total }}<span class="pm-stat__unit">单</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">日均</span></div>
              <div class="pm-stat__val">{{ metrics.daily_avg }}<span class="pm-stat__unit">单</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">周环比</span></div>
              <div class="pm-stat__val" :class="wowClass">{{ wowText }}</div>
            </div>
            <div class="pm-stat is-clickable" title="已知问题率越低，说明越在追新火" @click="drill({ week: metrics.week, known_flag: 0 }, '本周新增问题工单')">
              <div class="pm-stat__top"><span class="pm-stat__label">已知问题率</span></div>
              <div class="pm-stat__val" :class="known.known_rate >= 50 ? 'is-success' : 'is-danger'">{{ known.known_rate ?? 0 }}<span class="pm-stat__unit">%</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">根因分析覆盖</span></div>
              <div class="pm-stat__val" :class="(rc.coverage_pct || 0) >= 95 ? 'is-success' : 'is-warning'">{{ rc.coverage_pct ?? 0 }}<span class="pm-stat__unit">%</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">涉及根因簇</span></div>
              <div class="pm-stat__val">{{ rc.cluster_cnt ?? 0 }}<span class="pm-stat__unit">簇</span></div>
            </div>
          </div>

          <div v-if="partialBase" class="pm-note warn">
            上周（{{ metrics.prev_week }}）仅 {{ metrics.prev_days }} 天数据，<b>周环比不可比</b>——
            本页不给环比结论，不用残缺数据硬算（否则会把导入节奏误判成暴涨暴跌）。
          </div>

          <div class="sub-h cmp-title">
            日走势三线对标
            <span class="hint">同口径按「周内第几天」对齐：上周同星期 vs 上月同期（{{ metrics.prev_month }}，4 周前）</span>
          </div>
          <div class="cmp-line">
            <span class="cmp-item"><i class="dot dot-cur"></i>本周（已过 {{ cmpDays }} 天）<b>{{ cmpCurTotal }}</b> 单 / 日均 {{ cmpCurAvg }}</span>
            <span class="cmp-sep">｜</span>
            <span class="cmp-item"><i class="dot dot-prev"></i>上周同期 <b>{{ cmpPrevWeekTotal }}</b> 单 / 日均 {{ cmpPrevWeekAvg }}</span>
            <span class="cmp-sep">｜</span>
            <span class="cmp-item"><i class="dot dot-month"></i>上月同期 <b>{{ cmpPrevMonthTotal }}</b> 单 / 日均 {{ cmpPrevMonthAvg }}</span>
            <span class="cmp-tip">三线同按 {{ cmpDays }} 天截断对比；折线里基准线为整周实际走势</span>
          </div>

          <ChartLine :x-data="dailyX" :series="dailySeries" height="260px" />
        </div>
      </section>

      <!-- 二、已知 vs 新增 -->
      <section class="card">
        <div class="card-header">
          <h3>二、已知问题 vs 新增问题（核心指标）</h3>
          <span class="hint">判定：工单 →（根因簇 / 功能模块问题）是否被在办问题收纳；使用咨询不计入</span>
        </div>
        <div class="card-body">
          <div class="pm-stat-grid pm-stat-grid--5">
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">已知问题率</span></div>
              <div class="pm-stat__val" :class="known.known_rate >= 50 ? 'is-success' : 'is-danger'">{{ known.known_rate ?? 0 }}<span class="pm-stat__unit">%</span></div>
              <div class="pm-stat__sub">分母 = 已判定单量</div>
            </div>
            <div class="pm-stat is-clickable" @click="drill({ week: metrics.week, known_flag: 1 }, '已知问题工单')">
              <div class="pm-stat__top"><span class="pm-stat__label">已知问题</span></div>
              <div class="pm-stat__val is-danger">{{ known.known_cnt ?? 0 }}<span class="pm-stat__unit">单</span></div>
            </div>
            <div class="pm-stat is-clickable" @click="drill({ week: metrics.week, known_flag: 0 }, '新增问题工单')">
              <div class="pm-stat__top"><span class="pm-stat__label">新增问题</span></div>
              <div class="pm-stat__val is-accent">{{ known.new_cnt ?? 0 }}<span class="pm-stat__unit">单</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">使用咨询</span></div>
              <div class="pm-stat__val">{{ known.consult_cnt ?? 0 }}<span class="pm-stat__unit">单</span></div>
              <div class="pm-stat__sub">非缺陷，不计入</div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">已判定 / 总量</span></div>
              <div class="pm-stat__val">{{ known.judged ?? 0 }} / {{ known.total ?? metrics.total }}</div>
            </div>
          </div>

          <div class="pm-note">
            候选问题不计为已知——<b>没进台账就等于组织还没认账</b>。
            本周有 <b>{{ known.potential_known_cnt ?? 0 }}</b> 单属于「AI 已识别、待确认入账」，
            当前在办问题 <b>{{ known.inflight_problem_cnt ?? 0 }}</b> 个。
            <span v-if="known.consult_cnt">另有 <b>{{ known.consult_cnt }}</b> 单为使用咨询（非缺陷），不计入已知率分母。</span>
            <span v-if="known.unknown_cnt">另有 {{ known.unknown_cnt }} 单无法判定，不计入分母。</span>
          </div>

          <div class="sub-h">已知问题（按本周命中单量）</div>
          <el-table :data="known.known_problems || []" size="small" empty-text="本周没有一单能被在办问题解释">
            <el-table-column prop="problem_no" label="问题编号" width="150" />
            <el-table-column prop="title" label="在办问题（根因摘要）" min-width="280" show-overflow-tooltip />
            <el-table-column prop="owner" label="责任人" width="110" />
            <el-table-column label="本周命中" width="96" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column label="状态" width="92" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'resolving' ? 'warning' : 'primary'" size="small" effect="light">
                  {{ row.status === 'resolving' ? '处理中' : '在办' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drill({ week: metrics.week, known_flag: 1, known_problem_no: row.problem_no }, '已知问题·' + row.problem_no)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="sub-h">新增问题（本周出现、台账未收纳 → 应入账）</div>
          <el-table :data="known.new_clusters || []" size="small" empty-text="本周无新增问题">
            <el-table-column label="新增问题（根因簇）" min-width="300" show-overflow-tooltip>
              <template #default="{ row }"><b>{{ row.title || row.rootcause_no || '未归簇' }}</b></template>
            </el-table-column>
            <el-table-column prop="fault_system" label="系统" width="110" />
            <el-table-column prop="fault_stage" label="环节" width="100" />
            <el-table-column label="单量" width="76" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column label="候选状态" width="130" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.in_candidate" type="primary" size="small" effect="light">{{ row.cand_problem_no }}</el-tag>
                <el-tag v-else type="warning" size="small" effect="light">待入账</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillRootcause(row, { known_flag: 0 })">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <!-- 三、分类汇总 -->
      <section class="card">
        <div class="card-header">
          <h3>三、问题族分析（业务链路）</h3>
          <span class="hint">
            环比按日均对比（本周 {{ th.week_days || 0 }} 天 / 上周 {{ th.prev_days || 0 }} 天）；
            下钻按 {{ th.week || metrics.week || '所选周' }} 工单，「累计」列仅供全周期参考
          </span>
        </div>
        <div class="card-body">
          <el-table class="theme-table" :data="themeRows" size="small" empty-text="暂无问题族数据">
            <el-table-column label="问题族（业务链路）" min-width="170">
              <template #default="{ row }">
                <b>{{ row.name }}</b>
                <el-tag v-if="row.is_new" size="small" type="danger" class="rule-tag">本周新增</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="本周" width="70" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.week_cnt }}</b></template>
            </el-table-column>
            <el-table-column label="上周日均" width="86" align="right">
              <template #default="{ row }">{{ row.prev_avg }}</template>
            </el-table-column>
            <el-table-column label="本周日均" width="86" align="right">
              <template #default="{ row }">{{ row.avg }}</template>
            </el-table-column>
            <el-table-column label="日均环比" width="110" align="center">
              <template #default="{ row }">
                <!-- 「—」三种情况：本周无单 / 上周无单 / 上周数据不足。硬算 -100% 会被误读成已清零 -->
                <span v-if="row.wow === null || row.wow === undefined" class="text-muted" :title="row.wow_note || '缺少可比基期'">—</span>
                <span v-else :class="row.wow > 0 ? 'num-red' : 'num-green'">
                  {{ row.wow > 0 ? '+' : '' }}{{ row.wow }}%
                </span>
                <el-tag v-if="row.low_sample" size="small" type="info" class="rule-tag">样本小</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="累计" width="72" align="right">
              <template #default="{ row }">{{ row.total_cnt }}</template>
            </el-table-column>
            <el-table-column label="问题簇" width="76" align="center">
              <template #default="{ row }">{{ row.problem_cluster_cnt }}</template>
            </el-table-column>
            <el-table-column label="主要问题（累计 TOP）" min-width="300">
              <template #default="{ row }">
                <div v-for="c in row.top_clusters" :key="c.rc_no" class="top-cluster">
                  <span class="tc-cnt">{{ c.cnt }} 单</span>
                  <span class="tc-title">{{ c.title }}</span>
                </div>
                <span v-if="!row.top_clusters.length" class="text-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillTheme(row)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="case-line">
            <el-icon><InfoFilled /></el-icon>
            另有 <b>{{ th.cases?.cluster_cnt || 0 }}</b> 个一次性个案（共
            {{ th.cases?.ticket_cnt || 0 }} 单，仅出现 1 次、无同类可比），不计入族汇总；
            <span v-if="th.new_case_cnt">本周新增 {{ th.new_case_cnt }} 个。</span>
            <el-button v-if="th.cases?.cluster_cnt" size="small" text type="primary"
              @click="drillCases">查看个案明细（全周期）</el-button>
          </div>
          <div v-if="th.unattributed?.cnt" class="case-line warn">
            未归因工单 {{ th.unattributed.cnt }} 单（根因分析未完成），未摊入任何族。
          </div>

          <div class="sub-h">按投诉性质看（五类，分母 = 已根因分析 {{ rc.covered ?? 0 }} 单）</div>
          <div class="l1-row">
            <div class="l1-chart pm-col-5">
              <ChartPie :data="pieData" donut height="260px" @item-click="p => drill({ week: metrics.week, l1: p.name }, `一级性质「${p.name}」工单`)" />
            </div>
            <div class="l1-table pm-col-7">
              <el-table class="l1-class-table" :data="l1Rows" size="small">
                <el-table-column prop="name" label="一级性质" width="110" />
                <el-table-column prop="meaning" label="含义" min-width="200" show-overflow-tooltip />
                <el-table-column prop="cnt" label="单量" width="80" align="center" />
                <el-table-column prop="pct" label="占比" width="80" align="right">
                  <template #default="{ row }">{{ row.pct }}%</template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <div class="sub-h">重点根因簇（本周 ≥5 单，可直接立项修复）</div>
          <el-table :data="bigClusters" size="small" empty-text="暂无达到量级的根因簇">
            <el-table-column label="根因簇" min-width="320" show-overflow-tooltip>
              <template #default="{ row }"><b>{{ row.title }}</b></template>
            </el-table-column>
            <el-table-column prop="fault_system" label="系统" width="110" />
            <el-table-column prop="fault_type" label="缺陷性质" width="110" />
            <el-table-column prop="own_party" label="责任归属" width="100" />
            <el-table-column label="本周单量" width="88" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillRootcause(row)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <!-- 四、压降指引 -->
      <section class="card">
        <div class="card-header">
          <h3>四、工单压降分析指引</h3>
          <span class="hint">同根因簇 ≥{{ batchMin }} 单 = 修一处可整批消掉</span>
        </div>
        <div class="card-body">
          <div class="pm-stat-grid pm-stat-grid--4">
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">可整批压降单量</span></div>
              <div class="pm-stat__val is-danger">{{ winCnt }}<span class="pm-stat__unit">单</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">占已分析单量</span></div>
              <div class="pm-stat__val">{{ winPct }}<span class="pm-stat__unit">%</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">可修复根因簇</span></div>
              <div class="pm-stat__val">{{ (rc.batch || []).length }}<span class="pm-stat__unit">簇</span></div>
            </div>
            <div class="pm-stat">
              <div class="pm-stat__top"><span class="pm-stat__label">可批量修复/改造单量</span></div>
              <div class="pm-stat__val">{{ rc.quick_win_cnt ?? 0 }}<span class="pm-stat__unit">单</span></div>
            </div>
          </div>

          <el-table :data="rc.batch || []" size="small" empty-text="本周无可整批压降的问题">
            <el-table-column label="根因（改这里即可整批消掉）" min-width="300" show-overflow-tooltip>
              <template #default="{ row }"><b>{{ row.title }}</b></template>
            </el-table-column>
            <el-table-column prop="fault_system" label="系统" width="110" />
            <el-table-column prop="own_party" label="责任方" width="100" />
            <el-table-column label="覆盖单量" width="90" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column prop="fix_mode" label="处置方式" width="100" />
            <el-table-column label="建议动作" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">{{ fixAction(row.fix_mode) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillRootcause(row)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <!-- 五、措施进展 -->
      <section class="card">
        <div class="card-header">
          <h3>五、措施跟踪与自动验证</h3>
          <span class="hint">措施绑簇、按簇单量算降幅、每期导入后自动结算</span>
        </div>
        <div class="card-body">
          <el-table :data="metrics.actions || []" size="small" empty-text="尚未登记改进措施">
            <el-table-column prop="action_no" label="措施编号" width="170" />
            <el-table-column prop="title" label="措施" min-width="260" show-overflow-tooltip />
            <el-table-column prop="owner" label="责任人" width="100" />
            <el-table-column label="基线/本周" width="110" align="center">
              <template #default="{ row }">{{ row.baseline_cnt ?? '—' }} / {{ row.last_week_cnt ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="实际降幅" width="96" align="right">
              <template #default="{ row }">
                <b v-if="row.actual_drop_pct !== null" :class="row.actual_drop_pct >= 0 ? 'num-green' : 'num-red'">
                  {{ row.actual_drop_pct > 0 ? '+' : '' }}{{ row.actual_drop_pct }}%
                </b>
                <span v-else class="muted">待基线</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column label="操作" width="88" align="center">
              <template #default>
                <el-button size="small" text type="primary" @click="goActions">去跟踪</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>

    <el-empty v-else description="暂无投诉数据，请先上传工单" />

    <ComplaintUploadDialog v-model="uploadVisible" @done="loadAll" />
    <TicketDrillDrawer v-model="drillVisible" :filters="drillFilters" :title="drillTitle" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Upload, Download, InfoFilled, Document } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import ChartPie from '@/components/Charts/ChartPie.vue'
import ChartLine from '@/components/Charts/ChartLine.vue'
import ComplaintUploadDialog from './components/ComplaintUploadDialog.vue'
import TicketDrillDrawer from './components/TicketDrillDrawer.vue'
import OverallOverview from './components/OverallOverview.vue'
import { complaintApi } from '@/api/complaint'
import { downloadWithAuth, openWithAuth } from '@/utils/download.js'

const router = useRouter()
const loading = ref(false)
const uploadVisible = ref(false)
const metrics = ref({})
// 整体投诉全貌（全量/跨周期），与周维度 metrics 并列，不复用同一份数据
const overall = ref({})

// 主要投诉点速览（新闭集，与「主要投诉点」页同源）
const mpSummary = ref({})
const mpTop = ref([])
function goModuleProblemPage() {
  router.push({ path: '/complaint-center/module-problem' })
}
async function loadMp(week) {
  try {
    const [s, c] = await Promise.all([
      complaintApi.moduleProblemSummary(),
      // 必须与主指标同一周：后端不传 week 会取库内最新周（进行中周），与页面选周错开
      complaintApi.moduleProblemClasses({ include_consult: false, week: week || undefined }),
    ])
    mpSummary.value = s || {}
    // 排序由后端按 week_cnt 降序（与展示字段同源）；0 单的类不占 TOP 位
    mpTop.value = ((c && c.items) || []).filter(x => (x.week_cnt || 0) > 0).slice(0, 6)
  } catch (e) { /* 不影响主指标 */ }
}
const selectedWeek = ref('')
const weekOptions = ref([])
// 周报新鲜度（2026-11-10）：周报是静态快照，数据更新后须提示并自动重生成
const reportStale = ref(false)
const reportTip = ref('周报为静态快照，数据更新后会自动重新生成')
async function loadReportStatus() {
  const wk = metrics.value.week
  if (!wk) { reportStale.value = false; return }
  try {
    const st = await complaintApi.reportStatus(wk)
    reportStale.value = !st?.exists || !!st?.stale
    const pdfNote = st.pdf_stale ? '；PDF 为旧版，如需 PDF 请联系重建' : ''
    reportTip.value = !st?.exists
      ? `${wk} 周报尚未生成，点击将自动生成`
      : st.stale
        ? `${wk} 数据截至 ${st.data_until || st.data_updated_at}，当前文件生成于 ${st.generated_at}` +
          `（文件 ${st.file_total ?? '?'} 单 / 库内 ${st.week_total} 单，点击重新生成后下载）${pdfNote}`
        : `${wk} 周报生成于 ${st.generated_at}，已是最新（${st.week_total} 单，数据截至 ${st.data_until || '—'}）${pdfNote}`
  } catch (e) { reportStale.value = false }
}
const batchMin = 3

// 一级性质含义（展示用；字典与口径仍在后端唯一源自 pmwb_complaint_category）
const L1_MEANING = {
  系统问题: '系统缺陷，需研发修复',
  流程优化: '流程或规则不合理，需改造',
  数据异常: '数据不一致/错误，需批量修复',
  规则咨询: '客户对政策资费有疑问，解释即可化解',
  操作咨询: '客户不熟悉操作，指引或代办即可化解',
}
const FIX_ACTION = {
  批量修复: '出数据修复脚本，一次性回溯存量错误数据',
  系统改造: '提需求排期改造（评估版本窗口）',
  规则调整: '调整校验规则/配置口径，无需改代码',
  逐单处理: '无法批量，只能逐单兜底（不产生压降空间）',
  解释指引: '完善指引话术，压降重复咨询',
}
function fixAction(mode) {
  return FIX_ACTION[mode] || '逐单核实后再定'
}

const rc = computed(() => metrics.value.rootcause || {})
const known = computed(() => metrics.value.known || {})

const subTitle = computed(() => {
  if (!metrics.value.week) return 'AI 自动分析：本周新增 → 已知/新增 → 五类 → 压降空间'
  return `${metrics.value.week}｜AI 全自动分析，人工只在问题入账时确认一次`
})

const partialBase = computed(() => !!metrics.value.prev_partial)
const wowText = computed(() => {
  if (metrics.value.prev_partial) return '不可比'
  const v = metrics.value.wow_pct
  if (v === null || v === undefined) return '—'
  return `${v > 0 ? '+' : ''}${v}%`
})
const wowClass = computed(() => {
  if (metrics.value.prev_partial) return ''
  const v = metrics.value.wow_pct
  if (v === null || v === undefined) return ''
  return v > 0 ? 'is-danger' : 'is-success'
})

const pieData = computed(() => (metrics.value.by_l1 || []).map(x => ({ value: x.cnt, name: x.name })))
const l1Rows = computed(() => (metrics.value.by_l1 || []).map(x => ({
  ...x, meaning: L1_MEANING[x.name] || '—',
})))

// 问题族（业务链路）：报表主视角，替代原来平铺根因簇的「散」
const th = computed(() => metrics.value.themes || {})
const themeRows = computed(() => th.value.themes || [])
// 重点根因簇：只有达到量级的才值得单独立项，1~2 单的个案不进这张表
const bigClusters = computed(() => (rc.value.clusters || []).filter(c => (c.cnt || 0) >= 5))

function drillTheme(row) {
  const rcs = row.rc_nos || []
  // 族表「本周」列来自 theme_stats（按 created_time 自然周聚合族内簇）；
  // 下钻不带 week 会拉到全周期累计（W45「订单受理与提交」实测 494 单 vs 本周 34 单）。
  // 展示字段 = 下钻字段 = 同一周，与 TOP 榜/已知问题表同口径。
  const week = th.value.week || metrics.value.week
  if (!rcs.length || !(row.week_cnt > 0)) {
    return ElMessage.info(`该族 ${week || '所选周'} 无归因工单`)
  }
  drill({ week, rootcause_no: rcs.join(',') }, `问题族「${row.name}」${week || ''} 工单`)
}

function drillCases() {
  drill({ rc_max_tickets: 1 }, '一次性个案工单（所在簇仅 1 单）')
}
// 日走势三线对标：横轴取本周日期，基准线按「周内偏移」索引对齐（周一..周日同一位置）
const dailyKeys = computed(() => Object.keys(metrics.value.daily || {}))
const dailyX = computed(() => dailyKeys.value.map(k => k.slice(5)))
const todayIso = computed(() => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
})
function alignSeries(dict, cutFuture = false) {
  const vals = Object.values(dict || {})
  return dailyKeys.value.map((k, i) => {
    // 本周未到的日期是「未发生」不是「0 单」，落 null 让线止于今天，避免误读成断崖归零
    if (cutFuture && k > todayIso.value) return null
    return i < vals.length ? vals[i] : null
  })
}
const dailySeries = computed(() => [
  { name: '本周单量', data: alignSeries(metrics.value.daily, true), width: 2.5, area: true },
  { name: '上周同期', data: alignSeries(metrics.value.daily_prev_week), dash: true, area: false, color: '#7c8ba1' },
  { name: '上月同期（4 周前）', data: alignSeries(metrics.value.daily_prev_month), dash: true, area: false, width: 1.5, color: '#c2a06a' },
])
const weekElapsed = computed(() => dailyKeys.value.filter(k => k <= todayIso.value).length)

// 对标口径：三条线都按「本周已过天数」截断，否则本周 3 天 vs 上周 7 天必然假性暴跌
const cmpDays = computed(() => weekElapsed.value || dailyKeys.value.length)
const sliceSum = (dict) => Object.values(dict || {}).slice(0, cmpDays.value).reduce((s, v) => s + (v || 0), 0)
const cmpCurTotal = computed(() => sliceSum(metrics.value.daily))
const cmpPrevWeekTotal = computed(() => sliceSum(metrics.value.daily_prev_week))
const cmpPrevMonthTotal = computed(() => sliceSum(metrics.value.daily_prev_month))
const avgOf = (total) => (cmpDays.value ? Math.round((total / cmpDays.value) * 10) / 10 : 0)
const cmpCurAvg = computed(() => avgOf(cmpCurTotal.value))
const cmpPrevWeekAvg = computed(() => avgOf(cmpPrevWeekTotal.value))
const cmpPrevMonthAvg = computed(() => avgOf(cmpPrevMonthTotal.value))

const winCnt = computed(() => (rc.value.batch || []).reduce((s, x) => s + (x.cnt || 0), 0))
const winPct = computed(() => {
  const covered = rc.value.covered || 0
  return covered ? Math.round((winCnt.value / covered) * 1000) / 10 : 0
})

function weekLabel(w) {
  return w ? w.replace('-', ' 第') + ' 周' : ''
}

async function loadAll() {
  loading.value = true
  try {
    // 整体全貌与单周指标并行取，各自 catch：后端尚未加载 /overall 时，
    // 周维度 6 个区块仍照常可用（整体区 v-if 自动不渲染），不会整页空白。
    const [m, ov] = await Promise.all([
      complaintApi.getMetrics(selectedWeek.value || undefined).catch(() => ({})),
      complaintApi.getOverall().catch(() => ({})),
    ])
    overall.value = ov || {}
    metrics.value = m || {}
    if (metrics.value.week) {
      if (!selectedWeek.value) selectedWeek.value = metrics.value.week
      if (!weekOptions.value.includes(metrics.value.week)) {
        weekOptions.value = [...new Set([...(metrics.value.trend || []).map(t => t.week), metrics.value.week])]
          .filter(Boolean).sort().reverse()
      }
      loadReportStatus()
    }
    // 先定周再取 TOP：否则后端默认最新周，排序与页面选周错开（2026-11-10）
    await loadMp(metrics.value.week || selectedWeek.value || undefined)
  } catch (e) {
    metrics.value = {}
  } finally {
    loading.value = false
  }
}

function onWeekChange(w) {
  selectedWeek.value = w
  loadAll()
}

function drillRootcause(row, extra = {}) {
  // extra 由调用方声明口径：新增问题表传 {known_flag: 0}，避免把已知单混进来。
  // 本页三张根因簇表（新增问题 / 重点根因簇 / 可整批压降）都是**本周**口径：
  // rc.clusters[].cnt 来自 _rootcause_block 的本周 rows，旧文案误写「累计 ≥5 单」，
  // 已按实际口径改正；下钻必须带 week，否则会拉到全周期累计（RC-1104：14 vs 19）。
  const base = { week: metrics.value.week, ...extra }
  if (row?.rootcause_no) {
    drill({ ...base, rootcause_no: row.rootcause_no },
      `根因簇「${row.title || row.rootcause_no}」${metrics.value.week || ''} 工单`)
  } else if (row?.module_problem_id) {
    // 无根因簇的新增问题（key=mp:xxx）按模块锚下钻，避免点了没反应
    drill({ ...base, module_problem_id: row.module_problem_id },
      `新增问题「${row.title || row.module_problem_id}」${metrics.value.week || ''} 工单`)
  }
}

const drillVisible = ref(false)
const drillFilters = ref({})
const drillTitle = ref('')
function drill(filters, title) {
  drillFilters.value = { ...filters }
  drillTitle.value = title || '投诉工单下钻'
  drillVisible.value = true
}

// 周报是静态快照：数据更新后文件不会自动失效，查看与下载前都必须先确保文件最新。
// 抽成唯一实现，避免「预览」与「下载」两条链路的新鲜度逻辑漂移（2026-11-11）。
async function prepareReport(week) {
  const prepMsg = ElMessage({ message: '正在准备周报…', duration: 0, type: 'info' })
  let prepClosed = false
  const closePrep = () => { if (!prepClosed) { prepClosed = true; prepMsg.close() } }
  try {
    let st = null
    try {
      st = await complaintApi.reportStatus(week)
    } catch (e) {
      /* 状态查不到就退回"不存在则生成"的老路径 */
    }
    if (!st || !st.exists || st.stale) {
      const why = !st || !st.exists ? '首次生成' : `数据已更新（${st.data_updated_at}），重新生成`
      closePrep()
      const msg2 = ElMessage({ message: `周报${why}中，约需 10~30 秒…`, duration: 0, type: 'info' })
      try {
        await complaintApi.genReport({ week, with_pdf: false })
        ElMessage.success(`周报已刷新为最新数据（${week}，${st?.week_total ?? ''} 单）`)
      } finally {
        msg2.close()
      }
    }
  } finally {
    closePrep()
  }
}

async function openReport() {
  if (!metrics.value.week) return ElMessage.warning('暂无可导出的周报')
  const week = metrics.value.week
  try {
    await prepareReport(week)
    // 裸 window.open 不带 JWT，开启了鉴权会被 401 拦下；此处仍为「新标签页预览」
    await openWithAuth(complaintApi.reportDownloadUrl(week))
    loadReportStatus()
  } catch (e) {
    ElMessage.error('周报打开失败：' + (e?.message || e))
  }
}

// 下载 HTML 文件（2026-11-11）。后端 FileResponse 已带 attachment + RFC5987 中文文件名，
// downloadWithAuth 用 fetch+blob 触发浏览器保存；禁裸 URL（会被 JWT 拦成 401）。
const reportDownloading = ref(false)
async function downloadReportHtml() {
  if (!metrics.value.week) return ElMessage.warning('暂无可下载的周报')
  const week = metrics.value.week
  reportDownloading.value = true
  try {
    await prepareReport(week)
    const name = await downloadWithAuth(complaintApi.reportDownloadUrl(week, 'html'))
    ElMessage.success(`已下载 ${name}`)
    loadReportStatus()
  } catch (e) {
    ElMessage.error('周报下载失败：' + (e?.message || e))
  } finally {
    reportDownloading.value = false
  }
}

function goActions() {
  router.push('/complaint-center/actions')
}

onMounted(loadAll)
</script>

<style scoped>
.dashboard-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.mp-overview { margin-bottom: 4px; }
.stale-dot { color: var(--pm-warning, #e6a23c); font-size: 12px; }
.mp-top { margin-top: 14px; }
.mp-top__title { font-size: 12.5px; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; }
.mp-top__list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 18px; }
.mp-top__item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border: 1px solid var(--border-light, #eef0f4); border-radius: 8px;
  background: var(--bg-soft, #fafbfc); cursor: pointer; transition: all .15s;
}
.mp-top__item:hover { border-color: var(--brand, #3b6cff); background: var(--brand-soft, #eef4ff); }
.mp-rank {
  width: 20px; height: 20px; flex: none; border-radius: 6px;
  font-size: 12px; font-weight: 700; color: #fff; background: var(--brand, #3b6cff);
  display: flex; align-items: center; justify-content: center;
}
.mp-name { flex: 1; font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mp-cnt { flex: none; font-size: 12.5px; font-weight: 600; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.ml-auto { margin-left: auto; }
.hint {
  font-size: 12px;
  color: var(--text-muted);
}
.sub-h {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 18px 0 8px;
}
.cmp-title .hint { font-weight: 400; margin-left: 8px; }
.cmp-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin: 0 0 6px;
  padding: 8px 12px;
  font-size: 12.5px;
  color: var(--text-secondary);
  background: var(--bg-secondary, #f7f9fc);
  border-radius: 8px;
}
.cmp-item { display: inline-flex; align-items: center; gap: 6px; }
.cmp-item b { color: var(--text-primary); font-family: var(--font-mono); font-size: 13.5px; }
.cmp-sep { color: var(--text-muted); }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-cur { background: var(--accent); }
.dot-prev { background: #7c8ba1; }
.dot-month { background: #c2a06a; }
.cmp-tip { margin-left: auto; font-size: 11.5px; color: var(--text-muted); }
.pm-note {
  margin: 12px 0;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--text-secondary);
}
.pm-note.warn {
  background: var(--warning-soft);
  border-left-color: var(--warning);
}
.num-red { color: var(--danger); }
.num-green { color: var(--success); }
/* 问题族表：族内 TOP 问题紧凑堆叠，避免撑行高 */
.top-cluster {
  display: flex;
  gap: 8px;
  line-height: 1.6;
  font-size: 12px;
}
.top-cluster .tc-cnt {
  flex: 0 0 44px;
  color: var(--danger);
  font-variant-numeric: tabular-nums;
}
.top-cluster .tc-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}
/* 个案/未归因提示行 */
.case-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-app);
  font-size: 12px;
  color: var(--text-secondary);
}
.case-line.warn {
  background: var(--warning-soft);
  color: var(--warning);
}
.muted { color: var(--text-muted); }
.l1-row {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: 16px;
  align-items: center;
}
@media (max-width: 960px) {
  .l1-row { grid-template-columns: 1fr; }
}
</style>

<!-- 本页页头有 5 个操作（周选择/上传/预览/下载/刷新），共用 PageHeader 的
     actions 是 flex-shrink:0 且不换行，实测 960px 视口横向溢出 7px。
     用全局块 + 本页类名限定只让本页页头换行；禁 :deep()（scoped 中会被整条丢弃）。 -->
<style>
@media (max-width: 1100px) {
  .complaint-dashboard .pm-page-header { flex-wrap: wrap; }
  .complaint-dashboard .pm-page-header__actions { flex-wrap: wrap; justify-content: flex-end; }
}
</style>
