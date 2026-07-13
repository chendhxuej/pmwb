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
        path: 'ticket',
        name: 'Ticket',
        component: () => import('@/views/TicketView.vue'),
        meta: { title: '开发工单', icon: 'Tickets' },
      },
      {
        path: 'operation',
        name: 'Operation',
        component: () => import('@/views/OperationView.vue'),
        meta: { title: '运营监控', icon: 'Warning' },
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
