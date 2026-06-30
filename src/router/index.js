import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../pages/home/HomePage.vue'),
    meta: { tab: 'home', title: '首页' }
  },
  {
    path: '/signal',
    component: () => import('../pages/signal/SignalPage.vue'),
    meta: { tab: 'signal', title: '指标信号' }
  },
  {
    path: '/tools',
    component: () => import('../pages/tools/ToolsPage.vue'),
    meta: { tab: 'tools', title: '工具' }
  },
  {
    path: '/tools/tougu',
    component: () => import('../pages/tougu/TouguPage.vue'),
    meta: { tab: 'tools', title: '投顾产品精选' }
  },
  {
    path: '/tools/fund-rank',
    component: () => import('../pages/fund-rank/FundRankPage.vue'),
    meta: { tab: 'tools', title: '靠谱基金指数' }
  },
  {
    path: '/portfolio',
    component: () => import('../pages/portfolio/PortfolioPage.vue'),
    meta: { tab: 'tools', title: '基金组合' }
  },
  {
    path: '/lab',
    component: () => import('../pages/lab/LabPage.vue'),
    meta: { tab: 'lab', title: '实验室' }
  },
  {
    path: '/data-center',
    component: () => import('../pages/data-center/DataCenterPage.vue'),
    meta: { tab: 'tools', title: '数据中心' }
  },
  {
    path: '/profile',
    component: () => import('../pages/profile/ProfilePage.vue'),
    meta: { tab: 'profile', title: '我的' }
  },
  // 旧路径重定向（带 tab 参数，跳转到正确视图）
  {
    path: '/config',
    redirect: '/signal?tab=allocate'
  },
  {
    path: '/style-factor',
    redirect: '/signal?tab=factor'
  },
  {
    path: '/tools/industry-rank',
    redirect: '/signal?tab=industry'
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = (to.meta?.title || '靠谱指数评分工具') + ' | ALLFUND.CN'
})

export default router
