import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/components/Layout/MainLayout.vue'
import HomeView from '@/views/HomeView.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: HomeView,
        meta: { title: '首页看板', icon: 'House' },
      },
      {
        path: 'task-center',
        name: 'TaskCenter',
        component: () => import('@/views/TaskCenterView.vue'),
        meta: { title: '任务中心', icon: 'List' },
      },
      {
        path: 'requirement-delivery',
        name: 'RequirementDelivery',
        component: () => import('@/views/RequirementDeliveryView.vue'),
        meta: { title: '需求与交付', icon: 'Connection' },
      },
      {
        path: 'operation',
        component: () => import('@/views/OperationLayout.vue'),
        redirect: '/operation/overview',
        meta: { title: '运营监控', icon: 'Warning' },
        children: [
          {
            path: 'overview',
            name: 'OperationOverview',
            component: () => import('@/views/OperationView.vue'),
            meta: { title: '总览', icon: 'DataLine' },
          },
          {
            path: 'bug',
            name: 'WOBug',
            component: () => import('@/views/WorkOrderView.vue'),
            meta: { title: 'BUG管理', category: 'bug' },
          },
          {
            path: 'data',
            name: 'WOData',
            component: () => import('@/views/WorkOrderView.vue'),
            meta: { title: '数据异常管理', category: 'data' },
          },
          {
            path: 'prod',
            name: 'WOProd',
            component: () => import('@/views/WorkOrderView.vue'),
            meta: { title: '生产问题分析', category: 'prod' },
          },
          {
            path: 'task',
            name: 'WOTask',
            component: () => import('@/views/WorkOrderView.vue'),
            meta: { title: '临时交办任务', category: 'task' },
          },
          {
            path: 'complaint',
            name: 'WOComplaint',
            component: () => import('@/views/WorkOrderView.vue'),
            meta: { title: '热点投诉', category: 'complaint' },
          },
          {
            path: 'research',
            name: 'WOResearch',
            component: () => import('@/views/ResearchIssueView.vue'),
            meta: { title: '一线调研', category: 'research' },
          },
          {
            path: 'monitor',
            name: 'ProductionMonitor',
            component: () => import('@/views/ProductionMonitorPlaceholder.vue'),
            meta: { title: '生产监控', icon: 'Monitor', badge: '建设中' },
          },
        ],
      },
      {
        path: 'meeting',
        name: 'Meeting',
        component: () => import('@/views/MeetingLayout.vue'),
        redirect: '/meeting/list',
        meta: { title: '会议日程', icon: 'Calendar' },
        children: [
          {
            path: 'list',
            name: 'MeetingList',
            component: () => import('@/views/MeetingView.vue'),
            meta: { title: '会议列表', icon: 'Calendar' },
          },
          {
            path: 'actions',
            name: 'MeetingActions',
            component: () => import('@/views/MeetingActionsView.vue'),
            meta: { title: '行动项', icon: 'List' },
          },
        ],
      },
      {
        path: 'todo',
        name: 'Todo',
        component: () => import('@/views/TodoView.vue'),
        meta: { title: '个人待办', icon: 'Check' },
      },
      {
        path: 'key-works',
        name: 'KeyWork',
        component: () => import('@/views/KeyWorkView.vue'),
        meta: { title: '重点工作', icon: 'Files' },
      },
      // ── AI 中心：整合 AI问答 / AI总结 / 大模型管理 三大子模块 ──
      {
        path: 'ai-center',
        name: 'AiCenter',
        component: () => import('@/views/AiCenterLayout.vue'),
        redirect: '/ai-center/qa',
        meta: { title: 'AI中心', icon: 'MagicStick' },
        children: [
          {
            path: 'qa',
            name: 'AiQa',
            component: () => import('@/views/AiQaView.vue'),
            meta: { title: 'AI问答', icon: 'ChatDotRound' },
          },
          {
            path: 'summary',
            name: 'AiSummary',
            component: () => import('@/views/WorkReportView.vue'),
            meta: { title: 'AI总结', icon: 'EditPen' },
          },
          {
            path: 'llm',
            name: 'AiLlm',
            component: () => import('@/views/LlmProviderManage.vue'),
            meta: { title: '大模型管理', icon: 'Cpu' },
          },
        ],
      },
      {
        path: 'basic-data',
        name: 'BasicData',
        component: () => import('@/views/PersonnelCenterView.vue'),
        meta: { title: '人员中台', icon: 'OfficeBuilding' },
      },
      // ── 业务领域管理（隐藏菜单，从知识中心跳转） ──
      {
        path: 'business-domains',
        name: 'BusinessDomainManage',
        component: () => import('@/views/BusinessDomainManage.vue'),
        meta: { title: '业务领域管理', hidden: true },
      },
      // ── 知识中心：业务全景（保留子路由以防历史深链崩溃，菜单仅展示 hub） ──
      {
        path: 'knowledge-center',
        name: 'KnowledgeCenter',
        component: () => import('@/views/KnowledgeCenterView.vue'),
        redirect: '/knowledge-center/hub',
        meta: { title: '知识中心', icon: 'Reading' },
        children: [
          {
            path: 'hub',
            name: 'KcHub',
            component: () => import('@/views/KnowledgeCenter/HubPanel.vue'),
            meta: { title: '业务全景', icon: 'DataBoard' },
          },
          {
            path: 'timeline',
            name: 'KcTimeline',
            component: () => import('@/views/KnowledgeCenter/TimelineView.vue'),
            meta: { title: '全局时间线', icon: 'Clock', hidden: true },
          },
          {
            path: 'relations',
            name: 'KcRelations',
            component: () => import('@/views/KnowledgeCenter/RelationsView.vue'),
            meta: { title: '智能关联', icon: 'Connection', hidden: true },
          },
          {
            path: 'manage',
            name: 'KcManage',
            component: () => import('@/views/KnowledgeCenter/ManageView.vue'),
            meta: { title: '领域管理', icon: 'SetUp', hidden: true },
          },
          // ── 历史子模块（hidden：保留深链，不在左侧菜单展示） ───
          {
            path: 'knowledge',
            name: 'KcKnowledge',
            component: () => import('@/views/KnowledgeView.vue'),
            meta: { title: '知识库', icon: 'Collection' },
          },
          {
            path: 'product-bible',
            name: 'KcProductBible',
            component: () => import('@/views/ProductBibleView.vue'),
            meta: { title: '产品圣经', icon: 'Notebook', hidden: true },
          },
          {
            path: 'domain',
            name: 'KcDomain',
            component: () => import('@/views/DomainKnowledgeView.vue'),
            meta: { title: '按领域浏览', icon: 'Grid' },
          },
          {
            path: 'sql-scripts',
            name: 'KcSqlScripts',
            component: () => import('@/views/SqlScriptView.vue'),
            meta: { title: 'SQL脚本库', icon: 'Document', hidden: true },
          },
          {
            path: 'business-domains',
            name: 'KcBusinessDomains',
            component: () => import('@/views/BusinessDomainManage.vue'),
            meta: { title: '业务知识维度', icon: 'SetUp' },
          },
          {
            path: 'notes',
            name: 'KcNotes',
            component: () => import('@/views/KnowledgeCenter/HubPanel.vue'),
            meta: { title: '知识沉淀', icon: 'Files', hidden: true },
          },
        ],
      },
      // 旧催办中心深链兼容（隐藏于菜单，重定向到任务中心）
      {
        path: 'reminder-center',
        name: 'ReminderCenter',
        redirect: '/task-center',
        meta: { hidden: true },
      },
      // ── 邮件中心 ──
      {
        path: 'mail-records',
        redirect: '/mail-center/logs',
        meta: { hidden: true },
      },
      {
        path: 'mail-center',
        name: 'MailCenter',
        component: () => import('@/views/mail/MailCenterLayout.vue'),
        redirect: '/mail-center/logs',
        meta: { title: '邮件中心', icon: 'Message' },
        children: [
          {
            path: 'logs',
            name: 'MailLogs',
            component: () => import('@/views/mail/MailLogsView.vue'),
            meta: { title: '发送日志', icon: 'Tickets' },
          },
          {
            path: 'accounts',
            name: 'MailAccounts',
            component: () => import('@/views/mail/MailAccountsView.vue'),
            meta: { title: '邮件账号', icon: 'User' },
          },
          {
            path: 'contacts',
            name: 'MailContacts',
            component: () => import('@/views/mail/MailContactsView.vue'),
            meta: { title: '通讯录', icon: 'Avatar' },
          },
          {
            path: 'groups',
            name: 'MailGroups',
            component: () => import('@/views/mail/MailGroupsView.vue'),
            meta: { title: '联系人分组', icon: 'Grid' },
          },
          {
            path: 'templates',
            name: 'MailTemplates',
            component: () => import('@/views/mail/MailTemplatesView.vue'),
            meta: { title: '邮件模板', icon: 'Memo' },
          },
        ],
      },
      // 已并入「需求与交付」的旧路由，保留深链兼容（隐藏于菜单）
      {
        path: 'requirement',
        name: 'RequirementLegacy',
        component: () => import('@/views/RequirementDeliveryView.vue'),
        meta: { hidden: true },
      },
      {
        path: 'ticket',
        name: 'TicketLegacy',
        component: () => import('@/views/WorkOrderView.vue'),
        meta: { hidden: true },
      },
      {
        path: 'requirement-group',
        name: 'RequirementGroup',
        component: () => import('@/views/RequirementGroupView.vue'),
        meta: { hidden: true },
      },
      // ── AI 总结（已整合进 AI中心，保留深链兼容） ──
      {
        path: 'work-report',
        name: 'WorkReport',
        component: () => import('@/views/WorkReportView.vue'),
        meta: { title: 'AI总结', icon: 'EditPen', hidden: true },
      },
      // ── 大模型管理（已整合进 AI中心，保留深链兼容） ──
      {
        path: 'llm-provider',
        name: 'LlmProvider',
        component: () => import('@/views/LlmProviderManage.vue'),
        meta: { title: '大模型管理', icon: 'Cpu', hidden: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
