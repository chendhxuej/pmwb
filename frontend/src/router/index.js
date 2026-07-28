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
        component: () => import('@/views/MeetingView.vue'),
        meta: { title: '会议日程', icon: 'Calendar' },
      },
      {
        path: 'key-works',
        name: 'KeyWork',
        component: () => import('@/views/KeyWorkView.vue'),
        meta: { title: '重点工作', icon: 'Files' },
      },
      {
        path: 'basic-data',
        name: 'BasicData',
        component: () => import('@/views/BasicDataView.vue'),
        meta: { title: '团队信息', icon: 'OfficeBuilding' },
      },
      // ── 知识中心：聚合知识类子模块 ──
      {
        path: 'knowledge-center',
        name: 'KnowledgeCenter',
        component: () => import('@/views/KnowledgeCenterView.vue'),
        redirect: '/knowledge-center/knowledge',
        meta: { title: '知识中心', icon: 'Reading' },
        children: [
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
            meta: { title: '产品圣经', icon: 'Notebook' },
          },
          {
            path: 'notes',
            name: 'KcNotes',
            component: () => import('@/views/OperationNotesView.vue'),
            meta: { title: '知识沉淀', icon: 'Files' },
          },
          {
            path: 'sql-scripts',
            name: 'KcSqlScripts',
            component: () => import('@/views/SqlScriptView.vue'),
            meta: { title: 'SQL脚本库', icon: 'Document' },
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
