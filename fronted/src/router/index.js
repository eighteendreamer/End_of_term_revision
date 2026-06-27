import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue')
  },
  {
    path: '/subjects',
    name: 'Subjects',
    component: () => import('@/views/Subjects.vue')
  },
  {
    path: '/import',
    name: 'ImportQuestion',
    component: () => import('@/views/ImportQuestion.vue')
  },
  {
    path: '/practice',
    name: 'Practice',
    component: () => import('@/views/Practice.vue')
  },
  {
    path: '/errors',
    name: 'ErrorBook',
    component: () => import('@/views/ErrorBook.vue')
  },
  {
    path: '/error-practice',
    name: 'ErrorPractice',
    component: () => import('@/views/ErrorPractice.vue')
  },
  {
    path: '/model-config',
    name: 'ModelConfig',
    component: () => import('@/views/ModelConfig.vue')
  },
  {
    path: '/question-bank',
    name: 'QuestionBank',
    component: () => import('@/views/QuestionBank.vue')
  },
  {
    path: '/practice-history',
    name: 'PracticeHistory',
    component: () => import('@/views/PracticeHistory.vue')
  },
  {
    path: '/leaderboard',
    name: 'Leaderboard',
    component: () => import('@/views/Leaderboard.vue')
  },
  {
    path: '/exam-paper/:id',
    name: 'ExamPaper',
    component: () => import('@/views/ExamPaper.vue')
  },
  {
    path: '/materials',
    name: 'Materials',
    component: () => import('@/views/Materials.vue')
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/Chat.vue')
  },
  {
    path: '/semester',
    name: 'Semester',
    component: () => import('@/views/Semester.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
