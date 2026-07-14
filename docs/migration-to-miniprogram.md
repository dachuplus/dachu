# allfund 迁移到「靠谱指数工具」微信小程序 · 方案文档

> 文档版本：v1.0（规划稿，待用户确认后实施）
> 编写角色：架构规划 agent（migration-agent）
> 适用项目：allfund H5（Vue 3 + Vite，部署于 EdgeOne Pages，数据存 Supabase 新加坡项目 `tqhtegazxykkqfcpejky`）
> 目标平台：微信小程序「靠谱指数工具」
> 文档性质：**仅方案，不写代码**。所有结论均基于对当前仓库 `src/`、`scripts/`、`supabase-schema.sql`、`.github/` 的实际盘点。

---

## 0. 结论速览（给决策人）

| 维度 | 结论 |
|------|------|
| 是否全量迁移 | **不建议一次性全量迁移**。建议「核心功能（评分/信号/组合）先迁 + H5 长期共存」的渐进路线。 |
| 技术选型 | **uni-app（Vue3 + Vite 模式）**。理由：allfund 是 Vue 3 + Composition API 代码，uni-app Vue3 模式可最大化复用组件/工具函数/数据层逻辑，且一套代码后续可同时发 H5/小程序/App。Taro 次之（也支持 Vue3，但生态与本项目更偏 React 心智）。原生小程序不推荐（重写成本最高，且本项目无 WXML 积累）。 |
| 数据层改造 | **必须引入 BFF（Supabase Edge Functions 扩展）**。微信小程序无法直连绝大多数第三方数据源（域名白名单 + 无 CORS），且当前 anon key 直接打进前端有泄露风险。所有读/写统一收敛到自己的 Supabase 域名。 |
| 图表方案 | ECharts（DOM/Canvas）→ **uCharts（@qiun/ucharts）**。小程序无 DOM，ECharts 需改用 canvas 引擎且体积极大，uCharts 是 uni-app/小程序事实标准。 |
| 工作量粗估 | MVP（3 核心模块）约 **12–16 人天**；完整对齐约 **28–36 人天**；小程序特有能力（订阅消息/分享裂变）约 **8–12 人天**。合计 **48–64 人天**。 |
| 成本变化 | 服务器：几乎不变（复用 Supabase + 现有 Edge Functions，仅新增少量 Edge Function 调用量）。**无需新增服务器/域名/备案**，因为请求全部走已备案的 Supabase 项目域名 + 现有 allfund.cn 域名。 |
| 最大风险 | ① 微信对「基金/投资建议」类内容的**类目资质与内容审核**；② 第三方行情数据在小程序内的合规获取；③ 现有 19,660 条基金的排序/分页查询在小程序首屏性能。 |

---

## 1. 现状盘点

### 1.1 功能模块清单（基于 `src/router/index.js` 全部路由）

| 路由 | 页面文件（行数） | 功能说明 | 关键能力 |
|------|----------------|----------|----------|
| `/` `/tools/fund-rank` | `pages/fund-rank/FundRankPage.vue` (1823) | **靠谱基金指数**：全市场 ~19,660 只公募基金按收益率/最大回撤/夏普综合排名。8 列网格 + 多维筛选（一级/二级分类、ETF/LOF、定开、规模区间、搜索）、服务端排序分页、细分品类排名 | 核心流量入口 |
| `/signal` | `pages/signal/SignalPage.vue` (1974) | **指标信号**：宏观指标（股债利差/FED/大类资产性价比/风格因子/行业估值），含标签页 `asset`/`factor`/`industry`、ECharts 图表、申万一级行业实时涨跌、上证叠加 | 数据可视化重区 |
| `/tools` | `pages/tools/ToolsPage.vue` (26) | **工具聚合页**：入口导航（评分/投顾/组合/数据中心） | 轻量 |
| `/tools/tougu` | `pages/tougu/TouguPage.vue` (339) | **投顾产品精选**：高收益/稳健/养老三类，对比近3月/1年收益与回撤 | 偏展示 |
| `/portfolio` | `pages/portfolio/PortfolioPage.vue` (1345) + 子面板 | **智能组合**：自建组合、DeepSeek AI 推荐（16 策略）、Kan&Zhou 增强型风险平价组合、AI 大 PK、回测、基金指数面板 | 最复杂模块 |
| `/fund/:code` | `pages/fund-detail/FundDetailPage.vue` (273) | **基金详情**：靠谱分构成、各周期收益与同类排名 | |
| `/watchlist` | `pages/watchlist/WatchlistPage.vue` (246) | **我的关注**（收藏列表） | 依赖 localStorage |
| `/compare` | `pages/compare/CompareToolPage.vue` (375) | **基金对比**：多只同维度对比 | |
| `/calc` | `pages/calc/SipCalcPage.vue` (348) | **定投计算器**：输入金额/期限估算本息 | ECharts 绘制曲线 |
| `/data-center` | `pages/data-center/DataCenterPage.vue` (992) | **数据中心**：字段说明 + 全表数据下载（**仅 owner 邮箱 `57502460@qq.com` 可下载**） | 含文件下载 |
| `/profile` | `pages/profile/ProfilePage.vue` (176) | **我的**：登录/注册、管理自选组合、查看历史 AI 组合推荐 | Supabase Auth + localStorage 兜底 |

> 重定向路由：`/config`→`/signal?tab=asset`、`/style-factor`→`/signal?tab=factor`、`/tools/industry-rank`→`/signal?tab=industry`，均合并进 SignalPage 标签页。

**导航结构（移动端 TabBar，`MobileTabBar.vue`）**：首页 / 信号 / 评分 / 智能组合 / 我的（5 个 tab）。PC 端另有 gov.uk 风格顶部导航 + 金刚区（指标信号/靠谱指数/智能组合 + owner 专属「数据下载」）。**小程序仅需保留 5 个 TabBar 的概念，PC 导航整体废弃。**

### 1.2 技术栈详情

| 类别 | 现状 | 说明 |
|------|------|------|
| 前端框架 | **Vue 3.4**（Composition API，`<script setup>`） | 与 uni-app Vue3 模式高度兼容 |
| 路由 | vue-router 4（`createWebHistory`） | 小程序需改为 `pages.json` + `uni.navigateTo` |
| 数据 SDK | `@supabase/supabase-js` 2.39 | 小程序内**不能直接用**（依赖浏览器 fetch/WebSocket/window），改走 REST |
| 图表 | **ECharts 5.5**（+ 自研 `echarts-setup`/`echarts-theme`） | 小程序改用 uCharts |
| 二维码 | `qrcode` | 分享海报用；小程序改用服务端生成或小程序码 |
| 音视频/媒体 | `@ffmpeg/ffmpeg` + `@ffmpeg/core`（`MediaTools.vue`） | 浏览器内转码，**小程序不可行**，建议砍掉 |
| 状态/UI | 无第三方 UI 库，自研 gov.uk 风格 CSS 变量体系 | 需重写为 rpx 单位 + 小程序组件 |
| 构建 | Vite 5 + `manualChunks`（vendor/supabase/echarts 分包） | uni-app 用其自带的 Vite 改造链 |
| 后端/代理 | Supabase **Edge Functions**（`value500`：抓取 value500.com、蛋卷估值，解决 CORS） | 小程序需大幅扩展此层 |
| CI/CD | **GitHub Actions**（`update-fund-data.yml`）每日 21:30（北京）跑 ETL + `vite build` + `edgeone pages deploy` | 小程序需改 `mp` 构建产物 + 上传 |
| 部署 | **EdgeOne Pages**（CLI token 部署 dist.zip） | 小程序改微信开发者工具上传 / CI 上传 |

### 1.3 数据层架构

**数据库：Supabase（PostgreSQL + PostgREST + RLS + Auth + Edge Functions）。**

**数据表清单（从 `supabase-schema.sql` + 代码引用 + `scripts/` 推断的实际生产表）：**

公开读（`anon` 可读，前端直读）：
1. `fund_scores`（~19,660 行，核心：代码/名称/分类 t0·t1_tt/收益 r0w~r5y/靠谱分 k0w·k1·k2·k3·k5·k_all·score_grade/回撤 dd*/夏普 sr*/规模/费率/基金经理）
2. `fund_combined`（脚本重建，组合派生评分来源）
3. `fund_quarterly_scores`（季度引擎评分，脚本刷新）
4. `tougu_products`（~103 行，投顾产品）
5. `config`（配置项，含 API Key 等，H5 直读 + 直写）
6. `index_pe_history`（指数 PE/PB 历史）
7. `fund_scores_meta`（数据元信息：更新时间/基金总数/评分数）
8. `fund_tags`（行业/概念标签）
9. `index_eva`（指数估值：PE/PB 百分位/ROE，蛋卷源）
10. `factor_scores`（Barra 六因子性价比评分）
11. `style_factors`（风格因子信号 stock/bond/commodity）
12. `jqr_indicators`（恐惧贪婪/市场温度/发行热度，自建复合算法）
13. `fund_tag_funds`（标签关联基金）
14. `fund_tag_perf`（主题板块各周期涨跌幅）
15. `etf_returns`（场内 ETF/LOF 区间收益）
16. `fund_indices`（基金指数，腾讯源）

用户私有（`authenticated` + RLS 仅本人）：
17. `user_profiles`（注册/登录信息，关联 `auth.users`）
18. `user_portfolios`（用户自建组合，JSONB `portfolio_data`）

**RLS 策略现状（`supabase-schema.sql`）：**
- `fund_scores`/`tougu_products`/`config`/`index_pe_history`/`fund_scores_meta`：开放 `anon` 读；`config` 甚至开放 `anon` 写（H5 前端直写，存在越权风险）。
- `user_profiles`/`user_portfolios`：仅 `auth.uid() = user_id` 可读写。

**前端 API 调用方式（`src/api/data.js`、`src/api/user-data.js`、`src/utils/api.js`）：**
- 基金评分/分类/品类排名：直接 `supabase.from('fund_scores').select(...)` 服务端排序分页。
- 品类排名采用「拉全量 k_all 内存二分」`getCategoryRankInfo`（已优化避免 N+1）。
- 第三方实时数据直连浏览器：腾讯 `qt.gtimg.cn`（无 CORS 限制）、东财 `push2.eastmoney.com`（支持 CORS）、value500/蛋卷走 Edge Function 代理后 `fetch`。

**ETL 脚本（`scripts/`，Python 为主）：**
- `update-fund-data.yml` 每日调度：天天基金 `rankhandler`/`pingzhongdata`/`lsjz`/`fundf10 jbgk` 拉全量 → 风险指标（回撤/夏普）→ 合并重算靠谱分 → 写入 `fund_scores_staging` → `promote_staging.py` 原子切换 + 重建 `fund_combined` → 校验 → 导出 xlsx → 计算 `jqr_indicators`/`fund_indices`/`etf_returns`/`fund_tag_perf`/`fund_tags` → `npm i && vite build` → EdgeOne 部署。
- 数据抓取还依赖 **akshare**（宏观/基金指数）、**东财 ZTJJ**（`GetBKListByBKTypeNew`/`GetBKDetailInfoNew`）、**新浪行业** API（降级）。

### 1.4 第三方服务依赖

| 服务 | 用途 | 小程序可行性 |
|------|------|--------------|
| **Supabase** | 数据库/Auth/Edge Functions | ✅ 核心，重构后继续用 |
| **EdgeOne Pages** | H5 部署 | ❌ 小程序用不上（仅 H5 共存时保留） |
| **GitHub Actions** | CI/CD + 每日 ETL | ✅ 保留（小程序的构建/上传步骤并入） |
| **腾讯行情 `qt.gtimg.cn`** | 指数实时行情/PE/PB | ⚠️ 小程序禁直连（域名白名单 + 无 ICP 自有域名），必须过代理 |
| **东财 `push2.eastmoney.com`** | 申万行业板块 | ⚠️ 同上，必须过代理 |
| **东财 ZTJJ** | 标签/板块涨跌幅（ETL 服务端） | ✅ 服务端脚本不受影响 |
| **新浪行业** | 行业数据降级源 | ⚠️ 同上，客户端需代理 |
| **value500.com** | 宏观基准（债/SHIBOR/M2/CPI/EP/PE300） | ✅ 已走 Edge Function，小程序继续走 |
| **蛋卷估值** | 指数估值 | ✅ 已走 Edge Function，小程序继续走 |
| **akshare** | 宏观/基金指数（ETL 服务端） | ✅ 服务端脚本不受影响 |
| **DeepSeek API** | AI 智能组合推荐 | ⚠️ key 在前端 `VITE_DEEPSEEK_API_KEY` 暴露，小程序务必改走服务端 |
| **火山方舟/阿里百炼/百度千帆/智谱/月之暗面** | AI 大 PK 真实模型自选 | ⚠️ 同上，必须改走 Edge Function，密钥不得进包 |

### 1.5 用户量级预估

- **基金数据规模**：`fund_scores` ~19,660 条（项目文档明确），`tougu_products` ~103 条。数据量中等，查询以"服务端排序+分页(range)"为主，单页 100 条。
- **用户规模**：项目处于 **BETA 阶段**，文档标注"目标用户：有经验的个人投资者"，且"数据中心下载"仅限单一 owner 邮箱，说明**尚未规模化运营**。仓库内**无埋点/统计代码**，无 DAU/MAU 数据可考证。
- **保守估算**：当前为早期验证期，日活大概率在**数百～低千级**；评分页为最高频入口，信号/组合次之。
- **结论**：用户量级对小程序后端压力不构成瓶颈；瓶颈在**首屏大表查询性能**与**微信审核**，而非并发。

---

## 2. 目标平台分析

### 2.1 微信小程序能力边界（vs H5 差异）

| 能力 | H5（现状） | 微信小程序 | 对 allfund 的影响 |
|------|-----------|------------|------------------|
| DOM / 浏览器 API | 完整 | ❌ 无 DOM、无 `document`/`window` | ECharts、Canvas 海报、`keep-alive`、SEO meta 全部失效或需改写 |
| 网络请求 | `fetch` 任意域 | 仅**已配置 request 合法域名**（需 HTTPS + ICP 备案） | 腾讯/东财/value500/蛋卷直连全部不可行 → 必须 BFF |
| CORS | 浏览器跨域限制 | 不适用（白名单机制） | 同上 |
| `localStorage` | 有 | ❌ 改用 `wx.setStorageSync`/`uni.setStorageSync` | 收藏/未登录组合直接迁移 |
| 分享 | `<meta og>` + 复制链接 | `onShareAppMessage`/`onShareTimeline` + 分享卡片图 | 分享能力反而**增强**（裂变） |
| 订阅消息 | ❌ | ✅ 模板消息（需用户授权） | 新增「评分更新/信号提醒」推送 |
| 登录 | Supabase Auth（邮箱/手机号） | 微信 `wx.login` 一键登录 | 登录体验升级，但需对接 Supabase 微信 Provider |
| 支付/会员 | 规划中（项目文档提及付费用户） | ✅ 微信支付 | 未来变现路径更顺 |
| 内容审核 | 无 | 金融类目**需资质** + 敏感词 | 最大合规风险点 |
| 包体积 | 无限制 | 主包 ≤2MB、总包 ≤20MB（分包） | ECharts 必须替换（体积极大），uCharts 更轻 |
| 实时行情刷新 | `setInterval` + fetch | `setInterval` + `uni.request` | 可行，但要节流（小程序有请求并发/频率约束） |

### 2.2 小程序技术选型对比

| 方案 | Vue3 兼容 | 复用现有代码 | 图表生态 | 学习成本 | 适合度 |
|------|----------|--------------|----------|----------|--------|
| **原生微信小程序** | ❌（WXML/WXSS/JS） | 几乎 0 复用，逻辑层（JS/算法）可搬 | wx-charts/uCharts 手工接 | 高（团队需学 WXML） | 中低 |
| **uni-app（Vue3 模式）** | ✅ 原生支持 | **高**：`.vue` + Composition API + `uni.request` 替换 `fetch`/`supabase`，组件/工具函数/数据算法大量复用 | `@qiun/ucharts` 官方适配 | 低（团队已会 Vue3） | **高（推荐）** |
| **Taro（Vue3 模式）** | ✅ 支持 | 中：React 心智为主，Vue3 支持但生态略弱于 uni-app | `taro-charts`/uCharts 需适配 | 中 | 中高 |
| **mpvue** | ❌（仅 Vue2） | 低且不维护 | — | — | ❌ 不推荐 |

### 2.3 推荐选型与理由

**推荐：uni-app（Vue3 + Vite 模式）。**

核心理由（紧扣 allfund 实际）：
1. **Vue 3 生态零割裂**：`FundRankPage`(1823 行)、`SignalPage`(1974 行)、`PortfolioPage`(1345 行) 均为 `<script setup>` Composition API，uni-app Vue3 模式可**直接搬运并编译到小程序**，逻辑层（排序/分页/品类排名算法 `getCategoryRankInfo`、靠谱分计算、收益格式化）几乎 1:1 复用。
2. **BFF 与 Supabase 解耦**：无论选哪种框架，数据都走 REST（见 §3），与框架无关；uni-app 的 `uni.request` 封装最简单。
3. **图表标准方案**：uCharts 在 uni-app 有官方组件 `@qiun/ucharts`，覆盖 allfund 现有所有图表（折线/柱状/散点/雷达），ECharts 配置可映射。
4. **一套代码多端**：后续可一键发 H5（保留现有 allfund.cn 用户）和 App，降低"H5 长期共存"的维护成本。
5. **分包支持**：`FundRankPage`/`SignalPage`/`PortfolioPage` 体积大，uni-app 分包机制直接解决 2MB 主包限制。

> 备选：若团队更熟悉 React 或未来要深度定制渲染，可选 **Taro Vue3**。但综合代码复用率，**uni-app 为最优**。

---

## 3. 数据层迁移方案

### 3.1 Supabase 在小程序中的调用方式

**结论：放弃 `@supabase/supabase-js` SDK，改用 PostgREST REST API 直连（经 BFF）。**

原因：
- SDK 依赖浏览器全局 `fetch`、WebSocket（realtime）、`window`/`localStorage`，在小程序运行时易报错且体量大。
- 小程序**只需要「读」**（排行榜/信号/详情/组合展示），realtime 可不要；写（登录/组合/收藏）量小，用 REST + Auth REST 端点即可。

调用路径（两层，见 §3.2 BFF）：

```
小程序 ──uni.request──> 自有 Supabase 域名（Edge Function / PostgREST）
```

- 读：`GET https://{project}.supabase.co/rest/v1/fund_scores?select=...&order=k_all.desc&limit=100`（等价于现有 `supabase.from(...).select(...)`）。
- 组合写：`POST /rest/v1/user_portfolios`，Header 带 Supabase JWT（由微信登录换取，见 §3.3）。
- 品类排名 `getCategoryRankInfo` 的"拉全量内存二分"逻辑**保留**，但改为调用 BFF 封装的 RPC/视图，避免小程序侧多次往返。

### 3.2 是否需要后端 BFF 层

**必须建 BFF。强烈建议扩展现有 Supabase Edge Functions。**

当前 H5 把 `VITE_SUPABASE_ANON_KEY`、多个 AI 厂商 Key（`DEEPSEEK`/`ARK`/`QWEN`/`WENXIN`/`ZHIPU`/`KIMI`）直接打进前端 bundle，任何人都可抓取——**已是安全债**。小程序更危险（包可被反编译）。

BFF 职责（新增/扩展 Edge Function，建议命名为 `mp-api` + 复用 `value500`）：

| 能力 | 实现 | 解决的小程序问题 |
|------|------|------------------|
| DB 读代理 | Edge Function 内用 **service_role** 查询，对小程序只暴露"只读视图" | ① 不向前端下发 anon key；② 隐藏表结构；③ 可做字段裁剪/限流 |
| 第三方行情/估值代理 | 扩展 `value500`：新增腾讯行情、东财行业、蛋卷估值的服务端抓取分支 | 小程序**只能请求已备案的 Supabase 域名**，第三方数据全部由服务端代抓 |
| AI 接口代理 | DeepSeek / 多模型 PK 改走 Edge Function，**密钥仅存服务端** | 杜绝密钥进包；同时可做风控/频控 |
| 写操作代理 | 组合/收藏/配置的写，由 Edge Function 校验 JWT 后用 service_role 写（避免 open anon 写 `config`） | 修复现有 `config` 开放 anon 写的越权隐患 |
| 海报/分享图生成 | 服务端用无头渲染或预生成 PNG 返回 URL | 替代浏览器 Canvas + FFmpeg（小程序不可行） |

> 域名白名单只需配置 1 个：`{project}.supabase.co`（已备案）。彻底规避"给腾讯/东财/value500/蛋卷逐个加白名单且多半被拒"的困境。

### 3.3 登录/用户体系迁移

| 现状（H5） | 小程序方案 |
|-----------|-----------|
| Supabase Auth 邮箱/手机号（`useAuth.js`，1 周会话，localStorage 标记） | 用微信 `wx.login` 拿 code → Edge Function 调 Supabase **微信 Provider**（`signInWithIdToken`/`exchange`）换 JWT；或自建 `code→JWT` 桥。 |
| 未登录：收藏/组合落 `localStorage` | 未登录：落 `wx.setStorageSync`（替换 `localStorage`，`useFavorites.js` 改 storage 适配层即可） |
| owner 校验：`email === OWNER_EMAIL` | 改为 `user_profiles.role` 字段或 Supabase Auth `app_metadata.role`，避免依赖邮箱字符串 |

**MVP 可先不做微信登录**：收藏/组合用小程序本地存储（对应现有 localStorage 兜底路径），等 Phase 3 再接微信登录做跨设备同步。

### 3.4 数据同步策略（ETL 是否需要改造）

**ETL（`scripts/` + GitHub Actions）几乎不用改**，因为它完全是**服务端 Python**，只与 Supabase REST/PostgREST 交互，与前端形态无关。

只需：
1. 在 `promote_staging.py` 之外，确保小程序 BFF 读的视图与 `fund_scores` 生产表一致（已是原子切换，天然一致）。
2. 新增数据库**视图/函数**供小程序高效查询（如 `v_fund_rank_with_category_rank`），把"品类排名"下推到 SQL，减少小程序侧分页拉全量。
3. `fund_scores_meta` 继续作为"数据更新时间戳"供小程序展示"数据截至 X 日"。
4. 每日 ETL 跑完后可**触发一次 Edge Function 预热缓存**（可选），降低首屏冷启动延迟。

### 3.5 缓存策略（小程序本地存储）

| 类型 | 方案 | 对应现状 |
|------|------|----------|
| 静态字典（分类树、标签列表） | `uni.setStorageSync` 缓存 24h | 现有 `fetchFundCategories`/`fetchFundTags` 用内存 `withCache`（60s~24h TTL）——迁移为本地存储 + 版本号 |
| 排行榜分页 | 不缓存（服务端排序分页，按需翻页） | 同 H5 行为 |
| 收藏/自建组合（未登录） | `wx.setStorageSync('af_favorites')` / `('allfund_portfolio')` | 直接替换 `useFavorites.js`/`user-data.js` 的 `localStorage` |
| 行情快照 | `uni.setStorageSync` 缓存 60s（避免频繁请求） | 对应 `withCache('indexQuotes', 60000)` |
| 用户组合（已登录） | 服务端为主，本地做乐观缓存 | `user_portfolios` 表 |

> 注意小程序 `setStorageSync` 有**单条 1MB、总 10MB** 上限；收藏/组合 JSON 远小于此，安全。行情快照缓存也应控制体积。

---

## 4. 功能迁移映射表

复杂度：低 = 直接复用/小幅改写；中 = 需重写 UI 或替换图表/网络层；高 = 架构级改造或依赖 BFF/登录。

| H5 功能 | 小程序实现方式 | 复杂度 | 备注 |
|---------|---------------|--------|------|
| 靠谱基金指数排行（FundRankPage） | uni-app 列表页 + 分页 + 筛选抽屉；数据走 BFF REST | 中 | 8 列网格→单列/两列卡片列表；排序分页逻辑复用；品类排名改 SQL 视图 |
| 指标信号（SignalPage） | 同结构 3 标签页；ECharts→uCharts；行情经 BFF | 高 | 图表最多（股债利差/FED/大类资产/因子/行业），uCharts 需逐图重写；实时行情走代理 |
| 工具聚合页（ToolsPage） | 简单导航页，可并入 TabBar 或首页入口 | 低 | 26 行，几乎纯导航 |
| 投顾产品精选（TouguPage） | 列表 + 分类 tab + 对比，数据走 BFF | 低-中 | 纯展示，改造量小 |
| 智能组合（PortfolioPage） | 自建组合（本地+登录）、风险平价（纯算法可复用） | 高 | AI 推荐/大 PK 的 DeepSeek 多模型必须改 BFF；回测面板图表→uCharts；FFmpeg 媒体能力砍掉 |
| AI 大 PK（AIPkPanel） | 改走 BFF 调多模型；结果页 uCharts | 高 | 6 个 AI Key 必须移出前端；966 行需较大改写 |
| 基金详情（FundDetailPage） | 详情页 + 评分构成图（uCharts） | 中 | 数据同 BFF；评分雷达/柱状改 uCharts |
| 我的关注（WatchlistPage） | 收藏列表，存储改 `wx.setStorageSync` | 低 | `useFavorites` 换存储适配层即可 |
| 基金对比（CompareToolPage） | 多只对比表 + 雷达图（uCharts） | 中 | 同数据层 |
| 定投计算器（SipCalcPage） | 表单 + 收益曲线（uCharts） | 低-中 | 计算逻辑纯前端可复用；图表换 uCharts |
| 数据中心（DataCenterPage） | **建议砍或降级** | 中 | 原含全表 xlsx 下载 + owner 校验；小程序不适合大文件下载，改为"字段说明 + 申请数据"或 H5 承载 |
| 我的（ProfilePage） | 登录/组合管理/历史 AI 推荐 | 中 | 微信登录 Phase 3 接入；未登录沿用本地存储 |
| 分享海报（useSharePoster） | 改服务端生成分享图 / 用 `onShareAppMessage` 卡片 | 中 | 浏览器 Canvas+FFmpeg 不可行；用 BFF 预生成 PNG 或小程序原生分享卡 |
| SEO meta 注入 | **直接删除** | 低 | 小程序无 SEO 概念 |
| PC gov.uk 顶部导航/金刚区 | **删除** | 低 | 小程序移动端单一布局 |
| keep-alive（FundRankPage 缓存） | 改 `pages.json` 预加载 / 本地缓存查询结果 | 低 | 小程序无组件级 keep-alive，用缓存替代 |

### 4.1 逐个模块处置结论

- **可直接迁移（低改）**：工具聚合页、投顾精选、我的关注、定投计算器（图表换库即可）。
- **需重构（中改）**：基金排行（网格→列表）、基金详情、基金对比、我的（登录层）、分享海报。
- **架构级改造（高改）**：指标信号（图表+实时行情）、智能组合 + AI 大 PK（AI 密钥+BFF）、数据中心。
- **小程序中无意义/建议砍掉**：
  - **数据中心大文件下载**（违反小程序文件下载体验，且金融数据批量导出有合规风险）→ 改为 H5 保留或"申请数据"入口。
  - **MediaTools 的 FFmpeg 视频/动图生成** → 小程序不可行，砍掉。
  - **SEO/Open Graph 分享卡** → 小程序无此概念。
  - **PC 端导航与响应式分支** → 小程序天然移动端，删除 769px 断点逻辑。

---

## 5. UI/UX 迁移要点

### 5.1 布局适配
- H5 的 **8 列网格**（`FundRankPage` 宽屏多列）在小程序改为**单列卡片列表 / 两列瀑布流**；筛选条件收进**底部弹出抽屉（popup）**，符合小程序交互习惯。
- 重建为 rpx 单位体系，替换现有 px + CSS 变量断点。
- 顶/底导航：H5 的 `MobileTabBar`（5 tab）直接映射为 `pages.json` 的 `tabBar`（首页/信号/评分/智能组合/我的），图标需补 81×81px 普通+选中两张图。

### 5.2 组件替换
| H5 | 小程序 |
|----|--------|
| ECharts 5.5（DOM canvas） | **@qiun/ucharts**（uCharts），逐图重写 option→uCharts 配置 |
| 浏览器 `<canvas>` + `qrcode` 海报 | 服务端生成分享图（BFF）或 `wx.canvas` 2D + 小程序码 |
| `document.createElement` 动态 DOM | 禁止；改用数据驱动 + `v-if`/`v-for` |
| `window.innerWidth` 响应式 | `uni.getSystemInfoSync()` 或 `uni.upx2px` |
| `localStorage` | `uni.setStorageSync` / `wx.setStorageSync` |

### 5.3 导航结构变化（TabBar 对应）
| H5 TabBar key | 小程序 tabBar | 页面 |
|---------------|---------------|------|
| home (`/`) | 首页 | `pages/fund-rank/index`（或独立首页聚合） |
| signal (`/signal`) | 信号 | `pages/signal/index` |
| fundrank (`/tools/fund-rank`) | 评分 | `pages/fund-rank/index` |
| portfolio (`/portfolio`) | 智能组合 | `pages/portfolio/index` |
| profile (`/profile`) | 我的 | `pages/profile/index` |

> 注意：H5 的首页和"评分"都指向 `FundRankPage`。小程序建议**合并为「评分」单一 tab**，首页改为轻量聚合（信号摘要 + 热门基金 + 入口），或干脆让"首页"=评分列表。推荐：**首页=评分排行**，砍掉独立空壳首页，减少一个 tab 认知负担（也可保留首页做内容聚合，视设计稿定）。

### 5.4 分享能力增强
- 替换 `<meta og>` 为 `onShareAppMessage`（转发给好友）+ `onShareTimeline`（分享到朋友圈）。
- 分享卡片图由 **BFF 预生成**（基金/信号关键图 + 小程序码），提升点击率。
- 利用**小程序码**（太阳码）做"基金详情→分享→好友扫码直达该基金"，形成裂变闭环（H5 做不到）。
- 关注/收藏引导分享，结合 Phase 3 订阅消息做召回。

---

## 6. 分阶段迁移路线图

> 工期为"1 名熟悉 Vue3 + 小程序的前端 + 复用现有后端"的人天估算，含联调与自测，不含微信审核等待时间。

### Phase 1：MVP 核心功能
- **范围**：基金靠谱指数排行（含筛选/分页/品类排名）、指标信号（核心图表）、基金详情、我的关注、工具聚合入口。
- **交付物**：
  - uni-app 工程脚手架（Vue3 模式）+ `pages.json` TabBar + 网络层（`uni.request`→BFF REST 封装）。
  - BFF 基础版（`mp-api` Edge Function）：基金排行/分类/详情/标签/元信息的只读代理。
  - uCharts 图表组件库（排行/信号所需图）。
  - 微信开发者工具可运行预览版。
- **验收标准**：小程序内可浏览评分排行、按分类/ETF 筛选、查看基金详情与品类排名、收藏基金；数据与 H5 一致（同一 Supabase 源）；首屏加载 < 2s（分页 100 条）。
- **工期**：**12–16 人天**。

### Phase 2：完整功能对齐
- **范围**：投顾产品精选、智能组合（自建+风险平价+回测）、基金对比、定投计算器、AI 推荐与 AI 大 PK（改 BFF 调 AI）、我的（组合管理）。
- **交付物**：
  - BFF 扩展：AI 代理（DeepSeek+多模型）、组合读写（JWT 校验）、行情/估值代理。
  - uCharts 全图表（组合回测曲线、PK 对比、定投曲线）。
  - 砍掉数据中心大文件下载与 FFmpeg 媒体（或 H5 承载）。
- **验收标准**：组合创建/保存/回测可用；AI 推荐与大 PK 结果正确且密钥不进包；对比/定投功能与 H5 等价；通过微信基础库兼容性测试（iOS/Android 多版本）。
- **工期**：**16–20 人天**。

### Phase 3：小程序特有能力
- **范围**：微信登录（Supabase 微信 Provider 打通）、订阅消息（评分更新/信号提醒模板）、分享裂变（卡片图+小程序码）、支付/会员雏形（如规划）。
- **交付物**：
  - 微信登录桥 + `user_profiles.role` 鉴权（替代邮箱字符串）。
  - 订阅消息触发（ETL 每日跑完调用 Edge Function 推送模板）。
  - 分享海报服务端生成 + 小程序码。
- **验收标准**：微信一键登录并跨设备同步组合/收藏；可订阅并在数据更新时收到提醒；分享卡片带小程序码并可回流；提交微信审核通过。
- **工期**：**8–12 人天**。

> **总工期：48–64 人天**（约 2.5–3 个月，按 1 人全职；可并行压缩）。

---

## 7. 风险与应对

### 7.1 技术风险
| 风险 | 应对 |
|------|------|
| **ECharts→uCharts 重写成本高、个别图（如复杂 dataZoom、组合回测）还原度低** | 提前做图表清单与 uCharts 能力比对；复杂图降级为简化交互或拆子图；必要时用 `wx-canvas` 桥接 echarts（体积大，仅个别页用分包） |
| **Supabase SDK 不能在小程序跑** | 已定方案：REST + BFF，不依赖 SDK |
| **首屏大表查询性能**（19,660 行排序分页 + 品类排名） | 品类排名下推 SQL 视图；分页 range 限制；BFF 加 Redis/内存缓存热门查询 |
| **小程序包体积**（ECharts 是体积元凶） | 换 uCharts；大页面分包；不引入重型 UI 库 |
| **实时行情刷新频率受限** | 行情走 BFF 且做 60s 缓存；用 `setInterval` 节流，避免触发小程序请求限频 |

### 7.2 数据风险（迁移期间一致性）
- H5 与小程序**共用同一 Supabase 源**，不存在"双写不一致"问题，天然一致。
- 过渡期若 H5 与小程序并存：仅前端展示层差异，数据原子切换（`promote_staging`）对两者同步生效。
- 用户数据（组合/收藏）：未登录态存本地，迁移到小程序时**无法自动继承 H5 的 localStorage**——需在 Phase 3 微信登录后用 `user_portfolios` 做跨端同步，并引导老用户重新登录导入。

### 7.3 运营风险（用户迁移成本）
- H5（allfund.cn）已有 SEO 流量与自然用户，**不建议关闭 H5**。
- 小程序获客依赖微信社交裂变，初期需"H5 引导跳转小程序"（H5 放小程序码/跳转按钮）。
- 老用户收藏/组合在本地，迁移需引导；提供"一键导入"或 Phase 3 登录同步。

### 7.4 合规风险（金融内容审核 —— 最高优先）
- 微信对**基金/股票/投资建议**类小程序有**类目资质要求**（通常需《经营证券期货业务许可证》或相关金融资质，或走"工具类-查询"类目并规避"荐股/收益承诺"表述）。
- `靠谱指数`、`AI 大 PK`、`AI 推荐组合`等表述易被判定为"投资建议/诱导"，**审核高风险**。
- 应对：
  1. 上线前做**内容合规审查**：所有"收益""推荐"措辞加"历史数据，不构成投资建议"免责声明（H5 已有 BETA 横幅，小程序需常驻）。
  2. 类目选择「工具类-金融数据查询」而非"投资咨询"；AI 推荐明确标注"模型输出，非投资建议"。
  3. `data-center` 批量导出、AI PK 的"收益 PK"排序等敏感功能谨慎暴露或仅登录可见。
  4. 预留**被拒重提**时间（审核 1–7 天，可能多轮）。
  5. 服务端（Edge Function）对输出内容做敏感词过滤兜底。

---

## 8. 成本估算

### 8.1 开发工时
| 阶段 | 人天 |
|------|------|
| Phase 1 MVP | 12–16 |
| Phase 2 完整对齐 | 16–20 |
| Phase 3 小程序特有能力 | 8–12 |
| **合计** | **48–64 人天** |

### 8.2 服务器 / 云资源变化
- **Supabase**：继续用现有新加坡项目，**无新增费用**（免费层或现有付费层足够；BFF 仅增加 Edge Function 调用量，量小可忽略）。
- **GitHub Actions**：继续用（ETL 不变 + 小程序构建上传），免费额度足够。
- **EdgeOne Pages**：仅 H5 共存时保留；小程序部署走微信平台，**不新增 EdgeOne 费用**。
- **无新增服务器/域名/备案**：所有小程序请求收敛到**已备案的 Supabase 项目域名** + 现有 `allfund.cn`。无需新购云主机或 ICP 备案。
- 唯一潜在费用：若 AI 调用量随小程序用户增长而上升，DeepSeek 等 API 按量计费（与 H5 同源，可共用配额）。

### 8.3 一次性成本
- 微信小程序**认证费 300 元/年**（企业主体，金融类目可能需额外资质审核，无直接费用但需材料）。
- 设计资源：TabBar 图标、分享卡片模版（可由现有品牌蓝 `#1d70b8` 衍生）。

---

## 9. 建议

### 9.1 全量迁移 vs 只迁核心功能
**建议：只迁核心功能 + H5 长期共存，而非全量迁移。**
- 数据中心大文件下载、FFmpeg 媒体生成、SEO 等在小程序无价值或不可行，应保留在 H5。
- allfund 本质是「数据工具」，H5 的 SEO 带来的自然流量对早期获客很重要，不应废弃。

### 9.2 H5 与小程序是否长期共存
**是，建议长期共存（双端同源数据）。**
- H5：承担 SEO 获客、大文件数据下载、PC 端深度使用。
- 小程序：承担高频日常查看、社交分享裂变、微信登录与订阅消息召回。
- 二者共用 Supabase，开发上用 uni-app 一套代码可同时出 H5 + 小程序，维护成本可控。

### 9.3 最优实施路径推荐
1. **先接 BFF（最关键前置）**：扩展 Supabase Edge Functions 出 `mp-api`，把 DB 读 + 第三方行情/估值 + AI 调用全部收敛，密钥不下发。这是所有阶段的基础。
2. **Phase 1 上线 MVP**（评分+信号+详情+关注），快速过审拿小程序壳，验证图表与性能。
3. **Phase 2 补齐组合/AI/对比/定投**，与 H5 功能拉平。
4. **Phase 3 做微信登录 + 订阅消息 + 分享裂变**，把小程序的独特价值（留存/裂变）释放出来。
5. **合规贯穿全程**：上线前完成金融类目资质确认与内容审查，预留审核缓冲期。

> 一句话：**uni-app（Vue3）搭前端 + Supabase Edge Functions 做 BFF + uCharts 替换图表 + 双端共存**，是最贴合 allfund 现有 Vue3 代码资产、风险可控、成本最低的迁移路径。

---

## 附录 A：迁移检查清单（实施时逐项核对）

- [ ] 新建 uni-app（Vue3 + Vite）工程，配置 `pages.json` TabBar（5 tab）
- [ ] 网络层：封装 `uni.request` 版 Supabase REST 客户端（替代 `supabase-js`）
- [ ] 新建/扩展 Edge Function `mp-api` + `value500`：DB 只读代理、行情/估值代理、AI 代理、写代理
- [ ] 数据库新增视图 `v_fund_rank_with_category_rank` 等，将品类排名下推 SQL
- [ ] `useFavorites`/`user-data` 的 `localStorage` → `uni.setStorageSync`
- [ ] ECharts 全部替换 @qiun/ucharts，逐图重写配置（SignalPage/AIPkPanel/Backtest/SipCalc/FundDetail/HotTags/JqrIndicator）
- [ ] 删除：PC 导航、SEO meta、FFmpeg/MediaTools、keep-alive、响应式 769px 分支
- [ ] 分享：`onShareAppMessage`/`onShareTimeline` + BFF 生成分享图 + 小程序码
- [ ] 微信登录桥（Supabase 微信 Provider）+ `user_profiles.role` 鉴权
- [ ] 订阅消息模板接入（ETL 完成后触发）
- [ ] 金融类目资质申请 + 内容合规审查 + 免责声明常驻
- [ ] GitHub Actions 增加小程序构建/上传步骤（保留 H5 部署步骤）
- [ ] 真机兼容性测试（iOS/Android 多微信版本）+ 首屏性能压测

## 附录 B：关键文件索引（现状，便于实施定位）

| 关注点 | 文件 |
|--------|------|
| 路由/导航 | `src/router/index.js`、`src/App.vue`、`src/components/MobileTabBar.vue` |
| 数据 API | `src/api/data.js`、`src/api/user-data.js`、`src/api/supabase.js`、`src/utils/api.js`、`src/utils/market-data.js`、`src/utils/cache.js` |
| 组合/鉴权 | `src/composables/useAuth.js`、`useFavorites.js`、`useSharePoster.js` |
| 图表 | `src/utils/echarts-setup.js`、`src/utils/echarts-theme.js`、`**/SignalPage.vue`、`**/AIPkPanel.vue`、`**/PortfolioBacktestPanel.vue`、`**/SipCalcPage.vue` |
| 后端代理 | `supabase/functions/value500/index.ts` |
| 数据库 Schema | `supabase-schema.sql` |
| ETL/CI | `scripts/*.py`、`scripts/daily_update_scores.sh`、`.github/workflows/update-fund-data.yml` |
| 部署配置 | `vite.config.js`、`.env.local`（密钥清单） |
