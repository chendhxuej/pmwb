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
        path: 'todo',
        name: 'Todo',
        component: () => import('@/views/TodoView.vue'),
        meta: { title: '待办中心', icon: 'Check' },
      },
      {
        path: 'requirement',
        name: 'Requirement',
        component: () => import('@/views/RequirementView.vue'),
        meta: { title: '需求管理', icon: 'Document' },
      },
      {
        path: 'requirement-group',
        name: 'RequirementGroup',
        component: () => import('@/views/RequirementGroupView.vue'),
        meta: { title: '集团需求', icon: 'Postcard' },
      },
      {
        path: 'reminder-center',
        name: 'ReminderCenter',
        component: () => import('@/views/ReminderCenterView.vue'),
        meta: { title: '催办中心', icon: 'Bell' },
      },
      {
        path: 'mail-records',
        name: 'MailRecords',
        component: () => import('@/views/MailRecordsView.vue'),
        meta: { title: '邮件记录', icon: 'Message' },
      },
      {
        path: 'ticket',
        name: 'Ticket',
        component: () => import('@/views/TicketView.vue'),
        meta: { title: '开发工单', icon: 'Tickets' },
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
        meta: { title: '会议管理', icon: 'Calendar' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/KnowledgeView.vue'),
        meta: { title: '知识库', icon: 'Collection' },
      },
      {
        path: 'product-bible',
        name: 'ProductBible',
        component: () => import('@/views/ProductBibleView.vue'),
        meta: { title: '产品圣经', icon: 'Notebook' },
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
