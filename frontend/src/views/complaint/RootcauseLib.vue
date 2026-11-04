<template>
  <div class="rootcause-lib">
    <PageHeader title="根因库" :subtitle="subTitle">
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button :icon="Plus" @click="openCreate">新建根因簇</el-button>
        <el-button :icon="MagicStick" :loading="clustering" @click="doCluster">
          归并根因簇
        </el-button>
      </template>
    </PageHeader>

    <!-- KPI：根因分析的可靠性与收敛度 -->
    <div class="pm-stat-grid pm-stat-grid--5">
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">根因覆盖率</span></div>
        <div class="pm-stat__val" :class="status.coverage >= 90 ? 'is-success' : 'is-warning'">{{ status.coverage }}<span class="pm-stat__unit">%</span></div>
        <div class="pm-stat__sub">{{ status.filled }}/{{ status.total }} 单</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">已入账根因簇</span></div>
        <div class="pm-stat__val is-accent">{{ libStats.open || 0 }}<span class="pm-stat__unit">簇</span></div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">待确认候选</span></div>
        <div class="pm-stat__val" :class="(libStats.candidate || 0) > 0 ? 'is-warning' : 'is-success'">{{ libStats.candidate || 0 }}</div>
        <div class="pm-stat__sub">须人工命名入账</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">待人工根因</span></div>
        <div class="pm-stat__val" :class="status.low > 0 ? 'is-warning' : 'is-success'">{{ status.low }}</div>
        <div class="pm-stat__sub">信息不足 / 未过门禁</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">根因质量率</span></div>
        <div class="pm-stat__val" :class="status.quality >= 90 ? 'is-success' : 'is-warning'">{{ status.quality }}<span class="pm-stat__unit">%</span></div>
        <div class="pm-stat__sub">可用作分析基础</div>
      </div>
    </div>

    <!-- 主表：根因簇 -->
    <section class="card">
      <div class="card-header">
        <h3>根因簇（簇单量 = 该根因的理论压降空间）</h3>
        <div class="hdr-tools">
          <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 132px" @change="loadLib">
            <el-option label="待确认" value="candidate" />
            <el-option label="已入账" value="open" />
            <el-option label="已合并" value="merged" />
            <el-option label="已停用" value="disabled" />
          </el-select>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索根因标题 / 编号"
            clearable
            style="width: 220px"
            @keyup.enter="loadLib"
            @clear="loadLib"
          />
          <el-button type="primary" plain :icon="Search" @click="loadLib">查询</el-button>
        </div>
      </div>
      <div class="card-body">
        <el-alert
          v-if="mergedTotal && filters.status !== 'merged'"
          type="info"
          :closable="false"
          show-icon
          class="merged-tip"
        >
          共 <b>{{ liveTotal }}</b> 个在册根因簇；历史归并另产生 <b>{{ mergedTotal }}</b> 个「已合并」簇
          （单量已迁到主簇，仅用于追溯，不计入簇数）。要看这些历史簇，状态筛选选「已合并」。
        </el-alert>
        <el-table v-loading="loading" :data="clusters" size="default" border stripe>
          <el-table-column prop="rootcause_no" label="编号" width="96">
            <template #default="{ row }"><b>{{ row.rootcause_no }}</b></template>
          </el-table-column>
          <el-table-column label="根因（修哪里能一次消掉）" min-width="300" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="rc-title">{{ row.title }}</span>
              <div v-if="row.description" class="rc-desc">{{ row.description }}</div>
            </template>
          </el-table-column>
          <el-table-column label="系统 / 环节" width="140">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.fault_system || '—' }}</el-tag>
              <div class="sub-line">{{ row.fault_stage || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="fault_type" label="缺陷性质" width="100" />
          <el-table-column prop="own_party" label="责任归属" width="96" />
          <el-table-column prop="fix_mode" label="处置方式" width="96" />
          <el-table-column label="单量" width="76" align="center">
            <template #default="{ row }">
              <b :class="row.ticket_cnt >= 3 ? 'cnt-danger' : ''">{{ row.ticket_cnt }}</b>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="88" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTone(row.status)" size="small">{{ row.status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openDetail(row)">工单</el-button>
              <el-button
                v-if="row.status !== 'merged'"
                size="small"
                text
                @click="openEdit(row)"
              >编辑</el-button>
              <el-button
                v-if="row.status === 'candidate'"
                size="small"
                text
                type="success"
                @click="openConfirm(row)"
              >确认入账</el-button>
              <el-button
                v-if="row.status === 'open' || row.status === 'candidate'"
                size="small"
                text
                type="warning"
                @click="openMerge(row)"
              >合并</el-button>
              <el-button size="small" text @click="toggleDisable(row)">
                {{ row.status === 'disabled' ? '恢复' : '停用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager-bar">
          <el-pagination
            v-model:current-page="pager.page"
            v-model:page-size="pager.pageSize"
            :total="pager.total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadLib"
            @size-change="loadLib"
          />
        </div>
      </div>
    </section>

    <!-- 待人工确认单 -->
    <section class="card">
      <div class="card-header">
        <h3>待人工根因（门禁未过或信息不足，确认后即成为分析基础）</h3>
      </div>
      <div class="card-body">
        <el-table v-if="review.length" :data="review" size="default" border>
          <el-table-column prop="ticket_no" label="工单号" width="140" />
          <el-table-column prop="created_time" label="创建时间" width="140" />
          <el-table-column label="AI 根因（可能不够精准）" min-width="280" show-overflow-tooltip>
            <template #default="{ row }">{{ row.root_cause || '（未产出）' }}</template>
          </el-table-column>
          <el-table-column label="置信" width="70" align="center">
            <template #default="{ row }">
              <span :class="row.rc_confidence >= 0.5 ? 'conf-hi' : 'conf-low'">
                {{ row.rc_confidence.toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="evidence" label="原文依据" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openCorrect(row)">补根因</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="没有待人工确认的工单" :image-size="72" />
      </div>
    </section>

    <!-- 确认入账 -->
    <el-dialog v-model="confirmVisible" title="确认根因簇入账" width="620px">
      <el-alert type="info" :closable="false" show-icon class="dlg-tip">
        确认后该根因进入「已入账」，后续同机制工单会自动归入，并作为 AI 归并样例回流。
      </el-alert>
      <el-form label-width="92px">
        <el-form-item label="根因标题">
          <el-input v-model="confirmForm.title" type="textarea" :rows="2" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="判定边界">
          <el-input
            v-model="confirmForm.description"
            type="textarea"
            :rows="3"
            maxlength="500"
            placeholder="什么情况算这个根因、什么情况不算（防串簇）"
          />
        </el-form-item>
        <el-form-item label="缺陷性质">
          <el-select v-model="confirmForm.fault_type" clearable style="width: 100%">
            <el-option v-for="x in meta.fault_types" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="责任归属">
          <el-select v-model="confirmForm.own_party" clearable style="width: 100%">
            <el-option v-for="x in meta.own_parties" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="处置方式">
          <el-select v-model="confirmForm.fix_mode" clearable style="width: 100%">
            <el-option v-for="x in meta.fix_modes" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doConfirm">确认入账</el-button>
      </template>
    </el-dialog>

    <!-- 合并 -->
    <el-dialog v-model="mergeVisible" title="合并到主簇" width="520px">
      <el-alert type="warning" :closable="false" show-icon class="dlg-tip">
        本簇的工单会全部改归主簇，本簇置为「已合并」（历史保留可追溯）。
      </el-alert>
      <el-form label-width="92px">
        <el-form-item label="本簇">
          <span>{{ mergeForm.src_no }}｜{{ mergeForm.src_title }}</span>
        </el-form-item>
        <el-form-item label="并入主簇">
          <el-select v-model="mergeForm.dst_no" filterable style="width: 100%" placeholder="选择主簇">
            <el-option
              v-for="c in mergeTargets"
              :key="c.rootcause_no"
              :label="`${c.rootcause_no}｜${c.title}（${c.ticket_cnt} 单）`"
              :value="c.rootcause_no"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mergeVisible = false">取消</el-button>
        <el-button type="warning" :loading="saving" @click="doMerge">确认合并</el-button>
      </template>
    </el-dialog>

    <!-- 新建 / 编辑根因簇（按需动态维护：新业务、新场景可直接立簇） -->
    <el-dialog
      v-model="clusterVisible"
      :title="clusterMode === 'create' ? '新建根因簇' : '编辑根因簇'"
      width="680px"
    >
      <el-alert type="info" :closable="false" show-icon class="dlg-tip">
        簇键 = 环节 × 机制 × 业务对象。新业务/新场景可直接填新的业务对象（AI 自动链路仍只用受控枚举）；
        改动这三个要素会重算簇键，并与现存活簇查重，撞键不新建。
      </el-alert>
      <el-form label-width="96px">
        <el-form-item label="订单环节" required>
          <el-select v-model="clusterForm.fault_stage" filterable style="width: 100%" placeholder="断点所在环节">
            <el-option v-for="x in meta.fault_stages" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="失败机制" required>
          <el-select v-model="clusterForm.mechanism" filterable style="width: 100%" placeholder="怎么断的">
            <el-option-group v-for="g in mechanismGroups" :key="g.label" :label="g.label">
              <el-option v-for="x in g.items" :key="x" :label="x" :value="x" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="业务对象" required>
          <el-select
            v-model="clusterForm.biz_object"
            filterable
            allow-create
            default-first-option
            style="width: 100%"
            placeholder="断在谁身上（新业务可直接输入新对象）"
          >
            <el-option v-for="x in objectOptions" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发条件">
          <el-input
            v-model="clusterForm.trigger"
            maxlength="32"
            placeholder="可空；同对象同机制但修复点明显不同时才填"
          />
        </el-form-item>
        <el-form-item label="簇标题">
          <el-input
            v-model="clusterForm.title"
            type="textarea"
            :rows="2"
            maxlength="200"
            placeholder="留空则按「对象-机制（触发条件）」自动生成"
          />
        </el-form-item>
        <el-form-item label="判定边界">
          <el-input
            v-model="clusterForm.description"
            type="textarea"
            :rows="3"
            maxlength="500"
            placeholder="什么情况算这个根因、什么情况不算（防串簇）"
          />
        </el-form-item>
        <el-form-item label="缺陷性质">
          <el-select v-model="clusterForm.fault_type" clearable style="width: 100%">
            <el-option v-for="x in meta.fault_types" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="责任归属">
          <el-select v-model="clusterForm.own_party" clearable style="width: 100%">
            <el-option v-for="x in meta.own_parties" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="处置方式">
          <el-select v-model="clusterForm.fix_mode" clearable style="width: 100%">
            <el-option v-for="x in meta.fix_modes" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="clusterVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doSaveCluster">
          {{ clusterMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 移出工单（拆簇 / 并入其他簇） -->
    <el-dialog v-model="moveVisible" title="移出工单" width="620px">
      <el-alert type="warning" :closable="false" show-icon class="dlg-tip">
        将把选中的 {{ selectedTickets.length }} 单从「{{ detail.title }}」移出；
        源簇单量会自动重算，移空不删簇（可随时停用）。
      </el-alert>
      <el-form label-width="96px">
        <el-form-item label="移到">
          <el-radio-group v-model="moveForm.mode">
            <el-radio value="existing">已有簇</el-radio>
            <el-radio value="new">新建簇</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="moveForm.mode === 'existing'" label="目标簇">
          <el-select v-model="moveForm.target_no" filterable style="width: 100%" placeholder="选择要并入的簇">
            <el-option
              v-for="c in moveTargets"
              :key="c.rootcause_no"
              :label="`${c.rootcause_no}｜${c.title}（${c.ticket_cnt} 单）`"
              :value="c.rootcause_no"
            />
          </el-select>
        </el-form-item>
        <template v-else>
          <el-form-item label="订单环节" required>
            <el-select v-model="moveForm.fault_stage" filterable style="width: 100%">
              <el-option v-for="x in meta.fault_stages" :key="x" :label="x" :value="x" />
            </el-select>
          </el-form-item>
          <el-form-item label="失败机制" required>
            <el-select v-model="moveForm.mechanism" filterable style="width: 100%">
              <el-option-group v-for="g in mechanismGroups" :key="g.label" :label="g.label">
                <el-option v-for="x in g.items" :key="x" :label="x" :value="x" />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-form-item label="业务对象" required>
            <el-select
              v-model="moveForm.biz_object"
              filterable
              allow-create
              default-first-option
              style="width: 100%"
            >
              <el-option v-for="x in objectOptions" :key="x" :label="x" :value="x" />
            </el-select>
          </el-form-item>
          <el-form-item label="触发条件">
            <el-input v-model="moveForm.trigger" maxlength="32" placeholder="可空" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="moveVisible = false">取消</el-button>
        <el-button type="warning" :loading="saving" @click="doMove">确认移出</el-button>
      </template>
    </el-dialog>

    <!-- 簇详情：关联工单 -->
    <el-drawer v-model="detailVisible" :title="detail.title || '根因簇详情'" size="52%">
      <div v-if="detail.rootcause_no" class="detail-body">
        <div class="detail-meta">
          <el-tag size="small">{{ detail.rootcause_no }}</el-tag>
          <el-tag size="small" type="info">{{ detail.fault_system }}</el-tag>
          <el-tag size="small" type="info">{{ detail.fault_stage }}</el-tag>
          <el-tag size="small" type="warning">{{ detail.fault_type }}</el-tag>
          <el-tag size="small">{{ detail.own_party }}</el-tag>
          <el-tag size="small">{{ detail.fix_mode }}</el-tag>
          <el-tag size="small" type="danger">{{ detail.ticket_cnt }} 单</el-tag>
        </div>
        <p v-if="detail.description" class="detail-desc">{{ detail.description }}</p>
        <div class="detail-ops">
          <span class="detail-ops__hint">
            AI 归类不做人工纠偏；只有发现串簇时才勾选工单移出（拆簇或并入其他簇）
          </span>
          <el-button
            class="js-move-btn"
            size="small"
            :disabled="!selectedTickets.length"
            @click="openMove"
          >移出选中 {{ selectedTickets.length }} 单</el-button>
        </div>
        <el-table
          ref="detailTableRef"
          :data="detail.tickets"
          size="small"
          border
          max-height="520"
          row-key="ticket_no"
          @selection-change="onDetailSelect"
        >
          <el-table-column type="selection" width="42" reserve-selection />
          <el-table-column prop="ticket_no" label="工单号" width="132" />
          <el-table-column prop="week" label="周次" width="88" />
          <el-table-column prop="city" label="地市" width="76" />
          <el-table-column prop="root_cause" label="单条根因" min-width="300" show-overflow-tooltip />
        </el-table>
      </div>
    </el-drawer>

    <!-- 人工补根因 -->
    <el-dialog v-model="correctVisible" title="人工确认根因" width="640px">
      <el-alert type="warning" :closable="false" show-icon class="dlg-tip">
        人工确认后标记为「人工确认」，AI 重跑不会覆盖，并回流作为归并样例。
      </el-alert>
      <el-form label-width="92px">
        <el-form-item label="工单">
          <span>{{ correctForm.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="真实根因">
          <el-input
            v-model="correctForm.root_cause"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="写清哪个系统 + 哪个环节 + 具体报错/字段/状态 + 影响什么"
          />
        </el-form-item>
        <el-form-item label="故障环节">
          <el-select v-model="correctForm.fault_stage" clearable style="width: 100%">
            <el-option v-for="x in meta.fault_stages" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="涉及系统">
          <el-select v-model="correctForm.fault_system" clearable style="width: 100%">
            <el-option v-for="x in meta.fault_systems" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="缺陷性质">
          <el-select v-model="correctForm.fault_type" clearable style="width: 100%">
            <el-option v-for="x in meta.fault_types" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="责任归属">
          <el-select v-model="correctForm.own_party" clearable style="width: 100%">
            <el-option v-for="x in meta.own_parties" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="处置方式">
          <el-select v-model="correctForm.fix_mode" clearable style="width: 100%">
            <el-option v-for="x in meta.fix_modes" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="correctVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doCorrect">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Plus, Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import { complaintApi } from '@/api/complaint'

const route = useRoute()

const loading = ref(false)
const saving = ref(false)
const clustering = ref(false)
const clusters = ref([])
const review = ref([])
const status = ref({ total: 0, filled: 0, coverage: 0, quality: 0, low: 0, ai: 0, manual: 0 })
const filters = reactive({ status: '', keyword: '' })
const pager = reactive({ page: 1, pageSize: 20, total: 0 })
// 簇数口径由后端给（live_total / merged_total），前端不自行推导，避免与 KPI 卡漂移
const liveTotal = ref(0)
const mergedTotal = ref(0)
const meta = ref({
  fault_stages: [], fault_systems: [], fault_types: [], own_parties: [], fix_modes: [],
  mechanisms: [], objects: [],
})

const confirmVisible = ref(false)
const confirmForm = reactive({ no: '', title: '', description: '', fault_type: '', own_party: '', fix_mode: '' })
const mergeVisible = ref(false)
const mergeForm = reactive({ src_no: '', src_title: '', dst_no: '' })
const mergeTargets = ref([])
const detailVisible = ref(false)
const detail = ref({ tickets: [] })
const detailTableRef = ref(null)
const selectedTickets = ref([])
const correctVisible = ref(false)
const correctForm = reactive({ id: null, ticket_no: '', root_cause: '', fault_stage: '', fault_system: '', fault_type: '', own_party: '', fix_mode: '' })

// 簇维护（新建/编辑）与拆单移出
const clusterVisible = ref(false)
const clusterMode = ref('create')
const clusterForm = reactive({
  rootcause_no: '', fault_stage: '', mechanism: '', biz_object: '', trigger: '',
  title: '', description: '', fault_type: '', own_party: '', fix_mode: '',
})
const moveVisible = ref(false)
const moveForm = reactive({
  mode: 'existing', target_no: '', fault_stage: '', mechanism: '', biz_object: '', trigger: '',
})
const moveTargets = ref([])

// 机制按分组展示（meta 唯一源，前端不另存清单）
const mechanismGroups = computed(() => {
  const groups = []
  const idx = {}
  for (const it of meta.value.mechanisms || []) {
    const g = it.group || '其他'
    if (idx[g] === undefined) {
      idx[g] = groups.length
      groups.push({ label: g, items: [] })
    }
    groups[idx[g]].items.push(it.value)
  }
  return groups
})
const objectOptions = computed(() => (meta.value.objects || []).map((x) => x.value || x))

const libStats = computed(() => status.value.rootcause_lib || {})
const subTitle = computed(() =>
  `根因层 = 每单一句真实问题描述；根因簇 = 能一次修复的同一类问题｜在册 ${liveTotal.value} 个簇`
)

function statusTone(s) {
  return { candidate: 'warning', open: 'success', merged: 'info', disabled: 'info' }[s] || 'info'
}

async function loadAll() {
  loading.value = true
  try {
    const [st, lib, rv, mt] = await Promise.all([
      complaintApi.rootcauseStatus().catch(() => ({})),
      complaintApi.listRootcauseClusters({
        status: filters.status || undefined,
        keyword: filters.keyword || undefined,
        page: pager.page,
        page_size: pager.pageSize,
      }),
      complaintApi.rootcauseReview({ page: 1, page_size: 30 }).catch(() => ({ items: [] })),
      complaintApi.rootcauseMeta().catch(() => meta.value),
    ])
    status.value = st || {}
    clusters.value = lib.items || []
    pager.total = lib.total || 0
    liveTotal.value = lib.live_total ?? 0
    mergedTotal.value = lib.merged_total ?? 0
    review.value = rv.items || []
    if (mt && mt.fault_stages) meta.value = mt
  } finally {
    loading.value = false
  }
}

async function loadLib() {
  await loadAll()
}

async function doCluster() {
  clustering.value = true
  try {
    const res = await complaintApi.runRootcauseCluster({})
    ElMessage.success(`归并完成：扫描 ${res.scanned} 单，新建 ${(res.new_clusters || []).length} 簇`)
    await loadAll()
  } finally {
    clustering.value = false
  }
}

function openConfirm(row) {
  confirmForm.no = row.rootcause_no
  confirmForm.title = row.title
  confirmForm.description = row.description || ''
  confirmForm.fault_type = row.fault_type || ''
  confirmForm.own_party = row.own_party || ''
  confirmForm.fix_mode = row.fix_mode || ''
  confirmVisible.value = true
}

async function doConfirm() {
  saving.value = true
  try {
    await complaintApi.confirmRootcauseCluster(confirmForm.no, {
      title: confirmForm.title,
      description: confirmForm.description,
      fault_type: confirmForm.fault_type || undefined,
      own_party: confirmForm.own_party || undefined,
      fix_mode: confirmForm.fix_mode || undefined,
    })
    ElMessage.success('已入账')
    confirmVisible.value = false
    await loadAll()
  } finally {
    saving.value = false
  }
}

async function openMerge(row) {
  mergeForm.src_no = row.rootcause_no
  mergeForm.src_title = row.title
  mergeForm.dst_no = ''
  const res = await complaintApi.listRootcauseClusters({ status: 'open', page: 1, page_size: 200 })
  mergeTargets.value = (res.items || []).filter(c => c.rootcause_no !== row.rootcause_no)
  mergeVisible.value = true
}

async function doMerge() {
  if (!mergeForm.dst_no) {
    ElMessage.warning('请选择主簇')
    return
  }
  saving.value = true
  try {
    await complaintApi.mergeRootcauseCluster(mergeForm.src_no, mergeForm.dst_no)
    ElMessage.success('已合并')
    mergeVisible.value = false
    await loadAll()
  } finally {
    saving.value = false
  }
}

async function toggleDisable(row) {
  const reopen = row.status === 'disabled'
  await ElMessageBox.confirm(
    reopen ? '恢复该根因簇参与匹配？' : '停用后该簇不再参与新工单匹配，存量归属保留，确认停用？',
    reopen ? '恢复根因簇' : '停用根因簇',
    { type: 'warning' }
  )
  await complaintApi.disableRootcauseCluster(row.rootcause_no, reopen)
  ElMessage.success(reopen ? '已恢复' : '已停用')
  await loadAll()
}

async function openDetail(row) {
  const d = await complaintApi.getRootcauseCluster(row.rootcause_no)
  detail.value = d || { tickets: [] }
  selectedTickets.value = []
  detailVisible.value = true
}

function resetClusterForm() {
  Object.assign(clusterForm, {
    rootcause_no: '', fault_stage: '', mechanism: '', biz_object: '', trigger: '',
    title: '', description: '', fault_type: '', own_party: '', fix_mode: '',
  })
}

function openCreate() {
  clusterMode.value = 'create'
  resetClusterForm()
  clusterVisible.value = true
}

function fillClusterForm(c) {
  Object.assign(clusterForm, {
    rootcause_no: c.rootcause_no || '',
    fault_stage: c.fault_stage || '',
    mechanism: c.mechanism || '',
    biz_object: c.biz_object || '',
    trigger: triggerOf(c.title),
    title: c.title || '',
    description: c.description || '',
    fault_type: c.fault_type || '',
    own_party: c.own_party || '',
    fix_mode: c.fix_mode || '',
  })
}

/** 标题里的（触发条件）——编辑时回填，避免保存后被清掉。 */
function triggerOf(title) {
  const m = String(title || '').match(/[（(]([^）)]{1,32})[）)]/)
  return m ? m[1] : ''
}

function openEdit(row) {
  clusterMode.value = 'edit'
  fillClusterForm(row)
  clusterVisible.value = true
}

async function doSaveCluster() {
  const f = clusterForm
  if (!f.fault_stage || !f.mechanism || !f.biz_object) {
    ElMessage.warning('订单环节 / 失败机制 / 业务对象都必须填')
    return
  }
  saving.value = true
  try {
    let res
    if (clusterMode.value === 'create') {
      res = await complaintApi.createRootcauseCluster({
        fault_stage: f.fault_stage,
        mechanism: f.mechanism,
        biz_object: f.biz_object,
        trigger: f.trigger || '',
        title: f.title || '',
        description: f.description || '',
        fault_type: f.fault_type || '',
        own_party: f.own_party || '',
        fix_mode: f.fix_mode || '',
      })
    } else {
      res = await complaintApi.updateRootcauseCluster(f.rootcause_no, {
        fault_stage: f.fault_stage,
        mechanism: f.mechanism,
        biz_object: f.biz_object,
        trigger: f.trigger || '',
        title: f.title || '',
        description: f.description || '',
        fault_type: f.fault_type || '',
        own_party: f.own_party || '',
        fix_mode: f.fix_mode || '',
      })
    }
    if (res && res.ok === false) {
      if (res.conflict && res.existing) {
        if (clusterMode.value === 'create') {
          await ElMessageBox.confirm(`${res.message}。是否改为编辑该簇？`, '已有同键簇', { type: 'warning' })
          clusterVisible.value = false
          const d = await complaintApi.getRootcauseCluster(res.existing.rootcause_no)
          clusterMode.value = 'edit'
          fillClusterForm(d || {})
          clusterVisible.value = true
        } else {
          await ElMessageBox.confirm(`${res.message}。是否把本簇整体并入它？`, '簇键冲突', { type: 'warning' })
          await complaintApi.mergeRootcauseCluster(f.rootcause_no, res.existing.rootcause_no)
          ElMessage.success('已并入目标簇')
          clusterVisible.value = false
          await loadAll()
        }
      } else {
        ElMessage.error(res.message || '保存失败')
      }
      return
    }
    ElMessage.success(clusterMode.value === 'create' ? '根因簇已创建' : '已保存')
    clusterVisible.value = false
    await loadAll()
  } finally {
    saving.value = false
  }
}

function onDetailSelect(rows) {
  selectedTickets.value = (rows || []).map((r) => r.ticket_no)
}

async function openMove() {
  if (!selectedTickets.value.length) return
  moveForm.mode = 'existing'
  moveForm.target_no = ''
  moveForm.fault_stage = detail.value.fault_stage || ''
  moveForm.mechanism = detail.value.mechanism || ''
  moveForm.biz_object = detail.value.biz_object || ''
  moveForm.trigger = ''
  const res = await complaintApi.listRootcauseClusters({ status: 'open', page: 1, page_size: 200 })
  moveTargets.value = (res.items || []).filter((c) => c.rootcause_no !== detail.value.rootcause_no)
  moveVisible.value = true
}

async function doMove() {
  const f = moveForm
  if (f.mode === 'existing' && !f.target_no) {
    ElMessage.warning('请选择目标簇')
    return
  }
  if (f.mode === 'new' && (!f.fault_stage || !f.mechanism || !f.biz_object)) {
    ElMessage.warning('新建簇需要填订单环节 / 失败机制 / 业务对象')
    return
  }
  saving.value = true
  try {
    const payload = { ticket_nos: selectedTickets.value }
    if (f.mode === 'existing') {
      payload.target_no = f.target_no
    } else {
      payload.target_no = ''
      payload.new_cluster = {
        fault_stage: f.fault_stage,
        mechanism: f.mechanism,
        biz_object: f.biz_object,
        trigger: f.trigger || '',
      }
    }
    const res = await complaintApi.splitRootcauseCluster(detail.value.rootcause_no, payload)
    if (res && res.ok === false) {
      ElMessage.error(res.message || '移出失败')
      return
    }
    ElMessage.success(`已移出 ${res.moved || selectedTickets.value.length} 单`)
    moveVisible.value = false
    detailVisible.value = false
    await loadAll()
  } finally {
    saving.value = false
  }
}

function openCorrect(row) {
  correctForm.id = row.id
  correctForm.ticket_no = row.ticket_no
  correctForm.root_cause = row.root_cause || ''
  correctForm.fault_stage = row.fault_stage || ''
  correctForm.fault_system = row.fault_system || ''
  correctForm.fault_type = row.fault_type || ''
  correctForm.own_party = row.own_party || ''
  correctForm.fix_mode = row.fix_mode || ''
  correctVisible.value = true
}

async function doCorrect() {
  saving.value = true
  try {
    const res = await complaintApi.correctTicketRootcause(correctForm.id, {
      root_cause: correctForm.root_cause,
      fault_stage: correctForm.fault_stage,
      fault_system: correctForm.fault_system,
      fault_type: correctForm.fault_type,
      own_party: correctForm.own_party,
      fix_mode: correctForm.fix_mode,
      repro: 'unknown',
      evidence: '',
    })
    if (res && res.quality_warnings && res.quality_warnings.length) {
      ElMessage.warning(`已保存，但根因仍偏笼统：${res.quality_warnings.join('；')}`)
    } else {
      ElMessage.success('根因已确认')
    }
    correctVisible.value = false
    await loadAll()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  // 从工单台账点「RC-xxxx」跳转过来时带 keyword，直接定位该簇
  if (route.query.keyword) filters.keyword = String(route.query.keyword)
  loadAll()
})
</script>

<style scoped>
.hdr-tools {
  display: flex;
  gap: 8px;
  align-items: center;
}
.rc-title {
  font-weight: 600;
}
.rc-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sub-line {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.cnt-danger {
  color: var(--danger);
}
.conf-hi {
  color: var(--success);
  font-weight: 600;
}
.conf-low {
  color: var(--warning);
  font-weight: 600;
}
.dlg-tip {
  margin-bottom: 12px;
}
.detail-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.detail-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px;
}
.detail-ops {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.detail-ops__hint {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
}
.pager-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.merged-tip {
  margin-bottom: 10px;
}
</style>
