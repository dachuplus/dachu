<template>
  <div class="page-placeholder">
    <!-- 页面标题 -->
    <h1 class="page-title">管理</h1>

    <!-- 无访问权限提示（仅授权账户可见） -->
    <div class="no-access" v-if="!isOwner">
      <p class="no-access__title">无访问权限</p>
      <p class="no-access__desc">管理仅对授权账户开放，如需访问请使用授权账户登录。</p>
    </div>

    <template v-else>
    <p class="page-desc">大厨先生 数据库全部表一览。选择需要下载的数据表，点击下载 Excel 文件。数据每日 21:30（北京时间）自动更新。</p>

    <!-- 管理中心 header + tab 导航 -->
    <div class="mgmt-header">
      <h1 class="mgmt-title">管理</h1>
      <div class="mgmt-tabs">
        <button
          type="button"
          class="mgmt-tab"
          :class="{ 'mgmt-tab--active': activeTab === 'users' }"
          @click="activeTab = 'users'"
        >用户管理</button>
        <button
          type="button"
          class="mgmt-tab"
          :class="{ 'mgmt-tab--active': activeTab === 'download' }"
          @click="activeTab = 'download'"
        >数据下载</button>
      </div>
    </div>

    <!-- 更新简报 -->
    <div class="card" v-if="etlBriefReady" v-show="activeTab==='download'">
      <div class="card-title">更新简报</div>
      <!-- 多日汇总 -->
      <div class="brief-summary" v-if="etlDaySummaries.length > 0">
        <span class="ok">最近 {{ etlDaySummaries.length }} 天</span>
        <span class="sep">／</span>
        <span class="ok">完成 {{ totalSuccessDays }} 天</span>
        <span class="sep">／</span>
        <span :class="totalMissingDays > 0 ? 'warn' : 'muted'">未运行 {{ totalMissingDays }} 天</span>
        <span v-if="totalFailDays > 0">
          <span class="sep">／</span><span class="fail">失败 {{ totalFailDays }} 天</span>
        </span>
      </div>

      <!-- 按日期分组展示（可展开；用 etlDaySummaries 而非 etlLogs 控制显隐，确保无记录的天也以「未运行」展示） -->
      <table class="data-table etl-day-table" v-if="etlDaySummaries.length > 0">
        <thead>
          <tr>
            <th class="col-etl-date">日期</th>
            <th class="col-etl-step">步骤</th>
            <th class="col-etl-desc">说明</th>
            <th class="col-etl-status">状态</th>
            <th class="col-etl-rows">影响行数</th>
            <th class="col-etl-time">执行时间</th>
            <th class="col-etl-duration">耗时</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(dayGroup, dateKey) in etlLogByDate" :key="dateKey">
            <!-- 日期行 -->
            <tr class="date-row" @click="toggleDateExpand(dateKey)">
              <td class="col-etl-date" :colspan="dayExpanded[dateKey] ? 1 : 7">
                <span class="date-label">{{ formatDateLabel(dateKey) }}</span>
                <span class="date-summary" :class="getDayStatusClass(dayGroup)">
                  {{ getDaySummary(dayGroup) }}
                </span>
                <span v-if="!dayGroup || dayGroup.length === 0" class="date-missing-hint">· {{ getMissingReasonShort(dateKey) }}</span>
                <span class="date-toggle">{{ dayExpanded[dateKey] ? '收起 ▲' : '展开 ▼' }}</span>
              </td>
            </tr>
            <!-- 展开的步骤行 -->
            <template v-if="dayExpanded[dateKey]">
              <tr v-if="dayGroup.length === 0" class="etl-empty-row">
                <td :colspan="7">
                  <div class="missing-title">未更新成功</div>
                  <div class="missing-reason"><span class="reason-label">未更新成功原因：</span>{{ getMissingReason(dateKey) }}</div>
                </td>
              </tr>
              <tr v-for="(log, i) in dayGroup" :key="dateKey + '-' + i">
                <td class="col-etl-step">
                  <div class="step-name"><code>{{ log.step_name || log.name || log.step || '—' }}</code></div>
                  <div class="step-title">{{ stepView(log).title }}</div>
                  <div class="progress" :class="'pg-' + stepView(log).state">
                    <div class="progress-bar" :style="{ width: stepView(log).pct + '%' }"></div>
                  </div>
                </td>
                <td class="col-etl-desc">
                  <div class="step-desc">{{ stepView(log).desc }}</div>
                  <div class="step-reason" v-if="stepView(log).reason">
                    <span class="reason-label">失败原因：</span>{{ stepView(log).reason }}
                  </div>
                  <div class="step-suggestion" v-if="stepView(log).suggestion">
                    <span class="reason-label">解决建议：</span>{{ stepView(log).suggestion }}
                  </div>
                </td>
                <td class="col-etl-status">
                  <span class="status-badge" :class="badgeClass(log.status)">{{ statusLabel(log.status) }}</span>
                </td>
                <td class="col-etl-rows">{{ formatNum(log.rows_affected ?? log.rows ?? log.count) }}</td>
                <td class="col-etl-time">{{ fmtTime(log.start_time ?? log.created_at) }}</td>
                <td class="col-etl-duration">{{ log.duration_seconds != null ? formatDuration(log.duration_seconds) : '—' }}</td>
              </tr>
            </template>
          </template>
        </tbody>
      </table>
      <p class="section-desc" v-else>暂无运行记录，等待每日 21:30 自动执行。</p>
      <div class="brief-footer" v-if="etlLastRunTime">
        最近一次执行：{{ etlLastRunTime }}
      </div>
    </div>

    <!-- 项目简介 -->
    <div class="card" v-show="activeTab==='download'">
      <div class="card-title">项目简介 · 大厨先生</div>
      <p class="section-desc">本页面与整个 dachu 项目均托管于 GitHub，可依据本文档从零重新搭建网站。以下为项目全貌，供二次开发与部署参考。</p>
      <div class="intro-grid">
        <div class="intro-row">
          <div class="intro-key">项目功能</div>
          <div class="intro-val">
            基金「靠谱指数」量化评分（V7 算法：收益 50% + 回撤 25% + 夏普 25%）、热门基金行业/概念标签、AI 智能组合（DeepSeek / 百炼大模型选基）、资产 / 风格 / 宏观信号、基金组合回测、每日数据更新简报、全量数据库下载中心。
          </div>
        </div>
        <div class="intro-row">
          <div class="intro-key">技术栈 · 网站</div>
          <div class="intro-val">
            Vue 3 + Vite + Vue Router 4 + supabase-js；gov.uk 设计风格（品牌蓝 <code>#1d70b8</code>，无圆角 / 无阴影）；图表统一以表格呈现（不再依赖 ECharts）。构建产物经 EdgeOne Pages 部署上线。
          </div>
        </div>
        <div class="intro-row">
          <div class="intro-key">前端服务</div>
          <div class="intro-val">
            网站：EdgeOne Pages（海外节点部署）。直连 Supabase REST API 读取数据，无需自建后端应用服务器。
          </div>
        </div>
        <div class="intro-row">
          <div class="intro-key">后端 / 数据服务</div>
          <div class="intro-val">
            Supabase（PostgreSQL + PostgREST + 认证 + 存储 + Edge Functions）。数据 ETL 由 Python 脚本完成，经 GitHub Actions 每日 21:30（北京时间）自动运行：抓取东方财富 / 天天基金数据 → 计算评分 → 写入 Supabase。AI 选基接入 DeepSeek 与阿里百炼（豆包 / 智谱）大模型 API。
          </div>
        </div>
        <div class="intro-row">
          <div class="intro-key">数据库</div>
          <div class="intro-val">
            Supabase PostgreSQL。核心表：<code>fund_scores</code>（主表，约 2 万只基金 V7 评分）、<code>fund_tag_funds</code>（标签-基金映射）、<code>fund_tag_perf</code>（板块各周期涨跌 + 资金流）、<code>fund_tags</code>、<code>fund_combined</code>、<code>etl_run_log</code>、<code>user_ai_models</code>、<code>jqr_indicators</code>、<code>macro_history</code>、<code>tougu_products</code>、<code>user_profiles</code> 等。
          </div>
        </div>
        <div class="intro-row">
          <div class="intro-key">云服务</div>
          <div class="intro-val">
            Supabase（数据库 / 认证 / 函数）、EdgeOne Pages（静态托管 + 全球 CDN）、GitHub Actions（CI/CD 与定时数据流水线）、DeepSeek / 阿里百炼（AI 大模型）。
          </div>
        </div>
        <div class="intro-row">
          <div class="intro-key">GitHub 保存路径</div>
          <div class="intro-val">
            网站仓库：<code>github.com/dachuplus/dachu</code>。本地与远程仓库保持逐字节一致，推送使用受控脚本（非 git push 直推）。
          </div>
        </div>
        <div class="intro-row">
          <div class="intro-key">本地构建与部署</div>
          <div class="intro-val">
            网站：<code>cd dachu &amp;&amp; npm install &amp;&amp; npm run build</code> → <code>npx edgeone makers deploy dist.zip -n dachu -a overseas -t $EDGEONE_PAGES_API_TOKEN</code>。数据更新：<code>python3 scripts/sync_tag_performance.py</code> 等由 GitHub Actions 自动调度，详见仓库 <code>.github/workflows</code>。
          </div>
        </div>
      </div>
    </div>

    <!-- 用户权限管理（仅管理员可见） -->
    <div class="card" v-if="isOwner" v-show="activeTab==='users'">
      <div class="card-title">用户权限管理</div>
      <p class="section-desc">为注册用户开通功能：勾选需开通的功能后点击「保存」生效。未开通任何功能的用户登录后将显示「陌生人，无访问权限」。勾选「管理员」即授予该用户数据中心(管理)管理权限，可继续管理其他用户（主管理员账号固定不可改）。</p>

      <!-- 添加用户 -->
      <div class="perm-add">
        <input
          v-model.trim="newEmail"
          class="perm-email-input"
          type="email"
          placeholder="输入用户邮箱，如 user@example.com"
          @keyup.enter="addPermission"
        />
        <div class="perm-features">
          <label v-for="f in permFeatures" :key="f.key" class="perm-feature">
            <input type="checkbox" :value="f.key" v-model="newFeatures" /> {{ f.label }}
          </label>
        </div>
        <div class="perm-quick">
          <button type="button" class="btn-all" @click="newFeatures = FEATURES.map(f => f.key)">全部</button>
          <button type="button" class="btn-none" @click="newFeatures = []">全否</button>
        </div>
        <button class="btn-login" :disabled="permSaving || !newEmail" @click="addPermission">添加并保存</button>
      </div>

      <div v-if="permMsg" class="perm-msg" :class="permMsgType">{{ permMsg }}</div>

      <!-- 用户权限列表 -->
      <table class="data-table perm-table" v-if="permUsers.length > 0">
        <thead>
          <tr>
            <th class="col-perm-email">用户名</th>
            <th class="col-perm-features">开通功能</th>
            <th class="col-perm-granted">开通人</th>
            <th class="col-perm-pwd">密码状态</th>
            <th class="col-perm-action">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in permUsers" :key="row.user_email">
            <td class="col-perm-email">
              <span
                class="ua-name-link"
                role="button"
                tabindex="0"
                :title="row.user_email === adminEmail ? '管理员账户' : '点击查看用户详情'"
                @click="openUserDetail(row)"
                @keydown.enter="openUserDetail(row)"
              >{{ displayUsername(row.user_email) }}</span>
            </td>
            <td class="col-perm-features">
              <span v-if="row.user_email === adminEmail" class="perm-all">全部功能（主管理员）</span>
              <template v-else>
                <div class="perm-quick">
                  <button type="button" class="btn-all" @click="row._features = FEATURES.map(f => f.key)">全部</button>
                  <button type="button" class="btn-none" @click="row._features = []">全否</button>
                </div>
                <label v-for="f in permFeatures" :key="f.key" class="perm-feature">
                  <input type="checkbox" :value="f.key" v-model="row._features" /> {{ f.label }}
                </label>
              </template>
            </td>
            <td class="col-perm-granted">{{ row.granted_by || '—' }}</td>
            <td class="col-perm-pwd">
              <template v-if="passwordInfo[row.user_email]">
                <span class="pwd-tag" :class="passwordInfo[row.user_email].is_weak_password ? 'pwd-weak' : 'pwd-ok'">
                  {{ passwordInfo[row.user_email].is_weak_password ? '弱密码 123456' : '已自定义' }}
                </span>
                <div class="pwd-time">{{ passwordInfo[row.user_email].last_change ? fmtTime(passwordInfo[row.user_email].last_change) : '—' }}</div>
              </template>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="col-perm-action">
              <button class="btn-download" :disabled="row._saving" @click="saveRow(row)">保存</button>
              <button class="btn-reset" :disabled="row._saving || row.user_email === adminEmail" @click="resetPassword(row)">重置密码</button>
              <button class="btn-remove" :disabled="row._saving || row.user_email === adminEmail" @click="removeRow(row)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="section-desc" v-else>暂无用户权限记录。</p>
    </div>

    <!-- 权限申请（陌生人 → 管理员审批） -->
    <div class="card" v-show="activeTab==='users'">
      <div class="card-title">权限申请</div>
      <p class="section-desc">陌生人提交权限申请后在此审批。通过 将按所选功能写入用户权限；驳回 仅标记状态。</p>

      <div v-if="permReqLoading" class="section-desc">加载中…</div>
      <table class="data-table perm-req-table" v-else-if="requests.length > 0">
        <thead>
          <tr>
            <th class="col-req-email">用户邮箱</th>
            <th class="col-req-source">来源</th>
            <th class="col-req-name">真实姓名</th>
            <th class="col-req-phone">手机号</th>
            <th class="col-req-extra">补充信息</th>
            <th class="col-req-features">开通功能</th>
            <th class="col-req-status">状态</th>
            <th class="col-req-action">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in requests" :key="row.user_email">
            <td class="col-req-email"><code :title="row.user_email">{{ displayUsername(row.user_email) }}</code></td>
            <td class="col-req-source">
              <span class="source-badge" :class="row.source === 'mp' ? 'source-mp' : 'source-web'">{{ row.source === 'mp' ? '小程序' : '网页' }}</span>
            </td>
            <td class="col-req-name">{{ row.real_name || '—' }}</td>
            <td class="col-req-phone">{{ row.phone || '—' }}</td>
            <td class="col-req-extra">{{ row.extra || '—' }}</td>
            <td class="col-req-features">
              <label v-for="f in FEATURES" :key="f.key" class="perm-feature">
                <input type="checkbox" :value="f.key" v-model="row._features" :disabled="row._saving" /> {{ f.label }}
              </label>
            </td>
            <td class="col-req-status">
              <span
                class="status-badge"
                :class="row.status === 'pending' ? 'status-pending' : (row.status === 'approved' ? 'status-approved' : 'status-rejected')"
              >{{ row.status === 'pending' ? '待审批' : (row.status === 'approved' ? '已通过' : '已驳回') }}</span>
            </td>
            <td class="col-req-action">
              <template v-if="row.status === 'pending'">
                <button class="btn-download" :disabled="row._saving" @click="approveRequest(row, row._features)">通过</button>
                <button class="btn-remove" :disabled="row._saving" @click="rejectRequest(row)">驳回</button>
              </template>
              <span v-else class="text-muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="section-desc" v-else>暂无权限申请。</p>
    </div>

    <!-- 用户分析 -->
    <div class="card" v-if="userAnalyticsReady" v-show="activeTab==='users'">
      <div class="card-title">用户分析</div>
      <div class="analytics-summary">
        <div class="stat">
          <div class="stat-num">{{ activeNow }}</div>
          <div class="stat-label">当前在线活跃用户</div>
        </div>
        <div class="stat">
          <div class="stat-num">{{ activeToday }}</div>
          <div class="stat-label">当日累计活跃用户</div>
        </div>
        <div class="stat">
          <div class="stat-num">{{ visitorList.length }}</div>
          <div class="stat-label">活跃用户清单（去重）</div>
        </div>
      </div>
      <table class="data-table" v-if="visitorList.length > 0">
        <thead>
          <tr>
            <th class="col-ua-name">用户名</th>
            <th class="col-ua-ip">IP 地址</th>
            <th class="col-ua-region">地区</th>
            <th class="col-ua-pwd">密码</th>
            <th class="col-ua-firstvisit">首次访问时间</th>
            <th class="col-ua-duration">在线时间</th>
            <th class="col-ua-paths">访问路径</th>
            <th class="col-ua-action">用户操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(v, i) in visitorList" :key="i">
            <td class="col-ua-name">
              <span
                v-if="v.name !== '匿名访客'"
                class="ua-name-link"
                role="button"
                tabindex="0"
                @click="openUserPortfolios(v)"
                @keydown.enter="openUserPortfolios(v)"
              >{{ v.name }}</span>
              <code v-else>{{ v.name }}</code>
            </td>
            <td class="col-ua-ip">{{ v.ip }}</td>
            <td class="col-ua-region">{{ v.region || '—' }}</td>
            <td class="col-ua-pwd">
              <template v-if="v.email && v.email !== 'anonymous' && v.email !== 'authenticated' && passwordInfo[v.email]">
                <span class="pwd-tag" :class="passwordInfo[v.email].is_weak_password ? 'pwd-weak' : 'pwd-ok'">
                  {{ passwordInfo[v.email].is_weak_password ? '弱密码 123456' : '已自定义' }}
                </span>
                <div class="pwd-time">{{ passwordInfo[v.email].last_change ? fmtTime(passwordInfo[v.email].last_change) : '—' }}</div>
              </template>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="col-ua-firstvisit">{{ v.firstVisit ? fmtTime(v.firstVisit) : '—' }}</td>
            <td class="col-ua-duration">{{ v.durationMin > 0 ? v.durationMin + ' 分钟' : '—' }}</td>
            <td class="col-ua-paths">
              <span class="path-tag" v-for="(p, j) in v.paths" :key="j">{{ p }}</span>
            </td>
            <td class="col-ua-action">
              <template v-if="v.name !== '匿名访客'">
                <button class="btn-download ua-action-btn" type="button" :disabled="v.email === adminEmail" @click="kickUser(v)">踢出</button>
                <button class="btn-remove ua-action-btn" type="button" :disabled="v.email === adminEmail" @click="blockVisitor(v.email)">拉黑</button>
              </template>
              <span v-else class="text-muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="section-desc" v-else>今日暂无访问记录。</p>
    </div>

    <!-- 用户组合明细弹窗 -->
    <Teleport to="body">
      <div v-if="portfolioModal.open" class="ua-mask" @click.self="closePortfolioModal()">
        <div class="ua-modal" role="dialog" aria-modal="true" aria-label="用户组合明细">
          <div class="ua-modal__header">
            <span class="ua-modal__title">{{ portfolioModal.email }}</span>
            <button class="ua-modal__close" type="button" @click="closePortfolioModal()" aria-label="关闭">×</button>
          </div>

          <div v-if="portfolioModal.loading" class="ua-modal__loading">加载中…</div>

          <div v-else-if="portfolioModal.error" class="ua-modal__error">{{ portfolioModal.error }}</div>

          <div v-else class="ua-modal__body">
            <div class="ua-section">
              <div class="ua-section__title">自建组合（{{ portfolioModal.selfBuilt.length }}）</div>
              <ul v-if="portfolioModal.selfBuilt.length" class="ua-list">
                <li v-for="(p, i) in portfolioModal.selfBuilt" :key="'self-' + i" class="ua-item">
                  <span class="ua-item__name">{{ p.name }}</span>
                  <span class="ua-item__meta">{{ getFundCount(p) }} 只 · 更新 {{ fmtTime(p.updated_at) }}</span>
                </li>
              </ul>
              <p v-else class="ua-empty">暂无</p>
            </div>

            <div class="ua-section">
              <div class="ua-section__title">AI 生成组合（{{ portfolioModal.aiGenerated.length }}）</div>
              <ul v-if="portfolioModal.aiGenerated.length" class="ua-list">
                <li v-for="(p, i) in portfolioModal.aiGenerated" :key="'ai-' + i" class="ua-item">
                  <span class="ua-item__name">{{ p.name }}</span>
                  <span class="ua-item__meta">{{ getFundCount(p) }} 只 · 更新 {{ fmtTime(p.updated_at) }}</span>
                </li>
              </ul>
              <p v-else class="ua-empty">暂无</p>
            </div>
          </div>

          <div class="ua-modal__footer">
            <button class="btn-login" type="button" @click="closePortfolioModal()">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 用户详情弹窗（权限管理 → 点击用户名） -->
    <Teleport to="body">
      <div v-if="userDetailModal.open" class="ua-mask" @click.self="closeUserDetail()">
        <div class="ua-modal" role="dialog" aria-modal="true" aria-label="用户详情">
          <div class="ua-modal__header">
            <span class="ua-modal__title">{{ userDetailModal.email }}</span>
            <button class="ua-modal__close" type="button" @click="closeUserDetail()" aria-label="关闭">×</button>
          </div>

          <div v-if="userDetailModal.loading" class="ua-modal__loading">加载中…</div>

          <div v-else-if="userDetailModal.error" class="ua-modal__error">{{ userDetailModal.error }}</div>

          <div v-else class="ua-modal__body">
            <div class="ua-section">
              <div class="ua-section__title">基本信息</div>
              <ul class="ua-list ua-info">
                <li class="ua-item">
                  <span class="ua-item__name">注册时间</span>
                  <span class="ua-item__meta">{{ userDetailModal.registeredAt ? fmtTime(userDetailModal.registeredAt) : '—' }}</span>
                </li>
                <li class="ua-item">
                  <span class="ua-item__name">注册地区</span>
                  <span class="ua-item__meta">{{ userDetailModal.region || '—' }}</span>
                </li>
                <li class="ua-item">
                  <span class="ua-item__name">性别</span>
                  <span class="ua-item__meta">{{ userDetailModal.gender }}</span>
                </li>
                <li class="ua-item">
                  <span class="ua-item__name">年龄</span>
                  <span class="ua-item__meta">{{ userDetailModal.age }}</span>
                </li>
              </ul>
            </div>

            <div class="ua-section">
              <div class="ua-section__title">自建组合（{{ userDetailModal.portfolios.length }}）</div>
              <ul v-if="userDetailModal.portfolios.length" class="ua-list">
                <li v-for="(p, i) in userDetailModal.portfolios" :key="'pd-' + i" class="ua-item">
                  <span class="ua-item__name">{{ p.name }}</span>
                  <span class="ua-item__meta">{{ getFundCount(p) }} 只 · 更新 {{ fmtTime(p.updated_at) }}</span>
                </li>
              </ul>
              <p v-else class="ua-empty">暂无</p>
            </div>

            <p class="section-desc">注：性别、年龄未在注册流程中收集，故显示「未收集」；AI 组合仅保存在客户端，服务端不可见。</p>
          </div>

          <div class="ua-modal__footer">
            <button class="btn-login" type="button" @click="closeUserDetail()">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 未登录提示横幅 -->
    <div class="login-banner" v-if="!isLoggedIn">
      <div class="login-banner-text">
        <strong>注册并登录后可下载全部数据</strong>
        <span>大厨先生 数据库每日自动更新，登录后即可导出每张表的 Excel 文件。</span>
      </div>
      <button class="btn-login" @click="showLogin()">登录 / 注册</button>
    </div>

    <!-- 功能开放控制（仅主管理员可调） -->
    <div class="card" v-show="activeTab==='users'">
      <div class="card-title">功能开放控制</div>
      <p class="section-desc">
        全局开关：开启后对应功能对「已登录且已开通权限」的用户可见；「内容（博客）」开启时，任何人（含未注册访客）均可直接访问。
        仅主管理员 <strong>{{ adminEmail }}</strong> 可修改，其余授权账户仅可查看。
      </p>
      <div class="feature-flag-list">
        <div class="feature-flag-row" v-for="f in toggleableFeatures" :key="f.key">
          <div class="feature-flag-info">
            <div class="feature-flag-label">{{ f.label }}</div>
            <div class="feature-flag-desc">{{ f.desc }}</div>
          </div>
          <label class="switch" :class="{ 'switch--disabled': !isSuperAdmin }">
            <input
              type="checkbox"
              :checked="featureEnabled(f.key)"
              :disabled="!isSuperAdmin || savingFlag === f.key"
              @change="toggleFeature(f.key, $event.target.checked)"
            />
            <span class="switch__track"><span class="switch__thumb"></span></span>
            <span class="switch__state">{{ featureEnabled(f.key) ? '开放' : '关闭' }}</span>
          </label>
        </div>
      </div>
      <p v-if="!isSuperAdmin" class="feature-flag-readonly">
        当前账户 {{ user?.email }} 为授权管理员但非主管理员，功能开关为只读。如需调整请联系主管理员 {{ adminEmail }}。
      </p>
    </div>

    <!-- 数据库表列表 -->
    <div class="card" v-show="activeTab==='download'">
      <div class="card-title">数据库表 ({{ visibleTables.length }} 张)</div>
      <table class="data-table">
        <thead>
          <tr>
            <th class="col-name">表名</th>
            <th class="col-desc">说明</th>
            <th class="col-rows">行数</th>
            <th class="col-size">大小</th>
            <th class="col-action">下载</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in visibleTables" :key="t.key">
            <td class="col-name">
              <code>{{ t.key }}</code>
            </td>
            <td class="col-desc">{{ t.desc }}</td>
            <td class="col-rows">{{ formatNum(t.rows) }}</td>
            <td class="col-size">{{ formatSizeMB(t.size) }}</td>
            <td class="col-action">
              <a
                v-if="t.downloadable"
                :href="t.downloadUrl"
                class="btn-download"
                :download="t.key + '.xlsx'"
              >
                下载 Excel
              </a>
              <span v-else class="text-muted">请登录后下载</span>
            </td>
          </tr>
        </tbody>
      </table>
      
      <div class="table-footer">
        <p class="update-time" v-if="updateTime">
          数据更新时间：{{ updateTime }}
        </p>
      </div>
    </div>

    <!-- 评分方法论 -->
    <div class="card" v-show="activeTab==='download'">
      <div class="card-title">评分方法论 — V7 靠谱指数算法</div>
      <p class="section-desc">大厨先生 的"靠谱指数"（k_all）是对全市场基金进行量化评分的核心指标。以下详细说明从原始数据到最终评分的完整计算过程。</p>

      <!-- 第一步 -->
      <h2 class="method-step-title">第一步：原始数据采集</h2>
      <p>评分系统使用两类原始数据，分别来自不同的天天基金 API：</p>
      <table class="field-table">
        <thead><tr><th>数据类别</th><th>数据来源</th><th>字段</th><th>说明</th></tr></thead>
        <tbody>
          <tr>
            <td><strong>阶段收益率</strong></td>
            <td><code>FundGuideapi</code></td>
            <td>r0w / r1m / r3m / r6m / r1y / r2y / r3y / r5y</td>
            <td>天天基金直接返回的百分比收益率（如 12.35 表示 +12.35%），无需自行计算</td>
          </tr>
          <tr>
            <td><strong>风险指标</strong></td>
            <td><code>pingzhongdata</code></td>
            <td>dd1y~dd5y（最大回撤%）<br>sr1y~sr5y（夏普比率）</td>
            <td>从每日净值历史计算得出。回撤为负数（如 -15.23 表示最大回撤 15.23%），夏普为原始数值</td>
          </tr>
          <tr>
            <td><strong>风险指标补充</strong></td>
            <td><code>tsdata</code> (HTML 页面)</td>
            <td>sr1y~sr3y（夏普比率）<br>stddev1y~stddev3y（标准差）</td>
            <td>天天基金预计算的风险指标，补充 pingzhongdata 未覆盖的基金（如部分可转债/二级债基），优先级低于 pingzhongdata</td>
          </tr>
          <tr>
            <td><strong>货币基金收益率</strong></td>
            <td><code>rankhandler</code> (POST)</td>
            <td>f[9]=YTD / f[10]=近1年 / f[12]=近3年</td>
            <td>货币型基金使用独立的 rankhandler API（字段布局与 FundGuideapi 不同）</td>
          </tr>
        </tbody>
      </table>

      <!-- 第二步 -->
      <h2 class="method-step-title">第二步：单周期评分计算（k0w / k1m / k3m / k6m / k1 / k2 / k3 / k5）</h2>
      <p>将全市场每只基金的各项指标分别进行<strong>百分位排名</strong>，换算为 0~100 的得分：</p>

      <div class="formula-box">
        <div class="formula-title">百分位排名公式</div>
        <div class="formula-body">
          <strong>percentile = (1 − rank / (N − 1)) × 100</strong>
        </div>
        <div class="formula-note">
          其中 rank 为降序排序后的位置（rank=0 表示最优，rank=N−1 表示最差），N 为全市场有效基金数量。<br>
          最优基金得分 100，最差基金得分 0。
        </div>
      </div>

      <h3 class="method-subtitle">2.1 短周期评分（k0w / k1m / k3m / k6m）— 仅收益维度</h3>
      <p>短周期（1周/1月/3月/6月）缺乏可靠的风险指标（dd/sr），仅使用收益率排名：</p>
      <div class="formula-box">
        <div class="formula-body">
          <strong>k<sub>short</sub> = ret_percentile</strong>
        </div>
      </div>
      <p>即：按该周期收益率（r0w / r1m / r3m / r6m）在全市场中降序排名，直接转换为 0~100 得分。</p>

      <h3 class="method-subtitle">2.2 长周期评分（k1 / k2 / k3 / k5）— 三维度加权（V7 算法）</h3>
      <p>长周期（1年/2年/3年/5年）同时考虑收益、风险和风险调整后收益三个维度：</p>
      <div class="formula-box">
        <div class="formula-title">V7 长周期评分公式</div>
        <div class="formula-body">
          <strong>k<sub>long</sub> = 50% × ret_percentile + 25% × dd_percentile + 25% × sr_percentile</strong>
        </div>
        <div class="formula-note">
          各维度独立在全市场排名，分别得到 0~100 的百分位得分，然后加权合成。
        </div>
      </div>

      <div class="dimension-grid">
        <div class="dimension-card">
          <div class="dim-header">收益率维度 (50%)</div>
          <div class="dim-detail">
            <strong>数据</strong>：该周期的阶段收益率（如 k1 用 r1y）<br>
            <strong>排序</strong>：收益率越高，排名越好（降序）<br>
            <strong>含义</strong>：衡量基金的绝对收益能力
          </div>
        </div>
        <div class="dimension-card">
          <div class="dim-header">最大回撤维度 (25%)</div>
          <div class="dim-detail">
            <strong>数据</strong>：pingzhongdata 返回的 dd1y~dd5y（负数）<br>
            <strong>排序</strong>：回撤负数越大（越接近 0），排名越好（降序）<br>
            <strong>含义</strong>：衡量基金的下行风险控制能力<br>
            <strong>公式</strong>：<code>dd_max = −max(peak − nav<sub>i</sub>) / peak × 100</code>
          </div>
        </div>
        <div class="dimension-card">
          <div class="dim-header">夏普比率维度 (25%)</div>
          <div class="dim-detail">
            <strong>数据</strong>：pingzhongdata 返回的 sr1y~sr5y<br>
            <strong>排序</strong>：夏普比率越高，排名越好（降序）<br>
            <strong>含义</strong>：衡量基金的风险调整后收益（每单位风险获得的超额收益）<br>
            <strong>公式</strong>：<code>Sharpe = (E[R<sub>daily</sub>] − R<sub>f</sub>) / σ<sub>daily</sub> × √250</code><br>
            <strong>无风险利率</strong>：R<sub>f</sub> = 2%（年化），即每日 0.02/250 = 0.00008
          </div>
        </div>
      </div>

      <!-- 第三步 -->
      <h2 class="method-step-title">第三步：综合评分 k_all — 多周期加权汇总</h2>
      <p>将 8 个周期的评分按时间加权合成一个综合评分，近期的权重更大、远期的权重更小：</p>

      <div class="formula-box">
        <div class="formula-title">k_all 加权公式</div>
        <div class="formula-body">
          <strong>k_all = (k0w×5 + k1m×5 + k3m×10 + k6m×15 + k1×20 + k2×20 + k3×15 + k5×10) / total_weight</strong>
        </div>
        <div class="formula-note">
          仅对 k_i > 0（有有效数据）的周期参与加权。若某周期数据缺失，该周期排除，剩余权重按比例重新归一化。<br>
          权重总和 = 5+5+10+15+20+20+15+10 = 100（权重天然归一化）。
        </div>
      </div>

      <table class="field-table">
        <thead><tr><th>周期评分</th><th>对应收益</th><th>权重</th><th>组合维度</th><th>说明</th></tr></thead>
        <tbody>
          <tr><td><code>k0w</code></td><td>近1周 (r0w)</td><td style="text-align:center">5%</td><td>收益</td><td>超短线动量信号</td></tr>
          <tr><td><code>k1m</code></td><td>近1月 (r1m)</td><td style="text-align:center">5%</td><td>收益</td><td>短线动量信号</td></tr>
          <tr><td><code>k3m</code></td><td>近3月 (r3m)</td><td style="text-align:center">10%</td><td>收益</td><td>中线趋势</td></tr>
          <tr><td><code>k6m</code></td><td>近6月 (r6m)</td><td style="text-align:center">15%</td><td>收益</td><td>中长线趋势</td></tr>
          <tr><td><code>k1</code></td><td>近1年 (r1y)</td><td style="text-align:center"><strong>20%</strong></td><td>收益+回撤+夏普</td><td>核心长周期（权重最高）</td></tr>
          <tr><td><code>k2</code></td><td>近2年 (r2y)</td><td style="text-align:center"><strong>20%</strong></td><td>收益+回撤+夏普</td><td>核心长周期（权重最高）</td></tr>
          <tr><td><code>k3</code></td><td>近3年 (r3y)</td><td style="text-align:center">15%</td><td>收益+回撤+夏普</td><td>长周期稳定性</td></tr>
          <tr><td><code>k5</code></td><td>近5年 (r5y)</td><td style="text-align:center">10%</td><td>收益+回撤+夏普</td><td>超长周期稳定性</td></tr>
        </tbody>
      </table>

      <!-- 第四步 -->
      <h2 class="method-step-title">第四步：评级分类（score_grade）— 全市场百分位分级</h2>
      <p>将全市场所有有 k_all 的基金按得分从高到低排序，根据百分位分入四个等级：</p>

      <div class="formula-box">
        <div class="formula-title">百分位计算公式</div>
        <div class="formula-body">
          <strong>pct = (1 − rank / (N−1)) × 100</strong>
        </div>
      </div>

      <table class="field-table">
        <thead><tr><th>百分位范围</th><th>评级</th><th>标签</th><th>含义</th><th>全市场占比</th></tr></thead>
        <tbody>
          <tr><td>pct ≥ 80</td><td><span class="grade-badge grade-green">green</span></td><td style="color:#00703c;font-weight:700">优秀</td><td>全市场前 20%</td><td>约 3,865 只 (18.7%)</td></tr>
          <tr><td>50 ≤ pct &lt; 80</td><td><span class="grade-badge grade-blue">blue</span></td><td style="color:#1d70b8;font-weight:700">良好</td><td>全市场 20%~50%</td><td>约 5,798 只 (28.1%)</td></tr>
          <tr><td>0 &lt; pct &lt; 50</td><td><span class="grade-badge grade-orange">orange</span></td><td style="color:#d4351c;font-weight:700">一般</td><td>全市场后 50%</td><td>约 9,660 只 (46.8%)</td></tr>
          <tr><td>无 k_all</td><td><span class="grade-badge grade-gray">gray</span></td><td style="color:#6b7280;font-weight:700">无数据</td><td>数据不足无法评分</td><td>约 1,354 只 (6.5%)</td></tr>
        </tbody>
      </table>

      <!-- 第五步：完整数据流 -->
      <h2 class="method-step-title">完整数据流</h2>
      <div class="flow-diagram">
        <div class="flow-row">
          <div class="flow-node">FundGuideapi<br><small>阶段收益率</small></div>
          <div class="flow-arrow">→</div>
          <div class="flow-node">全市场<br>百分位排名</div>
          <div class="flow-arrow">→</div>
          <div class="flow-node">8 周期评分<br>k0w~k5</div>
          <div class="flow-arrow">→</div>
          <div class="flow-node">加权汇总<br>k_all</div>
          <div class="flow-arrow">→</div>
          <div class="flow-node">百分位分级<br>score_grade</div>
        </div>
        <div class="flow-row flow-row-aux">
          <div class="flow-node flow-node-aux">pingzhongdata<br><small>回撤(dd) + 夏普(sr)</small></div>
          <div class="flow-arrow flow-arrow-up">↗</div>
          <div class="flow-node flow-node-aux">tsdata<br><small>夏普(sr) 补充</small></div>
          <div class="flow-arrow flow-arrow-up">↗</div>
          <div style="width:80px"></div>
          <div style="width:80px"></div>
          <div style="width:80px"></div>
        </div>
      </div>

      <h2 class="method-step-title">算法版本演进</h2>
      <table class="field-table">
        <thead><tr><th>版本</th><th>公式</th><th>说明</th></tr></thead>
        <tbody>
          <tr><td><strong>V5</strong> (旧)</td><td>k = 60%×ret + 30%×dd + 10%×sr</td><td>偏重收益，已废弃</td></tr>
          <tr><td><strong>V7</strong> (当前)</td><td>k = 50%×ret + 25%×dd + 25%×sr</td><td>收益与风险平衡，当前生产使用</td></tr>
        </tbody>
      </table>
      <p class="api-note" style="margin-top:var(--space-md)">📐 用户可在"评分"页面自定义收益/回撤/夏普/卡玛/信息比率/跟踪误差的权重，实时计算个性化评分。</p>
    </div>

    <!-- API 接口文档 -->
    <div class="card" v-show="activeTab==='download'">
      <div class="card-title">数据接口文档</div>
      <p class="section-desc">以下是 本站 使用的所有外部数据接口，所有接口均来源于公开数据平台。</p>

      <!-- 天天基金 API -->
      <h2 class="api-group-title">一、天天基金 API</h2>

      <!-- rankhandler -->
      <div class="api-item">
        <h3 class="api-name">1. rankhandler — 基金排行接口</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://fund.eastmoney.com/data/rankhandler.aspx</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET（普通排行）/ POST（货币基金排行）</td></tr>
          <tr><td class="meta-label">用途</td><td>获取基金按指定指标排序的列表，支持普通基金和货币基金两种模式</td></tr>
        </table>
        <p class="api-subtitle">GET 请求参数（普通基金排行）</p>
        <table class="field-table">
          <thead><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>op</code></td><td>string</td><td>是</td><td>操作类型：<code>ph</code>（排行）</td></tr>
            <tr><td><code>dt</code></td><td>string</td><td>是</td><td>数据类型：<code>kf</code>（开放式基金）</td></tr>
            <tr><td><code>ft</code></td><td>string</td><td>否</td><td>基金类型：<code>all</code>（全部）/ <code>gp</code>（股票）/ <code>zq</code>（债券）/ <code>hh</code>（混合）/ <code>qdii</code> / <code>fof</code></td></tr>
            <tr><td><code>sc</code></td><td>string</td><td>否</td><td>排序指标：<code>1nzf</code>（近1年涨幅）/ <code>3nzf</code>（近3年涨幅）/ <code>6yzf</code>（近6月）/ <code>jnzf</code>（今年以来）/ <code>dm</code>（最大回撤）/ <code>rf</code>（日涨幅）</td></tr>
            <tr><td><code>st</code></td><td>string</td><td>否</td><td>排序方向：<code>desc</code>（降序）/ <code>asc</code>（升序）</td></tr>
            <tr><td><code>pi</code></td><td>int</td><td>否</td><td>页码（默认1）</td></tr>
            <tr><td><code>pn</code></td><td>int</td><td>否</td><td>每页条数（默认10）</td></tr>
            <tr><td><code>zf</code></td><td>string</td><td>否</td><td>固定 <code>diy</code></td></tr>
            <tr><td><code>rs</code></td><td>string</td><td>否</td><td>留空</td></tr>
            <tr><td><code>gs</code></td><td>string</td><td>否</td><td>固定 <code>0</code></td></tr>
          </tbody>
        </table>
        <p class="api-subtitle">POST 请求 Body 参数（货币基金排行）</p>
        <table class="field-table">
          <thead><tr><th>参数</th><th>类型</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>op</code></td><td>string</td><td>固定 <code>ph</code></td></tr>
            <tr><td><code>dt</code></td><td>string</td><td>固定 <code>hb</code></td></tr>
            <tr><td><code>ft</code></td><td>string</td><td>固定 <code>hb</code></td></tr>
            <tr><td><code>sc</code></td><td>string</td><td>排序指标：<code>1nzf</code>（近1年涨幅）/ <code>6yzf</code>（近6月）</td></tr>
            <tr><td><code>st</code></td><td>string</td><td><code>desc</code> / <code>asc</code></td></tr>
            <tr><td><code>pi</code></td><td>int</td><td>页码</td></tr>
            <tr><td><code>pn</code></td><td>int</td><td>每页条数（建议5000）</td></tr>
            <tr><td><code>rs</code></td><td>string</td><td>留空</td></tr>
            <tr><td><code>gs</code></td><td>string</td><td>固定 <code>0</code></td></tr>
            <tr><td><code>zf</code></td><td>string</td><td>固定 <code>diy</code></td></tr>
          </tbody>
        </table>
        <p class="api-subtitle">返回字段（datas 数组中每条数据用 | 分隔）</p>
        <table class="field-table">
          <thead><tr><th>索引</th><th>字段</th><th>说明</th><th>示例</th></tr></thead>
          <tbody>
            <tr><td>f[0]</td><td>基金代码</td><td>6位数字代码</td><td>000330</td></tr>
            <tr><td>f[1]</td><td>基金名称</td><td>完整名称</td><td>汇添富现金宝货币A</td></tr>
            <tr><td>f[2]</td><td>拼音简写</td><td>名称简拼</td><td>HTFXJBVOBA</td></tr>
            <tr><td>f[3]</td><td>基金类型</td><td>分类标签</td><td>货币型</td></tr>
            <tr><td>f[4]</td><td>万份收益</td><td>仅货币基金有值</td><td>0.2668</td></tr>
            <tr><td>f[5]</td><td>七日年化(%)</td><td>仅货币基金</td><td>0.911</td></tr>
            <tr><td>f[6]</td><td>近1周(%)</td><td>◀ 货币基金收益率从此开始</td><td>0.02</td></tr>
            <tr><td>f[7]</td><td>近1月(%)</td><td></td><td>0.08</td></tr>
            <tr><td>f[8]</td><td>近3月(%)</td><td></td><td>0.25</td></tr>
            <tr><td>f[9]</td><td>近6月/今年来(%)</td><td></td><td>0.51</td></tr>
            <tr><td>f[10]</td><td>近1年(%)</td><td></td><td>1.06</td></tr>
            <tr><td>f[11]</td><td>近2年(%)</td><td></td><td>2.48</td></tr>
            <tr><td>f[12]</td><td>近3年(%)</td><td></td><td>4.38</td></tr>
            <tr><td>f[13]</td><td>成立以来(%)</td><td></td><td>68.52</td></tr>
            <tr><td>f[14]</td><td>日期</td><td>净值日期</td><td>2025-06-27</td></tr>
            <tr><td>f[15]</td><td>净值/万份收益</td><td>数值</td><td>—</td></tr>
          </tbody>
        </table>
        <p class="api-subtitle">返回元数据</p>
        <table class="field-table">
          <thead><tr><th>字段</th><th>类型</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>allRecords</code></td><td>int</td><td>总记录数</td></tr>
            <tr><td><code>allPages</code></td><td>int</td><td>总页数</td></tr>
            <tr><td><code>datas</code></td><td>string[]</td><td>数据数组（每项为 | 分隔字符串）</td></tr>
            <tr><td><code>datacount</code></td><td>int</td><td>数据条数</td></tr>
          </tbody>
        </table>
        <p class="api-note">⚠️ 货币型基金（ft=hb）必须使用 POST 方式请求，与 FundGuideapi 不通用。</p>
      </div>

      <!-- FundGuideapi -->
      <div class="api-item">
        <h3 class="api-name">2. FundGuideapi — 基金分类/排行接口</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://fund.eastmoney.com/data/FundGuideapi.aspx</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">用途</td><td>按分类获取基金列表，支持5大类型（股票/债券/混合/QDII/FOF）的分类标签和基本收益数据</td></tr>
        </table>
        <p class="api-subtitle">请求参数</p>
        <table class="field-table">
          <thead><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>dt</code></td><td>string</td><td>是</td><td>固定 <code>0</code></td></tr>
            <tr><td><code>ft</code></td><td>string</td><td>是</td><td>基金类型：<code>gp</code>（股票型）/ <code>zq</code>（债券型）/ <code>hh</code>（混合型）/ <code>qdii</code> / <code>fof</code></td></tr>
            <tr><td><code>sc</code></td><td>string</td><td>否</td><td>排序指标：<code>3nzf</code>（近3年）/ <code>1nzf</code>（近1年）/ <code>6yzf</code>（近6月）/ <code>jnzf</code>（今年来）</td></tr>
            <tr><td><code>st</code></td><td>string</td><td>否</td><td>排序方向：<code>desc</code> / <code>asc</code></td></tr>
            <tr><td><code>pi</code></td><td>int</td><td>否</td><td>页码</td></tr>
            <tr><td><code>pn</code></td><td>int</td><td>否</td><td>每页条数（建议5000）</td></tr>
            <tr><td><code>sh</code></td><td>string</td><td>否</td><td>固定 <code>list</code>（列表模式，返回完整字段）</td></tr>
            <tr><td><code>zf</code></td><td>string</td><td>否</td><td>固定 <code>diy</code></td></tr>
            <tr><td><code>sd</code></td><td>string</td><td>否</td><td>起始日期</td></tr>
            <tr><td><code>ed</code></td><td>string</td><td>否</td><td>截止日期</td></tr>
          </tbody>
        </table>
        <p class="api-subtitle">返回字段（datas 数组中每条数据用 | 分隔）</p>
        <table class="field-table">
          <thead><tr><th>索引</th><th>字段</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td>f[0]</td><td>基金代码</td><td>6位数字代码</td></tr>
            <tr><td>f[1]</td><td>基金名称</td><td>完整名称</td></tr>
            <tr><td>f[2]</td><td>拼音简写</td><td>名称简拼</td></tr>
            <tr><td>f[3]</td><td>基金类型(t2)</td><td>完整分类标签，如"债券型-混合一级"、"混合型-偏股"</td></tr>
            <tr><td>f[4]</td><td>今年来(%)</td><td>YTD 收益率</td></tr>
            <tr><td>f[5]</td><td>近1周(%)</td><td></td></tr>
            <tr><td>f[6]</td><td>近1月(%)</td><td></td></tr>
            <tr><td>f[7]</td><td>近3月(%)</td><td></td></tr>
            <tr><td>f[8]</td><td>近6月(%)</td><td></td></tr>
            <tr><td>f[9]</td><td>近1年(%)</td><td></td></tr>
            <tr><td>f[10]</td><td>近2年(%)</td><td></td></tr>
            <tr><td>f[11]</td><td>近3年(%)</td><td></td></tr>
            <tr><td>f[12]</td><td>近5年(%)</td><td></td></tr>
            <tr><td>f[13]</td><td>成立以来(%)</td><td></td></tr>
            <tr><td>f[14]</td><td>手续费</td><td></td></tr>
            <tr><td>f[15]</td><td>净值日期</td><td>YYYY-MM-DD</td></tr>
            <tr><td>f[16]</td><td>单位净值</td><td></td></tr>
          </tbody>
        </table>
        <p class="api-note">⚠️ FundGuideapi 不支持货币型（ft=hb），货币基金需单独使用 rankhandler POST 方式拉取。</p>
      </div>

      <!-- pingzhongdata -->
      <div class="api-item">
        <h3 class="api-name">3. pingzhongdata — 基金净值/风险评级数据接口</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>http://fund.eastmoney.com/pingzhongdata/{基金代码}.js</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">用途</td><td>获取单只基金的历史净值趋势、累计净值、资产配置、基金经理信息、风险指标等</td></tr>
        </table>
        <p class="api-subtitle">返回的 JS 变量</p>
        <table class="field-table">
          <thead><tr><th>变量名</th><th>内容</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>Data_netWorthTrend</code></td><td>列表</td><td>每日净值趋势 [{x:date, y:netWorth, equityReturn, unitMoney}]</td></tr>
            <tr><td><code>Data_ACWorthTrend</code></td><td>列表</td><td>每日累计净值 [{x:date, y:[date,acWorth]}]</td></tr>
            <tr><td><code>Data_assetAllocation</code></td><td>列表</td><td>资产配置（净资产 = gpsz）</td></tr>
            <tr><td><code>Data_currentFundManager</code></td><td>列表</td><td>基金经理信息（姓名、任职日期）</td></tr>
            <tr><td><code>Data_buySedemption</code></td><td>列表</td><td>申购赎回状态</td></tr>
            <tr><td><code>Data_millionCopiesIncome</code></td><td>列表</td><td>万份收益（货币基金专用）</td></tr>
            <tr><td><code>Data_sevenDaysYearIncome</code></td><td>列表</td><td>七日年化（货币基金专用）</td></tr>
            <tr><td><code>Data_fluctuationScale</code></td><td>JSON</td><td>最大回撤（近1年/2年/3年/5年 dd1y/dd2y/dd3y/dd5y，负数%）</td></tr>
            <tr><td><code>Data_sharpeRatio</code></td><td>JSON</td><td>夏普比率（近1年/2年/3年/5年 sr1y/sr2y/sr3y/sr5y）</td></tr>
            <tr><td><code>Data_fundYear</code></td><td>JSON</td><td>年度收益率</td></tr>
            <tr><td><code>Data_quarter</code></td><td>JSON</td><td>季度涨跌幅</td></tr>
          </tbody>
        </table>
        <p class="api-note">⚠️ pingzhongdata 的最大回撤值（dd1y/dd2y等）是负数百分比（如 -15.23 表示最大回撤 15.23%），夏普比率（sr1y/sr2y等）是原始数值。</p>
      </div>

      <!-- F10 页面 -->
      <div class="api-item">
        <h3 class="api-name">4. fundf10 — 基金基本信息页面</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://fundf10.eastmoney.com/jbgk_{基金代码}.html</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">返回</td><td>HTML</td></tr>
          <tr><td class="meta-label">提取数据</td><td>基金经理(fund_manager)、管理人/公司名(company)、一级分类+二级分类(t0/t1)、净值规模(fund_scale)、份额规模(share_scale)、管理费率(manage_fee)、托管费率(custody_fee)、销售服务费率(sale_fee)、成立日期(found_date) — 通过正则表达式解析 HTML 表格</td></tr>
        </table>
      </div>

      <!-- tsdata -->
      <div class="api-item">
        <h3 class="api-name">5. tsdata — 基金特色数据页面（风险指标+风险等级）</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://fundf10.eastmoney.com/tsdata_{基金代码}.html</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">返回</td><td>HTML（服务端渲染，直接解析）</td></tr>
          <tr><td class="meta-label">用途</td><td>补充 pingzhongdata 未覆盖的基金风险指标，提供预计算的夏普比率和标准差</td></tr>
        </table>
        <p class="api-subtitle">提取数据</p>
        <table class="field-table">
          <thead><tr><th>数据项</th><th>字段</th><th>周期</th><th>说明</th></tr></thead>
          <tbody>
            <tr>
              <td><strong>夏普比率</strong></td>
              <td>sr1y / sr2y / sr3y</td>
              <td>近1年/近2年/近3年</td>
              <td>天天基金预计算的夏普比率，用于补充 pingzhongdata 缺失的基金（如部分可转债/二级债基）</td>
            </tr>
            <tr>
              <td><strong>标准差</strong></td>
              <td>stddev1y / stddev2y / stddev3y</td>
              <td>近1年/近2年/近3年</td>
              <td>反映基金收益率的波动程度，越小越稳定</td>
            </tr>
            <tr>
              <td><strong>风险等级</strong></td>
              <td>chooseLow CSS class</td>
              <td>全市场/同类</td>
              <td>低/中低/中/中高/高 五级分类</td>
            </tr>
          </tbody>
        </table>
        <p class="api-note">⚠️ tsdata 的夏普比率与 pingzhongdata 计算的夏普比率可能存在微小差异（计算窗口/无风险利率不同），优先使用 pingzhongdata，tsdata 仅作为补充数据源。</p>
      </div>

      <!-- 东财 ZTJJ GetBKDetailInfoNew -->
      <div class="api-item">
        <h3 class="api-name">6. GetBKDetailInfoNew — 主题板块(行业/概念)实时涨跌接口</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>http://api.fund.eastmoney.com/ztjj/GetBKDetailInfoNew</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET（JSONP，需 callback 参数）</td></tr>
          <tr><td class="meta-label">用途</td><td>获取单个主题板块（行业/概念）的各周期涨跌幅、区间排名、同类总数。热门基金「实时 / 近1周 / 近1月 / 近3月 / 近1年 / 今年来」排序即来源于此接口的<strong>板块级</strong>数据</td></tr>
          <tr><td class="meta-label">实时性</td><td><code>D</code>（日涨跌）为板块当日涨跌幅，<strong>盘中实时更新</strong>；其余周期字段（W/M/Q/Y/SY）为历史阶段涨跌幅，每日收盘更新（非实时）</td></tr>
        </table>
        <p class="api-subtitle">请求参数</p>
        <table class="field-table">
          <thead><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>callback</code></td><td>string</td><td>是</td><td>JSONP 回调名，固定 <code>cb</code>，返回 <code>cb({...})</code></td></tr>
            <tr><td><code>tp</code></td><td>string</td><td>是</td><td>板块指数代码，如 <code>BK000092</code>（中药）/ <code>BK000157</code>（航天装备）</td></tr>
          </tbody>
        </table>
        <p class="api-subtitle">返回字段（Data 对象，单位为 %）</p>
        <table class="field-table">
          <thead><tr><th>字段</th><th>含义</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>SEC_NAME</code></td><td>板块名称</td><td>如「中药」「航天装备」</td></tr>
            <tr><td><code>D</code></td><td>日涨跌(%)</td><td>当天涨跌幅，热门基金「实时」排序使用此值</td></tr>
            <tr><td><code>W</code></td><td>近1周(%)</td><td>热门基金「近1周」排序使用此值</td></tr>
            <tr><td><code>M</code></td><td>近1月(%)</td><td>热门基金「近1月」排序使用此值</td></tr>
            <tr><td><code>Q</code></td><td>近3月(%)</td><td>热门基金「近3月」排序使用此值</td></tr>
            <tr><td><code>Y</code></td><td>近1年(%)</td><td>热门基金「近1年」排序使用此值</td></tr>
            <tr><td><code>SY</code></td><td>今年以来(%)</td><td>热门基金「今年来」排序使用此值</td></tr>
            <tr><td><code>RANKW / RANKM / RANKQ / RANKY / RANKSY</code></td><td>各周期排名</td><td>板块在全部板块中的涨幅排名</td></tr>
            <tr><td><code>WSC</code></td><td>板块总数</td><td>参与排名的板块总数</td></tr>
          </tbody>
        </table>
        <p class="api-note">⚠️ 板块级数据（行业/概念整体涨跌）与「基金个体收益」不同：热门基金此前曾误用基金个体收益均值，已纠正为东财板块级接口的真实板块涨跌。<code>D</code> 为盘中实时数据，但本站存储与展示的 <code>fund_tag_perf</code> 表每日 21:30（北京）刷新，展示的是最近一个交易日收盘值，并非逐秒跳动行情。</p>
      </div>

      <!-- 东方财富 push2 -->
      <h2 class="api-group-title">二、东方财富行情 API</h2>
      <div class="api-item">
        <h3 class="api-name">7. push2 — 板块实时行情接口</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://push2.eastmoney.com/api/qt/clist/get</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">用途</td><td>获取申万行业板块实时数据（PE、涨跌幅、龙头股）</td></tr>
        </table>
        <p class="api-subtitle">请求参数</p>
        <table class="field-table">
          <thead><tr><th>参数</th><th>类型</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>pn</code></td><td>int</td><td>页码</td></tr>
            <tr><td><code>pz</code></td><td>int</td><td>每页条数</td></tr>
            <tr><td><code>fs</code></td><td>string</td><td>筛选条件：<code>m:90+t:2+f:!50</code>（申万一级行业）</td></tr>
            <tr><td><code>fields</code></td><td>string</td><td>返回字段：<code>f3,f12,f14,f24,f25,f128,f136</code>（涨跌幅/代码/名称/PE/PB等）</td></tr>
          </tbody>
        </table>
        <p class="api-subtitle">返回字段</p>
        <table class="field-table">
          <thead><tr><th>字段</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>f3</code></td><td>涨跌幅(%)</td></tr>
            <tr><td><code>f12</code></td><td>行业代码</td></tr>
            <tr><td><code>f14</code></td><td>行业名称</td></tr>
            <tr><td><code>f24</code></td><td>PE</td></tr>
            <tr><td><code>f25</code></td><td>PB</td></tr>
            <tr><td><code>f128</code></td><td>龙头股代码</td></tr>
            <tr><td><code>f136</code></td><td>龙头股名称</td></tr>
          </tbody>
        </table>
      </div>

      <!-- 腾讯行情 -->
      <h2 class="api-group-title">三、腾讯行情 API</h2>
      <div class="api-item">
        <h3 class="api-name">8. qt.gtimg.cn — 实时行情接口</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://qt.gtimg.cn/q={指数代码列表}</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">用途</td><td>获取主要指数实时行情，含 PE/PB/52周高低</td></tr>
        </table>
        <p class="api-subtitle">返回字段（用 ~ 分隔）</p>
        <table class="field-table">
          <thead><tr><th>索引</th><th>字段</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td>1</td><td>名称</td><td>指数名称</td></tr>
            <tr><td>2</td><td>代码</td><td>指数代码</td></tr>
            <tr><td>3</td><td>现价</td><td>当前点位</td></tr>
            <tr><td>4</td><td>昨收</td><td>昨日收盘</td></tr>
            <tr><td>5</td><td>开盘</td><td>今日开盘</td></tr>
            <tr><td>6</td><td>成交量</td><td></td></tr>
            <tr><td>7</td><td>成交额</td><td></td></tr>
            <tr><td>31</td><td>涨跌幅(%)</td><td></td></tr>
            <tr><td>32</td><td>涨跌额</td><td></td></tr>
            <tr><td>44</td><td>PE</td><td>市盈率</td></tr>
            <tr><td>46</td><td>PB</td><td>市净率</td></tr>
            <tr><td>47</td><td>52周最高</td><td></td></tr>
            <tr><td>48</td><td>52周最低</td><td></td></tr>
            <tr><td>50</td><td>更新时间</td><td></td></tr>
          </tbody>
        </table>
        <p class="api-subtitle">支持的指数代码</p>
        <div class="code-list">
          <code>sh000001</code> 上证指数 &nbsp;
          <code>sz399001</code> 深证成指 &nbsp;
          <code>sz399006</code> 创业板指 &nbsp;
          <code>sh000300</code> 沪深300 &nbsp;
          <code>sh000016</code> 上证50 &nbsp;
          <code>sh000688</code> 科创50 &nbsp;
          <code>sh000905</code> 中证500 &nbsp;
          <code>sz399673</code> 创业板50
        </div>
      </div>

      <!-- 蛋卷基金 -->
      <h2 class="api-group-title">四、蛋卷基金 API</h2>
      <div class="api-item">
        <h3 class="api-name">9. danjuanfunds — 指数估值接口</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://danjuanfunds.com/djapi/index_eva/dj</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">用途</td><td>获取全市场指数估值数据，含 PE/PB/股息率/ROE/PEG + 低估/适中/高估评级</td></tr>
        </table>
        <p class="api-subtitle">返回字段（data.items[]）</p>
        <table class="field-table">
          <thead><tr><th>字段</th><th>类型</th><th>说明</th></tr></thead>
          <tbody>
            <tr><td><code>name</code></td><td>string</td><td>指数名称</td></tr>
            <tr><td><code>index_code</code></td><td>string</td><td>指数代码</td></tr>
            <tr><td><code>ttype</code></td><td>string</td><td>指数类型：<code>big</code>（宽基）/ <code>industry</code>（行业）/ <code>theme</code>（主题）/ <code>abroad</code>（海外）</td></tr>
            <tr><td><code>pe</code></td><td>float</td><td>PE-TTM</td></tr>
            <tr><td><code>pe_percentile</code></td><td>float</td><td>PE 近10年历史分位（0~1）</td></tr>
            <tr><td><code>pb</code></td><td>float</td><td>PB</td></tr>
            <tr><td><code>pb_percentile</code></td><td>float</td><td>PB 近10年历史分位（0~1）</td></tr>
            <tr><td><code>yeild</code></td><td>float</td><td>股息率</td></tr>
            <tr><td><code>roe</code></td><td>float</td><td>ROE</td></tr>
            <tr><td><code>peg</code></td><td>float</td><td>PEG</td></tr>
            <tr><td><code>eva_type</code></td><td>string</td><td>估值评级：<code>valuation_low</code>（低估）/ <code>valuation_mid</code>（适中）/ <code>valuation_high</code>（高估）</td></tr>
            <tr><td><code>date</code></td><td>string</td><td>数据日期</td></tr>
          </tbody>
        </table>
      </div>

      <!-- macro-data -->
      <h2 class="api-group-title">五、macro-data 宏观数据（替代已失效的 value500.com）</h2>
      <div class="api-item">
        <h3 class="api-name">10. macro-data — 宏观指标聚合 Edge Function</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">方法</td><td>GET（服务端聚合多源，30 分钟缓存）</td></tr>
          <tr><td class="meta-label">用途</td><td>获取信号页 / 组合页所需的宏观基准（国债收益率、SHIBOR、M2、CPI、PMI、沪深300 估值）</td></tr>
          <tr><td class="meta-label">端点</td><td><code>https://{PROJECT_REF}.supabase.co/functions/v1/macro-data</code></td></tr>
          <tr><td class="meta-label">数据来源</td><td>东方财富（国债/SHIBOR/货币供应/PMI/沪深300 PE）+ 蛋卷基金估值中心，免鉴权、CORS 已开放</td></tr>
        </table>
        <p class="api-subtitle">聚合字段</p>
        <table class="field-table">
          <thead><tr><th>指标</th><th>来源</th><th>字段</th></tr></thead>
          <tbody>
            <tr><td>10Y 国债收益率</td><td>东方财富</td><td>bond.yield10y（小数）+ bond.spread（10Y-2Y 百分点）</td></tr>
            <tr><td>SHIBOR 隔夜</td><td>东方财富</td><td>shibor.on（小数）</td></tr>
            <tr><td>M2 同比</td><td>东方财富</td><td>m2.m2yoy（百分数）</td></tr>
            <tr><td>CPI 同比</td><td>东方财富</td><td>cpi.cpi（小数）</td></tr>
            <tr><td>PMI</td><td>东方财富</td><td>pmi.pmi</td></tr>
            <tr><td>沪深300 估值</td><td>蛋卷基金估值中心</td><td>pe300.pe / pe300.pePercentile（百分数）+ pe300.pb</td></tr>
          </tbody>
        </table>
      </div>

      <!-- akshare -->
      <h2 class="api-group-title">六、akshare 开源库</h2>
      <div class="api-item">
        <h3 class="api-name">11. akshare — 上证指数历史日线</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">方法</td><td><code>akshare.stock_zh_index_daily(symbol="sh000001")</code></td></tr>
          <tr><td class="meta-label">用途</td><td>获取上证指数历史日线数据（date, open, close, high, low, volume）</td></tr>
          <tr><td class="meta-label">使用文件</td><td><code>scripts/fetch_index_history.py</code></td></tr>
        </table>
        <p class="api-note">⚠️ akshare 是 Python 开源库，通过内部 HTTP 请求获取数据，不依赖单一 API 端点。</p>
      </div>

      <!-- Supabase -->
      <h2 class="api-group-title">七、Supabase 后端服务</h2>
      <div class="api-item">
        <h3 class="api-name">12. Supabase REST API + Management API + Edge Function</h3>
        <table class="field-table">
          <thead><tr><th>接口类型</th><th>URL</th><th>用途</th></tr></thead>
          <tbody>
            <tr><td>REST API</td><td><code>https://{PROJECT_REF}.supabase.co/rest/v1/{table}</code></td><td>前端/脚本读写数据库表</td></tr>
            <tr><td>Management API</td><td><code>https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query</code></td><td>Python 脚本执行 SQL（批量导入/更新/DDL）</td></tr>
            <tr><td>Edge Function</td><td><code>https://{PROJECT_REF}.supabase.co/functions/v1/macro-data</code></td><td>服务端聚合东财+蛋卷宏观数据，30 分钟 TTL 缓存（替代已失效的 value500）</td></tr>
            <tr><td>Edge Function</td><td><code>https://{PROJECT_REF}.supabase.co/functions/v1/wechat-login</code></td><td>微信登录代理：小程序(wx.login code)/网页(扫码 code) 经服务端用 AppSecret 换 openid，并签发 Supabase 会话；<code>POST { "type": "mp"|"web", "code": "..." }</code> 返回 <code>{ access_token, refresh_token, email }</code></td></tr>
          </tbody>
        </table>
      </div>

      <!-- 对接配置总览 -->
      <h2 class="api-group-title">对接配置总览（运维必读）</h2>
      <div class="api-item">
        <h3 class="api-name">小程序 / 后端 配置与密钥</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">微信小程序 AppID</td><td><code>wxac87803bace3ad2d</code></td></tr>
          <tr><td class="meta-label">Supabase 项目 ref</td><td><code>tqhtegazxykkqfcpejky</code></td></tr>
          <tr><td class="meta-label">Supabase URL</td><td><code>https://tqhtegazxykkqfcpejky.supabase.co</code></td></tr>
          <tr><td class="meta-label">主管理员</td><td><code>57****@qq.com</code></td></tr>
        </table>
        <p class="api-subtitle">密钥管理（由本地环境变量 / .env 维护，不在本页明文展示）</p>
        <table class="field-table">
          <thead><tr><th>密钥</th><th>用途</th><th>来源</th></tr></thead>
          <tbody>
            <tr><td>Supabase anon key</td><td>前端直连数据库（只读公开表）</td><td><code>.env.local</code> → VITE_SUPABASE_ANON_KEY</td></tr>
            <tr><td>Supabase PAT</td><td>Python 脚本执行 SQL / DDL</td><td><code>.env.local</code> → SUPABASE_PAT (sbp_...)</td></tr>
            <tr><td>EdgeOne Pages token</td><td>H5 部署</td><td><code>.env.local</code> → EDGEONE_PAGES_API_TOKEN</td></tr>
            <tr><td>GitHub PAT</td><td>源码推送</td><td><code>.env.local</code> → GITHUB_TOKEN</td></tr>
            <tr><td>DeepSeek API key</td><td>AI 选基 / 大 PK</td><td><code>.env</code> → VITE_DEEPSEEK_API_KEY</td></tr>
            <tr><td>微信小程序 AppSecret</td><td>小程序微信登录（jscode2session）</td><td>微信公众平台 → 开发 → 开发管理 → AppSecret（<code>supabase secrets set WECHAT_MP_APPSECRET</code>）</td></tr>
            <tr><td>微信开放平台 Web AppID / AppSecret</td><td>网页版微信扫码登录</td><td>微信开放平台 → 网站应用（<code>supabase secrets set WECHAT_WEB_APPID / WECHAT_WEB_APPSECRET</code>）</td></tr>
            <tr><td>微信登录 PEPPER</td><td>微信账号派生密码盐（不可泄露）</td><td><code>supabase secrets set WECHAT_PEPPER</code>（由主管理员生成保管）</td></tr>
          </tbody>
        </table>
        <p class="api-note">⚠️ 以上密钥仅存于本地 / CI 环境变量，禁止写入源码或公开仓库。完整密钥值由运维（主管理员）保管，AI 助手记忆中已留存，无需重复提供。</p>
        <p class="api-note">📅 <strong>令牌刷新记录（2026-07-24）</strong>：全部令牌已统一刷新为新令牌——EdgeOne Pages Token（1 年有效）、Supabase PAT、GitHub PAT。旧令牌均已吊销并删除，请勿再使用旧值，避免混淆。</p>
      </div>

      <!-- 东方财富 F10 基金档案 -->
      <h2 class="api-group-title">八、东方财富 F10 基金档案</h2>
      <div class="api-item">
        <h3 class="api-name">13. fundf10 — 资产配置(zcpz)</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">接口地址</td><td><code>https://fundf10.eastmoney.com/zcpz_{基金代码}.html</code>（代码去 .OF 后缀，如 zcpz_000001.html）</td></tr>
          <tr><td class="meta-label">方法</td><td>GET（解析页面内嵌 JS 变量 <code>var chartData</code>）</td></tr>
          <tr><td class="meta-label">用途</td><td>抓取基金最新报告期资产配置明细（股票/债券/现金占比）</td></tr>
          <tr><td class="meta-label">使用文件</td><td><code>scripts/fetch_fund_allocation.py</code></td></tr>
        </table>
        <p class="api-subtitle">返回字段（写入 fund_scores）</p>
        <table class="field-table">
          <thead><tr><th>字段</th><th>含义</th><th>单位</th></tr></thead>
          <tbody>
            <tr><td>stock_pct</td><td>股票占净值比例</td><td>%</td></tr>
            <tr><td>bond_pct</td><td>债券占净值比例</td><td>%</td></tr>
            <tr><td>cash_pct</td><td>现金占净值比例</td><td>%</td></tr>
          </tbody>
        </table>
      </div>

      <div class="api-item">
        <h3 class="api-name">14. fundf10 — 规模变动(gmbd)</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">接口地址</td><td><code>https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=gmbd&amp;code={基金代码}</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET（解析返回 JSONP 中的 <code>content</code> HTML 表格，取最新一行）</td></tr>
          <tr><td class="meta-label">用途</td><td>抓取基金最新报告期份额/净资产规模变动</td></tr>
          <tr><td class="meta-label">使用文件</td><td><code>scripts/fetch_fund_allocation.py</code></td></tr>
        </table>
        <p class="api-subtitle">返回字段（写入 fund_scores）</p>
        <table class="field-table">
          <thead><tr><th>字段</th><th>含义</th><th>单位</th></tr></thead>
          <tbody>
            <tr><td>sub_purchase</td><td>期间申购总份额</td><td>亿份</td></tr>
            <tr><td>sub_redemption</td><td>期间赎回总份额</td><td>亿份</td></tr>
            <tr><td>net_sub_share</td><td>期间净申购份额（=申购-赎回）</td><td>亿份</td></tr>
            <tr><td>total_share_end</td><td>期末总份额</td><td>亿份</td></tr>
            <tr><td>net_asset_end</td><td>期末净资产</td><td>亿元</td></tr>
            <tr><td>nav_change_rate</td><td>净资产变动率</td><td>%</td></tr>
          </tbody>
        </table>
      </div>

      <div class="api-item">
        <h3 class="api-name">15. fundf10 — 持有人结构(cyrjg)</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">接口地址</td><td><code>https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=cyrjg&amp;code={基金代码}</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET（解析返回 JSONP 中的 <code>content</code> HTML 表格，取最新一行）</td></tr>
          <tr><td class="meta-label">用途</td><td>抓取基金最新公告期持有人结构（机构/个人/内部持有比例）</td></tr>
          <tr><td class="meta-label">使用文件</td><td><code>scripts/fetch_fund_allocation.py</code></td></tr>
        </table>
        <p class="api-subtitle">返回字段（写入 fund_scores）</p>
        <table class="field-table">
          <thead><tr><th>字段</th><th>含义</th><th>单位</th></tr></thead>
          <tbody>
            <tr><td>inst_hold_pct</td><td>机构持有比例</td><td>%</td></tr>
            <tr><td>indiv_hold_pct</td><td>个人持有比例</td><td>%</td></tr>
            <tr><td>internal_hold_pct</td><td>内部持有比例（基金公司/高管/员工）</td><td>%</td></tr>
          </tbody>
        </table>
        <p class="api-note">⚠️ zcpz 页面需用<b>裸基金代码</b>（去掉 .OF）；gmbd/cyrjg 的 FundArchivesDatas 接口对带 .OF 后缀的代码兼容。三类数据按「接口拉取 → fund_scores_staging → fund_scores_test 验证 → fund_scores 生产」三级流水线入库，每日增量更新。</p>
      </div>

      <!-- 接口汇总 -->
      <h2 class="api-group-title">接口汇总</h2>
      <table class="field-table summary-table">
        <thead><tr><th>#</th><th>接口名称</th><th>用途</th><th>方法</th></tr></thead>
        <tbody>
          <tr><td>1</td><td>rankhandler API</td><td>基金排行（含货币型）</td><td>GET/POST</td></tr>
          <tr><td>2</td><td>FundGuideapi</td><td>基金分类 + 收益数据（5大类）</td><td>GET</td></tr>
          <tr><td>3</td><td>pingzhongdata</td><td>净值历史/回撤/夏普/风险评级</td><td>GET</td></tr>
          <tr><td>4</td><td>fundf10 (jbgk)</td><td>基金经理/管理人/分类/规模/费率/成立日期</td><td>GET</td></tr>
          <tr><td>5</td><td>fundf10 (tsdata)</td><td>夏普比率+标准差+风险等级（补充数据源）</td><td>GET</td></tr>
          <tr><td>6</td><td>GetBKDetailInfoNew (ZTJJ)</td><td>主题板块(行业/概念)各周期实时涨跌 + 排名</td><td>GET(JSONP)</td></tr>
          <tr><td>7</td><td>push2 API</td><td>申万行业板块实时行情</td><td>GET</td></tr>
          <tr><td>8</td><td>qt.gtimg.cn</td><td>指数实时行情</td><td>GET</td></tr>
          <tr><td>9</td><td>danjuanfunds</td><td>指数估值评级</td><td>GET</td></tr>
          <tr><td>10</td><td>macro-data Edge Function</td><td>宏观指标（国债/Shibor/M2/CPI/PMI/沪深300估值，多源聚合）</td><td>GET</td></tr>
          <tr><td>11</td><td>akshare</td><td>上证指数历史日线</td><td>库调用</td></tr>
          <tr><td>12</td><td>Supabase</td><td>数据库 + SQL + 代理函数</td><td>REST/SQL</td></tr>
          <tr><td>13</td><td>fundf10 (zcpz)</td><td>资产配置（股票/债券/现金占比）</td><td>GET</td></tr>
          <tr><td>14</td><td>fundf10 (gmbd)</td><td>规模变动（申购/赎回/净申购/期末份额/净资产/变动率）</td><td>GET</td></tr>
          <tr><td>15</td><td>fundf10 (cyrjg)</td><td>持有人结构（机构/个人/内部持有比例）</td><td>GET</td></tr>
        </tbody>
      </table>
    </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAuth, FEATURES, ADMIN_EMAIL } from '../../composables/useAuth'
import { confirm, toast } from '../../composables/useToast'
import { usePermissionRequests } from '../../composables/usePermissionRequests'
import { useFeatureFlags, TOGGLEABLE_FEATURES } from '../../composables/useFeatureFlags'

const { user, isLoggedIn, isOwner, showLogin, savePermissions, deletePermissions, blockUser } = useAuth()
const permFeatures = FEATURES
const adminEmail = ADMIN_EMAIL

// 功能开放控制：全局开关（仅主管理员 57502460@qq.com 可改）
const { featureEnabled, setFeatureFlag, loadFeatureFlags } = useFeatureFlags()
const toggleableFeatures = TOGGLEABLE_FEATURES
const isSuperAdmin = computed(() => user.value?.email === adminEmail)
const savingFlag = ref('')
async function toggleFeature(key, open) {
  if (!isSuperAdmin.value) return
  savingFlag.value = key
  try {
    await setFeatureFlag(key, open)
    toast(open ? `已开放「${key}」` : `已关闭「${key}」`, 'success')
  } catch (e) {
    toast('操作失败：' + (e?.message || '无权限'), 'error')
  } finally {
    savingFlag.value = ''
  }
}

// 管理中心 tab：'download' 数据下载 / 'users' 用户管理
const activeTab = ref('users')

// 权限申请（陌生人 → 管理员审批）
const { requests, loading: permReqLoading, loadRequests, approveRequest, rejectRequest } = usePermissionRequests()

const updateTime = ref('')
const tableData = ref({})

// 更新简报（ETL 运行记录）— 多日视图
const etlBriefReady = ref(false)
const etlLogs = ref([])
const etlLastRunTime = ref('')
const etlLogByDate = ref({})
const etlDaySummaries = ref([])
const dayExpanded = ref({})

const totalSuccessDays = computed(() => etlDaySummaries.value.filter(d => d.allOk).length)
const totalFailDays = computed(() => etlDaySummaries.value.filter(d => d.hasError).length)
const totalMissingDays = computed(() => etlDaySummaries.value.filter(d => d.missing).length)

// 用户分析（visitor_logs）
const userAnalyticsReady = ref(false)
const activeNow = ref(0)
const activeToday = ref(0)
const visitorList = ref([])

// 用户权限管理（user_permissions）
const permUsers = ref([])
const permLoading = ref(false)
const permSaving = ref(false)
const newEmail = ref('')
const newFeatures = ref([])
const permMsg = ref('')
const permMsgType = ref('')
function clearPermMsg() { permMsg.value = '' }

// 密码状态（来自 get_user_password_info RPC：是否弱密码123456 / 最后改密时间），按邮箱索引
const passwordInfo = ref({})
async function loadPasswordInfo() {
  if (!isOwner.value) return
  try {
    const { supabase } = await import('../../api/supabase.js')
    if (!supabase) return
    const { data, error } = await supabase.rpc('get_user_password_info')
    if (error) { console.warn('[perm] password info error', error); return }
    const map = {}
    ;(data || []).forEach(r => { map[r.user_email] = r })
    passwordInfo.value = map
  } catch (e) {
    console.warn('[perm] password info failed', e)
  }
}

// 用户组合明细弹窗（get_user_portfolios_by_email）
const portfolioModal = ref({
  open: false,
  email: '',
  loading: false,
  error: '',
  selfBuilt: [],
  aiGenerated: [],
})
function closePortfolioModal() {
  portfolioModal.value.open = false
}
function getFundCount(p) {
  const d = p && p.portfolio_data
  return Array.isArray(d) ? d.length : 0
}
async function openUserPortfolios(v) {
  if (!v || v.name === '匿名访客') return
  portfolioModal.value.open = true
  portfolioModal.value.email = v.name
  portfolioModal.value.loading = true
  portfolioModal.value.error = ''
  portfolioModal.value.selfBuilt = []
  portfolioModal.value.aiGenerated = []
  try {
    const { supabase } = await import('../../api/supabase.js')
    if (!supabase) {
      portfolioModal.value.error = '当前环境未连接数据库，无法查看组合明细'
      return
    }
    // 脱敏后访客邮箱不再入库，非邮箱格式的聚合项（如「已登录访客」）直接提示，不查组合
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.name || '')) {
      portfolioModal.value.error = '该访客信息已脱敏，无法查看组合明细'
      return
    }
    const { data, error } = await supabase.rpc('get_user_portfolios_by_email', { p_email: v.name })
    if (error) {
      // 非管理员无权限等情况：返回友好提示
      portfolioModal.value.error = '仅管理员可查看用户组合明细'
      return
    }
    const rows = Array.isArray(data) ? data : []
    portfolioModal.value.selfBuilt = rows.filter(r => !r.is_ai)
    portfolioModal.value.aiGenerated = rows.filter(r => r.is_ai)
  } catch (e) {
    portfolioModal.value.error = '仅管理员可查看用户组合明细'
  } finally {
    portfolioModal.value.loading = false
  }
}

// 用户详情弹窗（权限管理 → 点击用户名）：注册时间 / 注册地区(按 IP 分析) / 性别 / 年龄 / 组合信息
// 注：性别、年龄未在注册流程收集，如实标注「未收集」；AI 组合仅存于客户端 localStorage，服务端不可见。
const userDetailModal = ref({
  open: false,
  email: '',
  loading: false,
  error: '',
  registeredAt: '',
  region: '—',
  gender: '未收集',
  age: '未收集',
  portfolios: [],
})
function closeUserDetail() {
  userDetailModal.value.open = false
}
async function openUserDetail(row) {
  if (!row || !row.user_email) return
  userDetailModal.value.open = true
  userDetailModal.value.email = displayUsername(row.user_email)
  userDetailModal.value.loading = true
  userDetailModal.value.error = ''
  userDetailModal.value.registeredAt = row.created_at || ''
  userDetailModal.value.region = '—'
  userDetailModal.value.portfolios = []
  try {
    const { supabase } = await import('../../api/supabase.js')
    if (!supabase) {
      userDetailModal.value.error = '当前环境未连接数据库，无法查看用户详情'
      return
    }
    // 注册地区：取该用户 visitor_logs 中出现最频繁的地区（IP 解析所得，无独立注册地区字段）
    const { data: logs, error: eLog } = await supabase
      .from('visitor_logs')
      .select('region')
      .eq('email', row.user_email)
      .not('region', 'is', null)
      .limit(200)
    if (!eLog && logs && logs.length) {
      const freq = {}
      for (const l of logs) freq[l.region] = (freq[l.region] || 0) + 1
      const top = Object.entries(freq).sort((a, b) => b[1] - a[1])[0]
      userDetailModal.value.region = top ? (normalizeRegion(top[0]) || '—') : '—'
    }
    // 组合信息（仅自建组合可见；AI 组合存于客户端不可见）
    // 脱敏后访客邮箱不再入库，非邮箱格式（如「已登录访客」）跳过组合查询
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(row.user_email || '')) {
      userDetailModal.value.portfolios = []
    } else {
      const { data, error } = await supabase.rpc('get_user_portfolios_by_email', { p_email: row.user_email })
      if (error) {
        userDetailModal.value.error = '仅管理员可查看用户组合明细'
        return
      }
      const rows = Array.isArray(data) ? data : []
      userDetailModal.value.portfolios = rows.filter(r => !r.is_ai)
    }
  } catch (e) {
    userDetailModal.value.error = '仅管理员可查看用户组合明细'
  } finally {
    userDetailModal.value.loading = false
  }
}

// 表定义
const tables = [
  { key: 'fund_combined', name: '基金综合数据表', desc: '基金分类(t0/t1)、详情(公司/规模/费率)、收益(ytd~r5y)、风险(dd1y/sr1y)、评分(k_all/score_grade/k0w~k10) — 核心合并表，20,860条', rows: 20860 },
  { key: 'fund_scores', name: '基金评分表（完整版）', desc: '每日更新：基金代码/名称/基金经理/管理人/分类(一级+二级)/净值规模/份额规模/管理费率/托管费率/销售服务费率/成立日期 → 阶段收益(ytd~r10y/成立以来) → 阶段回撤(dd1y~dd5y) → 阶段夏普(sr1y~sr5y) → 基金评分(k0w~k_all/score_grade) → 资产配置(股票/债券/现金占比) → 规模变动(申购/赎回/净份额/总份额/净资产/变动率) → 持有人结构(机构/个人/内部持有比例)，58列完整数据', rows: 20860 },
  { key: 'fund_indices', name: '基金指数表（万得 Wind）', desc: '万得(Wind)基金指数：代码/名称/分类/类型 + 基本信息(发布日期/成分数量/加权方式/收益方式) + 市场表现(近1周~成立以来收益率) + 历年表现(年度收益) + 估值分析(总市值/流通市值/市盈率/净利率/股息率/Beta/波动率/换手率)，14条', rows: 14 },
  { key: 'fund_scores_test', name: '基金评分测试表', desc: 'fund_scores 的测试副本，结构与生产表一致。新抓取数据先写入此表验证无误后再导入生产环境', rows: 0 },
  { key: 'fund_quarterly_scores', name: '季度评分表', desc: '基于季报数据的各时间窗口评分（3m/6m/1y/2y/3y/5y/7y/10y）+ 原始季度数据JSON', rows: 18584 },
  { key: 'macro_history', name: '宏观历史数据表', desc: '中国10年国债(cn10y)、美国10年国债(us10y)、Shibor、CPI、M2历史数据，覆盖1996-至今', rows: 24109 },
  { key: 'tougu_products', name: '投顾产品表', desc: '天天基金/华宝/盈米/新浪仓石四来源基金投顾产品，含收益率、最大回撤、标签分类', rows: 103 },
  { key: 'fund_scores_meta', name: '评分元数据表', desc: '评分更新时间、基金总数、有评分数、净值日期等元信息', rows: 2 },
  { key: 'config', name: '配置表', desc: '全站配置项（键值对，含meta/timestamp）', rows: 3 },
  { key: 'index_pe_history', name: '指数PE历史表', desc: '沪深300等指数的PE/PB历史估值数据', rows: 0 },
  { key: 'site_stats', name: '站点统计表', desc: '网站访问量统计', rows: 1 },
  { key: 'user_portfolios', name: '用户组合表', desc: '用户自建智能组合（含portfolio_data JSON）', rows: 3, sensitive: true },
  { key: 'user_profiles', name: '用户档案表', desc: '用户注册信息', rows: 0, sensitive: true },
  { key: 'fund_tags', name: '热门标签表', desc: '热门基金标签（行业/概念），含标签名/类型/近1年板块收益/排序，来源东财 ZTJJ 接口', rows: 158 },
  { key: 'fund_tag_funds', name: '标签-基金映射表', desc: '每个热门标签关联的基金列表（代码/名称/类型/近1年收益/排序），来源东财 ZTJJ GetBKRelTopicFundNew 接口', rows: 1847 },
  { key: 'fund_tag_perf', name: '主题板块涨跌表', desc: '154个热门行业/概念板块的板块级涨跌幅：日涨跌(D)/近1周(W)/近1月(M)/近3月(Q)/近1年(Y)/今年来(SY) + 各周期排名 + 板块总数，来源东财 ZTJJ GetBKDetailInfoNew 接口（板块级真实涨跌，非基金个体均值），热门基金排序/阶段选择的数据基础', rows: 154 },
  { key: 'ai_pk_models', name: 'AI大PK 模型表', desc: 'AI 大PK 参赛模型信息（模型名/厂商/描述/状态）', rows: 0 },
  { key: 'ai_pk_picks', name: 'AI大PK 选基表', desc: '各 AI 模型每期选出的基金及权重（基于 fund_scores 真实数据）', rows: 0 },
  { key: 'factor_scores', name: '风格因子评分表（生产）', desc: '股票/债券/商品风格因子性价比评分（估值分/动量分/综合信号）', rows: 0 },
  { key: 'factor_scores_test', name: '风格因子评分测试表', desc: 'factor_scores 的测试副本，抓取数据先写入此表验证', rows: 0 },
  { key: 'style_factors', name: '风格因子明细表', desc: '风格因子原始明细数据（指数代码/名称/PE/PB/历史分位/收益）', rows: 0 },
  { key: 'jqr_indicators', name: '特色指标表（生产）', desc: '市场情绪特色指标（恐惧贪婪/估值温度计/新发基金/股债差/破净率/证券化率）', rows: 0 },
  { key: 'jqr_indicators_test', name: '特色指标测试表', desc: 'jqr_indicators 的测试副本，抓取数据先写入此表验证', rows: 0 },
  { key: 'etf_returns', name: 'ETF 收益率表', desc: 'ETF 各周期收益率数据（代码/名称/近1周~成立以来/规模）', rows: 0 },
  { key: 'fund_category_indices', name: '基金分类指数表', desc: '各基金分类对应的指数行情（分类名/指数代码/点位/各周期收益）', rows: 0 },
  { key: 'fund_scores_staging', name: '评分暂存表（staging）', desc: 'fund_scores 的 staging 暂存表，每日抓取先写入并经严格校验后原子切换到生产，通常为临时状态', rows: 0 },
  { key: 'stock_scores', name: '股票评分表（生产）', desc: '全市场股票多周期评分主表，由 fetch_stock_scores 抓取、promote_stock_scores 切到生产，股票 PK 选股数据基础', rows: 0 },
  { key: 'stock_scores_staging', name: '股票评分暂存表', desc: 'stock_scores 的 staging 暂存表，抓取先写入此表校验后再切到生产', rows: 0 },
  { key: 'stock_scores_test', name: '股票评分测试表', desc: 'stock_scores 的测试副本，结构与生产表一致', rows: 0 },
  { key: 'stock_pk_models', name: '股票PK模型表', desc: '股票 PK 参赛模型信息（模型名/厂商/描述/状态）', rows: 0 },
  { key: 'stock_pk_picks', name: '股票PK选股表', desc: '各模型每期选出的股票及权重（基于 stock_scores 真实数据）', rows: 0 },
]

const visibleTables = computed(() => {
  const idx = tableData.value || {}
  const idxKeys = Object.keys(idx)
  let base
  if (idxKeys.length > 0) {
    // 以 index.json（导出脚本产物）为准，自动包含所有已导出表（含后续新建表）
    base = idxKeys.slice().sort().map(key => {
      const meta = idx[key] || {}
      const local = tables.find(t => t.key === key) || {}
      return {
        key,
        name: meta.name || local.name || key,
        desc: meta.desc || local.desc || '',
        rows: meta.rows != null ? meta.rows : (local.rows ?? null),
        sensitive: meta.sensitive != null ? meta.sensitive : (local.sensitive || false),
        size: meta.size_mb != null ? meta.size_mb : null,
      }
    })
  } else {
    // 索引文件未加载时回退到内置表清单
    base = tables.map(t => ({ ...t, size: null }))
  }
  return base.map(t => ({
    ...t,
    downloadable: isLoggedIn.value,
    downloadUrl: `/downloads/${t.key}.xlsx`,
  }))
})

function formatNum(n) {
  if (n === 0) return '0'
  if (n == null) return '—'
  return n.toLocaleString('zh-CN')
}

function formatSizeMB(mb) {
  if (mb == null) return '—'
  if (mb === 0) return '0 MB'
  if (mb >= 1) return mb.toFixed(2) + ' MB'
  return (mb * 1024).toFixed(0) + ' KB'
}

// 简报状态标签文案
function statusLabel(s) {
  const m = {
    success: '成功', ok: '完成', done: '已完成',
    error: '失败', fail: '失败', failed: '失败',
    running: '运行中', pending: '等待',
    cancelled: '已取消', canceled: '已取消',
    skipped: '跳过',
  }
  return m[String(s || '').toLowerCase()] || (s || '—')
}

// 状态归一化（后端可能写 failed/ok/canceled 等别名，统一为展示用的规范值）
function normStatus(s) {
  const m = {
    success: 'success', ok: 'success', done: 'success',
    error: 'error', fail: 'error', failed: 'error',
    running: 'running', pending: 'pending',
    cancelled: 'cancelled', canceled: 'cancelled',
    skipped: 'skipped',
  }
  return m[String(s || '').toLowerCase()] || 'pending'
}

// 状态徽章样式类
function badgeClass(s) {
  const st = normStatus(s)
  if (st === 'success') return 'status-ok'
  if (st === 'error') return 'status-error'
  if (st === 'cancelled') return 'status-cancelled'
  if (st === 'running') return 'status-running'
  if (st === 'skipped') return 'status-skipped'
  return 'status-pending'
}
// 时间格式化
function fmtTime(v) {
  if (!v) return '—'
  try { return new Date(v).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) }
  catch { return String(v) }
}
// 耗时格式化（秒→可读）
function formatDuration(sec) {
  if (!sec) return '—'
  const n = Number(sec)
  if (isNaN(n)) return String(sec)
  if (n < 60) return Math.round(n) + 's'
  if (n < 3600) return Math.floor(n / 60) + 'm' + Math.round(n % 60) + 's'
  return Math.floor(n / 3600) + 'h' + Math.round((n % 3600) / 60) + 'm'
}

// ETL 步骤说明 + 进度/超时判定
const ETL_STEP_INFO = {
  fetch_return_all: { title: '基金收益数据', desc: '抓取全市场公募基金各周期收益率、回撤与夏普比率' },
  fetch_tsdata_risk: { title: '风险指标时序', desc: '抓取最大回撤、波动率等风险指标时序数据' },
  fetch_fund_basic_info: { title: '基金基础信息', desc: '抓取基金规模、费率、经理、成立日期等基础资料' },
  fetch_currency_funds: { title: '货币型基金', desc: '抓取货币型基金收益与规模数据' },
  fetch_risk_indicators: { title: '特色风险指标', desc: '抓取恐惧贪婪指数、估值温度计等市场情绪指标' },
  fetch_and_import_funds: { title: '基金列表导入', desc: '抓取基金列表与分类并导入评分库' },
  export_fund_details: { title: '导出数据文件', desc: '将最新数据导出为 Excel 并发布到数据下载中心' },
  fetch_stock_scores: { title: '股票评分抓取', desc: '抓取全市场股票多周期评分，写入 stock_scores 暂存/测试表' },
  promote_stock_scores: { title: '股票评分切换', desc: '校验并原子切换到 stock_scores 生产表，刷新 stock_pk_models / stock_pk_picks' },
  run_stock_pk_monthly: { title: '股票PK月度重选', desc: '每月自动重选股票 PK 组合（真实 LLM 选股或规则兜底）' },
  stock_pk: { title: '股票PK选股', desc: '生成当期股票 PK 推荐组合' },
  // —— 两条基金自动更新流水线（方案B）写入的简报步骤 ——
  '评分流水线 · 抓取基金数据': { title: '基金评分 · 抓取与评分', desc: '抓取全市场基金收益/风险指标，重算 V7 靠谱分写入 staging 临时表' },
  '评分流水线 · 评分切换(promote)': { title: '基金评分 · 原子切换生产', desc: '校验 staging 并原子切换到 fund_scores 生产表（守卫拦截则生产不变）' },
  '评分流水线 · 收尾(校验/导出)': { title: '基金评分 · 收尾校验导出', desc: '经理回填、数据校验、导出 Excel/全部表、特色指标与标签同步' },
  '评分流水线 · 前端部署': { title: '基金评分 · 前端部署', desc: '构建站点并部署 EdgeOne Pages（含 functions）' },
  '配置季度 · 资产配置分片': { title: '配置季度 · 资产配置分片', desc: '分片并行抓取资产配置/规模/持有人并直写生产 12 列（--to-prod）' },
  '配置季度 · 季度评分分片': { title: '配置季度 · 季度评分分片', desc: '分片并行刷新 fund_quarterly_scores 季度净值数据' },
  '配置季度 · 季度评分切换': { title: '配置季度 · 季度评分切换', desc: '读库统一重算横截面季度评分（--score-only）' },
  '配置季度 · 合并表重建': { title: '配置季度 · 合并表重建', desc: '基于最新季度评分重建 fund_combined 合并表' },
}
function stepInfo(name) {
  if (ETL_STEP_INFO[name]) return ETL_STEP_INFO[name]
  // 矩阵分片步骤名形如 "配置季度 · 资产配置分片 #3"，去掉 " #N" 后缀再查
  const base = String(name || '').split(' #')[0]
  if (ETL_STEP_INFO[base]) return ETL_STEP_INFO[base]
  return { title: name || '未知步骤', desc: 'ETL 数据处理步骤' }
}
const ETL_OVERTIME_MIN = 30
// 根据真实报错信息推断解决建议
function inferSuggestion(err, stepName) {
  const e = String(err || '').toLowerCase()
  if (!e) return '查看 ETL 运行日志定位错误，必要时手动重跑该步骤。'
  if (e.includes('rate') || e.includes('429') || e.includes('限流') || e.includes('too many')) {
    return '数据源（东财）触发限流，建议稍后重跑或降低并发请求频率。'
  }
  if (e.includes('timeout') || e.includes('timed out') || e.includes('超时') || e.includes('etimedout')) {
    return '请求超时，建议检查服务器到数据源 / Supabase 的网络连通性后重跑。'
  }
  if (e.includes('econnrefused') || e.includes('enotfound') || e.includes('connection') || e.includes('连接') || e.includes('refused')) {
    return '数据库连接失败，请检查 Supabase 连接串与网络，确认服务可达后重跑。'
  }
  if (e.includes('401') || e.includes('403') || e.includes('unauthorized') || e.includes('鉴权') || e.includes('token') || e.includes('forbidden') || e.includes('过期')) {
    return '接口鉴权失败，请检查 API Token / 密钥是否过期或被重置。'
  }
  if (e.includes('500') || e.includes('502') || e.includes('503') || e.includes('504') || e.includes('服务器') || e.includes('bad gateway') || e.includes('service unavailable')) {
    return '上游服务器异常，建议稍后重试该步骤。'
  }
  if (e.includes('empty') || e.includes('no data') || e.includes('null') || e.includes('空') || e.includes('无数据')) {
    return '数据源返回为空，可能当日数据尚未发布或接口字段变更，确认后重跑。'
  }
  return `查看 ETL 运行日志定位具体错误，必要时手动重跑该步骤（${stepName || '对应'}）。`
}
function stepView(log) {
  const info = stepInfo(log.step_name)
  const status = normStatus(log.status)
  let pct = 0, state = 'pending', reason = '', suggestion = ''
  const start = log.start_time ? new Date(log.start_time).getTime() : null
  const elapsedMin = start != null ? (Date.now() - start) / 60000 : null
  if (status === 'success') {
    pct = 100; state = 'ok'
  } else if (status === 'error') {
    pct = 100; state = 'error'
    reason = log.error_message || '执行失败，详见 ETL 运行日志'
    suggestion = inferSuggestion(log.error_message, log.step_name)
  } else if (status === 'cancelled') {
    pct = 100; state = 'error'
    reason = log.error_message || '任务被取消：可能因 GitHub Actions 超时（job 的 timeout-minutes 触发）或被手动取消。'
    suggestion = '若是超时：检查该步骤抓取量/并发是否过大、是否需要提高 timeout-minutes；若是被取消：确认是否有人手动取消了本次 run。可到 GitHub Actions 查看对应 run 日志。'
  } else if (status === 'skipped') {
    pct = 0; state = 'pending'
    reason = log.error_message || '该步骤被跳过（上游失败触发 fail-fast，或条件不满足）。'
    suggestion = '通常因同流水线前序步骤失败而跳过，请优先处理上游失败步骤。'
  } else if (status === 'running') {
    state = 'running'
    if (elapsedMin != null && elapsedMin > ETL_OVERTIME_MIN) {
      state = 'overtime'
      reason = `任务疑似超时：自 ${fmtTime(log.start_time)} 起已约 ${Math.round(elapsedMin)} 分钟仍未完成（单步通常几分钟内结束）。`
      suggestion = '常见原因：数据源限流(东财 push2)、网络超时、Supabase 连接中断或服务进程异常。建议重跑 ETL 或检查服务。'
    } else {
      pct = 100
    }
  } else {
    state = 'pending'; pct = 0
  }
  return { title: info.title, desc: info.desc, pct, state, reason, suggestion, status }
}

async function loadIndex() {
  try {
    const resp = await fetch('/downloads/index.json?' + Date.now())
    if (resp.ok) {
      const data = await resp.json()
      tableData.value = data.tables || {}
      updateTime.value = data.updated_at ? new Date(data.updated_at).toLocaleString('zh-CN') : ''
    }
  } catch (e) {
    console.log('加载索引文件失败，使用默认值')
  }
}

// 加载每日 ETL 运行简报（多日视图：固定最近 ETL_BRIEF_DAYS 天，按 run_date 分组；窗口内无记录的天标记为「未运行」）
const ETL_BRIEF_DAYS = 7
async function loadEtlBrief() {
  try {
    const { supabase } = await import('../../api/supabase.js')
    if (!supabase) { etlBriefReady.value = true; return }

    // 生成最近 N 天窗口（截止今天，含今天），格式 YYYY-MM-DD
    const today = new Date()
    const windowDates = []
    for (let i = ETL_BRIEF_DAYS - 1; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(today.getDate() - i)
      windowDates.push(dateKeyOf(d))
    }
    const windowStart = windowDates[0]

    // 取窗口内（含）的 ETL 记录，按 run_date 分组
    const { data: rows, error } = await supabase
      .from('etl_run_log')
      .select('*')
      .not('run_date', 'is', null)
      .gte('run_date', windowStart)
      .order('run_date', { ascending: false })
      .order('id', { ascending: true })

    if (error || !rows) {
      etlLogs.value = []
      etlBriefReady.value = true
      return
    }
    etlLogs.value = rows || []

    // 按 run_date 分组
    const grouped = {}
    for (const row of rows) {
      const d = row.run_date || 'unknown'
      if (!grouped[d]) grouped[d] = []
      grouped[d].push(row)
    }

    // 生成日期汇总 + 分组映射（含窗口内无记录的天，标记为「缺/未运行」）
    const summaries = []
    // etlLogByDate 按「最新→最旧」顺序渲染
    const byDateNewestFirst = {}
    for (let i = windowDates.length - 1; i >= 0; i--) {
      const d = windowDates[i]
      const logs = grouped[d] || []
      byDateNewestFirst[d] = logs
      if (logs.length === 0) {
        summaries.push({ date: d, total: 0, okCount: 0, errCount: 0, runCount: 0, allOk: false, hasError: false, hasRunning: false, missing: true })
      } else {
        const okCount = logs.filter((l) => l.status === 'success').length
        const errCount = logs.filter((l) => l.status === 'error').length
        const runCount = logs.filter((l) => l.status === 'running').length
        summaries.push({ date: d, total: logs.length, okCount, errCount, runCount,
          allOk: errCount === 0 && runCount === 0 && okCount > 0,
          hasError: errCount > 0, hasRunning: runCount > 0, missing: false })
      }
    }
    etlLogByDate.value = byDateNewestFirst
    etlDaySummaries.value = summaries

    // 默认展开最新一天（今天）
    const expandedInit = {}
    if (windowDates.length > 0) expandedInit[windowDates[windowDates.length - 1]] = true
    dayExpanded.value = expandedInit

    // 最近执行时间取窗口内最后一条的 created_at 或 start_time
    if (rows.length > 0) {
      const last = rows[rows.length - 1]
      etlLastRunTime.value = fmtTime(last.created_at || last.start_time)
    }
    etlBriefReady.value = true
  } catch (e) {
    console.warn('[DataCenter] 加载 ETL 简报失败', e)
    etlBriefReady.value = true
  }
}

// 多日视图辅助函数
function toggleDateExpand(dateKey) {
  dayExpanded.value[dateKey] = !dayExpanded.value[dateKey]
}

function formatDateLabel(dateKey) {
  // "2026-07-15" → "7月15日"
  try {
    const [y, m, d] = dateKey.split('-')
    return `${parseInt(m)}月${parseInt(d)}日`
  } catch { return dateKey }
}

function dateKeyOf(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function getDaySummary(dayGroup) {
  if (!dayGroup || dayGroup.length === 0) return '未运行'
  const ok = dayGroup.filter(l => normStatus(l.status) === 'success').length
  const err = dayGroup.filter(l => normStatus(l.status) === 'error' || normStatus(l.status) === 'cancelled').length
  const running = dayGroup.filter(l => normStatus(l.status) === 'running').length
  const skipped = dayGroup.filter(l => normStatus(l.status) === 'skipped').length
  if (err > 0) return `失败 ${err}/${dayGroup.length}`
  if (running > 0) return `运行中 ${ok}/${dayGroup.length}`
  if (skipped > 0) return `跳过 ${skipped}/${dayGroup.length}`
  return `完成 ${ok}/${dayGroup.length}`
}

function getDayStatusClass(dayGroup) {
  if (!dayGroup || dayGroup.length === 0) return 'day-missing'
  const hasErr = dayGroup.some(l => normStatus(l.status) === 'error' || normStatus(l.status) === 'cancelled')
  const hasRunning = dayGroup.some(l => normStatus(l.status) === 'running')
  if (hasErr) return 'day-error'
  if (hasRunning) return 'day-running'
  return 'day-ok'
}

// 未更新成功原因说明（针对「未运行」——当日无任何 etl_run_log 记录）
// 注意：仅在当天确实没有任何记录时显示；若流水线已写入记录，则失败原因会直接显示在「说明」列。
function getMissingReason(dateKey) {
  try {
    const today = dateKeyOf(new Date())
    if (dateKey === today) {
      const now = new Date()
      const passedSchedule = now.getHours() > 21 || (now.getHours() === 21 && now.getMinutes() >= 30)
      if (!passedSchedule) {
        return '尚未到当日 21:30 定时执行时间，属正常等待（每日北京时间 21:30 由 GitHub Actions 自动运行两条流水线：基金评分、资产配置/季度评分）。'
      }
      return '已过当日 21:30 执行时间但无任何运行记录：流水线可能未触发，或在启动阶段即失败（尚未写入 etl_run_log）。可到 GitHub Actions 查看对应 workflow 的运行状态与日志。'
    }
    return '当日 ETL 未执行或启动即失败，未产生任何运行记录。常见原因：GitHub Actions 定时任务未触发（cron 被延迟/跳过）、仓库 Actions 被禁用、或运行环境初始化失败。可到 GitHub Actions 历史记录核实。'
  } catch {
    return '当日无任何运行记录，ETL 可能未触发或启动即失败。'
  }
}

// 未更新成功原因的简短版（用于折叠态日期行的内联提示）
function getMissingReasonShort(dateKey) {
  try {
    const today = dateKeyOf(new Date())
    if (dateKey === today) {
      const now = new Date()
      const passedSchedule = now.getHours() > 21 || (now.getHours() === 21 && now.getMinutes() >= 30)
      return passedSchedule ? '尚未产生运行记录（可能未触发或启动即失败）' : '未到 21:30 执行时间'
    }
    return '当日无运行记录（可能未触发或启动即失败）'
  } catch { return '未产生运行记录' }
}

// 地区字符串规范化：去相邻重复词（ipwho.is 常返回 "Hong Kong Hong Kong, Hong Kong"），
// 并按国家规范表述港澳台（中国香港 / 中国台湾 / 中国澳门）
function normalizeRegion(s) {
  if (!s) return ''
  let t = String(s).trim()
  if (!t) return ''
  // 港澳台规范表述（先做映射，再去重）
  t = t.replace(/Hong\s*Kong/gi, '中国香港')
       .replace(/Macao|Macau/gi, '中国澳门')
       .replace(/Taiwan/gi, '中国台湾')
  // 拆分为 词/逗号 序列，去掉相邻重复
  const tokens = t.split(/(\s*,\s*|\s+)/).map(x => x.trim()).filter(x => x && x !== ',')
  const out = []
  for (const tk of tokens) { if (out[out.length - 1] !== tk) out.push(tk) }
  return out.join(' ').trim()
}

// 根据 IP 地址补全地区（双保险：先 ipwho.is 国际库，失败则用国内库兜底）
// 采用小并发（4 路）避免免费接口突发限流导致整批解析失败
async function enrichRegions(list) {
  const ips = [...new Set(list.filter(v => v.ip && v.ip !== '—' && (v.region === '—' || !v.region)).map(v => v.ip))]
  if (ips.length === 0) return
  const resolveOne = async (ip) => {
    // 第一道防线：ipwho.is（国际，覆盖全球）
    let text = await resolveIP_1(ip)
    // 第二道防线：国内库（太平洋电脑网）兜底
    if (!text) text = await resolveIP_2(ip)
    if (!text) return
    const region = normalizeRegion(text)
    if (!region) return
    list.forEach(v => { if (v.ip === ip && (v.region === '—' || !v.region)) v.region = region })
  }
  // 并发池：每次最多 4 个请求
  const POOL = 4
  for (let i = 0; i < ips.length; i += POOL) {
    await Promise.all(ips.slice(i, i + POOL).map(resolveOne))
  }
}

// 第一道：ipwho.is（国际源）
async function resolveIP_1(ip) {
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 4000)
    const r = await fetch('https://ipwho.is/' + encodeURIComponent(ip), { signal: ctrl.signal })
    clearTimeout(timer)
    if (!r.ok) return null
    const d = await r.json()
    if (!d || d.success === false) return null
    const loc = [d.region, d.city].filter(Boolean).join(' ')
    const text = (d.country === 'China' || d.country_code === 'CN')
      ? (loc || d.country)
      : (loc ? loc + ', ' + d.country : d.country)
    return text || null
  } catch (_) { return null }
}

// 第二道：国内库（ip.useragentinfo.com，中文输出，对国内 IP 命中率高）
async function resolveIP_2(ip) {
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 5000)
    // 太平洋电脑网 IP 查询接口（JSONP/JSON 均支持，返回中文省市）
    const r = await fetch('https://whois.pconline.com.cn/ipJson.jsp?ip=' + encodeURIComponent(ip) + '&json=true', { signal: ctrl.signal })
    clearTimeout(timer)
    if (!r.ok) return null
    const d = await r.json()
    if (!d || d.pro === undefined) return null
    // 返回格式: { pro: "省份", city: "城市", addr: "..." }
    const loc = [d.pro, d.city].filter(Boolean).join(' ')
    return loc || null
  } catch (_) { return null }
}

// 加载用户分析（从 visitor_logs 读取当日访问，统计活跃用户与清单）
async function loadUserAnalytics() {
  try {
    const { supabase } = await import('../../api/supabase.js')
    if (!supabase) { userAnalyticsReady.value = true; return }
    const now = new Date()
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString()
    const fifteenAgo = new Date(now.getTime() - 15 * 60 * 1000).toISOString()
    const { data, error } = await supabase
      .from('visitor_logs')
      .select('email, ip_address, region, page_path, visit_time')
      .gte('visit_time', startOfDay)
      .order('visit_time', { ascending: false })
      .limit(1000)
    if (error || !data) { userAnalyticsReady.value = true; return }
    const keyOf = (r) => (r.email && r.email !== 'anonymous') ? ('e:' + r.email) : ('ip:' + (r.ip_address || 'unknown'))
    const recent = data.filter(r => new Date(r.visit_time) >= new Date(fifteenAgo))
    activeNow.value = new Set(recent.map(keyOf)).size
    activeToday.value = new Set(data.map(keyOf)).size
    const map = new Map()
    for (const r of data) {
      const k = keyOf(r)
      if (!map.has(k)) map.set(k, { email: r.email, ip: r.ip_address || null, region: r.region || '', paths: new Set(), min: r.visit_time, max: r.visit_time })
      const u = map.get(k)
      // 同一用户的 IP / 地区可能分散在多条日志（不同写入路径，部分行为空），取最完整的一条补全
      if (!u.ip && r.ip_address) u.ip = r.ip_address
      if (!u.region && r.region) u.region = r.region
      if (r.page_path) u.paths.add(r.page_path)
      if (r.visit_time < u.min) u.min = r.visit_time
      if (r.visit_time > u.max) u.max = r.visit_time
    }
    const list = [...map.values()].map(u => ({
      name: (u.email && u.email !== 'anonymous') ? (u.email === 'authenticated' ? '已登录访客' : u.email) : '匿名访客',
      email: u.email,
      ip: u.ip || '—',
      region: normalizeRegion(u.region) || '',
      firstVisit: u.min,
      durationMin: Math.max(0, Math.round((new Date(u.max) - new Date(u.min)) / 60000)),
      paths: [...u.paths]
    }))
    await enrichRegions(list)
    visitorList.value = list
    userAnalyticsReady.value = true
  } catch (e) {
    console.warn('[DataCenter] 加载用户分析失败', e)
    userAnalyticsReady.value = true
  }
}

// ========== 用户权限管理 ==========
// 用户名展示：手机号注册用户的 user_email 为合成邮箱（如 8613800138000@dachu.user，
// 历史账号为 @allfund.user），去掉后缀只显示手机号；微信登录用户为 wx_xxx@dachu.wechat
// （历史为 @allfund.wechat），显示为「微信用户」；真实邮箱（如管理员）原样显示。
function displayUsername(email) {
  if (!email) return '—'
  if (email === 'authenticated') return '已登录访客'
  if (email.endsWith('@dachu.wechat') || email.endsWith('@allfund.wechat')) return '微信用户'
  if (email.endsWith('@dachu.user')) return email.slice(0, -'@dachu.user'.length)
  if (email.endsWith('@allfund.user')) return email.slice(0, -'@allfund.user'.length)
  return email
}

async function loadPermissionsList() {
  // 防御：主管理员邮箱始终放行（不依赖 permissions 异步加载）
  const ownerOk = isOwner.value
  const email = user?.email || ''
  console.log('[perm] loadPermissionsList: isOwner=' + ownerOk + ' email=' + email)
  if (!ownerOk) return
  permLoading.value = true
  try {
    const { supabase } = await import('../../api/supabase.js')
    if (!supabase) { console.warn('[perm] supabase client not ready'); permUsers.value = []; return }
    // 全部注册用户（app_users，由 auth.users 触发器自动写入）
    const { data: users, error: e1 } = await supabase
      .from('app_users')
      .select('id, user_email, created_at')
      .order('created_at', { ascending: false })
    console.log('[perm] app_users query: count=' + (users?.length || 0) + ' error=' + (e1?.message || 'none'))
    if (e1) { console.error('[perm] app_users error', e1); permUsers.value = []; return }
    // 已授予的权限（可能为空）
    const { data: perms, error: e2 } = await supabase
      .from('user_permissions')
      .select('user_email, is_admin, enabled_features, granted_by')
    if (e2) { console.error('[perm] perms error', e2); permUsers.value = []; return }
    const permMap = {}
    ;(perms || []).forEach(p => { permMap[p.user_email] = p })
    permUsers.value = (users || []).map(u => {
      const p = permMap[u.user_email] || {}
      const isAdminRow = u.user_email === adminEmail || !!p.is_admin
      // 管理员以「开通功能」中的 admin 选项呈现（与 is_admin 字段双向同步）
      const feats = new Set(Array.isArray(p.enabled_features) ? p.enabled_features.filter(f => f !== 'all') : [])
      if (isAdminRow) feats.add('admin')
      return {
        user_email: u.user_email,
        user_id: u.id,
        created_at: u.created_at,
        _features: [...feats],
        granted_by: p.granted_by || null,
        _saving: false,
      }
    })
  } catch (e) {
    console.error('[perm] load error', e)
    permUsers.value = []
  } finally {
    permLoading.value = false
  }
}

// 踢出用户：调用 Edge Function 永久删除该账号（仅管理员）
async function kickUser(v) {
  if (!v.email || v.email === 'anonymous') return
  const ok = await confirm('踢出用户', `确定要踢出用户「${displayUsername(v.email)}」吗？此操作将永久删除该账号及其全部数据，不可恢复。`)
  if (!ok) return
  try {
    const { supabase } = await import('../../api/supabase.js')
    const { data: { session } } = await supabase.auth.getSession()
    if (!session?.access_token) throw new Error('未登录或会话已过期')
    const url = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/admin-delete-user`
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ email: v.email }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
    toast('已踢出用户 ' + displayUsername(v.email), 'success')
    visitorList.value = visitorList.value.filter(x => x.email !== v.email)
    // 同步刷新权限列表（该用户可能已在 user_permissions 中有记录）
    await loadPermissionsList()
  } catch (e) {
    toast('踢出失败：' + (e?.message || e), 'error')
  }
}

// 拉黑用户：写入 blocked_users，该用户下次访问将被强制登出（仅管理员）
async function blockVisitor(email) {
  if (!email || email === 'anonymous') return
  try {
    await blockUser(email)
    toast('已拉黑 ' + displayUsername(email), 'success')
  } catch (e) {
    toast('拉黑失败：' + (e?.message || e), 'error')
  }
}

async function addPermission() {
  const email = (newEmail.value || '').trim().toLowerCase()
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    permMsg.value = '请输入有效的邮箱地址'
    permMsgType.value = 'perm-msg--error'
    return
  }
  permSaving.value = true
  permMsg.value = ''
  try {
    await savePermissions(email, { is_admin: newFeatures.value.includes('admin'), enabled_features: [...newFeatures.value] })
    newEmail.value = ''
    newFeatures.value = []
    await loadPermissionsList()
    permMsg.value = `已为 ${email} 保存权限`
    permMsgType.value = 'perm-msg--ok'
  } catch (e) {
    permMsg.value = '保存失败：' + (e?.message || '未知错误')
    permMsgType.value = 'perm-msg--error'
  } finally {
    permSaving.value = false
  }
}

async function saveRow(row) {
  row._saving = true
  permMsg.value = ''
  try {
    await savePermissions(row.user_email, { is_admin: row._features.includes('admin'), enabled_features: [...row._features] })
    await loadPermissionsList()
    permMsg.value = `已更新 ${row.user_email} 的权限`
    permMsgType.value = 'perm-msg--ok'
  } catch (e) {
    permMsg.value = '保存失败：' + (e?.message || '未知错误')
    permMsgType.value = 'perm-msg--error'
  } finally {
    row._saving = false
  }
}

async function removeRow(row) {
  const ok = await confirm('确定删除？', `将删除 ${row.user_email} 的权限记录，该用户登录后将变为「陌生人，无访问权限」。`)
  if (!ok) return
  row._saving = true
  permMsg.value = ''
  try {
    await deletePermissions(row.user_email)
    await loadPermissionsList()
    permMsg.value = `已删除 ${row.user_email} 的权限`
    permMsgType.value = 'perm-msg--ok'
  } catch (e) {
    permMsg.value = '删除失败：' + (e?.message || '未知错误')
    permMsgType.value = 'perm-msg--error'
  } finally {
    row._saving = false
  }
}

// 重置用户密码为默认 123456（仅管理员；主管理员自身不可重置，避免误锁账号）
async function resetPassword(row) {
  const email = row.user_email
  if (!email || email === adminEmail) return
  const ok = await confirm(
    '重置密码',
    `确定要将用户「${displayUsername(email)}」的密码重置为默认密码 123456 吗？该用户下次登录需使用 123456，请务必通过安全渠道告知对方。`
  )
  if (!ok) return
  row._saving = true
  permMsg.value = ''
  try {
    const { supabase } = await import('../../api/supabase.js')
    const { data: { session } } = await supabase.auth.getSession()
    if (!session?.access_token) throw new Error('未登录或会话已过期')
    const url = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/admin-reset-password`
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ email }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
    toast('已将 ' + displayUsername(email) + ' 的密码重置为 123456', 'success')
  } catch (e) {
    toast('重置失败：' + (e?.message || e), 'error')
  } finally {
    row._saving = false
  }
}

onMounted(() => {
  loadIndex()
  loadEtlBrief()
  loadUserAnalytics()
  loadPermissionsList()
  loadRequests()
  loadPasswordInfo()
  loadFeatureFlags()
})

// 保底：auth 初始化时序可能导致 onMounted 时 isOwner 尚未为 true
// watch 确保一旦 isOwner 变为 true（permissions 异步加载完成）立即加载用户列表
watch(isOwner, (val) => {
  if (val && permUsers.value.length === 0) {
    console.log('[perm] watch(isOwner) triggered reload, email=' + (user?.email || ''))
    loadPermissionsList()
  }
  if (val) {
    loadPasswordInfo()
  }
})
</script>

<style scoped>
.page-placeholder { padding-bottom: var(--space-2xl); }

.page-title {
  font-size: 32px; font-weight: 700; color: var(--text-primary);
  margin: 0 0 var(--space-xs);
}
.page-desc {
  font-size: 16px; color: var(--text-secondary); margin: 0 0 var(--space-xl);
  line-height: 1.6;
}

/* 无访问权限提示 */
.no-access {
  background: #fff; border: 1px solid var(--border); border-left: 4px solid #d4351c;
  padding: var(--space-lg); margin-bottom: var(--space-xl);
}
.no-access__title { font-size: 18px; font-weight: 700; color: #d4351c; margin: 0 0 var(--space-xs); }
.no-access__desc { font-size: 14px; color: var(--text-secondary); margin: 0; line-height: 1.6; }

/* 登录提示横幅 */
.login-banner {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--space-md); flex-wrap: wrap;
  background: #f3f8fc; border: 1px solid #1d70b8; border-left: 4px solid #1d70b8;
  padding: var(--space-md) var(--space-lg); margin-bottom: var(--space-xl);
}
.login-banner-text { display: flex; flex-direction: column; gap: 2px; }
.login-banner-text strong { font-size: 15px; color: #1d70b8; }
.login-banner-text span { font-size: 13px; color: var(--text-secondary); }
.btn-login {
  flex: 0 0 auto; padding: 8px 20px; background: #1d70b8; color: #fff;
  border: none; font-size: 14px; font-weight: 700; cursor: pointer; white-space: nowrap;
}
.btn-login:hover { background: #003078; }

/* Card */
.card {
  background: #ffffff; border: 1px solid var(--border);
  padding: var(--space-lg); margin-bottom: var(--space-xl);
}
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-md); }
.section-desc { font-size: 16px; color: var(--text-secondary); margin-bottom: var(--space-lg); }

/* ===== 功能开放控制 ===== */
.feature-flag-list { display: flex; flex-direction: column; margin-top: var(--space-md); }
.feature-flag-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--space-md); padding: var(--space-md) 0;
  border-bottom: 1px solid var(--border);
}
.feature-flag-row:last-child { border-bottom: none; }
.feature-flag-info { flex: 1; }
.feature-flag-label { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.feature-flag-desc { font-size: 14px; color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }

.switch { display: inline-flex; align-items: center; gap: 10px; cursor: pointer; flex-shrink: 0; }
.switch--disabled { cursor: not-allowed; opacity: 0.7; }
.switch input { position: absolute; opacity: 0; width: 0; height: 0; }
.switch__track {
  position: relative; width: 52px; height: 28px;
  background: #b1b4b6; border: 2px solid #0b0c0c; transition: background 0.15s;
}
.switch__thumb {
  position: absolute; top: 2px; left: 2px; width: 20px; height: 20px;
  background: #0b0c0c; transition: transform 0.15s, background 0.15s;
}
.switch input:checked + .switch__track { background: #1d70b8; }
.switch input:checked + .switch__track .switch__thumb { transform: translateX(24px); background: #ffffff; }
.switch__state { font-size: 14px; font-weight: 700; min-width: 32px; color: var(--text-primary); }
.feature-flag-readonly { margin-top: var(--space-md); color: #d4351c; font-weight: 700; }

/* 项目简介 */
.intro-grid { border: 1px solid var(--border); }
.intro-row { display: flex; border-bottom: 1px solid var(--border); }
.intro-row:last-child { border-bottom: none; }
.intro-key {
  flex: 0 0 140px; padding: var(--space-md);
  font-weight: 700; color: var(--text-primary);
  background: #f3f2f1; border-right: 1px solid var(--border);
  font-size: 14px;
}
.intro-val {
  flex: 1; padding: var(--space-md);
  font-size: 14px; color: var(--text-secondary); line-height: 1.7;
}
.intro-val code {
  background: #f3f2f1; padding: 1px 5px; border-radius: 2px;
  font-family: monospace; font-size: 12px; color: var(--text-primary);
}
@media (max-width: 640px) {
  .intro-row { flex-direction: column; }
  .intro-key { flex-basis: auto; border-right: none; border-bottom: 1px solid var(--border); }
}

/* 表格 */
.data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.data-table th {
  text-align: left; padding: var(--space-sm); font-weight: 700;
  border-bottom: 2px solid var(--text-primary); color: var(--text-primary);
}
.data-table td { padding: var(--space-sm); border-bottom: 1px solid var(--border); vertical-align: top; }
.col-name { width: 200px; font-family: monospace; }
.col-desc { font-size: 13px; color: var(--text-secondary); line-height: 1.5; }
.col-rows { width: 80px; text-align: right; font-family: monospace; }
.col-size { width: 80px; text-align: right; font-family: monospace; color: var(--text-secondary); }
.col-action { width: 110px; text-align: center; }

.btn-download {
  display: inline-block; padding: 4px 12px; background: #1d70b8; color: #fff;
  text-decoration: none; font-size: 13px; font-weight: 700; white-space: nowrap;
}
.btn-download:hover { background: #003078; }
.text-muted { font-size: 12px; color: var(--text-secondary); }

/* 密码状态标签 */
.pwd-tag {
  display: inline-block; font-size: 13px; font-weight: 700;
  padding: 2px 8px; border-left: 4px solid transparent;
}
.pwd-weak { color: #d4351c; background: #fbe9e7; border-left-color: #d4351c; }
.pwd-ok { color: #00703c; background: #f0faf3; border-left-color: #00703c; }
.pwd-time { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

.table-footer { margin-top: var(--space-md); }
.update-time { font-size: 14px; color: var(--text-secondary); margin: 0; }

/* ETL 简报 */
.brief-footer {
  margin-top: var(--space-sm);
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border);
  font-size: 13px; color: var(--text-secondary);
}
.status-badge {
  display: inline-block;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 700;
  border-radius: 2px;
  text-align: center;
  white-space: nowrap;
}
.status-ok { background: #00703c; color: #fff; }
.status-error { background: #d4351c; color: #fff; }
.status-running { background: #1d70b8; color: #fff; animation: pulse 1.5s infinite; }
.status-pending { background: #f3f2f1; color: #6b7280; }
.status-cancelled { background: #b53c00; color: #fff; }
.status-skipped { background: #b1b4b6; color: #0b0c0c; }
.source-badge {
  display: inline-block;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 700;
  border-radius: 2px;
  text-align: center;
  white-space: nowrap;
}
.source-mp { background: #1d70b8; color: #fff; }
.source-web { background: #f3f2f1; color: #505a5f; }
@keyframes pulse {
  0%, 100% { opacity: 1; } 50% { opacity: 0.5; }
}
.col-etl-step { width: 220px; vertical-align: top; }
.col-etl-desc { width: 280px; vertical-align: top; }
.col-etl-status { width: 80px; text-align: center; }
.col-etl-rows { width: 100px; text-align: right; font-family: monospace; }
.col-etl-time { width: 160px; }
.col-etl-duration { width: 90px; text-align: right; font-family: monospace; }
.col-etl-date { width: 120px; }

/* 多日视图：日期行 */
.etl-day-table .date-row { cursor: pointer; background: #f8f9fa; }
.etl-day-table .date-row:hover { background: #eef2f6; }
.date-label { font-weight: 700; font-size: 14px; color: #0b0c0c; }
.date-summary {
  display: inline-block; padding: 1px 10px; font-size: 12px; font-weight: 700;
  border-radius: 2px; margin-left: 12px;
}
.day-ok .date-summary { background: #00703c; color: #fff; }
.day-error .date-summary { background: #d4351c; color: #fff; }
.day-running .date-summary { background: #1d70b8; color: #fff; animation: pulse 1.5s infinite; }
.day-missing .date-summary { background: #b1b4b6; color: #0b0c0c; }
.day-missing .date-label { color: #505a5f; }
.date-toggle { float: right; font-size: 12px; color: #505a5f; }
.date-missing-hint { font-size: 12px; color: #b53c00; margin-left: 8px; }
.etl-empty-row td { color: var(--text-secondary); font-size: 13px; padding: 10px 12px; }
.etl-empty-row .missing-title { font-weight: 700; color: #b53c00; font-size: 14px; }
.etl-empty-row .missing-reason {
  font-size: 12px; color: #b53c00; line-height: 1.5; margin-top: 6px;
  background: #fef7f0; border-left: 3px solid #b53c00; padding: 4px 8px;
}

/* ETL 简报汇总 */
.brief-summary { font-size: 14px; color: var(--text-secondary); margin: 0 0 var(--space-md); }
.brief-summary .ok { color: #00703c; font-weight: 700; }
.brief-summary .fail { color: #d4351c; font-weight: 700; }
.brief-summary .warn { color: #b53c00; font-weight: 700; }
.brief-summary .muted { color: #505a5f; font-weight: 700; }
.brief-summary .sep { margin: 0 8px; color: var(--border); }

/* ETL 步骤说明 + 进度条 */
.step-name { margin-bottom: 2px; }
.step-name code { font-size: 12px; color: var(--text-secondary); }
.step-title { font-weight: 700; color: var(--text-primary); font-size: 14px; margin-top: 2px; }
.step-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.4; margin-top: 2px; }
.progress { width: 160px; height: 6px; background: #f3f2f1; border: 1px solid var(--border); margin-top: 8px; overflow: hidden; }
.progress-bar { height: 100%; background: #1d70b8; transition: width .3s; }
.pg-ok .progress-bar { background: #00703c; }
.pg-error .progress-bar { background: #d4351c; }
.pg-overtime .progress-bar { background: #d4351c; animation: pulse 1.2s infinite; }
.pg-running .progress-bar {
  background-color: #1d70b8;
  background-image: linear-gradient(45deg, rgba(255,255,255,.4) 25%, transparent 25%, transparent 50%, rgba(255,255,255,.4) 50%, rgba(255,255,255,.4) 75%, transparent 75%, transparent);
  background-size: 18px 18px;
  animation: pg-slide 1s linear infinite;
}
.pg-pending .progress-bar { background: #b1b4b6; }
@keyframes pg-slide { from { background-position: 0 0; } to { background-position: 18px 0; } }
.step-reason {
  font-size: 12px; color: #d4351c; line-height: 1.5; margin-top: 6px;
  background: #fdf2f0; border-left: 3px solid #d4351c; padding: 4px 8px;
}
.step-suggestion {
  font-size: 12px; color: #1d70b8; line-height: 1.5; margin-top: 4px;
  background: #eaf2fb; border-left: 3px solid #1d70b8; padding: 4px 8px;
}
.reason-label { font-weight: 700; }

/* 用户分析 */
.analytics-summary { display: flex; gap: var(--space-lg); margin: 0 0 var(--space-lg); flex-wrap: wrap; }
.analytics-summary .stat {
  flex: 1; min-width: 140px; background: #f3f2f1; border: 1px solid var(--border);
  padding: var(--space-md); text-align: center;
}
.analytics-summary .stat-num { font-size: 28px; font-weight: 700; color: #1d70b8; line-height: 1.1; }
.analytics-summary .stat-label { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
.col-ua-name { width: 200px; }
.col-ua-ip { width: 140px; font-family: monospace; }
.col-ua-region { width: 180px; }
.col-ua-firstvisit { width: 160px; font-family: monospace; }
.col-ua-duration { width: 100px; text-align: right; font-family: monospace; }
.col-ua-paths { min-width: 240px; }
.col-ua-action { width: 150px; white-space: nowrap; }
.ua-action-btn { margin: 2px 4px 2px 0; padding: 4px 10px; font-size: 13px; }
.ua-action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.path-tag {
  display: inline-block; background: #f3f2f1; border: 1px solid var(--border);
  border-radius: 2px; padding: 1px 6px; margin: 2px 4px 2px 0; font-size: 12px;
  font-family: monospace; color: var(--text-secondary);
}

/* 用户组合明细弹窗 */
.ua-name-link {
  color: #1d70b8; cursor: pointer;
  text-decoration: underline; text-decoration-color: transparent;
  transition: text-decoration-color .15s;
}
.ua-name-link:hover { text-decoration-color: #1d70b8; }
.ua-name-link:focus { outline: 2px solid #1d70b8; outline-offset: 2px; }

.ua-mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4);
  display: flex; align-items: center; justify-content: center;
  padding: var(--space-md); z-index: 1000;
}
.ua-modal {
  background: #fff; border-left: 4px solid #1d70b8;
  width: 100%; max-width: 520px; max-height: 85vh; overflow-y: auto;
}
.ua-modal__header {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--space-sm); padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border);
}
.ua-modal__title {
  font-size: 15px; font-weight: 700; color: var(--text-primary);
  font-family: monospace; word-break: break-all; line-height: 1.4;
}
.ua-modal__close {
  flex: 0 0 auto; background: none; border: none; color: var(--text-secondary);
  font-size: 22px; line-height: 1; cursor: pointer; padding: 0 4px;
}
.ua-modal__close:hover { color: #1d70b8; }
.ua-modal__loading, .ua-modal__error {
  padding: var(--space-lg); font-size: 14px; line-height: 1.6;
}
.ua-modal__error {
  color: #d4351c; background: #fdf2f0; border-left: 3px solid #d4351c;
}
.ua-modal__body { padding: var(--space-md) var(--space-lg); }
.ua-section { margin-bottom: var(--space-lg); }
.ua-section:last-child { margin-bottom: 0; }
.ua-section__title {
  font-size: 15px; font-weight: 700; color: var(--text-primary);
  margin-bottom: var(--space-sm);
  padding-bottom: var(--space-xs); border-bottom: 2px solid #1d70b8;
}
.ua-list { list-style: none; margin: 0; padding: 0; }
.ua-item {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--space-sm); padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--border);
}
.ua-item__name { font-weight: 700; color: var(--text-primary); word-break: break-all; }
.ua-item__meta { font-size: 12px; color: var(--text-secondary); white-space: nowrap; flex: 0 0 auto; }
.ua-empty { font-size: 14px; color: var(--text-secondary); margin: 0; }
.ua-modal__footer {
  padding: var(--space-md) var(--space-lg);
  border-top: 1px solid var(--border); text-align: right;
}

/* API 接口文档 */
.api-group-title {
  font-size: 22px; font-weight: 700; color: var(--text-primary);
  margin: var(--space-2xl) 0 var(--space-md);
  padding-bottom: var(--space-sm); border-bottom: 2px solid #1d70b8;
}
.api-item {
  margin-bottom: var(--space-xl); padding-bottom: var(--space-xl);
  border-bottom: 1px solid var(--border);
}
.api-name {
  font-size: 18px; font-weight: 700; color: #1d70b8; margin: 0 0 var(--space-sm);
}
.api-meta-table {
  width: 100%; border-collapse: collapse; margin-bottom: var(--space-sm);
  font-size: 14px;
}
.api-meta-table td { padding: 2px var(--space-sm); border: none; }
.meta-label {
  font-weight: 700; color: var(--text-primary); width: 80px;
  vertical-align: top;
}
.api-meta-table code {
  background: #f3f2f1; padding: 1px 6px; font-size: 13px; word-break: break-all;
}

.api-subtitle {
  font-size: 15px; font-weight: 700; color: var(--text-primary);
  margin: var(--space-md) 0 var(--space-sm);
}

.field-table {
  width: 100%; border-collapse: collapse; margin-bottom: var(--space-md);
  font-size: 13px;
}
.field-table th {
  text-align: left; padding: 6px var(--space-sm); background: #f3f2f1;
  font-weight: 700; color: var(--text-primary); border: 1px solid var(--border);
}
.field-table td {
  padding: 4px var(--space-sm); border: 1px solid var(--border);
  vertical-align: top; line-height: 1.5;
}
.field-table code {
  background: #f3f2f1; padding: 1px 4px; font-size: 12px;
}

.api-note {
  font-size: 13px; color: #d4351c; margin: var(--space-sm) 0 0; padding: var(--space-sm);
  background: #fef7f7; border-left: 4px solid #d4351c;
}

.code-list {
  font-size: 13px; color: var(--text-secondary); line-height: 1.8;
}
.code-list code {
  background: #f3f2f1; padding: 1px 6px; font-size: 12px; margin-right: var(--space-xs);
}

.summary-table th { background: #1d70b8; color: #fff; }
.summary-table td { font-size: 14px; }

/* 评分方法论 */
.method-step-title {
  font-size: 22px; font-weight: 700; color: #1d70b8;
  margin: var(--space-2xl) 0 var(--space-md);
  padding-bottom: var(--space-sm); border-bottom: 2px solid #1d70b8;
}
.method-subtitle {
  font-size: 17px; font-weight: 700; color: var(--text-primary);
  margin: var(--space-lg) 0 var(--space-sm);
}

/* 公式框 */
.formula-box {
  background: #f8f8f8; border: 1px solid var(--border);
  padding: var(--space-md); margin: var(--space-md) 0;
  border-left: 4px solid #1d70b8;
}
.formula-title {
  font-size: 14px; font-weight: 700; color: var(--text-secondary);
  margin-bottom: var(--space-xs); text-transform: uppercase; letter-spacing: 0.5px;
}
.formula-body {
  font-size: 18px; font-weight: 700; color: #1d70b8;
  font-family: 'Courier New', monospace; line-height: 1.8;
}
.formula-note {
  font-size: 13px; color: var(--text-secondary); margin-top: var(--space-sm);
  line-height: 1.6;
}

/* 维度卡片 */
.dimension-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: var(--space-md); margin: var(--space-md) 0;
}
@media (max-width: 768px) {
  .dimension-grid { grid-template-columns: 1fr; }
}
.dimension-card {
  background: #f8f8f8; border: 1px solid var(--border);
  padding: var(--space-md);
}
.dim-header {
  font-size: 15px; font-weight: 700; color: #1d70b8;
  margin-bottom: var(--space-sm); padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border);
}
.dim-detail {
  font-size: 13px; color: var(--text-secondary); line-height: 1.7;
}
.dim-detail code {
  background: #e8e8e8; padding: 1px 4px; font-size: 12px;
}

/* 评级标签 */
.grade-badge {
  display: inline-block; padding: 2px 10px; font-size: 12px;
  font-weight: 700; font-family: monospace;
}
.grade-green { background: #00703c; color: #fff; }
.grade-blue { background: #1d70b8; color: #fff; }
.grade-orange { background: #d4351c; color: #fff; }
.grade-gray { background: #6b7280; color: #fff; }

/* 数据流 */
.flow-diagram {
  background: #f8f8f8; border: 1px solid var(--border);
  padding: var(--space-lg); margin: var(--space-md) 0;
}
.flow-row {
  display: flex; align-items: center; justify-content: center;
  gap: var(--space-sm); flex-wrap: wrap;
}
.flow-row-aux {
  margin-top: var(--space-sm); padding-top: var(--space-sm);
  border-top: 2px dashed var(--border);
}
.flow-node {
  background: #ffffff; border: 2px solid #1d70b8; padding: var(--space-sm) var(--space-md);
  text-align: center; font-size: 14px; font-weight: 700; color: var(--text-primary);
  min-width: 100px;
}
.flow-node small { display: block; font-weight: 400; color: var(--text-secondary); margin-top: 2px; }
.flow-node-aux { border-color: #5694ca; }
.flow-arrow { font-size: 24px; color: #1d70b8; font-weight: 700; }
.flow-arrow-up { font-size: 28px; }

/* ========== 用户权限管理 ========== */
.perm-add {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-md);
  padding: var(--space-md); border: 1px solid var(--border); background: #f8f8f8;
  margin-bottom: var(--space-md);
}
.perm-email-input {
  flex: 1; min-width: 240px; padding: var(--space-sm);
  border: 1px solid var(--border); font-size: 16px; box-sizing: border-box;
}
.perm-email-input:focus { outline: 2px solid #1d70b8; outline-offset: -1px; }
.perm-features { display: flex; flex-wrap: wrap; gap: var(--space-md); }
.perm-feature {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 15px; font-weight: 700; color: var(--text-primary); cursor: pointer;
}
.perm-feature input { width: 16px; height: 16px; accent-color: #1d70b8; }
.perm-msg {
  font-size: 14px; font-weight: 700; padding: var(--space-sm) var(--space-md);
  margin-bottom: var(--space-md); border-left: 4px solid transparent;
}
.perm-msg--ok { color: #00703c; background: #f0faf3; border-left-color: #00703c; }
.perm-msg--error { color: #d4351c; background: #fdf3f2; border-left-color: #d4351c; }

.perm-table .col-perm-email { min-width: 200px; }
.perm-table .col-perm-features { min-width: 280px; }
.perm-table .col-perm-granted { width: 140px; }
.perm-table .col-perm-action { width: 140px; white-space: nowrap; }
.perm-table .perm-feature { margin-right: var(--space-sm); }
.perm-all { font-size: 14px; font-weight: 700; color: #1d70b8; }
.btn-remove {
  background: #ffffff; color: #d4351c; border: 1px solid #d4351c;
  padding: 4px 10px; font-size: 14px; font-weight: 700; cursor: pointer; margin-left: 6px;
}
.btn-remove:hover:not(:disabled) { background: #d4351c; color: #ffffff; }
.btn-remove:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-reset {
  background: #ffffff; color: #f47738; border: 1px solid #f47738;
  padding: 4px 10px; font-size: 14px; font-weight: 700; cursor: pointer; margin-left: 6px;
}
.btn-reset:hover:not(:disabled) { background: #f47738; color: #ffffff; }
.btn-reset:disabled { opacity: 0.5; cursor: not-allowed; }

/* ===== 管理中心 header + tabs ===== */
.mgmt-header { margin: 0 0 var(--space-lg); }
.mgmt-title {
  font-size: 28px; font-weight: 700; color: #1d70b8;
  margin: 0 0 var(--space-md);
}
.mgmt-tabs {
  display: flex; gap: 0;
  border-bottom: 2px solid var(--border);
}
.mgmt-tab {
  appearance: none; background: none; border: none;
  padding: 10px 20px; font-size: 16px; font-weight: 700;
  color: var(--text-secondary); cursor: pointer;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
}
.mgmt-tab:hover { color: #1d70b8; }
.mgmt-tab--active {
  color: #1d70b8; font-weight: 700;
  border-bottom-color: #1d70b8;
}

/* 全部 / 全否 快捷按钮 */
.perm-quick {
  display: flex; gap: var(--space-sm); margin-bottom: var(--space-sm);
  flex-wrap: wrap;
}
.btn-all, .btn-none {
  padding: 4px 14px; font-size: 13px; font-weight: 700; cursor: pointer;
  border: 1px solid #1d70b8; background: #fff; color: #1d70b8;
  white-space: nowrap;
}
.btn-all:hover:not(:disabled), .btn-none:hover:not(:disabled) { background: #eaf2fb; }
.btn-all:disabled, .btn-none:disabled { opacity: 0.5; cursor: not-allowed; }

/* 权限申请表 */
.perm-req-table .col-req-email { min-width: 200px; }
.perm-req-table .col-req-source { width: 90px; text-align: center; }
.perm-req-table .col-req-name { width: 100px; }
.perm-req-table .col-req-phone { width: 120px; }
.perm-req-table .col-req-extra { min-width: 160px; }
.perm-req-table .col-req-features { min-width: 280px; }
.perm-req-table .col-req-status { width: 90px; text-align: center; }
.perm-req-table .col-req-action { width: 140px; white-space: nowrap; }
.perm-req-table .perm-feature { margin-right: var(--space-sm); }

/* 权限申请状态徽章 */
.status-pending { background: #f3f2f1; color: #6b7280; }
.status-approved { background: #00703c; color: #fff; }
.status-rejected { background: #d4351c; color: #fff; }
</style>
