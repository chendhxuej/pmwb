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
            path: 'notes',
            name: 'OperationNotes',
            component: () => import('@/views/OperationNotesView.vue'),
            meta: { title: '知识沉淀', icon: 'Notebook' },
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
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/KnowledgeView.vue'),
        meta: { title: '知识库', icon: 'Collection' },
      },
      // ── 保留的独立能力模块 ──
      {
        path: 'product-bible',
        name: 'ProductBible',
        component: () => import('@/views/ProductBibleView.vue'),
        meta: { title: '产品圣经', icon: 'Notebook' },
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
