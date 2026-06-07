# allfund 项目投资工作助手 - 项目文档

**版本**: v1.0.0  
**更新时间**: 2026-06-07  
**技术栈**: Vue 3 + Vite + Vue Router 4 + @supabase/supabase-js + ECharts  
**部署平台**: EdgeOne Pages  
**数据库**: Supabase (PostgreSQL)

---

## 一、项目概述

allfund 是一个面向个人基金投资者的投资工作助手 H5 网页应用，提供资产配置、工具、内容运营和 AI 对话等功能。核心理念是基于估值百分位 + Barra 因子性价比，逐层推导"配什么、配多少"。

**核心价值**：
- 📊 **靠谱基金指数**：基于收益、回撤、夏普比率的综合评分系统
- ⚖️ **大类资产配置**：Kan & Zhou (2007) 增强型风险平价模型
- 🎯 **风格因子分析**：Barra 六因子实时计算
- 📈 **实时市场数据**：腾讯 API + value500.com 多源数据整合

---

## 二、项目结构

```
allfund/
├── index.html                  # 入口 HTML
├── package.json                # 项目配置
├── vite.config.js              # Vite 配置
├── .edgeone/                   # EdgeOne Pages 配置
├── public/                     # 静态资源
├── src/
│   ├── main.js                 # 应用入口
│   ├── App.vue                 # 根组件（TabBar 布局）
│   ├── router/
│   │   └── index.js            # 路由配置
│   ├── api/
│   │   ├── supabase.js         # Supabase 客户端
│   │   └── data.js             # 数据 API 封装层
│   ├── utils/
│   │   ├── api.js              # API 工具函数
│   │   ├── calc.js             # 计算引擎
│   │   ├── market-data.js      # 市场数据处理
│   │   └── value500.js         # value500 数据解析
│   ├── data/
│   │   └── funds_meta.js       # 基金分类数据
│   └── pages/                  # 页面组件
│       ├── home/               # 首页
│       ├── asset-class/        # 大类资产配置
│       ├── style-factor/       # 风格因子
│       ├── fund-rank/          # 靠谱基金指数
│       ├── industry-rank/      # 指数估值
│       ├── tougu/              # 投顾产品
│       ├── portfolio/          # 基金组合
│       ├── tools/              # 工具聚合页
│       ├── lab/                # 实验室
│       └── profile/            # 个人中心
├── scripts/                    # 数据导入脚本
│   ├── create_tables.js        # 创建 Supabase 表
│   ├── import_data.js          # 导入初始数据
│   ├── init_supabase.js        # 初始化 Supabase
│   └── ...
└── supabase/                   # Supabase 相关
    └── .temp/
```

---

## 三、功能模块详解

### 3.1 首页（HomePage.vue）

**功能**：
- ✅ 金刚区：8 个核心功能入口
- ✅ 实时指数行情（腾讯 API）：上证、沪深 300、创业板、中证 500
- ✅ 全市场加权平均隐含夏普比率
- ✅ 股债性价比（Fed Model）
- ✅ 大类资产性价比概览
- ✅ 参考基准（利率走廊、资金面、宏观经济、估值参考）
- ✅ 指数估值概览（低估/高估 TOP5）
- ✅ 帮助弹窗（数据说明 + 更新频率）

**数据流**：
```
腾讯 API (qt.gtimg.cn)
    ↓
getIndexQuotes() → 实时行情
    ↓
value500.com (6个页面并行抓取)
    ↓
fetchValue500All() → 国债/Shibor/M2/CPI/股债比/沪深300PE百分位
    ↓
计算引擎 (calc.js)
    ↓
展示层
```

---

### 3.2 大类资产配置（AssetClassPage.vue）

**功能**：
- ✅ 6 大类资产预期收益率计算
  - 股票：Gordon 模型 E[R] = (1/PE) × adjust
  - 债券：10Y 国债 YTM
  - 黄金：实际利率模型
  - 现金：Shibor 隔夜
  - 商品/REITs：暂无数据源
- ✅ 隐含夏普比率计算
- ✅ Kan & Zhou (2007) 增强型风险平价权重
  - 公式：`w_i* = w_RP × (1 + (SR_i - median_SR) × sensitivity)`
  - `sensitivity = 0.5`，限幅 `[0%, 50%]`
- ✅ 刷新按钮（手动更新数据）

**数据来源**：
- 股票 PE：腾讯 API / 云数据库 `index_pe_history`
- 国债收益率：tushare `yc_cb` 接口
- Shibor：value500.com
- CPI：value500.com

---

### 3.3 风格因子（StyleFactorPage.vue）

**功能**：
- ✅ Barra 六因子实时计算
  - 规模因子（Size）
  - 价值因子（Value）
  - 动量因子（Momentum）
  - 质量因子（Quality）
  - 成长因子（Growth）
  - 流动性因子（Liquidity）
- ✅ ECharts 雷达图可视化
- ✅ 债券/商品 Tab 切换

**数据来源**：
- 指数 PE：腾讯 API
- PE 历史：云数据库 `index_pe_history`
- 商品期货价格：新浪财经 API

---

### 3.4 靠谱基金指数（FundRankPage.vue）

**功能**：
- ✅ 基金列表展示（100 条/页，分页加载）
- ✅ 按靠谱指数排序（点击周期 Tab 切换升序/降序）
- ✅ 多维度筛选：
  - 一级分类（t0）：股票型/债券型/混合型/FOF/QDII/货币
  - 二级分类（t1）：更细分类
  - 搜索：基金代码/名称
  - 智能识别：ETF/LOF/FOF/定开/持有期/±20%
  - 申购状态：可申购/暂停申购
- ✅ 筛选结果数量实时显示
- ✅ 基金详情页（跳转）

**靠谱分计算**（v6）：
```
靠谱指数 = 收益排位 × 50% + 回撤排位 × 25% + 夏普排位 × 25%
排位计算：全市场统一排名百分位 × 100（不按分类分组）
```

**数据来源**：
- 基金列表：Supabase `fund_scores` 表
- 收益率数据：天天基金 `rankhandler.aspx` API
- 风险指标（回撤/夏普）：天天基金 `pingzhongdata` 接口

---

### 3.5 指数估值（IndustryRankPage.vue）

**功能**：
- ✅ 63 个主流指数 PE/PB/股息率/ROE 展示
- ✅ PE 百分位实时计算
- ✅ 估值分布可视化

**数据来源**：
- 蛋卷基金估值中心 API

---

### 3.6 投顾产品（TouguPage.vue）

**功能**：
- ✅ 103 个全市场投顾组合展示
- ✅ 分类筛选：追求高收益/稳健理财/养老储蓄
- ✅ 按收益率排序

**数据来源**：
- 天天基金投顾页面 `fund.eastmoney.com/tg/`
- Supabase `tougu_products` 表

---

### 3.7 基金组合（PortfolioPage.vue）

**功能**：
- ✅ 权重计算（Kan & Zhou 风险平价实时计算）
- ✅ ETF 查询（从 Supabase `fund_scores` 按 t0+ETF 关键词查询）
- ✅ 组合展示

---

### 3.8 实验室（LabPage.vue）

**功能**：
- ✅ 运营助手：6 平台 × 3 选题 × 完整文案生成
- ✅ 娱乐助手：11 品类 × 3 推荐
- ✅ AI 助手：DeepSeek 前端直调 + 天天基金 Skill
- ✅ 重点资讯：每日 5 条

---

### 3.9 工具聚合页（ToolsPage.vue）

**功能**：
- ✅ 指数工具合集（10 家基金公司小程序跳转）
- ✅ 大 V 加仓减仓榜
- ✅ 快捷入口：靠谱基金指数、指数估值、投顾产品

---

## 四、数据架构

### 4.1 Supabase 数据库表

| 表名 | 用途 | 记录数 | 更新频率 |
|------|------|--------|---------|
| `fund_scores` | 基金靠谱指数数据 | 18,933 只基金（11,517 只有靠谱分） | 每日 17:30 |
| `tougu_products` | 投顾产品数据 | 103 条 | 手动更新 |
| `config` | 配置（API Key 等） | 2 条 | 手动更新 |
| `index_pe_history` | 指数 PE 历史 | 20 条（2026-03-25~2026-04-21） | 每日 17:30 |
| `fund_scores_meta` | 基金元信息（总数、更新日期） | 1 条 | 每日更新 |

### 4.2 外部数据源

| 数据源 | 用途 | 更新频率 | 访问方式 |
|--------|------|---------|---------|
| 腾讯 API (`qt.gtimg.cn`) | 实时行情 | 实时 | 前端直连 |
| value500.com | 国债/Shibor/M2/CPI/股债比 | 日度 | 前端直连（已部署 Supabase Edge Function） |
| 蛋卷基金 | 指数估值 | 日度 | 前端直连 |
| 天天基金 `rankhandler.aspx` | 基金收益率 | 日度 | Python 脚本抓取 → Supabase |
| 天天基金 `pingzhongdata` | 基金风险指标 | 日度 | Python 脚本抓取 → Supabase |
| tushare `yc_cb` | 国债收益率 | 日度 | 前端直连（token 存云数据库） |

---

## 五、技术实现细节

### 5.1 前端技术栈

- **框架**: Vue 3 (Composition API)
- **路由**: Vue Router 4 (HTML5 History Mode)
- **数据库**: @supabase/supabase-js (REST API)
- **图表**: ECharts 5.5
- **构建**: Vite 5.4
- **部署**: EdgeOne Pages

### 5.2 后端数据 pipeline

```
GitHub Actions (每日 17:30)
    ↓
1. fetch_risk_indicators.py (5并发，17分钟)
   → 抓取 20,000+ 只基金的风险指标
    ↓
2. fetch_return_all.py (35秒)
   → 抓取所有基金的成立以来收益率
    ↓
3. import_via_rest.py
   → 合并数据 → tcb CLI 分批导入 Supabase
    ↓
4. 完成（约 20 分钟）
```

### 5.3 关键代码示例

**Supabase 查询（带分页 + 排序 + 筛选）**：
```javascript
export async function fetchFundScores(params = {}) {
  const { t0, t1, search, kKey = 'k1', page = 1, pageSize = 100, sortAsc, sg } = params
  if (supabase) {
    let query = supabase.from('fund_scores').select('*', { count: 'exact' })
    if (t0) query = query.eq('t0', t0)
    if (t1) query = query.eq('t1', t1)
    if (search) query = query.or(`n.ilike.%${search}%,c.ilike.%${search}%`)
    if (sg === '1') query = query.eq('sg', 1)
    if (sg === '0') query = query.eq('sg', 0)
    const from = (page - 1) * pageSize
    const { data, count, error } = await query
      .order(kKey, { ascending: !!sortAsc, nullsFirst: false })
      .range(from, from + pageSize - 1)
    if (error) throw error
    return { data: data || [], count }
  }
  return { data: MOCK_FUNDS, count: MOCK_FUNDS.length }
}
```

---

## 六、当前问题与优化建议

### 6.1 性能优化

| 问题 | 影响 | 优化建议 | 优先级 |
|------|------|---------|--------|
| 首页加载慢（多个 API 并行） | 用户体验差 | 使用 Skeleton 骨架屏 + 分阶段加载 | 🔴 高 |
| 基金列表分页加载（100 条/页） | 滚动不流畅 | 改为虚拟滚动（vue-virtual-scroller） | 🟡 中 |
| 无客户端缓存 | 重复请求相同数据 | 使用 localStorage 缓存（10 分钟过期） | 🟡 中 |
| value500.com 数据抓取慢 | 首页加载阻塞 | 使用 Supabase Edge Function 代理（已部署但需验证） | 🔴 高 |
| ECharts 打包体积大 | 首屏加载慢 | 按需引入 ECharts 模块 | 🟡 中 |

### 6.2 功能完善

| 问题 | 影响 | 优化建议 | 优先级 |
|------|------|---------|--------|
| 申购状态筛选无效（sg 字段为空） | 功能不可用 | 从天天基金详情页抓取申购状态，批量更新 | 🔴 高 |
| 成立以来收益率数据不完整 | 数据不准确 | 定期运行 `fetch_return_all.py` | 🟡 中 |
| PE 历史数据不足（仅 20 天） | 百分位计算不准确 | 积累更多历史数据（≥250 个交易日） | 🟡 中 |
| 无用户登录系统 | 无法保存个人配置 | 接入 Supabase Auth | 🟢 低 |
| 无基金对比功能 | 用户体验单一 | 添加"加入对比"功能 | 🟢 低 |

### 6.3 代码质量

| 问题 | 影响 | 优化建议 | 优先级 |
|------|------|---------|--------|
| 无 TypeScript | 类型错误难发现 | 逐步迁移到 TypeScript | 🟡 中 |
| 无单元测试 | 代码质量难保证 | 使用 Vitest 编写单元测试 | 🟡 中 |
| CSS 散落各处 | 样式难维护 | 使用 CSS 变量 + 全局样式系统 | 🟡 中 |
| 无错误监控 | 线上问题难追踪 | 接入 Sentry 或腾讯 RUM | 🟡 中 |
| 无 SEO 优化 | 搜索引擎不收录 | 使用 SSR（Nuxt 3）或预渲染 | 🟢 低 |

### 6.4 数据更新

| 问题 | 影响 | 优化建议 | 优先级 |
|------|------|---------|--------|
| GitHub Actions 每日更新可能失败 | 数据过期 | 添加失败通知（企业微信/钉钉机器人） | 🔴 高 |
| 无数据更新日志 | 难以排查问题 | 在首页显示"数据更新时间" | 🟡 中 |
| 风险指标计算可能出错 | 靠谱分不准确 | 添加数据校验逻辑 | 🟡 中 |

### 6.5 用户体验

| 问题 | 影响 | 优化建议 | 优先级 |
|------|------|---------|--------|
| 无黑暗模式切换 | 用户体验单一 | 添加黑暗/明亮模式切换 | 🟢 低 |
| 无 PWA 支持 | 无法离线访问 | 添加 PWA 支持（Service Worker） | 🟡 中 |
| 无分享功能 | 难以传播 | 添加"分享到微信"功能 | 🟢 低 |
| 无多语言支持 | 仅支持中文 | 添加中英文切换 | 🟢 低 |

---

## 七、版本迭代建议（V2.0）

### 7.1 短期目标（1-2 周）

1. ✅ **修复申购状态筛选**：从天天基金详情页抓取申购状态，批量更新 `sg` 字段
2. ✅ **优化首页加载速度**：使用 Skeleton 骨架屏 + 分阶段加载
3. ✅ **添加数据更新时间显示**：在首页底部显示各数据源的更新时间
4. ✅ **GitHub Actions 失败通知**：接入企业微信机器人

### 7.2 中期目标（1-2 月）

1. ✅ **迁移到 TypeScript**：逐步将 JS 文件改为 TS
2. ✅ **添加单元测试**：使用 Vitest 编写核心计算函数的测试
3. ✅ **优化数据库查询**：为 `fund_scores` 表添加索引（t0, t1, k1, k2, ...）
4. ✅ **添加基金对比功能**：用户可以选择 2-4 只基金进行对比
5. ✅ **完善风险指标数据**：确保所有基金的回撤和夏普比率都有数据

### 7.3 长期目标（3-6 月）

1. ✅ **接入 Supabase Auth**：支持用户登录，保存个人配置
2. ✅ **添加 PWA 支持**：离线访问 + 推送通知
3. ✅ **SEO 优化**：使用 SSR 或预渲染
4. ✅ **多语言支持**：中英文切换
5. ✅ **接入 AI 模型**：使用 DeepSeek 提供智能投顾建议

---

## 八、部署与运维

### 8.1 部署流程

```bash
# 1. 构建
cd allfund && npm run build

# 2. 打包
cd dist && zip -r ../dist.zip . -x "*.DS_Store"

# 3. 部署到 EdgeOne Pages
cd .. && npx edgeone pages deploy dist.zip -n allfund -t 'TOKEN'
```

### 8.2 环境变量

```
VITE_SUPABASE_URL=https://tqhtegazxykkqfcpejky.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 8.3 监控与日志

- **前端错误监控**: 建议接入 Sentry 或腾讯 RUM
- **API 请求监控**: 使用 Supabase Dashboard 查看数据库请求
- **GitHub Actions 日志**: 查看每日数据更新是否成功

---

## 九、附录

### 9.1 相关文档

- [基金分类体系](./docs/fund-classification.md)
- [Supabase 数据库 schema](./supabase-schema.sql)
- [GitHub Actions workflow](../.github/workflows/update-fund-data.yml)

### 9.2 外部资源

- **腾讯 API 文档**: https://qt.gtimg.cn (实时行情)
- **value500.com**: https://value500.com (宏观数据)
- **蛋卷基金**: https://danjuanfunds.com (指数估值)
- **天天基金**: https://fund.eastmoney.com (基金数据)
- **Supabase 文档**: https://supabase.com/docs
- **EdgeOne Pages 文档**: https://www.tencentcloud.com/products/edgeone

### 9.3 联系方式

- **项目作者**: 大厨
- **项目地址**: https://allfund.edgeone.dev
- **GitHub 仓库**: (待补充)

---

**文档版本**: v1.0  
**最后更新**: 2026-06-07  
**下次更新**: 版本迭代完成后
