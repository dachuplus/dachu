<template>
  <div class="page-fund-rank">
    <!-- 顶部：搜索 -->
    <div class="top-bar">
      <div class="search-box">
        <input
          class="search-input"
          placeholder="搜基金名/代码"
          v-model="searchText"
          @keyup.enter="doSearch"
        />
        <span class="search-clear" v-if="searchText" @click="clearSearch">✕</span>
      </div>
    </div>

    <!-- 筛选区 -->
    <div class="filter-section">
      <!-- 一级分类（动态，来自 fund_scores.t0） -->
      <div class="filter-row">
        <span class="filter-label">一级分类</span>
        <div class="filter-chips">
          <div class="filter-chip" :class="{ active: filterT0 === '' }" @click="setT0('')">全部</div>
          <div v-for="item in t0List" :key="item.value" class="filter-chip" :class="{ active: filterT0 === item.value }" @click="setT0(item.value)">
            {{ item.label }}<span class="chip-cnt" v-if="item.cnt">{{ item.cnt }}</span>
          </div>
        </div>
      </div>

      <!-- 二级分类（依赖一级，来自 fund_scores.t1_tt） -->
      <div class="filter-row" v-if="filterT0 && t1List.length > 0">
        <span class="filter-label">二级分类</span>
        <div class="filter-chips">
          <div class="filter-chip" v-if="filterT0 !== '货币型'" :class="{ active: filterT1 === '' }" @click="setT1('')">全部</div>
          <div v-for="item in t1List" :key="item.value" class="filter-chip" :class="{ active: filterT1 === item.value }" @click="setT1(item.value)">
            {{ item.label }}<span class="chip-cnt" v-if="item.cnt">{{ item.cnt }}</span>
          </div>
        </div>
      </div>

      <!-- 更多筛选（弹窗入口） -->
      <div class="filter-actions-row">
        <div class="filter-action-btn" @click="openMoreFilter">
          <span>更多筛选</span>
          <span class="more-badge" v-if="activeMoreFilterCount">{{ activeMoreFilterCount }}</span>
          <span class="toggle-arrow">▾</span>
        </div>

        <!-- 评分指标（弹窗入口） -->
        <div class="filter-action-btn" @click="showScoreIndicator = true">
          <SvgIcon name="gear" :size="16" class="wt-icon" /> 评分指标
        </div>
      </div>

      <!-- 更多筛选弹窗 -->
      <Teleport to="body">
        <template v-if="showMoreFilter">
          <div class="mask" @click="cancelMoreFilter"></div>
          <div class="more-modal">
            <div class="more-modal-header">
              <span class="more-modal-title">更多筛选</span>
              <span class="more-modal-close" @click="cancelMoreFilter">&#x2715;</span>
            </div>
            <div class="more-modal-body">
              <!-- 份额类别 -->
              <div class="filter-row">
                <span class="filter-label">份额</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterSC === '' }" @click="mToggleSC('')">全部</div>
                  <div v-for="sc in shareClassOptions" :key="sc" class="filter-chip" :class="{ active: filterSC === sc }" @click="mToggleSC(sc)">{{ sc }}类</div>
                </div>
              </div>

              <!-- 是否场内 -->
              <div class="filter-row">
                <span class="filter-label">场内</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterCN === '' }" @click="mToggleCN('')">全部</div>
                  <div class="filter-chip" :class="{ active: filterCN === '1' }" @click="mToggleCN('1')">是</div>
                  <div class="filter-chip" :class="{ active: filterCN === '0' }" @click="mToggleCN('0')">否</div>
                </div>
              </div>

              <!-- 是否ETF -->
              <div class="filter-row">
                <span class="filter-label">ETF</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterETF === '' }" @click="mToggleFlag('ETF', '')">全部</div>
                  <div class="filter-chip" :class="{ active: filterETF === '1' }" @click="mToggleFlag('ETF', '1')">是</div>
                  <div class="filter-chip" :class="{ active: filterETF === '0' }" @click="mToggleFlag('ETF', '0')">否</div>
                </div>
              </div>

              <!-- 是否LOF -->
              <div class="filter-row">
                <span class="filter-label">LOF</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterLOF === '' }" @click="mToggleFlag('LOF', '')">全部</div>
                  <div class="filter-chip" :class="{ active: filterLOF === '1' }" @click="mToggleFlag('LOF', '1')">是</div>
                  <div class="filter-chip" :class="{ active: filterLOF === '0' }" @click="mToggleFlag('LOF', '0')">否</div>
                </div>
              </div>

              <!-- 是否FOF -->
              <div class="filter-row">
                <span class="filter-label">FOF</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterFOF === '' }" @click="mToggleFlag('FOF', '')">全部</div>
                  <div class="filter-chip" :class="{ active: filterFOF === '1' }" @click="mToggleFlag('FOF', '1')">是</div>
                  <div class="filter-chip" :class="{ active: filterFOF === '0' }" @click="mToggleFlag('FOF', '0')">否</div>
                </div>
              </div>

              <!-- 是否定开 -->
              <div class="filter-row">
                <span class="filter-label">定开</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterDK === '' }" @click="mToggleFlag('DK', '')">全部</div>
                  <div class="filter-chip" :class="{ active: filterDK === '1' }" @click="mToggleFlag('DK', '1')">是</div>
                  <div class="filter-chip" :class="{ active: filterDK === '0' }" @click="mToggleFlag('DK', '0')">否</div>
                </div>
              </div>

              <!-- 申购状态 -->
              <div class="filter-row">
                <span class="filter-label">状态</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterSG === '' }" @click="mToggleSG('')">全部</div>
                  <div class="filter-chip" :class="{ active: filterSG === '1' }" @click="mToggleSG('1')">可申购</div>
                  <div class="filter-chip" :class="{ active: filterSG === '0' }" @click="mToggleSG('0')">暂停申购</div>
                </div>
              </div>

              <!-- 单日涨跌≥20% -->
              <div class="filter-row">
                <span class="filter-label">20%</span>
                <div class="filter-chips">
                  <div class="filter-chip" :class="{ active: filterDailyLimit === '' }" @click="mToggleDailyLimit('')">全部</div>
                  <div class="filter-chip" :class="{ active: filterDailyLimit === '0' }" @click="mToggleDailyLimit('0')">否</div>
                  <div class="filter-chip" :class="{ active: filterDailyLimit === '1' }" @click="mToggleDailyLimit('1')">是</div>
                </div>
              </div>

              <!-- 基金规模区间（亿元）：预设选择或自定义 -->
              <div class="filter-row">
                <span class="filter-label">规模</span>
                <div class="filter-scale-presets">
                  <div v-for="p in SCALE_PRESETS" :key="p.key" class="filter-chip" :class="{ active: scalePreset === p.key }" @click="pickScalePreset(p.key)">{{ p.label }}</div>
                </div>
              </div>
              <div class="filter-row" v-if="scalePreset === 'custom'">
                <span class="filter-label">自定义</span>
                <div class="filter-scale-range">
                  <input type="number" class="scale-input" v-model="filterScaleMin" placeholder="最小" @input="onScaleInput" @keyup.enter="applyMoreFilters" />
                  <span class="scale-dash">—</span>
                  <input type="number" class="scale-input" v-model="filterScaleMax" placeholder="最大" @input="onScaleInput" @keyup.enter="applyMoreFilters" />
                  <span class="scale-unit">亿</span>
                </div>
              </div>

              <!-- 筛选说明 -->
              <div class="filter-tip">
                注：ETF/LOF/定开/申购状态/单日涨跌基于数据库字段精确筛选；场内/份额类别基于基金名称识别，可能存在少量误判。<br>
                机构占比、股票占比数据暂未收录，后续版本更新。
              </div>
            </div>
            <div class="more-modal-footer">
              <button class="btn-reset" @click="resetMoreFilters">重置</button>
              <button class="btn-confirm" @click="applyMoreFilters">确认</button>
            </div>
          </div>
        </template>
      </Teleport>

      <!-- 评分指标弹窗 -->
      <Teleport to="body">
        <template v-if="showScoreIndicator">
          <div class="mask" @click="cancelScoreIndicator"></div>
          <div class="score-indicator-modal">
            <div class="more-modal-header">
              <span class="more-modal-title">评分指标</span>
              <span class="more-modal-close" @click="cancelScoreIndicator">&#x2715;</span>
            </div>
            <div class="more-modal-body">
              <p class="score-tip">自定义评分权重（合计 100%）
                <span class="weight-sum" :class="{ valid: weightSum === 100, invalid: weightSum !== 100 }">当前：{{ weightSum }}%</span>
              </p>
              <div class="weight-sliders">
                <div class="weight-row" v-for="item in weightItems" :key="item.key">
                  <span class="weight-label">{{ item.label }}</span>
                  <input type="range" :min="0" :max="100" :value="item.value" class="weight-range" @input="e => item.value = Number(e.target.value)" />
                  <input type="number" :min="0" :max="100" :value="item.value" class="weight-num" @input="e => item.value = Number(e.target.value)" />%
                </div>
              </div>
            </div>
            <div class="more-modal-footer">
              <button class="btn-reset" @click="resetWeights">恢复默认</button>
              <button class="btn-confirm" :disabled="weightSum !== 100" @click="applyScoreIndicator">确认</button>
            </div>
          </div>
        </template>
      </Teleport>

      <!-- 显示周期选择器 -->
      <div class="period-select-row">
        <span class="period-select-label">显示周期：</span>
        <span v-for="p in displayPeriods" :key="p.key" class="period-tag" :class="{ active: currentPeriod === p.key }" @click="switchPeriod(p.key)">
          {{ p.label }}
        </span>
        <select class="period-select" :value="extraPeriod" @change="e => extraPeriod = e.target.value">
          <option value="">+ 选择其他周期</option>
          <option v-for="p in availableExtraPeriods" :key="p.key" :value="p.key">{{ p.label }}</option>
        </select>
      </div>

      <!-- 筛选结果数量 -->
      <div class="filter-result-row" v-if="dataLoaded">
        <span class="filter-result-count">
          筛选结果：<strong>{{ totalCount != null ? totalCount : funds.length }}</strong> 只，已加载 <strong>{{ funds.length }}</strong> 只
        </span>
        <span class="data-refresh" :class="{ refreshing }" @click="refreshData">
          {{ refreshing ? '刷新中' : '刷新' }}
        </span>
      </div>
    </div>

    <!-- 基金列表 - 桌面端：横向表格 -->
    <div class="fund-table-wrap" v-if="!isMobile && funds.length > 0">
      <table class="fund-table">
        <thead>
          <tr>
            <th class="col-code sortable" @click="toggleColumnSort('c')">
              基金代码<span class="th-arrow" v-if="sortField === 'c'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-name sortable" @click="toggleColumnSort('n')">
              基金简称<span class="th-arrow" v-if="sortField === 'n'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-manager sortable" @click="toggleColumnSort('fund_manager')">
              基金经理<span class="th-arrow" v-if="sortField === 'fund_manager'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-t1">二级分类</th>
            <th class="col-scale sortable" @click="toggleColumnSort('fund_scale')">
              基金规模（亿）<span class="th-arrow" v-if="sortField === 'fund_scale'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-fee">管理费%</th>
            <th class="col-ret sortable" @click="toggleColumnSort('r1y')">
              近1年收益%<span class="th-arrow" v-if="sortField === 'r1y'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-ret sortable" @click="toggleColumnSort('r2y')">
              近2年收益%<span class="th-arrow" v-if="sortField === 'r2y'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-ret sortable" @click="toggleColumnSort('r3y')">
              近3年收益%<span class="th-arrow" v-if="sortField === 'r3y'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-ret sortable" @click="toggleColumnSort('r5y')">
              近5年收益%<span class="th-arrow" v-if="sortField === 'r5y'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th v-for="p in displayPeriods" :key="p.key" class="col-score sortable" :class="{ 'col-sort': currentPeriod === p.key }" @click="switchPeriod(p.key)">
              {{ p.label }}评分<span class="th-arrow" v-if="currentPeriod === p.key">{{ sortAsc ? '▲' : '▼' }}</span>
            </th>
            <th class="col-actions">投票</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(fund, idx) in sortedFunds"
            :key="fund.c"
            class="fund-row"
          >
            <td class="col-code"><a :href="eastMoneyUrl(fund.c)" target="_blank" @click.stop>{{ fund.c }}</a></td>
            <td class="col-name"><a :href="eastMoneyUrl(fund.c)" target="_blank" @click.stop>{{ fund.n || '基金' + fund.c }}</a></td>
            <td class="col-manager" :title="fund.fund_manager">{{ fund.fund_manager || '--' }}</td>
            <td class="col-t1" :title="fund.t1_tt || fund.t1">{{ fund.t1_tt || fund.t1 || '--' }}</td>
            <td class="col-scale">{{ fmtFundScale(fund.fund_scale) }}</td>
            <td class="col-fee">{{ fmtManageFee(fund.manage_fee) }}</td>
            <td class="col-ret" :style="{ color: retColor(fund.r1y) }">{{ fmtRetPlain(fund.r1y) }}</td>
            <td class="col-ret" :style="{ color: retColor(fund.r2y) }">{{ fmtRetPlain(fund.r2y) }}</td>
            <td class="col-ret" :style="{ color: retColor(fund.r3y) }">{{ fmtRetPlain(fund.r3y) }}</td>
            <td class="col-ret" :style="{ color: retColor(fund.r5y) }">{{ fmtRetPlain(fund.r5y) }}</td>
            <td v-for="p in displayPeriods" :key="p.key" class="col-score" :class="{ 'col-sort': currentPeriod === p.key }">
              <span class="score-val" :style="scoreColor(fund[p.key])">{{ fmtScore(fund[p.key]) }}</span>
            </td>
            <td class="col-actions">
              <span class="action-btn" :class="{ active: likesMap[fund.c] > 0 }" title="点赞" @click.stop="thumbUp(fund)">
                <SvgIcon name="thumbs-up" :size="16" />
                <span class="action-count" v-if="likesMap[fund.c] > 0">{{ likesMap[fund.c] }}</span>
              </span>
              <span class="action-btn" :class="{ active: dislikedSet.has(fund.c) }" title="吐槽" @click.stop="thumbDown(fund)">
                <SvgIcon name="thumbs-down" :size="16" />
              </span>
              <span class="action-btn action-add" title="加入组合" @click.stop="openPortfolioPicker(fund)">
                <SvgIcon name="plus-circle" :size="16" />
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 基金列表 - 移动端：卡片布局 -->
    <div class="mobile-fund-list" v-if="isMobile && funds.length > 0">
      <div
        v-for="fund in sortedFunds"
        :key="fund.c"
        class="fund-card"
      >
        <div class="fund-card-top">
          <a class="fund-code" :href="eastMoneyUrl(fund.c)" target="_blank" @click.stop>{{ fund.c }}</a>
          <a class="fund-name" :href="eastMoneyUrl(fund.c)" target="_blank" @click.stop>{{ fund.n || '基金' + fund.c }}</a>
          <span class="fund-card-actions" @click.stop>
            <span class="action-icon" :class="{ active: likesMap[fund.c] > 0 }" title="点赞" @click="thumbUp(fund)">
              <SvgIcon name="thumbs-up" :size="16" />
              <span class="action-count-sm" v-if="likesMap[fund.c] > 0">{{ likesMap[fund.c] }}</span>
            </span>
            <span class="action-icon" :class="{ active: dislikedSet.has(fund.c) }" title="吐槽" @click="thumbDown(fund)">
              <SvgIcon name="thumbs-down" :size="16" />
            </span>
            <span class="action-icon" title="加入组合" @click="openPortfolioPicker(fund)">
              <SvgIcon name="plus-circle" :size="16" />
            </span>
          </span>
        </div>
        <div class="fund-card-mgr" v-if="fund.fund_manager">{{ fund.fund_manager }}</div>
        <div class="fund-card-scale" v-if="fund.fund_scale != null">规模（亿）：{{ fmtFundScale(fund.fund_scale) }} · 管理费%：{{ fmtManageFee(fund.manage_fee) }}</div>
        <div class="fund-card-ret">
          <span :style="{ color: retColor(fund.r1y) }">近1年收益 {{ fmtRetPlain(fund.r1y) }}</span>
          <span :style="{ color: retColor(fund.r2y) }">近2年收益 {{ fmtRetPlain(fund.r2y) }}</span>
          <span :style="{ color: retColor(fund.r3y) }">近3年收益 {{ fmtRetPlain(fund.r3y) }}</span>
          <span :style="{ color: retColor(fund.r5y) }">近5年收益 {{ fmtRetPlain(fund.r5y) }}</span>
        </div>
        <div class="fund-card-scores">
          <span
            v-for="p in displayPeriods"
            :key="p.key"
            class="score-chip"
            :class="{ 'score-chip-active': currentPeriod === p.key }"
            @click.stop="switchPeriod(p.key)"
          >
            <span class="chip-label">{{ p.label }}</span>
            <span class="chip-val" :style="scoreColor(fund[p.key])">{{ fmtScore(fund[p.key]) }}</span>
          </span>
        </div>
      </div>
    </div>

    <!-- 加载更多 -->
    <div class="load-more" v-if="hasMore && funds.length > 0" @click="loadMore">
      {{ loading ? '加载中...' : '加载更多' }}
    </div>

    <!-- 已加载完全部 -->
    <div class="loaded-all" v-if="!hasMore && funds.length > 0 && dataLoaded">
      已加载全部 <strong>{{ funds.length }}</strong> 只
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-if="dataLoaded && funds.length === 0 && !loading">
      <template v-if="loadError">
        <p class="empty-text">基金数据加载失败</p>
        <p class="empty-hint retry-hint" @click="refreshData">点击此处重试 ↻</p>
      </template>
      <template v-else>
        <p class="empty-text">没有找到符合条件的基金</p>
        <p class="empty-hint">试试调整筛选条件或关键词</p>
      </template>
    </div>

    <!-- 加载中（首次） -->
    <div class="loading-wrap" v-if="loading && funds.length === 0">
      <span class="loading-text">正在加载基金数据...</span>
    </div>

    <!-- 底部说明 -->
    <div class="bottom-info">
      <p class="bottom-line">
        <span>更新时间：{{ meta.tsq ? fmtUpdateTime(meta.tsq) : (dataLoaded ? '暂无' : '加载中...') }}</span>
      </p>
      <p class="bottom-line">数据来源：公募基金公开数据</p>
      <p class="bottom-line">评分说明：靠谱指数评分为综合收益率、最大回撤、夏普比率、卡玛比率，信息比率，跟踪误差等指标，在全市场排名后加权计算。满分100分，分值越高表现越优秀。</p>
      <p class="bottom-warning">风险提示：评分仅供娱乐，不可作为投资依据，不对任何因此而产生的风险负责。市场有风险，投资需谨慎。</p>
    </div>

    <!-- 详情弹窗 -->
    <Teleport to="body">
      <template v-if="detailFund">
        <div class="mask" @click="detailFund = null"></div>
        <div class="detail-panel">
          <div class="detail-header">
            <span class="detail-name">{{ detailFund.n }}</span>
            <span class="detail-close" @click="detailFund = null">&#x2715;</span>
          </div>
          <div class="detail-body">
            <!-- 基本信息 -->
            <div class="detail-section">
              <div class="attr-row">
                <span class="attr-label">基金代码</span>
                <span class="attr-value">{{ detailFund.c }}</span>
              </div>
              <div class="attr-row">
                <span class="attr-label">分类</span>
                <span class="attr-value">{{ detailFund.t0 }} › {{ detailFund.t1 }}</span>
              </div>
              <div class="attr-row" v-if="detailFund.nav">
                <span class="attr-label">最新净值</span>
                <span class="attr-value">{{ detailFund.nav }}<span v-if="detailFund.date" class="attr-date">（{{ detailFund.date }}）</span></span>
              </div>
              <div class="attr-row" v-if="detailFund.fund_manager">
                <span class="attr-label">基金经理</span>
                <span class="attr-value">{{ detailFund.fund_manager }}</span>
              </div>
              <div class="attr-row" v-if="detailFund.company">
                <span class="attr-label">管理人</span>
                <span class="attr-value">{{ detailFund.company }}</span>
              </div>
              <div class="attr-row" v-if="detailFund.found_date">
                <span class="attr-label">成立日期</span>
                <span class="attr-value">{{ detailFund.found_date }}</span>
              </div>
              <div class="attr-row" v-if="detailFund.share_scale != null">
                <span class="attr-label">份额规模</span>
                <span class="attr-value">{{ fmtScale(detailFund.share_scale) }}</span>
              </div>
              <div class="attr-row" v-if="detailFund.custody_fee != null">
                <span class="attr-label">托管费率</span>
                <span class="attr-value">{{ detailFund.custody_fee }}%/年</span>
              </div>
              <div class="attr-row" v-if="detailFund.sale_fee != null">
                <span class="attr-label">销售服务费率</span>
                <span class="attr-value">{{ detailFund.sale_fee }}%/年</span>
              </div>
            </div>

            <!-- 靠谱分 -->
            <div class="detail-section">
              <span class="detail-section-title">靠谱指数评分（v6）</span>
              <div class="detail-scores-grid">
                <div v-for="p in periods" :key="p.key" class="ds-item">
                  <span class="ds-period">{{ p.label }}</span>
                  <span class="ds-score" :style="scoreColor(detailFund[p.key])">
                    {{ fmtScore(detailFund[p.key]) }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 阶段收益率 -->
            <div class="detail-section" v-if="hasReturns(detailFund)">
              <div class="section-title-row">
                <span class="detail-section-title">阶段收益率</span>
                <span class="section-source">天天基金{{ detailFund.date ? ' · 截至' + detailFund.date : '' }}</span>
              </div>
              <div class="returns-grid">
                <div class="return-col" v-if="detailFund.r0w != null">
                  <span class="ret-label">近1周</span>
                  <span class="ret-value" :class="retCls(detailFund.r0w)">{{ fmtRet(detailFund.r0w) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r1m != null">
                  <span class="ret-label">近1月</span>
                  <span class="ret-value" :class="retCls(detailFund.r1m)">{{ fmtRet(detailFund.r1m) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r3m != null">
                  <span class="ret-label">近3月</span>
                  <span class="ret-value" :class="retCls(detailFund.r3m)">{{ fmtRet(detailFund.r3m) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r6m != null">
                  <span class="ret-label">近6月</span>
                  <span class="ret-value" :class="retCls(detailFund.r6m)">{{ fmtRet(detailFund.r6m) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r1y != null">
                  <span class="ret-label">近1年</span>
                  <span class="ret-value" :class="retCls(detailFund.r1y)">{{ fmtRet(detailFund.r1y) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r2y != null">
                  <span class="ret-label">近2年</span>
                  <span class="ret-value" :class="retCls(detailFund.r2y)">{{ fmtRet(detailFund.r2y) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r3y != null">
                  <span class="ret-label">近3年</span>
                  <span class="ret-value" :class="retCls(detailFund.r3y)">{{ fmtRet(detailFund.r3y) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r5y != null">
                  <span class="ret-label">近5年</span>
                  <span class="ret-value" :class="retCls(detailFund.r5y)">{{ fmtRet(detailFund.r5y) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.ytd != null">
                  <span class="ret-label">今年来</span>
                  <span class="ret-value" :class="retCls(detailFund.ytd)">{{ fmtRet(detailFund.ytd) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.return_all != null">
                  <span class="ret-label">成立以来</span>
                  <span class="ret-value" :class="retCls(detailFund.return_all)">{{ fmtRet(detailFund.return_all) }}</span>
                </div>
              </div>
            </div>

            <!-- 风险指标 -->
            <div class="detail-section" v-if="hasRisk(detailFund)">
              <div class="section-title-row">
                <span class="detail-section-title">风险指标</span>
                <span class="section-source">历史净值回算</span>
              </div>
              <div class="risk-table">
                <div class="risk-head">
                  <span class="risk-th" style="width:60px">周期</span>
                  <span class="risk-th" style="flex:1;text-align:center">最大回撤</span>
                  <span class="risk-th" style="flex:1;text-align:center">夏普比率</span>
                </div>
                <div v-for="rp in riskPeriods" :key="rp.label" class="risk-row"
                  v-show="detailFund[rp.dd] != null || detailFund[rp.sr] != null">
                  <span class="risk-label">{{ rp.label }}</span>
                  <span class="risk-val" :class="ddCls(detailFund[rp.dd])">
                    {{ fmtDD(detailFund[rp.dd]) }}
                  </span>
                  <span class="risk-val">{{ fmtSR(detailFund[rp.sr]) }}</span>
                </div>
              </div>
            </div>

            <!-- 天天基金跳转 -->
            <a :href="eastMoneyUrl(detailFund.c)" target="_blank" class="detail-goto">
              在天天基金查看详情 →
            </a>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 靠谱分说明弹窗 -->
    <Teleport to="body">
      <template v-if="showScoreHelp">
        <div class="mask" @click="showScoreHelp = false"></div>
        <div class="help-panel">
          <div class="help-header">
            <span class="help-title">靠谱指数评分说明（v6）</span>
            <span class="help-close" @click="showScoreHelp = false">&#x2715;</span>
          </div>
          <div class="help-body">
            <div class="help-section">
              <span class="help-desc">
                靠谱指数综合考虑基金的收益率、最大回撤和夏普比率，在全市场中进行百分位排名后加权计算。满分100分，分值越高代表该周期内综合表现越优秀。
              </span>
              <span class="help-desc" style="margin-top:12px;font-weight:600;">
                评分权重：收益排位 50% + 回撤排位 25% + 夏普排位 25%
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">颜色等级（全市场百分位渐变）</span>
              <div class="gradient-legend">
                <div class="gradient-bar"></div>
                <div class="gradient-labels">
                  <span>0分 · 绿（后 50%）</span>
                  <span>50分 · 黄绿（中位）</span>
                  <span>75分 · 橙（前 25%）</span>
                  <span>100分 · 红（前 1%）</span>
                </div>
              </div>
            </div>
            <div class="help-section">
              <span class="help-section-label">参与条件</span>
              <span class="help-desc">
                所有基金均参与评分排名（不再限制收益率>0）。评分基于全市场统一百分位排名，满分100分。
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">数据更新</span>
              <span class="help-desc">
                基金数据每个交易日 21:30 后更新（源自天天基金 FundGuideapi），靠谱分在数据更新后同步重算。净值日期见页面顶部。
              </span>
            </div>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 加入组合选择器 -->
    <Teleport to="body">
      <template v-if="pickerFund">
        <div class="mask" @click="pickerFund = null"></div>
        <div class="picker-panel">
          <div class="picker-header">
            <span class="picker-title">加入组合</span>
            <span class="picker-close" @click="pickerFund = null">&#x2715;</span>
          </div>
          <div class="picker-body">
            <p class="picker-fund-name">{{ pickerFund.name }}（{{ pickerFund.code }}）</p>
            <p class="picker-hint">请选择要加入的自建组合：</p>
            <div class="picker-list" v-if="portfolios && portfolios.length > 0">
              <button
                v-for="p in portfolios"
                :key="p.id"
                class="picker-item"
                @click="confirmAddToPortfolio(p.id)"
              >
                <SvgIcon name="portfolio" :size="18" />
                <span class="picker-item-name">{{ p.name }}</span>
                <span class="picker-item-count">{{ (p.portfolio_data || []).length }} 只基金</span>
              </button>
            </div>
            <div class="picker-empty" v-else>
              <p>暂无自建组合</p>
              <p class="picker-empty-hint">请先在「基金组合」页面创建一个组合</p>
            </div>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted, onActivated } from 'vue'
import { fetchFundScores, fetchFundMeta, fetchFundCategories } from '../../api/data.js'
import { fmtScore, fmtRet, fmtRetPlain, fmtDD, fmtSR, fmtScale, fmtFundScale, fmtManageFee, scoreColor } from '../../utils/format.js'
import { addFundToPortfolio } from '../../api/user-data'
import { useAuth } from '../../composables/useAuth.js'
import { toast } from '../../composables/useToast.js'
import SvgIcon from '../../components/SvgIcon.vue'
const { isLoggedIn, portfolios } = useAuth()

// ========== 常量 ==========
const periods = [
  { key: 'k0w', label: '1周' },
  { key: 'k1m', label: '1月' },
  { key: 'k3m', label: '3月' },
  { key: 'k6m', label: '6月' },
  { key: 'k1',  label: '1年' },
  { key: 'k2',  label: '2年' },
  { key: 'k3',  label: '3年' },
  { key: 'k5',  label: '5年' },
]

// 默认显示周期 + 可选额外周期
const defaultPeriodKeys = ['k1', 'k2', 'k3', 'k5']   // 默认显示：1年/2年/3年/5年
const extraPeriod = ref('')                      // 用户自选的第4列周期

const displayPeriods = computed(() => {
  const result = periods.filter(p => defaultPeriodKeys.includes(p.key))
  if (extraPeriod.value) {
    const ep = periods.find(p => p.key === extraPeriod.value)
    if (ep) result.push(ep)
  }
  return result
})

// 可选周期（排除默认已显示的）
const availableExtraPeriods = computed(() =>
  periods.filter(p => !defaultPeriodKeys.includes(p.key))
)

const riskPeriods = [
  { label: '近1年', dd: 'dd1y', sr: 'sr1y' },
  { label: '近2年', dd: 'dd2y', sr: 'sr2y' },
  { label: '近3年', dd: 'dd3y', sr: 'sr3y' },
  { label: '近5年', dd: 'dd5y', sr: 'sr5y' },
]

// 分类数据源：动态取自 fund_scores 的 t0（一级分类）与 t1_tt（二级分类）
// 通过 Supabase RPC get_fund_categories() 聚合，保证筛选项与数据完全一致
const catLoading = ref(false)
const t0List = ref([])   // [{ value, label, cnt }]
const t1Map = ref({})    // { [t0]: [{ value, label, cnt }] }

async function fetchCategories() {
  catLoading.value = true
  try {
    const data = await fetchFundCategories()
    const t0Arr = (data && data.t0) || []
    const t1Arr = (data && data.t1) || []
    // 一级分类
    t0List.value = t0Arr.map(x => ({ value: x.t0, label: x.t0, cnt: x.cnt }))
    // 二级分类按 t0 分组
    const map = {}
    for (const x of t1Arr) {
      if (!x.t1_tt) continue
      if (!map[x.t0]) map[x.t0] = []
      map[x.t0].push({ value: x.t1_tt, label: x.t1_tt, cnt: x.cnt })
    }
    t1Map.value = map
  } catch (e) {
    console.error('[fund-rank] fetchCategories error', e)
  } finally {
    catLoading.value = false
  }
}

// ========== 响应式断点 ==========
const isMobile = ref(window.innerWidth < 641)
function onResize() { isMobile.value = window.innerWidth < 641 }

// ========== 状态 ==========
const funds = ref([])
const meta = ref({})

// 分类筛选
const filterT0 = ref('')
const filterT1 = ref('')

// 更多筛选
const showMoreFilter = ref(false)
const filterSC = ref('')
const filterETF = ref('')
const filterLOF = ref('')
const filterFOF = ref('')
const filterCN = ref('')       // 场内：''全部 '1'是(ETF/LOF/REITs不计联接) '0'否(场外+ETF联接)
const filterDK = ref('')
const filterDailyLimit = ref('')
const filterSG = ref('')       // 申购状态：''全部 '1'可申购 '0'暂停申购
const filterScaleMin = ref('')  // 基金规模区间（亿元）最小值
const filterScaleMax = ref('')  // 基金规模区间（亿元）最大值
const scalePreset = ref('all')  // 规模预设：all/gt2/2to5/5to10/10to20/20to50/50to100/gt100/custom
const SCALE_PRESETS = [
  { key: 'all',     label: '全部',      min: '',   max: '' },
  { key: 'gt2',     label: '大于2亿',   min: 2,    max: '' },
  { key: '2to5',    label: '2-5亿',     min: 2,    max: 5 },
  { key: '5to10',   label: '5-10亿',    min: 5,    max: 10 },
  { key: '10to20',  label: '10-20亿',   min: 10,   max: 20 },
  { key: '20to50',  label: '20-50亿',   min: 20,   max: 50 },
  { key: '50to100', label: '50-100亿',  min: 50,   max: 100 },
  { key: 'gt100',   label: '100亿以上', min: 100,  max: '' },
  { key: 'custom',  label: '自定义',    min: null, max: null },
]

// 评分指标权重（6项）
const showScoreIndicator = ref(false)
const DEFAULT_WEIGHTS = { ret: 50, dd: 25, sr: 25, calmar: 0, ir: 0, te: 0 }
const weightItems = reactive([
  { key: 'ret',    label: '区间收益', value: DEFAULT_WEIGHTS.ret },
  { key: 'dd',     label: '最大回撤', value: DEFAULT_WEIGHTS.dd },
  { key: 'sr',     label: '夏普比率', value: DEFAULT_WEIGHTS.sr },
  { key: 'calmar', label: '卡玛比例', value: DEFAULT_WEIGHTS.calmar },
  { key: 'ir',     label: '信息比率', value: DEFAULT_WEIGHTS.ir },
  { key: 'te',     label: '跟踪误差', value: DEFAULT_WEIGHTS.te },
])
const weightSum = computed(() => weightItems.reduce((s, i) => s + (Number(i.value) || 0), 0))

function resetWeights() {
  weightItems.forEach(i => { i.value = DEFAULT_WEIGHTS[i.key] })
}

function applyCustomWeights() {
  if (weightSum.value !== 100) return
  showScoreIndicator.value = false
  // Re-fetch with updated weights (custom weight scoring computed client-side)
  loadData(true)
}

// 评分指标弹窗操作
function cancelScoreIndicator() {
  showScoreIndicator.value = false
}

function applyScoreIndicator() {
  applyCustomWeights()
}

// 搜索/周期/分页/排序
const searchText = ref('')
const currentPeriod = ref('k1')     // 默认按 1 年排序（用户可切换到 k3/k5/k_all 等）
const sortAsc = ref(false)        // 靠谱指数排序方向（false=降序，true=升序）
const sortField = ref('')          // 客户端排序列（非评分列）：'c'|'n'|'equityPct'|'bondPct'
const sortDir = ref('desc')        // 客户端排序方向
const page = ref(1)
const pageSize = 100
const hasMore = ref(false)
const loading = ref(false)
const dataLoaded = ref(false)
const loadError = ref(false)
const refreshing = ref(false)
const totalCount = ref(null)      // 当前筛选条件下后端总数（来自 Supabase count）

// 弹窗
const detailFund = ref(null)
const showScoreHelp = ref(false)

// ========== 计算属性：分类联动（数据来自 RPC，已存 t0List / t1Map ref）==========
const t1List = computed(() => {
  if (!filterT0.value) return []
  // 货币型无 t1_tt，二级分类用自身「货币基金」表示（点击等同于按 t0='货币型' 过滤）
  if (filterT0.value === '货币型') {
    const cnt = (t0List.value.find(x => x.value === '货币型') || {}).cnt || 0
    return [{ value: '', label: '货币基金', cnt }]
  }
  return t1Map.value[filterT0.value] || []
})


// ========== 点赞 / 吐槽（localStorage 持久化） ==========
const LS_LIKES_KEY = 'af_fund_likes'
const LS_DISLIKES_KEY = 'af_fund_dislikes'

function loadLikes() {
  try { return JSON.parse(localStorage.getItem(LS_LIKES_KEY) || '{}') } catch { return {} }
}
function loadDislikes() {
  try { return JSON.parse(localStorage.getItem(LS_DISLIKES_KEY) || '{}') } catch { return {} }
}
function saveLikes(m) { localStorage.setItem(LS_LIKES_KEY, JSON.stringify(m)) }
function saveDislikes(m) { localStorage.setItem(LS_DISLIKES_KEY, JSON.stringify(m)) }

const likesMap = ref(loadLikes())       // { [code]: count }
const dislikedSet = ref(new Set(Object.keys(loadDislikes())))

function persistLikes() { saveLikes(likesMap.value) }
function persistDislikes() { saveDislikes(Object.fromEntries([...dislikedSet.value].map(c => [c, 1]))) }

function thumbUp(fund) {
  const c = fund.c
  if (dislikedSet.value.has(c)) dislikedSet.value.delete(c)
  const cur = (likesMap.value[c] || 0)
  if (cur > 0) {
    // 已点赞：取消
    delete likesMap.value[c]
  } else {
    // 未点赞：+1
    likesMap.value[c] = cur + 1
  }
  likesMap.value = { ...likesMap.value }
  dislikedSet.value = new Set(dislikedSet.value)
  persistLikes()
  persistDislikes()
}

function thumbDown(fund) {
  const c = fund.c
  if (likesMap.value[c]) delete likesMap.value[c]
  if (dislikedSet.value.has(c)) {
    dislikedSet.value.delete(c)
  } else {
    dislikedSet.value.add(c)
  }
  likesMap.value = { ...likesMap.value }
  dislikedSet.value = new Set(dislikedSet.value)
  persistLikes()
  persistDislikes()
}

// ========== 加入组合选择器 ==========
const pickerFund = ref(null)        // 当前要添加的基金 { code, name }

function openPortfolioPicker(fund) {
  if (!isLoggedIn.value) {
    toast('请先登录', 'error')
    return
  }
  pickerFund.value = { code: fund.c, name: fund.n || ('基金' + fund.c) }
}
async function confirmAddToPortfolio(portfolioId) {
  if (!pickerFund.value) return
  const f = pickerFund.value
  const result = await addFundToPortfolio(f.code, f.name, portfolioId)
  if (result.success) {
    toast(result.message, 'success')
  } else {
    toast(result.message || result.error || '添加失败', 'error')
  }
  pickerFund.value = null
}

function retCls(v) {
  const n = parseFloat(v) || 0
  if (n > 0) return 'ret-up'
  if (n < 0) return 'ret-down'
  return ''
}

function ddCls(v) {
  if (v == null) return ''
  const n = parseFloat(v)
  if (n <= -20) return 'risk-high'
  if (n <= -10) return 'risk-mid'
  return 'risk-low'
}

// ========== 份额类别提取（基于基金名称末尾大写字母） ==========
function hasReturns(f) {
  return f.r1y != null || f.r3y != null || f.ytd != null
}

function hasRisk(f) {
  return riskPeriods.some(p => f[p.dd] != null || f[p.sr] != null)
}

function eastMoneyUrl(code) {
  if (!code) return '#'
  const pureCode = code.replace(/\.of$/i, '').replace(/\.OF$/, '')
  return `https://fund.eastmoney.com/${pureCode}.html`
}

function fmtUpdateTime(tsq) {
  if (!tsq) return ''
  try {
    const d = new Date(tsq)
    return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
  } catch { return '' }
}

// ========== 份额类别提取（基于基金名称，排除产品类型关键词） ==========
// 产品类型关键词（ETF/LOF/FOF/QDII/REITs 不是份额类别！）
// 按长关键词优先顺序排列，避免 ETF联接 被误剥离为 ETF
const PRODUCT_TYPE_KEYWORDS = ['ETF联接', 'ETF', 'LOF', 'FOF', 'QDII', 'REITs', 'REIT']
// 有效份额类别字母
const VALID_SHARE_CLASSES = ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'R', 'T', 'Y']

/** 判断名称是否为场内产品（ETF不含联接/LOF/REITs） */
function isExchangeListed(name) {
  if (!name) return false
  return (name.includes('ETF') && !name.includes('ETF联接')) || name.includes('LOF') || name.includes('REIT')
}

/** 从基金名称提取份额类别字母，排除 ETF/LOF/FOF/QDII/REITs 等产品类型 */
function extractShareClass(name) {
  if (!name) return ''
  let clean = name
  // 剥离末尾的产品类型关键词
  for (const kw of PRODUCT_TYPE_KEYWORDS) {
    if (clean.endsWith(kw)) {
      clean = clean.slice(0, -kw.length)
      break  // 只剥离一个产品类型（不循环复用）
    }
  }
  // 提取末尾大写字母作为份额类别
  const match = clean.match(/([A-Z])$/)
  if (match && VALID_SHARE_CLASSES.includes(match[1])) {
    return match[1]
  }
  return ''
}

const shareClassOptions = VALID_SHARE_CLASSES

// ========== 数据加载 ==========
const LOAD_TIMEOUT_MS = 60000 // 60 秒超时（Supabase 免费档偶尔响应偏慢，给足时间避免误报 0 只）
const MAX_RETRIES = 1           // 失败后自动重试 1 次

function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('请求超时（' + ms / 1000 + 's）')), ms))
  ])
}

async function loadData(reset = true, _retryCount = 0) {
  if (loading.value && _retryCount === 0) return
  loading.value = true
  loadError.value = false
  if (reset) page.value = 1

  try {
    // 确定 t0 过滤（FOF 类型筛选用 t0_eq）
    let t0Filter = filterT0.value || undefined
    if (filterFOF.value === '1') t0Filter = 'FOF'
    if (filterFOF.value === '0' && !filterT0.value) t0Filter = undefined

    // t0（一级分类）/ t1（二级分类 t1_tt）直接来自 fund_scores，服务端按总表过滤
    const result = await withTimeout(fetchFundScores({
      t0: t0Filter,
      t1: filterT1.value || undefined,
      search: buildSearchText(),
      kKey: currentPeriod.value,
      sortAsc: sortAsc.value,
      page: page.value,
      pageSize,
      etf: filterETF.value || undefined,
      lof: filterLOF.value || undefined,
      dk: filterDK.value || undefined,
      sg: filterSG.value || undefined,
      dailyLimit: filterDailyLimit.value || undefined,
      scaleMin: filterScaleMin.value !== '' ? parseFloat(filterScaleMin.value) : undefined,
      scaleMax: filterScaleMax.value !== '' ? parseFloat(filterScaleMax.value) : undefined,
    }), LOAD_TIMEOUT_MS)

    if (result.data) {
      // 服务端过滤后的真实总数（已含 t0/t1/search 及下推的 ETF/LOF/定开/申购状态/±20%）
      if (result.count != null) totalCount.value = result.count
      // 前端补充筛选（仅保留无法服务端下推的份额类别/场内，其余已在服务端过滤）
      let filtered = result.data
      // 份额类别（名称末尾字母，排除产品类型关键词）
      if (filterSC.value) filtered = filtered.filter(f => extractShareClass(f.n) === filterSC.value)
      // 场内（ETF不含联接/LOF/REITs → 是；其余含ETF联接 → 否）
      if (filterCN.value === '1') filtered = filtered.filter(f => isExchangeListed(f.n))
      if (filterCN.value === '0') filtered = filtered.filter(f => !isExchangeListed(f.n))

      funds.value = reset ? filtered : funds.value.concat(filtered)
      hasMore.value = result.data.length >= pageSize
    }
  } catch (e) {
    console.error('[fund-rank] load error', e)
    if (_retryCount < MAX_RETRIES) {
      // 自动重试一次（网络抖动 / DNS / 限流等瞬时问题）
      console.warn('[fund-rank] retrying...', _retryCount + 1, '/', MAX_RETRIES)
      return loadData(reset, _retryCount + 1)
    }
    loadError.value = true
  } finally {
    loading.value = false
    dataLoaded.value = true
  }
}

function buildSearchText() {
  return searchText.value || undefined
}

async function loadMeta() {
  try {
    const m = await fetchFundMeta()
    if (m) meta.value = m
    else console.warn('[fund-rank] meta: no data')
  } catch (e) {
    console.error('[fund-rank] meta load error:', e)
  }
}

async function refreshData() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await Promise.all([loadData(true), loadMeta()])
  } finally {
    refreshing.value = false
  }
}

// ========== 交互 ==========
function setT0(val) {
  filterT0.value = val
  filterT1.value = ''
  clearMoreFilters()
  loadData(true)
}

function setT1(val) {
  filterT1.value = val
  loadData(true)
}

/** 清除所有更多筛选条件 */
function clearMoreFilters() {
  filterSC.value = ''
  filterCN.value = ''
  filterETF.value = ''
  filterLOF.value = ''
  filterFOF.value = ''
  filterDK.value = ''
  filterDailyLimit.value = ''
  filterSG.value = ''
  filterScaleMin.value = ''
  filterScaleMax.value = ''
  scalePreset.value = 'all'
}

// ========== 更多筛选弹窗（确认后才查询，取消恢复） ==========
let moreFilterSnapshot = null

function openMoreFilter() {
  moreFilterSnapshot = {
    sc: filterSC.value, etf: filterETF.value, lof: filterLOF.value, fof: filterFOF.value,
    cn: filterCN.value, dk: filterDK.value, dl: filterDailyLimit.value, sg: filterSG.value,
    smin: filterScaleMin.value, smax: filterScaleMax.value, t0: filterT0.value, t1: filterT1.value,
    sp: scalePreset.value,
  }
  showMoreFilter.value = true
}

function cancelMoreFilter() {
  if (moreFilterSnapshot) {
    filterSC.value = moreFilterSnapshot.sc
    filterETF.value = moreFilterSnapshot.etf
    filterLOF.value = moreFilterSnapshot.lof
    filterFOF.value = moreFilterSnapshot.fof
    filterCN.value = moreFilterSnapshot.cn
    filterDK.value = moreFilterSnapshot.dk
    filterDailyLimit.value = moreFilterSnapshot.dl
    filterSG.value = moreFilterSnapshot.sg
    filterScaleMin.value = moreFilterSnapshot.smin
    filterScaleMax.value = moreFilterSnapshot.smax
    filterT0.value = moreFilterSnapshot.t0
    filterT1.value = moreFilterSnapshot.t1
    scalePreset.value = moreFilterSnapshot.sp
  }
  showMoreFilter.value = false
}

function applyMoreFilters() {
  showMoreFilter.value = false
  loadData(true)
}

function resetMoreFilters() {
  clearMoreFilters()
  scalePreset.value = 'all'
}

// 弹窗内筛选只改本地状态，确认后才查询
function mToggleSC(val) { filterSC.value = filterSC.value === val ? '' : val }
function mToggleCN(val) { filterCN.value = filterCN.value === val ? '' : val }
function mToggleSG(val) { filterSG.value = filterSG.value === val ? '' : val }
function mToggleDailyLimit(val) { filterDailyLimit.value = filterDailyLimit.value === val ? '' : val }
function mToggleFlag(type, val) {
  const map = { ETF: filterETF, LOF: filterLOF, FOF: filterFOF, DK: filterDK }
  const r = map[type]
  if (!r) return
  const next = r.value === val ? '' : val
  r.value = next
  if (type === 'FOF' && next === '1') { filterT0.value = ''; filterT1.value = '' }
}

function pickScalePreset(key) {
  scalePreset.value = key
  if (key === 'custom') return
  const p = SCALE_PRESETS.find(x => x.key === key)
  if (!p) return
  filterScaleMin.value = p.min
  filterScaleMax.value = p.max
}

function onScaleInput() {
  // 手动修改规模输入框视为自定义
  scalePreset.value = 'custom'
}

const activeMoreFilterCount = computed(() => {
  let n = 0
  if (filterSC.value) n++
  if (filterETF.value) n++
  if (filterLOF.value) n++
  if (filterFOF.value) n++
  if (filterCN.value) n++
  if (filterDK.value) n++
  if (filterDailyLimit.value) n++
  if (filterSG.value) n++
  if (filterScaleMin.value !== '' && filterScaleMin.value != null) n++
  if (filterScaleMax.value !== '' && filterScaleMax.value != null) n++
  return n
})

function switchPeriod(key) {
  sortField.value = ''  // 切换到服务端排序，清除客户端排序
  if (currentPeriod.value === key) {
    // 已选中：切换升降序
    sortAsc.value = !sortAsc.value
  } else {
    // 新选中：默认降序（高分在前）
    currentPeriod.value = key
    sortAsc.value = false
  }
  loadData(true)
}

/** 客户端列排序（代码/简称/规模/权益%/债券%） */
function toggleColumnSort(field) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = 'asc'  // 首次点击默认升序
  }
}

/** 收益涨跌幅颜色：涨红跌绿（中国习惯），0/空为次要文本色 */
function retColor(v) {
  if (v == null) return 'var(--text-secondary)'
  const n = parseFloat(v)
  if (isNaN(n) || n === 0) return 'var(--text-secondary)'
  return n > 0 ? '#d4351c' : '#00703c'
}

/** 排序后的基金列表 */
const sortedFunds = computed(() => {
  if (!sortField.value) return funds.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  const key = sortField.value
  return [...funds.value].sort((a, b) => {
    let va = a[key], vb = b[key]
    if (va == null) va = dir > 0 ? Infinity : -Infinity
    if (vb == null) vb = dir > 0 ? Infinity : -Infinity
    if (typeof va === 'string') va = va.toLowerCase()
    if (typeof vb === 'string') vb = vb.toLowerCase()
    return va > vb ? dir : va < vb ? -dir : 0
  })
})

function doSearch() { loadData(true) }

function clearSearch() {
  searchText.value = ''
  loadData(true)
}

function loadMore() {
  if (!loading.value && hasMore.value) {
    page.value++
    loadData(false)
  }
}

function openDetail(fund) {
  detailFund.value = { ...fund }
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  fetchCategories()
  loadData()
  loadMeta()
})
onActivated(() => {
  // keep-alive 缓存激活时：数据已存在（秒开），仅刷新 meta（更新时间）
  loadMeta()
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
/* ========== gov.uk 风格靠谱指数 ========== */
.page-fund-rank { min-height: 100vh; }

/* 顶部栏 */
.top-bar {
  display: flex; align-items: center; gap: var(--space-md);
  padding: var(--space-md); border-bottom: 1px solid var(--border);
  background: #ffffff;
}
.top-title-row { display: flex; align-items: baseline; gap: 6px; flex-shrink: 0; }
.top-title-text { font-size: 24px; font-weight: 700; color: var(--text-primary); }
@media (min-width: 641px) { .top-title-text { font-size: 36px; } }

.help-icon-btn {
  width: 24px; height: 24px; line-height: 24px; text-align: center;
  font-size: 14px; color: var(--text-secondary);
  border: 2px solid var(--text-secondary); cursor: pointer;
  flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center;
}

.search-box { flex: 1; position: relative; width: 100%; }
.search-input {
  width: 100%; padding: 8px 36px 8px 8px;
  border: 2px solid #1d70b8; font-size: 16px;
  color: var(--text-primary); outline: none; box-sizing: border-box;
}
.search-input:focus { outline: 3px solid #ffdd00; outline-offset: 0; }
.search-input::placeholder { color: var(--text-secondary); }
.search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  color: var(--text-secondary); font-size: 14px; cursor: pointer;
}

/* 数据信息条 */
.data-info-bar {
  display: flex; flex-direction: column; align-items: flex-start;
  padding: var(--space-sm) var(--space-md); background: #ffffff;
  border-bottom: 1px solid var(--border); font-size: 14px; color: var(--text-secondary);
}
.data-info-row { display: flex; align-items: center; gap: var(--space-sm); }
.data-refresh {
  margin-left: var(--space-sm); padding: 2px 8px;
  font-size: 14px; color: var(--link); cursor: pointer; text-decoration: underline;
}
.data-refresh.refreshing { opacity: 0.5; }

/* 筛选区 */
.filter-section { background: #ffffff; border-bottom: 1px solid var(--border); }
.filter-row { display: flex; align-items: flex-start; padding: var(--space-sm) var(--space-md); gap: var(--space-sm); }
.filter-label {
  font-size: 14px; color: var(--text-secondary); font-weight: 700;
  flex-shrink: 0; padding-top: 4px;
}
.filter-select {
  padding: 6px 12px; font-size: 16px; border: 1px solid var(--border);
  background: #fff; color: var(--text-primary); flex: 1; max-width: 100%;
  -webkit-appearance: none; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23505a5f' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
  padding-right: 30px; cursor: pointer;
}
.filter-select:focus { outline: 3px solid #ffdd00; outline-offset: 0; }
.filter-chips { display: flex; flex-wrap: wrap; gap: 0; flex: 1; }
.filter-chip {
  padding: 4px 12px; font-size: 16px; color: var(--link);
  cursor: pointer; text-decoration: underline; text-underline-offset: 4px;
  text-decoration-color: transparent; transition: text-decoration-color 0.15s;
}
.filter-chip:hover { text-decoration-color: var(--link); }
.filter-chip.active {
  color: #1d70b8; font-weight: 700; text-decoration: none;
  border-bottom: 4px solid #1d70b8; padding-bottom: 0;
}
.chip-cnt {
  font-size: 12px; font-weight: 400; color: var(--text-secondary);
  margin-left: 4px; font-variant-numeric: tabular-nums;
}
.filter-chip.active .chip-cnt { color: #1d70b8; }
.more-chip { position: relative; }
.source-dropdown {
  position: absolute; top: 100%; left: 0; z-index: 100;
  background: #fff; border: 1px solid var(--border); min-width: 160px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.source-drop-item {
  padding: var(--space-sm) var(--space-md); font-size: 14px; cursor: pointer;
  color: var(--text-primary); text-decoration: none;
}
.source-drop-item:hover { background: #f3f2f1; }
.source-drop-item.disabled { color: var(--text-secondary); cursor: not-allowed; }

.more-filter-toggle {
  display: flex; align-items: center; gap: 4px;
  padding: var(--space-sm) var(--space-md); font-size: 16px; color: var(--link);
  cursor: pointer; text-decoration: underline;
}
.filter-action-btn {
  display: flex; align-items: center; gap: 4px;
  padding: var(--space-sm) var(--space-md); font-size: 16px; color: var(--link);
  cursor: pointer; text-decoration: underline; text-underline-offset: 4px;
}
.filter-action-btn:hover { color: #1d70b8; }
.filter-action-btn .wt-icon { display: inline-flex; }
.toggle-arrow { display: inline-block; transition: transform 0.2s; font-size: 16px; }
.toggle-arrow.open { transform: rotate(180deg); }
.filter-scale-range { display: flex; align-items: center; gap: 6px; flex: 1; }
.scale-input {
  width: 80px; padding: 4px 8px; font-size: 14px;
  border: 1px solid var(--border); background: #fff; color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.scale-input:focus { outline: 3px solid #ffdd00; outline-offset: 0; }
.scale-dash { color: var(--text-secondary); }
.scale-unit { font-size: 14px; color: var(--text-secondary); }
.filter-tip { padding: var(--space-sm) var(--space-md); font-size: 14px; color: var(--text-secondary); }

/* 周期Tab - 已移除 toolbar 行，周期选择通过表头点击完成 */

.filter-result-row {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-md);
  padding: var(--space-sm) var(--space-md); background: #f3f2f1;
  border-top: 1px solid var(--border);
}
.filter-result-left { display: flex; align-items: center; gap: var(--space-md); flex-wrap: wrap; }
.filter-result-count { font-size: 16px; color: var(--text-secondary); }
.filter-result-count strong { color: #0b0c0c; font-weight: 700; }
.filter-update-time { font-size: 13px; color: var(--text-secondary); }
.filter-update-time::before { content: '·'; margin-right: 6px; }

/* 基金列表 - 横向滚动表格 */
.fund-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-top: 1px solid var(--border);
  position: relative;
}
.fund-table-wrap::-webkit-scrollbar {
  height: 8px; width: 8px;
}
.fund-table-wrap::-webkit-scrollbar-thumb {
  background: #b1b4b6; border-radius: 4px;
}
.fund-table-wrap::-webkit-scrollbar-thumb:hover { background: #808185; }
.fund-table-wrap::-webkit-scrollbar-track {
  background: #f3f2f1;
}
.fund-table {
  width: 100%; border-collapse: collapse; font-size: 14px; white-space: nowrap;
  min-width: 860px; table-layout: fixed;
}
.fund-table thead { background: #f3f2f1; }
.fund-table th {
  padding: var(--space-xs) 6px; text-align: center;
  font-size: 13px; font-weight: 700; color: var(--text-primary);
  border-bottom: 2px solid var(--border);
  position: sticky; top: 0; background: #f3f2f1; z-index: 1;
}
.fund-table td {
  padding: 5px 6px; border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.fund-row:hover { background: #f8f8f8; }

.col-code { width: 80px; font-weight: 700; color: var(--text-primary); font-family: monospace; font-size: 12px; }
.col-code a { color: var(--text-primary); text-decoration: none; }
.col-code a:hover { color: var(--link); text-decoration: underline; }
/* 固定首列 */
.fund-table th.col-code {
  position: sticky; left: 0; z-index: 3;
}
.fund-table td.col-code {
  position: sticky; left: 0; z-index: 1; background: #fff;
}
.fund-row:hover td.col-code {
  background: #f8f8f8;
}
.col-name { width: 156px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-name a { color: var(--text-primary); text-decoration: none; }
.col-name a:hover { color: var(--link); text-decoration: underline; }
.col-manager { width: 96px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-manager.sortable { cursor: pointer; user-select: none; }
.col-manager.sortable:hover { background: #e0e7ef; }
.col-scale { width: 115px; text-align: right; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.col-scale.sortable { cursor: pointer; user-select: none; }
.col-scale.sortable:hover { background: #e0e7ef; }
.col-num { width: 80px; text-align: right; color: var(--text-secondary); }
.col-pct { width: 60px; text-align: right; color: var(--text-secondary); }
.col-score { width: 52px; text-align: center; }
.col-score .score-val { font-weight: 700; font-size: 13px; }
.col-sort { background: #e8f0fe; }
.col-actions { width: 90px; text-align: center; }
.col-fee { width: 80px; text-align: right; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.col-t1 { width: 120px; color: var(--text-secondary); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-ret { width: 84px; text-align: right; color: var(--text-secondary); font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }
.col-ret.sortable { cursor: pointer; user-select: none; }
.col-ret.sortable:hover { background: #e0e7ef; }

/* ===== 移动端卡片布局 ===== */
.mobile-fund-list {
  border-top: 1px solid var(--border);
}

.fund-card {
  padding: var(--space-md); border-bottom: 1px solid var(--border);
  background: #fff;
}
.fund-card:active { background: #f3f2f1; }

.fund-card-top {
  display: flex; align-items: center; gap: var(--space-sm);
}

.fund-code {
  font-size: 13px; font-weight: 700; color: var(--text-primary);
  font-family: monospace; flex-shrink: 0; min-width: 56px;
  text-decoration: none;
}
.fund-code:hover { color: var(--link); text-decoration: underline; }

.fund-name {
  flex: 1; font-size: 15px; font-weight: 700; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  min-width: 0; line-height: 1.4; text-decoration: none;
}
.fund-name:hover { color: var(--link); text-decoration: underline; }

.fund-card-mgr {
  font-size: 13px; color: var(--text-secondary);
  margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.fund-card-scale {
  font-size: 13px; color: var(--text-secondary);
  margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.fund-card-ret {
  display: flex; flex-wrap: wrap; gap: 4px 14px;
  font-size: 12px; color: var(--text-secondary); margin-top: 4px;
}
.fund-card-ret span { font-weight: 700; }

.fund-card-actions {
  display: flex; align-items: center; gap: 2px; flex-shrink: 0;
}

.action-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; cursor: pointer; color: var(--text-muted);
}
.action-icon:active, .action-icon.active { color: #d4351c; }

.fund-card-scores {
  display: flex; gap: var(--space-sm); margin-top: 8px;
  flex-wrap: wrap;
}

.score-chip {
  display: flex; align-items: center; gap: 3px;
  padding: 3px 10px; border: 1px solid var(--border);
  background: #f8f8f8;
}

.score-chip-active {
  border-color: #1d70b8; background: #e8f0fe;
  box-shadow: inset 0 0 0 1px #1d70b8;
}

.chip-label {
  font-size: 11px; color: var(--text-secondary); font-weight: 400;
}

.chip-val {
  font-size: 14px; font-weight: 700;
}

/* 可排序表头 */
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { background: #e0e7ef; }
.th-arrow { font-size: 11px; margin-left: 3px; color: #1d70b8; }

/* 渐变色条图例 */
.gradient-legend { margin-top: 8px; }
.gradient-bar {
  height: 12px; border-radius: 6px;
  background: linear-gradient(to right,
    hsl(120, 85%, 45%),   /* 0分 绿 */
    hsl(90, 85%, 45%),    /* 25分 */
    hsl(60, 85%, 45%),    /* 50分 黄绿 */
    hsl(30, 85%, 45%),    /* 75分 橙 */
    hsl(0, 85%, 45%)      /* 100分 红 */
  );
}
.gradient-labels {
  display: flex; justify-content: space-between;
  margin-top: 6px; font-size: 11px; color: var(--text-secondary);
}

.action-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; cursor: pointer; color: var(--text-muted);
  vertical-align: middle; margin: 0 2px; position: relative;
}
.action-btn:hover { color: var(--brand); }
.action-btn.active { color: #d4351c; }
.action-add:hover { color: #00703c; }
.action-count {
  position: absolute; top: -6px; right: -8px;
  font-size: 10px; line-height: 14px; padding: 0 3px;
  background: #d4351c; color: #fff; border-radius: 7px;
  font-weight: 700; min-width: 14px; text-align: center;
}
.action-count-sm {
  font-size: 9px; margin-left: 1px; color: #d4351c; font-weight: 700;
}

/* 加载更多 */
.load-more {
  text-align: center; padding: var(--space-lg);
  font-size: 16px; color: var(--link); cursor: pointer; text-decoration: underline;
}
.load-more:hover { background: #f3f2f1; }
.loaded-all {
  padding: var(--space-md); text-align: center; font-size: 14px; color: var(--text-secondary);
  border-top: 1px solid var(--border);
}
.loaded-all strong { color: #0b0c0c; font-weight: 700; }

/* 筛选操作行：更多筛选 + 评分指标 并列 */
.filter-actions-row {
  display: flex; align-items: center; gap: var(--space-md);
}

/* 显示周期选择器 */
.period-select-row {
  display: flex; align-items: center; gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  background: #f3f2f1;
  flex-wrap: wrap;
}
.period-select-label {
  font-size: 14px; color: var(--text-secondary); font-weight: 700;
}
.period-tag {
  display: inline-block; padding: 4px 12px;
  font-size: 14px; color: var(--link);
  cursor: pointer; border: 1px solid var(--border);
  background: #fff;
}
.period-tag:hover { border-color: #1d70b8; }
.period-tag.active {
  color: #fff; background: #1d70b8; border-color: #1d70b8;
}
.period-select {
  padding: 4px 8px; font-size: 14px;
  border: 1px solid var(--border); color: var(--text-secondary);
  background: #fff; cursor: pointer; margin-left: var(--space-xs);
}
.period-select:focus { border-color: #1d70b8; outline: none; }

/* 状态 */
.empty-state { text-align: center; padding: var(--space-2xl) var(--space-md); }
.empty-text { font-size: 19px; color: var(--text-primary); font-weight: 700; margin-bottom: var(--space-sm); }
.empty-hint { font-size: 16px; color: var(--text-secondary); }
.retry-hint { color: var(--link); cursor: pointer; text-decoration: underline; }
.loading-wrap { display: flex; justify-content: center; padding: var(--space-2xl) 0; }
.loading-text { font-size: 16px; color: var(--text-secondary); }

/* 底部 */
.bottom-info {
  display: flex; flex-direction: column; gap: 4px;
  padding: var(--space-xl) var(--space-md) var(--space-2xl);
  border-top: 1px solid var(--border); margin-top: var(--space-xl);
}
.bottom-line {
  margin: 0; font-size: 14px; color: var(--text-secondary); line-height: 1.6;
}
.bottom-warning {
  margin: 8px 0 0; font-size: 13px; color: #d4351c; line-height: 1.6; font-weight: 700;
}

/* 颜色 */
.ret-up { color: var(--color-up); }
.ret-down { color: var(--color-down); }

/* ===== 弹窗 ===== */
.mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }

/* 更多筛选弹窗 */
.more-modal {
  position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 100%; max-width: 560px; max-height: 82vh;
  background: #ffffff; border: 1px solid var(--border);
  display: flex; flex-direction: column; z-index: 101;
}
.more-modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border);
  background: #f3f2f1; flex-shrink: 0;
}
.more-modal-title { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.more-modal-close { font-size: 24px; color: var(--text-primary); cursor: pointer; padding: 4px; line-height: 1; }
.more-modal-body { flex: 1; overflow-y: auto; padding: var(--space-sm) 0; }
.more-modal-footer {
  display: flex; justify-content: flex-end; gap: var(--space-sm);
  padding: var(--space-md) var(--space-lg); border-top: 1px solid var(--border);
  flex-shrink: 0; background: #ffffff;
}
.more-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px;
  background: #1d70b8; color: #fff; font-size: 12px; font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.filter-scale-presets { display: flex; flex-wrap: wrap; gap: 0; flex: 1; }

.detail-panel {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 600px; max-height: 88vh;
  background: #ffffff; border: 1px solid var(--border);
  overflow: hidden; display: flex; flex-direction: column; z-index: 101;
}
.detail-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border);
  background: #f3f2f1; flex-shrink: 0;
}
.detail-name { font-size: 19px; font-weight: 700; flex: 1; margin-right: var(--space-md); line-height: 1.3; }
.detail-close { font-size: 24px; color: var(--text-primary); cursor: pointer; padding: 4px; line-height: 1; }
.detail-body { flex: 1; overflow-y: auto; padding: var(--space-lg); }
.detail-section { margin-bottom: var(--space-xl); }
.detail-section-title {
  font-size: 19px; font-weight: 700; color: var(--text-primary);
  display: block; margin-bottom: var(--space-md);
  border-bottom: 2px solid var(--border); padding-bottom: 4px;
}
.section-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
.section-source { font-size: 14px; color: var(--text-secondary); }
.attr-row { display: flex; justify-content: space-between; padding: var(--space-sm) 0; border-bottom: 1px solid var(--border); }
.attr-label { font-size: 16px; color: var(--text-secondary); flex-shrink: 0; width: 80px; }
.attr-value { font-size: 16px; color: var(--text-primary); text-align: right; flex: 1; line-height: 1.4; }
.attr-date { font-size: 14px; color: var(--text-secondary); }

.detail-scores-grid {
  display: flex; justify-content: space-around; padding: var(--space-md);
  border: 1px solid var(--border);
}
.ds-item { display: flex; flex-direction: column; align-items: center; }
.ds-period { font-size: 14px; color: var(--text-secondary); margin-bottom: 4px; }
.ds-score { font-size: 19px; font-weight: 700; }

.returns-grid { display: flex; flex-wrap: wrap; gap: var(--space-md); }
.return-col { display: flex; flex-direction: column; align-items: center; min-width: 70px; padding: var(--space-sm); border: 1px solid var(--border); }
.ret-label { font-size: 14px; color: var(--text-secondary); margin-bottom: 4px; }
.ret-value { font-size: 16px; font-weight: 700; color: var(--text-primary); }

.risk-table { border: 1px solid var(--border); }
.risk-head { display: flex; padding: var(--space-sm); border-bottom: 2px solid var(--border); background: #f3f2f1; }
.risk-th { font-size: 14px; color: var(--text-secondary); font-weight: 700; }
.risk-row { display: flex; align-items: center; padding: var(--space-sm); border-bottom: 1px solid var(--border); }
.risk-row:last-child { border-bottom: none; }
.risk-label { width: 60px; font-size: 14px; color: var(--text-secondary); flex-shrink: 0; font-weight: 700; }
.risk-val { flex: 1; text-align: center; font-size: 16px; font-weight: 700; color: var(--text-primary); }
.risk-val.risk-high { color: #d4351c; }
.risk-val.risk-mid { color: #f47738; }
.risk-val.risk-low { color: #00703c; }

.detail-goto {
  display: block; text-align: center; padding: var(--space-md) 0 var(--space-sm);
  margin-top: var(--space-lg); border-top: 1px solid var(--border);
  font-size: 16px; color: var(--link); font-weight: 700; text-decoration: underline;
}

/* 帮助弹窗 */
.help-panel {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 600px; max-height: 70vh;
  background: #ffffff; border: 1px solid var(--border);
  overflow: hidden; display: flex; flex-direction: column; z-index: 101;
}
.help-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border);
  background: #f3f2f1; flex-shrink: 0;
}
.help-title { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.help-close { font-size: 24px; color: var(--text-primary); cursor: pointer; padding: 4px; line-height: 1; }
.help-body { flex: 1; overflow-y: auto; padding: var(--space-lg); }
.help-section { margin-bottom: var(--space-lg); }
.help-section-label { display: block; font-size: 19px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-sm); border-bottom: 2px solid var(--border); padding-bottom: 4px; }
.help-desc { display: block; font-size: 16px; color: var(--text-primary); line-height: 1.7; }
/* 评分指标弹窗 */
.score-indicator-modal {
  position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
  z-index: 101;
  width: min(480px, 90vw); max-height: 80vh;
  background: #fff; border: 2px solid var(--border);
  display: flex; flex-direction: column;
}
.score-tip {
  font-size: 14px; font-weight: 700; color: var(--text-primary);
  margin-bottom: var(--space-sm); display: flex; align-items: center; gap: var(--space-xs); flex-wrap: wrap;
}

.weight-sliders { display: flex; flex-direction: column; gap: var(--space-sm); }
.weight-row { display: flex; align-items: center; gap: var(--space-sm); }
.weight-label { font-size: 14px; min-width: 80px; color: var(--text-primary); }
.weight-range { flex: 1; height: 6px; -webkit-appearance: none; background: #f3f2f1; outline: none; }
.weight-range::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 18px; background: #1d70b8; cursor: pointer; }
.weight-num { width: 50px; padding: 2px 4px; border: 1px solid var(--border); font-size: 14px; text-align: center; }
.weight-sum { font-size: 14px; margin-left: var(--space-sm); }
.weight-sum.valid { color: #00703c; }
.weight-sum.invalid { color: #d4351c; }

.weight-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-md); }
.btn-reset { padding: var(--space-xs) var(--space-lg); font-size: 14px; background: #f3f2f1; color: var(--text-primary); border: 1px solid var(--border); cursor: pointer; }
.btn-confirm { padding: var(--space-xs) var(--space-lg); font-size: 14px; background: #00703c; color: #fff; border: none; cursor: pointer; }
.btn-confirm:disabled { opacity: 0.5; cursor: not-allowed; }

.weight-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-md); }
.btn-reset {
  background: none; border: 1px solid var(--border); color: var(--text-secondary);
  padding: var(--space-xs) var(--space-md); font-size: 14px; cursor: pointer;
}
.btn-reset:hover { background: #f3f2f1; }

/* 分类源禁用 */
.filter-chip.disabled { color: var(--text-secondary); opacity: 0.5; cursor: not-allowed; }

/* ===== 组合选择器弹窗 ===== */
.picker-panel {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 440px; max-height: 70vh;
  background: #ffffff; border: 2px solid #1d70b8;
  overflow: hidden; display: flex; flex-direction: column; z-index: 101;
}
.picker-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-md) var(--space-lg); border-bottom: 2px solid var(--border);
  background: #f3f2f1; flex-shrink: 0;
}
.picker-title { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.picker-close { font-size: 24px; color: var(--text-primary); cursor: pointer; padding: 4px; line-height: 1; }
.picker-body { flex: 1; overflow-y: auto; padding: var(--space-lg); }
.picker-fund-name { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-sm); }
.picker-hint { font-size: 14px; color: var(--text-secondary); margin-bottom: var(--space-md); }
.picker-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.picker-item {
  display: flex; align-items: center; gap: var(--space-sm);
  width: 100%; padding: var(--space-sm) var(--space-md);
  border: 2px solid var(--border); background: #fff;
  cursor: pointer; text-align: left; font-size: 15px;
  color: var(--text-primary); font-weight: 600;
}
.picker-item:hover { border-color: #1d70b8; background: #e8f0fe; }
.picker-item-name { flex: 1; }
.picker-item-count { font-size: 13px; font-weight: 400; color: var(--text-secondary); }
.picker-empty { text-align: center; padding: var(--space-xl) 0; }
.picker-empty p { font-size: 16px; color: var(--text-secondary); margin: var(--space-xs) 0; }
.picker-empty-hint { font-size: 14px; color: var(--link); }
</style>
