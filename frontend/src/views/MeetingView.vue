<template>
  <div class="meeting-view">
    <!-- 顶部标题栏 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">会议日程</h2>
        <div class="page-crumb">工作台 / 会议日程</div>
      </div>
      <div class="page-actions">
        <el-input
          v-model="keyword"
          placeholder="搜索会议 / 参会人"
          clearable
          class="head-search"
        >
          <template #prefix>
            <span class="search-ico">🔍</span>
          </template>
        </el-input>
        <el-button type="primary" @click="handleAdd">＋ 新增会议</el-button>
      </div>
    </div>

    <!-- 本周概览 KPI 卡片 -->
    <div class="bento-grid kpi-strip">
      <div class="card kpi-card">
        <div class="kpi-num blue">{{ weekCount }}</div>
        <div class="kpi-label">本周会议</div>
      </div>
      <div class="card kpi-card">
        <div class="kpi-num amber">{{ plannedCount }}</div>
        <div class="kpi-label">待开会议</div>
      </div>
      <div class="card kpi-card">
        <div class="kpi-num green">{{ mineCount }}</div>
        <div class="kpi-label">我参与</div>
      </div>
      <div class="card kpi-card">
        <div class="kpi-num">{{ noteCount }}</div>
        <div class="kpi-label">已生成纪要</div>
      </div>
    </div>

    <!-- 视图切换 -->
    <div class="view-bar">
      <div class="view-tabs">
        <button
          v-for="v in viewDefs"
          :key="v.key"
          :class="['view-tab', { active: activeView === v.key }]"
          @click="activeView = v.key"
        >
          {{ v.label }}
        </button>
      </div>
      <div class="view-hint">
        当前共 <b>{{ filteredMeetings.length }}</b> 场会议
      </div>
    </div>

    <!-- ===== 月历视图 ===== -->
    <div v-show="activeView === 'cal'" class="bento-grid">
      <div class="card cal-card">
        <div class="card-header">
          <div>
            <div class="card-title">{{ calTitle }}</div>
            <div class="card-sub">点击日期查看当日会议安排</div>
          </div>
          <div class="cal-nav">
            <button class="pm-btn btn-sm" @click="prevMonth">‹ 上月</button>
            <button class="pm-btn btn-sm" @click="goToday">今天</button>
            <button class="pm-btn btn-sm" @click="nextMonth">下月 ›</button>
          </div>
        </div>
        <div class="cal-grid">
          <div v-for="d in dowLabels" :key="d" class="cal-dow">{{ d }}</div>
          <div
            v-for="cell in calendarDays"
            :key="cell.key"
            :class="['cal-cell', { other: !cell.inMonth, today: cell.isToday }]"
            @click="onCellClick(cell)"
          >
            <div class="cal-day">{{ cell.dayNum }}</div>
            <div class="cal-dots">
              <span
                v-for="m in cell.dayMeetings"
                :key="m.id"
                :class="['cal-dot', typeDotClass(m.meeting_type)]"
                :title="m.title"
              ></span>
            </div>
            <div v-if="cell.dayMeetings.length" class="cal-meta">
              {{ cell.dayMeetings.length }} 场会议
            </div>
          </div>
        </div>
      </div>

      <div class="card today-card">
        <div class="card-header">
          <div class="card-title">今日会议 · {{ todayLabel }}</div>
        </div>
        <div class="card-body today-list">
          <div
            v-for="m in todayMeetings"
            :key="m.id"
            class="mt-row"
            @click="openDetail(m.id)"
          >
            <div class="mt-time">
              <div class="mt-hour">{{ formatTime(m.start_time) }}</div>
              <div class="mt-dur">{{ durationText(m) }}</div>
            </div>
            <div class="mt-line" :class="lineCls(m.status)"></div>
            <div class="mt-body">
              <div class="mt-title">{{ m.title }}</div>
              <div class="mt-info"><span>📍 {{ m.location || '—' }}</span></div>
              <span class="mt-tag" :class="typeTagCls(m.meeting_type)">{{
                typeText(m.meeting_type)
              }}</span>
            </div>
          </div>
          <div v-if="!todayMeetings.length" class="empty-hint">今日暂无会议安排</div>
        </div>
      </div>

      <div class="card up-card">
        <div class="card-header">
          <div class="card-title">待开会议</div>
        </div>
        <div class="card-body up-list">
          <div v-for="m in upcomingMeetings" :key="m.id" class="up-item" @click="openDetail(m.id)">
            <b class="up-date">{{ formatDateMD(m.start_time) }}</b>
            {{ m.title }} · {{ formatTime(m.start_time) }}
          </div>
          <div v-if="!upcomingMeetings.length" class="empty-hint">暂无待开会议</div>
          <div class="up-tip">点击右上「新增会议」发起安排</div>
        </div>
      </div>

      <div class="card room-card">
        <div class="card-header">
          <div class="card-title">会议室占用</div>
        </div>
        <div class="card-body room-list">
          <div v-for="r in roomUsage" :key="r.name" class="room-row">
            <span class="room-name">{{ r.name }}</span>
            <div class="room-bar">
              <div class="room-fill" :class="r.cls" :style="{ width: r.pct + '%' }"></div>
            </div>
            <span class="room-pct">{{ r.pct }}%</span>
          </div>
        </div>
      </div>

      <div class="card month-card">
        <div class="card-header">
          <div class="card-title">{{ currentDate.getMonth() + 1 }} 月概览</div>
        </div>
        <div class="card-body month-stats">
          <div class="mini-stat">
            <div class="mini-num" style="color: var(--accent)">{{ monthCount }}</div>
            <div class="mini-lab">本月会议</div>
          </div>
          <div class="mini-stat">
            <div class="mini-num" style="color: var(--success)">{{ monthMine }}</div>
            <div class="mini-lab">我参与</div>
          </div>
          <div class="mini-stat">
            <div class="mini-num" style="color: var(--warning)">{{ monthNote }}</div>
            <div class="mini-lab">已生成纪要</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 会议列表视图 ===== -->
    <div v-show="activeView === 'list'" class="bento-grid">
      <div class="card span-12">
        <div class="card-header list-head">
          <div class="card-title">全部会议</div>
          <div class="list-filters">
            <el-select v-model="filterType" placeholder="全部类型" clearable style="width: 140px">
              <el-option
                v-for="t in meetingTypeOptions"
                :key="t.value"
                :label="t.label"
                :value="t.value"
              />
            </el-select>
            <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 130px">
              <el-option
                v-for="s in statusOptions"
                :key="s.value"
                :label="s.label"
                :value="s.value"
              />
            </el-select>
          </div>
        </div>
        <el-table
          :data="listMeetings"
          v-loading="loading"
          @row-click="(row) => openDetail(row.id)"
        >
          <el-table-column label="日期" width="100">
            <template #default="{ row }">{{ formatDateMD(row.start_time) }}</template>
          </el-table-column>
          <el-table-column label="时间" width="90">
            <template #default="{ row }">
              <span class="font-mono">{{ formatTime(row.start_time) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="会议主题" min-width="200" show-overflow-tooltip />
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <span class="pm-tag" :class="typeTagCls(row.meeting_type)">{{
                typeText(row.meeting_type)
              }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="host" label="组织者" width="120" />
          <el-table-column prop="location" label="地点" min-width="150" show-overflow-tooltip />
          <el-table-column label="参会人" width="90">
            <template #default="{ row }">{{ (row.attendees || []).length }} 人</template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <span class="pm-tag" :class="statusMetaOf(row.status).cls">{{
                statusMetaOf(row.status).label
              }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openDetail(row.id)">详情</el-button>
              <el-button link type="primary" @click.stop="handleEdit(row)">编辑</el-button>
              <el-button link type="danger" @click.stop="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- ===== 我的会议视图 ===== -->
    <div v-show="activeView === 'mine'" class="bento-grid">
      <div class="card span-12">
        <div class="card-header">
          <div>
            <div class="card-title">我参与的会议</div>
            <div class="card-sub">{{ currentUser }} 作为组织者或参会人</div>
          </div>
        </div>
        <el-table
          :data="mineMeetings"
          v-loading="loading"
          @row-click="(row) => openDetail(row.id)"
        >
          <el-table-column label="日期" width="100">
            <template #default="{ row }">{{ formatDateMD(row.start_time) }}</template>
          </el-table-column>
          <el-table-column label="时间" width="90">
            <template #default="{ row }">
              <span class="font-mono">{{ formatTime(row.start_time) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="会议主题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="location" label="地点" min-width="150" show-overflow-tooltip />
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <span class="pm-tag" :class="typeTagCls(row.meeting_type)">{{
                typeText(row.meeting_type)
              }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <span class="pm-tag" :class="statusMetaOf(row.status).cls">{{
                statusMetaOf(row.status).label
              }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openDetail(row.id)">详情</el-button>
              <el-button link type="primary" @click.stop="handleEdit(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 会议详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="detailMeeting?.title || '会议详情'" size="520px" direction="rtl">
      <div v-loading="detailLoading" class="dw-body">
        <template v-if="detailMeeting">
          <div class="detail-block">
            <div class="pm-section-title">基本信息</div>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-k">时间</span>
                <span class="info-v">{{ formatDateTime(detailMeeting.start_time) }} ·
                  {{ durationText(detailMeeting) }}</span>
              </div>
              <div class="info-item">
                <span class="info-k">地点</span>
                <span class="info-v">{{ detailMeeting.location || '—' }}</span>
              </div>
              <div class="info-item">
                <span class="info-k">类型</span>
                <span class="info-v">{{ typeText(detailMeeting.meeting_type) }}</span>
              </div>
              <div class="info-item">
                <span class="info-k">状态</span>
                <span class="info-v">
                  <span class="pm-tag" :class="statusMetaOf(detailMeeting.status).cls">{{
                    statusMetaOf(detailMeeting.status).label
                  }}</span>
                </span>
              </div>
              <div class="info-item">
                <span class="info-k">组织者</span>
                <span class="info-v">{{ detailMeeting.host || '—' }}</span>
              </div>
              <div class="info-item">
                <span class="info-k">参会人</span>
                <span class="info-v">{{ (detailMeeting.attendees || []).length }} 人</span>
              </div>
            </div>
          </div>

          <div class="detail-block">
            <div class="pm-section-title">参会人</div>
            <div class="attendee-wrap">
              <span
                v-for="(a, i) in detailMeeting.attendees || []"
                :key="i"
                class="attendee-chip"
              >
                <span class="av" :style="{ background: avColors[i % avColors.length] }">{{
                  avatarChar(a.name)
                }}</span>
                {{ a.name }}
              </span>
              <span v-if="!(detailMeeting.attendees || []).length" class="empty-hint">暂无参会人</span>
            </div>
          </div>

          <div class="detail-block">
            <div class="pm-section-title">议程要点</div>
            <div
              v-for="(act, i) in detailMeeting.actions || []"
              :key="i"
              class="agenda-item"
            >
              <span class="agenda-idx">{{ i + 1 }}</span>
              <span class="agenda-txt">{{ act.content }}</span>
            </div>
            <div v-if="!(detailMeeting.actions || []).length" class="empty-hint">暂无议程</div>
          </div>

          <div class="detail-block">
            <div class="pm-section-title">关联需求 / 工单</div>
            <span
              v-for="(l, i) in relatedLinks(detailMeeting)"
              :key="i"
              class="link-chip"
              @click="ElMessage.info('跳转到 ' + l)"
            >🔗 {{ l }}</span>
            <span v-if="!relatedLinks(detailMeeting).length" class="empty-hint">无关联</span>
          </div>

          <div class="detail-block">
            <div class="pm-section-title">会议纪要（Obsidian）</div>
            <div
              v-if="detailMeeting.obsidian_path"
              class="link-chip"
              @click="ElMessage.info('打开 ' + detailMeeting.obsidian_path)"
            >📝 {{ detailMeeting.obsidian_path }}</div>
            <span v-else class="empty-hint">尚未生成纪要</span>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button @click="ElMessage.info('已复制会议链接')">🔗 分享</el-button>
        <el-button @click="ElMessage.success('会议通知已发送给参会人')">📧 发送通知</el-button>
        <el-button type="primary" @click="editFromDetail">编辑</el-button>
      </template>
    </el-drawer>

    <!-- 新增 / 编辑会议弹层 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑会议' : '新增会议'"
      width="640px"
      destroy-on-close
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="会议主题" prop="title">
          <el-input v-model="form.title" placeholder="如：集团客户拜访准备会" />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker
                v-model="form.start_time"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="选择开始时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时长(分钟)">
              <el-input-number v-model="form.duration" :min="5" :step="5" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="会议地点">
              <el-input v-model="form.location" placeholder="会议室 / 线上链接" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="会议类型" prop="meeting_type">
              <el-select v-model="form.meeting_type" style="width: 100%">
                <el-option
                  v-for="t in meetingTypeOptions"
                  :key="t.value"
                  :label="t.label"
                  :value="t.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="组织者" prop="host">
              <el-input v-model="form.host" placeholder="组织者" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option
                  v-for="s in statusOptions"
                  :key="s.value"
                  :label="s.label"
                  :value="s.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="参会人">
          <div class="chip-input">
            <span v-for="(c, i) in attendeeChips" :key="i" class="chip">
              {{ c }}
              <span class="chip-x" @click="attendeeChips.splice(i, 1)">✕</span>
            </span>
            <input
              v-model="attendeeInput"
              class="chip-text"
              placeholder="输入姓名后回车"
              @keydown.enter.prevent="addChip"
            />
          </div>
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="关联需求">
              <el-input v-model="form.related_req_id" placeholder="如 REQ-2026-0718" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联工单">
              <el-input v-model="form.related_ticket_no" placeholder="如 OP-2026-0456" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="议程要点">
          <el-input
            v-model="agendaText"
            type="textarea"
            :rows="3"
            placeholder="每行一条议程"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">创建并通知</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { meetingApi } from '@/api/meeting'

const currentUser = '陈大虾'

const loading = ref(false)
const activeView = ref('cal')
const keyword = ref('')
const filterType = ref('')
const filterStatus = ref('')
const currentDate = ref(new Date())

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailMeeting = ref(null)

const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const attendeeInput = ref('')
const attendeeChips = ref([])
const agendaText = ref('')

const meetings = ref([])

const viewDefs = [
  { key: 'cal', label: '月历视图' },
  { key: 'list', label: '会议列表' },
  { key: 'mine', label: '我的会议' },
]

const meetingTypeOptions = [
  { value: 'requirement_review', label: '需求评审' },
  { value: 'project_weekly', label: '项目周报' },
  { value: 'troubleshooting', label: '问题排查' },
  { value: 'training', label: '培训' },
  { value: 'other', label: '其他' },
]

const statusOptions = [
  { value: 'planned', label: '计划中' },
  { value: 'held', label: '已召开' },
  { value: 'cancelled', label: '已取消' },
]

const statusMeta = {
  planned: { label: '计划中', cls: 'blue' },
  held: { label: '已召开', cls: 'green' },
  cancelled: { label: '已取消', cls: 'gray' },
}
const statusMetaOf = (s) => statusMeta[s] || { label: s || '—', cls: 'gray' }

const typeTagMap = {
  requirement_review: 'amber',
  project_weekly: 'blue',
  troubleshooting: 'red',
  training: 'green',
  other: 'gray',
}
const typeTagCls = (t) => typeTagMap[t] || 'blue'
const typeDotClass = (t) => typeTagCls(t)
const typeText = (t) => {
  const item = meetingTypeOptions.find((i) => i.value === t)
  return item ? item.label : t || '其他'
}

const avColors = ['#2f6fed', '#0f9d6b', '#d98a1f', '#7c3aed', '#d9544d', '#3b82f6']
const avatarChar = (name) => (name ? name.charAt(0) : '?')

/* ── 时间格式化辅助 ── */
const pad = (n) => String(n).padStart(2, '0')
const toDate = (v) => (v instanceof Date ? v : v ? new Date(v) : null)
const dateKeyOf = (v) => {
  const d = toDate(v)
  return d && !isNaN(d.getTime())
    ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    : ''
}
const formatTime = (v) => {
  const d = toDate(v)
  return d && !isNaN(d.getTime()) ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : '—'
}
const formatDateMD = (v) => {
  const d = toDate(v)
  return d && !isNaN(d.getTime()) ? `${pad(d.getMonth() + 1)}/${pad(d.getDate())}` : '—'
}
const formatDateTime = (v) => {
  const d = toDate(v)
  return d && !isNaN(d.getTime())
    ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
    : '—'
}
const durationText = (m) => {
  if (!m || !m.start_time || !m.end_time) return '—'
  const s = toDate(m.start_time)
  const e = toDate(m.end_time)
  if (isNaN(s) || isNaN(e)) return '—'
  const mins = Math.round((e - s) / 60000)
  if (mins < 60) return mins + ' 分钟'
  return Math.floor(mins / 60) + ' 小时' + (mins % 60 ? ' ' + (mins % 60) + ' 分' : '')
}

/* ── 派生数据 ── */
const filteredMeetings = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  let list = meetings.value
  if (kw) {
    list = list.filter((m) => {
      const hay = [
        m.title,
        m.host,
        m.location,
        m.meeting_id,
        ...((m.attendees || []).map((a) => a.name)),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(kw)
    })
  }
  if (filterType.value) list = list.filter((m) => m.meeting_type === filterType.value)
  if (filterStatus.value) list = list.filter((m) => m.status === filterStatus.value)
  return list.slice().sort((a, b) => (dateKeyOf(a.start_time) < dateKeyOf(b.start_time) ? 1 : -1))
})

const listMeetings = computed(() => filteredMeetings.value)
const mineMeetings = computed(() =>
  filteredMeetings.value.filter(
    (m) =>
      m.host === currentUser ||
      (m.attendees || []).some((a) => a.name === currentUser)
  )
)

const isMine = (m) =>
  m.host === currentUser || (m.attendees || []).some((a) => a.name === currentUser)

/* 周范围 */
const weekRange = computed(() => {
  const now = new Date()
  const dow = (now.getDay() + 6) % 7
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - dow)
  const sunday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6)
  return {
    start: `${monday.getFullYear()}-${pad(monday.getMonth() + 1)}-${pad(monday.getDate())}`,
    end: `${sunday.getFullYear()}-${pad(sunday.getMonth() + 1)}-${pad(sunday.getDate())}`,
  }
})
const todayKey = computed(() => dateKeyOf(new Date()))

const weekCount = computed(
  () =>
    meetings.value.filter((m) => {
      const k = dateKeyOf(m.start_time)
      return k >= weekRange.value.start && k <= weekRange.value.end
    }).length
)
const plannedCount = computed(() => meetings.value.filter((m) => m.status === 'planned').length)
const mineCount = computed(() => meetings.value.filter(isMine).length)
const noteCount = computed(() => meetings.value.filter((m) => m.obsidian_path).length)

const monthKey = computed(() => {
  const y = currentDate.value.getFullYear()
  const m = currentDate.value.getMonth() + 1
  return `${y}-${pad(m)}`
})
const monthCount = computed(
  () => meetings.value.filter((m) => dateKeyOf(m.start_time).startsWith(monthKey.value)).length
)
const monthMine = computed(
  () => mineMeetings.value.filter((m) => dateKeyOf(m.start_time).startsWith(monthKey.value)).length
)
const monthNote = computed(
  () =>
    meetings.value.filter(
      (m) => dateKeyOf(m.start_time).startsWith(monthKey.value) && m.obsidian_path
    ).length
)

/* 月历网格 */
const dowLabels = ['一', '二', '三', '四', '五', '六', '日']
const calTitle = computed(
  () => `${currentDate.value.getFullYear()} 年 ${currentDate.value.getMonth() + 1} 月`
)
const calendarDays = computed(() => {
  const y = currentDate.value.getFullYear()
  const m = currentDate.value.getMonth()
  const first = new Date(y, m, 1)
  const startDow = (first.getDay() + 6) % 7
  const start = new Date(y, m, 1 - startDow)
  const days = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    const key = dateKeyOf(d)
    days.push({
      date: d,
      dayNum: d.getDate(),
      inMonth: d.getMonth() === m,
      isToday: key === todayKey.value,
      key,
      dayMeetings: meetings.value.filter((mt) => dateKeyOf(mt.start_time) === key),
    })
  }
  return days
})

const todayLabel = computed(() => formatDateMD(new Date()))
const todayMeetings = computed(() =>
  meetings.value
    .filter((m) => dateKeyOf(m.start_time) === todayKey.value)
    .sort((a, b) => (a.start_time < b.start_time ? -1 : 1))
)
const upcomingMeetings = computed(() =>
  meetings.value
    .filter((m) => m.status === 'planned' && dateKeyOf(m.start_time) >= todayKey.value)
    .sort((a, b) => (a.start_time < b.start_time ? -1 : 1))
    .slice(0, 6)
)

const roomUsage = [
  { name: '3F 主会议室', pct: 64, cls: '' },
  { name: '5F 小间', pct: 38, cls: 'green' },
  { name: '线上腾讯会议', pct: 82, cls: 'amber' },
]

const lineCls = (status) =>
  status === 'held' ? 'green' : status === 'planned' ? 'amber' : ''
const relatedLinks = (m) =>
  [m?.related_req_id, m?.related_ticket_no].filter(Boolean)

/* ── API 调用 ── */
const loadMeetings = async () => {
  loading.value = true
  try {
    const res = await meetingApi.listMeetings({ page: 1, page_size: 999 })
    meetings.value = res.items || []
  } catch (e) {
    ElMessage.error('加载会议失败')
  } finally {
    loading.value = false
  }
}

const openDetail = async (id) => {
  detailVisible.value = true
  detailLoading.value = true
  detailMeeting.value = null
  try {
    const m = await meetingApi.getMeeting(id)
    detailMeeting.value = m
  } catch (e) {
    ElMessage.error('加载会议详情失败')
  } finally {
    detailLoading.value = false
  }
}

const editFromDetail = () => {
  if (detailMeeting.value) {
    detailVisible.value = false
    handleEdit(detailMeeting.value)
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除会议「${row.title}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      await meetingApi.deleteMeeting(row.id)
      ElMessage.success('删除成功')
      loadMeetings()
    })
    .catch(() => {})
}

/* ── 月历导航 ── */
const prevMonth = () =>
  (currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() - 1, 1))
const nextMonth = () =>
  (currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() + 1, 1))
const goToday = () => (currentDate.value = new Date())
const onCellClick = (cell) => {
  if (cell.dayMeetings.length === 1) openDetail(cell.dayMeetings[0].id)
  else if (cell.dayMeetings.length > 1) ElMessage.info(`${cell.key} 有 ${cell.dayMeetings.length} 场会议`)
}

/* ── 新增 / 编辑 ── */
const defaultForm = {
  id: null,
  title: '',
  meeting_type: 'requirement_review',
  status: 'planned',
  start_time: '',
  duration: 60,
  host: currentUser,
  location: '',
  related_req_id: '',
  related_ticket_no: '',
  obsidian_path: '',
}
const form = reactive({ ...defaultForm })

const rules = {
  title: [{ required: true, message: '请输入会议主题', trigger: 'blur' }],
  meeting_type: [{ required: true, message: '请选择会议类型', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  host: [{ required: true, message: '请输入组织者', trigger: 'blur' }],
}

const generateMeetingId = () => {
  const d = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const r = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `MEET-${d}-${r}`
}

const addChip = () => {
  const v = attendeeInput.value.trim()
  if (v && !attendeeChips.value.includes(v)) attendeeChips.value.push(v)
  attendeeInput.value = ''
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(form, { ...defaultForm, host: currentUser, meeting_id: generateMeetingId() })
  attendeeChips.value = []
  agendaText.value = ''
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    title: row.title || '',
    meeting_type: row.meeting_type || 'other',
    status: row.status || 'planned',
    start_time: row.start_time ? row.start_time.slice(0, 19).replace('T', ' ') : '',
    duration: 60,
    host: row.host || currentUser,
    location: row.location || '',
    related_req_id: row.related_req_id || '',
    related_ticket_no: row.related_ticket_no || '',
    obsidian_path: row.obsidian_path || '',
  })
  if (row.start_time && row.end_time) {
    const s = toDate(row.start_time)
    const e = toDate(row.end_time)
    if (!isNaN(s) && !isNaN(e)) form.duration = Math.max(5, Math.round((e - s) / 60000))
  }
  attendeeChips.value = (row.attendees || []).map((a) => a.name).filter(Boolean)
  agendaText.value = (row.actions || []).map((a) => a.content).filter(Boolean).join('\n')
  dialogVisible.value = true
}

const handleSubmit = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    const start = toDate(form.start_time)
    if (isNaN(start)) {
      ElMessage.error('开始时间无效')
      return
    }
    const end = new Date(start.getTime() + form.duration * 60000)
    const payload = {
      title: form.title,
      meeting_type: form.meeting_type,
      status: form.status,
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      location: form.location || null,
      host: form.host,
      related_req_id: form.related_req_id || null,
      related_ticket_no: form.related_ticket_no || null,
      obsidian_path: form.obsidian_path || null,
      attendees: attendeeChips.value
        .filter((n) => n.trim())
        .map((n) => ({ name: n.trim(), is_required: 1 })),
      actions: agendaText.value
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((c) => ({ content: c, status: 'pending' })),
    }
    try {
      if (isEdit.value) {
        await meetingApi.updateMeeting(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        await meetingApi.createMeeting(payload)
        ElMessage.success('创建成功，通知已发送')
      }
      dialogVisible.value = false
      loadMeetings()
    } catch (e) {
      ElMessage.error(e?.response?.data?.message || '操作失败')
    }
  })
}

onMounted(() => {
  loadMeetings()
})
</script>

<style scoped>
.meeting-view {
  padding: 22px 28px 40px;
  max-width: 1600px;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.page-crumb {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 2px;
}
.page-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.head-search {
  width: 220px;
}
.search-ico {
  font-size: 13px;
}

.kpi-strip {
  margin-bottom: 18px;
}
.kpi-card {
  padding: 20px 16px !important;
  text-align: center;
}
.kpi-num {
  font-size: 34px;
  font-weight: 800;
  font-family: var(--font-mono);
  line-height: 1.1;
  letter-spacing: -1.5px;
  color: var(--text-primary);
}
.kpi-num.blue {
  color: var(--accent);
}
.kpi-num.amber {
  color: var(--warning);
}
.kpi-num.green {
  color: var(--success);
}
.kpi-label {
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-top: 6px;
}

.view-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}
.view-tabs {
  display: inline-flex;
  background: var(--border-subtle);
  border-radius: 11px;
  padding: 4px;
  gap: 2px;
}
.view-tab {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  border: none;
  background: transparent;
  transition: all var(--transition-fast);
}
.view-tab.active {
  background: var(--surface);
  color: var(--accent);
  box-shadow: var(--shadow-card);
}
.view-hint {
  font-size: 13px;
  color: var(--text-secondary);
}
.view-hint b {
  color: var(--accent);
}

/* 卡片标题（design.css 无 card-title，这里补） */
.card-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.card-sub {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 3px;
}
.card-body {
  padding: 16px 20px 20px;
}
.btn-sm {
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
}
.span-12 {
  grid-column: span 12;
}

/* 月历 */
.cal-card {
  grid-column: span 8;
}
.cal-nav {
  display: flex;
  gap: 6px;
}
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
  padding: 18px 20px 22px;
}
.cal-dow {
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  padding: 4px 0;
}
.cal-cell {
  min-height: 84px;
  border-radius: 10px;
  border: 1px solid var(--border-subtle);
  background: #fcfdff;
  padding: 8px;
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}
.cal-cell:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.cal-cell.other {
  background: transparent;
  opacity: 0.42;
}
.cal-cell.today {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.cal-day {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}
.cal-cell.today .cal-day {
  color: var(--accent);
}
.cal-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}
.cal-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.cal-dot.blue {
  background: var(--accent);
}
.cal-dot.green {
  background: var(--success);
}
.cal-dot.amber {
  background: var(--warning);
}
.cal-dot.red {
  background: var(--danger);
}
.cal-dot.gray {
  background: var(--text-muted);
}
.cal-meta {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
  line-height: 1.3;
}

/* 今日 / 待开 / 会议室 */
.today-card,
.up-card,
.room-card,
.month-card {
  grid-column: span 4;
}
.today-list,
.up-list,
.room-list,
.month-stats {
  display: flex;
  flex-direction: column;
}
.mt-row {
  display: flex;
  gap: 14px;
  padding: 12px 4px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background var(--transition-fast);
}
.mt-row:last-child {
  border-bottom: none;
}
.mt-row:hover {
  background: var(--accent-soft);
}
.mt-time {
  width: 56px;
  flex-shrink: 0;
  text-align: center;
}
.mt-hour {
  font-size: 15px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
}
.mt-dur {
  font-size: 10.5px;
  color: var(--text-muted);
  margin-top: 3px;
}
.mt-line {
  width: 2px;
  border-radius: 2px;
  background: var(--accent);
  flex-shrink: 0;
  margin-top: 3px;
}
.mt-line.amber {
  background: var(--warning);
}
.mt-line.green {
  background: var(--success);
}
.mt-body {
  flex: 1;
  min-width: 0;
}
.mt-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.mt-info {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.mt-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 20px;
  background: var(--accent-soft);
  color: var(--accent);
  margin-top: 6px;
}
.empty-hint {
  font-size: 12.5px;
  color: var(--text-muted);
  padding: 8px 4px;
}
.up-item {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 4px;
  border-bottom: 1px dashed var(--border);
  cursor: pointer;
}
.up-item:hover {
  color: var(--accent);
}
.up-item:last-of-type {
  border-bottom: none;
}
.up-date {
  color: var(--accent);
  font-family: var(--font-mono);
  margin-right: 4px;
}
.up-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}
.room-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
  color: var(--text-secondary);
  padding: 8px 0;
}
.room-name {
  width: 96px;
  flex-shrink: 0;
}
.room-bar {
  flex: 1;
  height: 7px;
  border-radius: 6px;
  background: #eef2f7;
  overflow: hidden;
}
.room-fill {
  height: 100%;
  border-radius: 6px;
  background: var(--accent);
}
.room-fill.green {
  background: var(--success);
}
.room-fill.amber {
  background: var(--warning);
}
.room-pct {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
  width: 38px;
  text-align: right;
}
.month-stats {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}
.mini-stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 14px 12px;
  border-radius: 12px;
  background: var(--border-subtle);
}
.mini-num {
  font-size: 24px;
  font-weight: 800;
  font-family: var(--font-mono);
  line-height: 1;
}
.mini-lab {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 列表 */
.list-head {
  padding: 18px 20px;
}
.list-filters {
  display: flex;
  gap: 8px;
}

/* 抽屉 */
.dw-body {
  padding: 4px 4px 8px;
}
.detail-block {
  margin-bottom: 20px;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.info-k {
  font-size: 11.5px;
  color: var(--text-muted);
}
.info-v {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
}
.attendee-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.attendee-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  font-weight: 600;
  background: var(--border-subtle);
  padding: 5px 11px;
  border-radius: 9px;
}
.av {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
}
.agenda-item {
  display: flex;
  gap: 11px;
  padding: 9px 0;
  border-bottom: 1px dashed var(--border);
}
.agenda-item:last-child {
  border-bottom: none;
}
.agenda-idx {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.agenda-txt {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}
.link-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 11px;
  border-radius: 9px;
  background: var(--border-subtle);
  color: var(--text-secondary);
  cursor: pointer;
  margin: 0 6px 6px 0;
  transition: all var(--transition-fast);
}
.link-chip:hover {
  background: var(--accent-soft);
  color: var(--accent);
}

/* 弹层 chip 多选 */
.chip-input {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 10px;
  width: 100%;
}
.chip-input:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 9px;
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent);
}
.chip-x {
  cursor: pointer;
  opacity: 0.7;
}
.chip-x:hover {
  opacity: 1;
}
.chip-text {
  border: none;
  outline: none;
  flex: 1;
  font-size: 13px;
  min-width: 80px;
  background: transparent;
}
</style>
