import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../pages/fund-rank/FundRankPage.vue'),
    meta: {
      tab: 'tools',
      title: '靠谱基金指数',
      description: '靠谱基金指数评分工具：覆盖全市场近2万只公募基金，按收益率、最大回撤、夏普比率综合排名，支持分类、份额、ETF/LOF 等多维筛选。',
      keywords: '靠谱基金指数,基金评分,基金排名,基金筛选,基金靠谱指数'
    }
  },
  {
    path: '/signal',
    component: () => import('../pages/signal/SignalPage.vue'),
    meta: {
      tab: 'signal',
      title: '指标信号',
      description: '宏观指标信号：股债利差、FED模型、大类资产性价比、风格因子与行业估值，叠加上证指数走势，辅助判断市场位置。',
      keywords: '宏观指标,股债利差,FED模型,大类资产,风格因子,行业估值'
    }
  },
  {
    path: '/tools',
    component: () => import('../pages/tools/ToolsPage.vue'),
    meta: {
      tab: 'tools',
      title: '工具',
      description: 'ALLFUND.CN 基金投资工具集：靠谱基金指数评分、投顾产品精选、智能组合与数据中心的入口。',
      keywords: '基金工具,基金评分,投顾产品,智能组合'
    }
  },
  {
    path: '/tools/tougu',
    component: () => import('../pages/tougu/TouguPage.vue'),
    meta: {
      tab: 'tools',
      title: '投顾产品精选',
      description: '精选高收益、稳健、养老三类投顾产品，对比近3月、近1年收益与最大回撤，辅助挑选基金投顾组合。',
      keywords: '投顾产品,基金投顾,稳健理财,养老储蓄'
    }
  },
  {
    path: '/tools/fund-rank',
    component: () => import('../pages/fund-rank/FundRankPage.vue'),
    meta: {
      tab: 'tools',
      title: '靠谱基金指数',
      description: '靠谱基金指数评分工具：覆盖全市场近2万只公募基金，按收益率、最大回撤、夏普比率综合排名，支持分类、份额、ETF/LOF 等多维筛选。',
      keywords: '靠谱基金指数,基金评分,基金排名,基金筛选,基金靠谱指数'
    }
  },
  {
    path: '/portfolio',
    component: () => import('../pages/portfolio/PortfolioPage.vue'),
    meta: {
      tab: 'tools',
      title: '智能组合',
      description: '智能组合构建：自建组合、DeepSeek AI 推荐组合（16 策略）与基于 Kan&Zhou 增强型风险平价的风险平价组合，辅助资产配置。',
      keywords: '智能组合,资产配置,风险平价,AI组合'
    }
  },
  {
    path: '/lab',
    component: () => import('../pages/lab/LabPage.vue'),
    meta: {
      tab: 'lab',
      title: '实验室',
      description: 'ALLFUND.CN 实验室：基金投资策略、量化模型与数据实验的尝鲜区。',
      keywords: '基金实验室,量化策略,投资模型'
    }
  },
  {
    path: '/data-center',
    component: () => import('../pages/data-center/DataCenterPage.vue'),
    meta: {
      tab: 'tools',
      title: '数据中心',
      description: '基金数据中心：基金基础信息、靠谱指数评分、宏观历史数据与投顾产品的字段说明与更新机制。',
      keywords: '基金数据,数据中心,基金基本信息,宏观数据'
    }
  },
  {
    path: '/profile',
    component: () => import('../pages/profile/ProfilePage.vue'),
    meta: {
      tab: 'profile',
      title: '我的',
      description: '我的：管理自选智能组合、查看历史 AI 组合推荐与账户信息。',
      keywords: '我的,自选基金,基金账户'
    }
  },
  // 旧路径重定向（带 tab 参数，跳转到正确视图）
  {
    path: '/config',
    redirect: '/signal?tab=asset'
  },
  {
    path: '/style-factor',
    redirect: '/signal?tab=factor'
  },
  {
    path: '/tools/industry-rank',
    redirect: '/signal?tab=industry'
  },
  // SPA 兜底：未匹配的前端路由重定向到首页（配合 EdgeOne SPA fallback）
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const baseTitle = 'ALLFUND.CN'
  document.title = (to.meta?.title || '靠谱指数评分工具') + ' | ' + baseTitle

  // 动态注入 SEO meta（description / keywords）
  const meta = to.meta || {}
  setMeta('description', meta.description || 'allfund.cn — 用数据说话，帮助你做出更好的基金投资决策。')
  setMeta('keywords', meta.keywords || '基金,靠谱基金,基金排名,基金投资')
  // Open Graph（社交分享卡片）
  setMeta('og:title', document.title, 'property')
  setMeta('og:description', meta.description || '用数据辅助基金投资决策：靠谱指数评分、股债性价比、大类资产预期收益。', 'property')
  setMeta('og:type', 'website', 'property')
  setMeta('og:url', location.origin + to.fullPath, 'property')
})

/** 获取或创建 meta 标签（name 或 property 属性）并设值 */
function setMeta(key, value, attr = 'name') {
  if (!value) return
  let el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', value)
}

export default router
