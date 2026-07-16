import { createRouter, createWebHistory } from 'vue-router'
import { supabase } from '../api/supabase.js'

const routes = [
  {
    path: '/',
    component: () => import('../pages/fund-rank/FundRankPage.vue'),
    meta: {
      tab: 'tools',
      feature: 'fund-rank',
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
      feature: 'signal',
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
      feature: 'fund-rank',
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
      feature: 'portfolio',
      title: '智能组合',
      description: '智能组合构建：自建组合、DeepSeek AI 推荐组合（16 策略）与基于 Kan&Zhou 增强型风险平价的风险平价组合，辅助资产配置。',
      keywords: '智能组合,资产配置,风险平价,AI组合'
    }
  },
  {
    path: '/fund/:code',
    component: () => import('../pages/fund-detail/FundDetailPage.vue'),
    meta: {
      tab: 'tools',
      feature: 'fund-rank',
      title: '基金详情',
      description: '单只基金详情：靠谱指数评分构成、各周期收益与同类排名。',
      keywords: '基金详情,基金评分,基金收益'
    }
  },
  {
    path: '/watchlist',
    component: () => import('../pages/watchlist/WatchlistPage.vue'),
    meta: {
      tab: 'profile',
      title: '我的关注',
      description: '自选关注基金列表：快速查看评分与各周期收益。',
      keywords: '自选基金,关注列表,基金关注'
    }
  },
  {
    path: '/compare',
    component: () => import('../pages/compare/CompareToolPage.vue'),
    meta: {
      tab: 'tools',
      title: '基金对比',
      description: '多只基金同维度对比：评分、收益、回撤与同类排名。',
      keywords: '基金对比,基金比较,基金筛选'
    }
  },
  {
    path: '/calc',
    component: () => import('../pages/calc/SipCalcPage.vue'),
    meta: {
      tab: 'tools',
      title: '定投计算器',
      description: '基金定投收益计算器：输入定投金额与期限，估算期末本息与总收益。',
      keywords: '定投计算器,基金定投,收益计算'
    }
  },
  {
    path: '/data-center',
    component: () => import('../pages/data-center/DataCenterPage.vue'),
    meta: {
      tab: 'tools',
      feature: 'data-center',
      ownerOnly: true,
      title: '管理中心',
      description: '管理中心：提供数据中心的数据下载与用户管理（含权限申请审批）等功能。',
      keywords: '管理中心,基金数据,数据中心,基金基本信息,宏观数据'
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
  // 微信网页扫码登录回调（公开路由：未登录即可访问，由 App.vue 绕过登录墙渲染）
  {
    path: '/wechat-callback',
    component: () => import('../pages/wechat-callback/WechatCallbackPage.vue'),
    meta: {
      public: true,
      title: '微信登录中',
      description: '微信扫码登录回调处理',
    }
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

// ---- 访问日志（数据中心「用户分析」数据来源） ----
let _geoCache = null
let _lastTrackPath = ''
let _lastTrackTs = 0
async function _getGeo() {
  if (_geoCache) return _geoCache
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 4000)
    const r = await fetch('https://ipwho.is/', { signal: ctrl.signal })
    clearTimeout(timer)
    if (r.ok) {
      const d = await r.json()
      if (d && d.success) {
        const loc = [d.region, d.city].filter(Boolean).join(' ')
        const region = (d.country === 'China' || d.country_code === 'CN')
          ? (loc || d.country)
          : (loc ? loc + ', ' + d.country : d.country)
        _geoCache = { ip: d.ip || null, region: region || null }
        return _geoCache
      }
    }
  } catch (e) { /* 忽略：geo 仅用于展示，失败则留空 */ }
  _geoCache = { ip: null, region: null }
  return _geoCache
}
async function _trackVisit(path) {
  try {
    const now = Date.now()
    if (path === _lastTrackPath && now - _lastTrackTs < 5000) return // 同路径 5s 内节流，避免刷屏
    _lastTrackPath = path
    _lastTrackTs = now
    const { data: { user } } = await supabase.auth.getUser()
    const geo = await _getGeo()
    await supabase.from('visitor_logs').insert({
      email: user?.email || 'anonymous',
      page_path: path,
      user_agent: navigator.userAgent,
      ip_address: geo.ip,
      region: geo.region,
      visit_time: new Date().toISOString()
    })
  } catch (e) { /* 静默失败，绝不阻塞页面 */ }
}

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
  // 记录访问（异步，不阻塞导航）
  _trackVisit(to.fullPath)
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
