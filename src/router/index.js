import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../pages/home/HomePage.vue'),
    meta: { tab: 'home', title: '首页' }
  },
  {
    path: '/config',
    component: () => import('../pages/asset-class/AssetClassPage.vue'),
    meta: { tab: 'config', title: '大类资产配置' }
  },
  {
    path: '/style-factor',
    component: () => import('../pages/style-factor/StyleFactorPage.vue'),
    meta: { tab: 'config', title: '风格因子' }
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
    path: '/tools/industry-rank',
    component: () => import('../pages/industry-rank/IndustryRankPage.vue'),
    meta: { tab: 'tools', title: '指数估值' }
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
    path: '/profile',
    component: () => import('../pages/profile/ProfilePage.vue'),
    meta: { tab: 'profile', title: '我的' }
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = (to.meta?.title || '投资工作助手') + ' - 大厨仪表盘'
})

export default router
