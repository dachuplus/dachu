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
      <!-- 分类数据源 -->
      <div class="filter-row">
        <span class="filter-label">分类：</span>
        <div class="filter-chips">
          <div class="filter-chip" :class="{ active: classSource === 'hspj' }" @click="setClassSource('hspj')">聚源</div>
          <div class="filter-chip" :class="{ active: classSource === 'tt' }" @click="setClassSource('tt')">天天</div>
          <div class="filter-chip more-chip" @click="showMoreSources = !showMoreSources">
            更多 ▾
            <div class="source-dropdown" v-if="showMoreSources" @click.stop>
              <div v-for="src in otherSources" :key="src.key" class="source-drop-item"
                :class="{ disabled: !src.available }"
                @click="setClassSource(src.key); showMoreSources = false">
                {{ src.label }}{{ src.available ? '' : '（接入中）' }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 一级分类 -->
      <div class="filter-row">
        <span class="filter-label">一级分类</span>
        <div class="filter-chips">
          <div class="filter-chip" :class="{ active: filterT0 === '' }" @click="setT0('')">全部</div>
          <div v-for="t0 in t0List" :key="t0" class="filter-chip" :class="{ active: filterT0 === t0 }" @click="setT0(t0)">{{ t0 }}</div>
        </div>
      </div>

      <!-- 二级分类（依赖一级） -->
      <div class="filter-row" v-if="t1List.length > 0">
        <span class="filter-label">二级分类</span>
        <div class="filter-chips">
          <div class="filter-chip" :class="{ active: filterT1 === '' }" @click="setT1('')">全部</div>
          <div v-for="t1 in t1List" :key="t1" class="filter-chip" :class="{ active: filterT1 === t1 }" @click="setT1(t1)">{{ t1 }}</div>
        </div>
      </div>

      <!-- 更多筛选（展开/收起） -->
      <div class="more-filter-toggle" @click="showMoreFilter = !showMoreFilter">
        <span>更多筛选</span>
        <span class="toggle-arrow" :class="{ open: showMoreFilter }">▾</span>
      </div>

      <div class="more-filter-body" v-if="showMoreFilter">
        <!-- 份额类别 -->
        <div class="filter-row">
          <span class="filter-label">份额类别</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterSC === '' }" @click="setSC('')">全部</div>
            <div v-for="sc in shareClassOptions" :key="sc" class="filter-chip" :class="{ active: filterSC === sc }" @click="setSC(sc)">{{ sc }}类</div>
          </div>
        </div>

        <!-- 是否ETF -->
        <div class="filter-row">
          <span class="filter-label">ETF</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterETF === '' }" @click="setFlag('ETF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterETF === '1' }" @click="setFlag('ETF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterETF === '0' }" @click="setFlag('ETF', '0')">否</div>
          </div>
        </div>

        <!-- 是否LOF -->
        <div class="filter-row">
          <span class="filter-label">LOF</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterLOF === '' }" @click="setFlag('LOF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterLOF === '1' }" @click="setFlag('LOF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterLOF === '0' }" @click="setFlag('LOF', '0')">否</div>
          </div>
        </div>

        <!-- 是否FOF -->
        <div class="filter-row">
          <span class="filter-label">FOF</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterFOF === '' }" @click="setFlag('FOF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterFOF === '1' }" @click="setFlag('FOF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterFOF === '0' }" @click="setFlag('FOF', '0')">否</div>
          </div>
        </div>

        <!-- 是否定开 -->
        <div class="filter-row">
          <span class="filter-label">定开</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterDK === '' }" @click="setFlag('DK', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterDK === '1' }" @click="setFlag('DK', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterDK === '0' }" @click="setFlag('DK', '0')">否</div>
          </div>
        </div>

        <!-- 申购状态 -->
        <div class="filter-row">
          <span class="filter-label">申购状态</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterSG === '' }" @click="setSG('')">全部</div>
            <div class="filter-chip" :class="{ active: filterSG === '1' }" @click="setSG('1')">可申购</div>
            <div class="filter-chip" :class="{ active: filterSG === '0' }" @click="setSG('0')">暂停申购</div>
          </div>
        </div>

        <!-- 单日涨跌≥20%（涨停/跌停基金，如T+2） -->
        <div class="filter-row">
          <span class="filter-label">单日±20%</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterDailyLimit === '' }" @click="setDailyLimit('')">全部</div>
            <div class="filter-chip" :class="{ active: filterDailyLimit === '0' }" @click="setDailyLimit('0')">否</div>
            <div class="filter-chip" :class="{ active: filterDailyLimit === '1' }" @click="setDailyLimit('1')">是</div>
          </div>
        </div>

        <!-- 持有期 -->
        <div class="filter-row">
          <span class="filter-label">持有期</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterHP === '' }" @click="setHP('')">全部</div>
            <div class="filter-chip" :class="{ active: filterHP === 'no' }" @click="setHP('no')">无限制</div>
            <div class="filter-chip" :class="{ active: filterHP === '7' }" @click="setHP('7')">7天</div>
            <div class="filter-chip" :class="{ active: filterHP === '30' }" @click="setHP('30')">30天</div>
            <div class="filter-chip" :class="{ active: filterHP === '90' }" @click="setHP('90')">90天</div>
            <div class="filter-chip" :class="{ active: filterHP === '180' }" @click="setHP('180')">180天</div>
            <div class="filter-chip" :class="{ active: filterHP === '365' }" @click="setHP('365')">1年+</div>
          </div>
        </div>

        <!-- 规模筛选说明 -->
        <div class="filter-tip">
          注：ETF/LOF/FOF/定开/持有期/±20%等属性基于基金名称智能识别，可能存在误判。<br>
          基金规模、机构占比、股票占比数据暂未收录，后续版本更新。
        </div>
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

    <!-- 周期Tab + 自定义指标 -->
    <div class="toolbar">
      <div class="period-tabs">
        <div
          v-for="p in periods"
          :key="p.key"
          class="period-tab"
          :class="{ active: currentPeriod === p.key }"
          @click="switchPeriod(p.key)"
        >
          {{ p.label }}
          <span class="sort-arrow" v-if="currentPeriod === p.key">
            {{ sortAsc ? '▲' : '▼' }}
          </span>
        </div>
        <div class="weight-toggle" @click="showWeightPanel = !showWeightPanel">
          <SvgIcon name="gear" :size="16" class="wt-icon" /> 自定义指标
        </div>
      </div>
    </div>

    <!-- 自定义指标面板 -->
    <div class="weight-panel" v-if="showWeightPanel">
      <div class="weight-panel-header">
        <span>自定义评分权重（合计 100%）
          <span class="weight-sum" :class="{ valid: weightSum === 100, invalid: weightSum !== 100 }">当前：{{ weightSum }}%</span>
        </span>
        <span class="weight-panel-close" @click="showWeightPanel = false"><SvgIcon name="close" :size="16" /></span>
      </div>
      <div class="weight-sliders">
        <div class="weight-row" v-for="item in weightItems" :key="item.key">
          <span class="weight-label">{{ item.label }}</span>
          <input type="range" :min="0" :max="100" :value="item.value" class="weight-range" @input="e => item.value = Number(e.target.value)" />
          <input type="number" :min="0" :max="100" :value="item.value" class="weight-num" @input="e => item.value = Number(e.target.value)" />%
        </div>
      </div>
      <div class="weight-actions">
        <button class="btn-reset" @click="resetWeights">恢复默认</button>
        <button class="btn-confirm" :disabled="weightSum !== 100" @click="applyCustomWeights">确认</button>
      </div>
    </div>
    <!-- 基金列表 - 横向表格 -->
    <div class="fund-table-wrap" v-if="funds.length > 0">
      <table class="fund-table">
        <thead>
          <tr>
            <th class="col-code sortable" @click="toggleColumnSort('c')">
              代码<span class="th-arrow" v-if="sortField === 'c'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-name sortable" @click="toggleColumnSort('n')">
              简称<span class="th-arrow" v-if="sortField === 'n'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-num sortable" @click="toggleColumnSort('scale')">
              规模(亿)<span class="th-arrow" v-if="sortField === 'scale'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-pct sortable" @click="toggleColumnSort('equityPct')">
              权益%<span class="th-arrow" v-if="sortField === 'equityPct'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th class="col-pct sortable" @click="toggleColumnSort('bondPct')">
              债券%<span class="th-arrow" v-if="sortField === 'bondPct'">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
            </th>
            <th v-for="p in periods" :key="p.key" class="col-score sortable" :class="{ 'col-sort': currentPeriod === p.key }" @click="switchPeriod(p.key)">
              {{ p.label }}<span class="th-arrow" v-if="currentPeriod === p.key">{{ sortAsc ? '▲' : '▼' }}</span>
            </th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(fund, idx) in sortedFunds"
            :key="fund.c"
            class="fund-row"
          >
            <td class="col-code">{{ fund.c }}</td>
            <td class="col-name" @click="openDetail(fund)">{{ fund.n || '基金' + fund.c }}</td>
            <td class="col-num">{{ fmtNum(fund.scale) }}</td>
            <td class="col-pct">{{ fmtPct(fund.equityPct) }}</td>
            <td class="col-pct">{{ fmtPct(fund.bondPct) }}</td>
            <td v-for="p in periods" :key="p.key" class="col-score" :class="{ 'col-sort': currentPeriod === p.key }">
              <span class="score-val" :class="scoreCls(fund[p.key])">{{ fmtScore(fund[p.key]) }}</span>
            </td>
            <td class="col-actions">
              <span class="action-btn" title="点赞" @click.stop="thumbUp(fund)">
                <SvgIcon name="thumbs-up" :size="16" />
              </span>
              <span class="action-btn" title="吐槽" @click.stop="thumbDown(fund)">
                <SvgIcon name="thumbs-down" :size="16" />
              </span>
              <span class="action-btn action-add" title="加入组合" @click.stop="addToPortfolio(fund)">
                <SvgIcon name="plus-circle" :size="16" />
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 加载更多 -->
    <div class="load-more" v-if="hasMore && funds.length > 0" @click="loadMore">
      {{ loading ? '加载中...' : '加载更多' }}
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-if="dataLoaded && funds.length === 0 && !loading">
      <p class="empty-text">没有找到符合条件的基金</p>
      <p class="empty-hint">试试调整筛选条件或关键词</p>
    </div>

    <!-- 加载中（首次） -->
    <div class="loading-wrap" v-if="loading && funds.length === 0">
      <span class="loading-text">正在加载基金数据...</span>
    </div>

    <!-- 底部说明 + 评分帮助 -->
    <div class="bottom-info" v-if="dataLoaded">
      <span>数据来源：FundGuideapi · 风险指标自行计算（历史净值回算）</span>
      <span v-if="meta.nav_date">数据截止：{{ meta.nav_date }}</span>
      <div class="bottom-help">
        <span class="bottom-help-title" @click="showScoreHelp = true">靠谱指数评分说明</span>
        <p>综合收益率、最大回撤、夏普比率在全市场排名后加权计算。满分100分，分值越高表现越优秀。默认权重：收益50% + 回撤25% + 夏普25%。</p>
      </div>
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
            </div>

            <!-- 靠谱分 -->
            <div class="detail-section">
              <span class="detail-section-title">靠谱指数评分（v6）</span>
              <div class="detail-scores-grid">
                <div v-for="p in periods" :key="p.key" class="ds-item">
                  <span class="ds-period">{{ p.label }}</span>
                  <span class="ds-score" :class="scoreCls(detailFund[p.key])">
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
              <span class="help-section-label">颜色等级</span>
              <div class="help-color-row">
                <span class="help-dot" style="background:#FFB800;"></span>
                <span class="help-color-text score-gold-text">85分及以上</span>
                <span class="help-color-desc">顶尖水平</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#FF6B35;"></span>
                <span class="help-color-text score-orange-text">75 ~ 84分</span>
                <span class="help-color-desc">优秀水平</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#06B6D4;"></span>
                <span class="help-color-text score-cyan-text">65 ~ 74分</span>
                <span class="help-color-desc">中等偏上</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#8B949E;"></span>
                <span class="help-color-text score-default-text">65分以下</span>
                <span class="help-color-desc">中等及以下</span>
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
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted } from 'vue'
import { fetchFundScores, fetchFundMeta } from '../../api/data.js'
import { addFundToPortfolio } from '../../api/user-data'
import { toast } from '../../composables/useToast.js'
import SvgIcon from '../../components/SvgIcon.vue'

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
  { key: 'k7',  label: '7年' },
  { key: 'k10', label: '10年' },
]

const riskPeriods = [
  { label: '近1年', dd: 'dd1y', sr: 'sr1y' },
  { label: '近2年', dd: 'dd2y', sr: 'sr2y' },
  { label: '近3年', dd: 'dd3y', sr: 'sr3y' },
  { label: '近5年', dd: 'dd5y', sr: 'sr5y' },
]

// 恒生聚源分类树（基于聚源基金分类标准Excel + DB 实际数据兜底）
// 每个 t0 下：Excel 精确分类在前，"未细分"兜底在后（匹配 DB 中 t1=t0 的通用记录）
const CAT_TREE_HSPJ = {
  'FOF': {
    '混合型FOF': ['混合型FOF'],
    '养老目标FOF': ['养老目标FOF'],
    '债券型FOF': ['债券型FOF'],
    '未细分': ['FOF'],
  },
  'QDII基金': {
    'QDII混合型基金': ['QDII混合型基金'],
    'QDII股票型基金': ['QDII股票型基金'],
    '未细分': ['QDII基金'],
  },
  '债券型基金': {
    '纯债型基金': ['纯债型基金'],
    '混合债券型基金': ['混合债券型基金'],
    '指数型债券基金': ['指数型债券基金'],
    '未细分': ['债券型基金'],
  },
  '混合型基金': {
    '偏股混合型基金': ['偏股混合型基金'],
    '偏债混合型基金': ['偏债混合型基金'],
    '灵活配置型基金': ['灵活配置型基金'],
    '平衡混合型基金': ['平衡混合型基金'],
    '未细分': ['混合型基金'],
  },
  '股票型基金': {
    '指数型股票基金': ['指数型股票基金'],
    '普通股票型基金': ['普通股票型基金'],
    '未细分': ['股票型基金'],
  },
}

// 天天基金分类树（基于 FundGuideapi 实际返回的 dt/gp/zq/hh/fof/qdii 分类 t2 值）
// 分类值严格匹配 API 返回的 f[3] 字段，存储在数据库 t1_tt 列
const CAT_TREE_TT = {
  '股票型': {
    '指数型-股票': ['指数型-股票'],
    '股票型': ['股票型'],
  },
  '混合型': {
    '混合型-偏股': ['混合型-偏股'],
    '混合型-灵活': ['混合型-灵活'],
    '混合型-偏债': ['混合型-偏债'],
    '混合型-平衡': ['混合型-平衡'],
    '混合型-绝对收益': ['混合型-绝对收益'],
    '指数型-固收': ['指数型-固收'],
    '指数型-其他': ['指数型-其他'],
    'FOF-稳健型': ['FOF-稳健型'],
    'FOF-均衡型': ['FOF-均衡型'],
    'FOF-进取型': ['FOF-进取型'],
  },
  '债券型': {
    '债券型-长债': ['债券型-长债'],
    '债券型-混合二级': ['债券型-混合二级'],
    '债券型-中短债': ['债券型-中短债'],
    '债券型-混合一级': ['债券型-混合一级'],
    '指数型-固收': ['指数型-固收'],
    '债券型-利率债': ['债券型-利率债'],
    '债券型-信用债': ['债券型-信用债'],
  },
  'QDII': {
    '指数型-海外股票': ['指数型-海外股票'],
    'QDII-混合偏股': ['QDII-混合偏股'],
    'QDII-普通股票': ['QDII-普通股票'],
    'QDII-纯债': ['QDII-纯债'],
    'QDII-混合灵活': ['QDII-混合灵活'],
    'QDII-混合债': ['QDII-混合债'],
    'QDII-商品': ['QDII-商品'],
    'QDII-REITs': ['QDII-REITs'],
    'QDII-FOF': ['QDII-FOF'],
    'QDII-混合平衡': ['QDII-混合平衡'],
    '指数型-股票': ['指数型-股票'],
  },
  'FOF': {
    'FOF-稳健型': ['FOF-稳健型'],
    'FOF-均衡型': ['FOF-均衡型'],
    'FOF-进取型': ['FOF-进取型'],
  },
}

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
const filterDK = ref('')
const filterHP = ref('')
const filterDailyLimit = ref('')
const filterSG = ref('')       // 申购状态：''全部 '1'可申购 '0'暂停申购
const classSource = ref('hspj')    // 分类数据源：hspj=恒生聚源，tt=天天分类，choice/ifind/wind/mstar/jajx/yhfl
const classSources = [
  { key: 'hspj',   label: '恒生聚源', available: true },
  { key: 'tt',     label: '天天分类', available: true },
  { key: 'choice', label: 'Choice',   available: false },
  { key: 'ifind',  label: 'iFinD',    available: false },
  { key: 'wind',   label: 'Wind',     available: false },
  { key: 'mstar',  label: 'Morningstar', available: false },
  { key: 'jajx',   label: '济安金信', available: false },
  { key: 'yhfl',   label: '银河分类', available: false },
]
const showMoreSources = ref(false)
const otherSources = classSources.filter(s => s.key !== 'hspj' && s.key !== 'tt')

// 自定义指标权重（6项）
const showWeightPanel = ref(false)
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
  showWeightPanel.value = false
  // Re-fetch with updated weights (custom weight scoring computed client-side)
  loadData(true)
}

function setClassSource(key) {
  const src = classSources.find(s => s.key === key)
  if (!src || !src.available) return
  if (classSource.value === key) return
  classSource.value = key
  // 切换数据源时重置分类筛选（不同来源的分类体系不同）
  filterT0.value = ''
  filterT1.value = ''
  loadData(true)
}

// 搜索/周期/分页/排序
const searchText = ref('')
const currentPeriod = ref('k1')
const sortAsc = ref(false)        // 靠谱指数排序方向（false=降序，true=升序）
const sortField = ref('')          // 客户端排序列（非评分列）：'c'|'n'|'scale'|'equityPct'|'bondPct'
const sortDir = ref('desc')        // 客户端排序方向
const page = ref(1)
const pageSize = 100
const hasMore = ref(false)
const loading = ref(false)
const dataLoaded = ref(false)
const refreshing = ref(false)
const totalCount = ref(null)      // 当前筛选条件下后端总数（来自 Supabase count）

// 弹窗
const detailFund = ref(null)
const showScoreHelp = ref(false)

// ========== 计算属性：分类联动 ==========
const currentCatTree = computed(() => classSource.value === 'tt' ? CAT_TREE_TT : CAT_TREE_HSPJ)

const t0List = computed(() => Object.keys(currentCatTree.value))

const t1List = computed(() => {
  if (!filterT0.value || !currentCatTree.value[filterT0.value]) return []
  return Object.keys(currentCatTree.value[filterT0.value])
})

// ========== 格式化 ==========
function fmtScore(v) {
  const n = parseFloat(v)
  if (!n || n <= 0) return '--'
  return n.toFixed(2)
}

function fmtRet(v) {
  if (v == null) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
}

function fmtDD(v) {
  if (v == null) return '--'
  return parseFloat(v).toFixed(2) + '%'
}

function fmtSR(v) {
  if (v == null) return '--'
  return parseFloat(v).toFixed(4)
}

function scoreCls(v) {
  const n = parseFloat(v) || 0
  if (n >= 85) return 'score-hot'
  if (n >= 70) return 'score-warm'
  if (n >= 50) return 'score-mid'
  return 'score-cool'
}

function fmtNum(v) {
  if (v == null || v === 0) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  return n.toFixed(2)
}

function fmtPct(v) {
  if (v == null) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  return n.toFixed(0) + '%'
}

// 点赞/吐槽
const thumbedFunds = ref(new Set())
const dislikedFunds = ref(new Set())

function thumbUp(fund) {
  if (dislikedFunds.value.has(fund.c)) dislikedFunds.value.delete(fund.c)
  if (thumbedFunds.value.has(fund.c)) {
    thumbedFunds.value.delete(fund.c)
  } else {
    thumbedFunds.value.add(fund.c)
  }
  thumbedFunds.value = new Set(thumbedFunds.value)
}

function thumbDown(fund) {
  if (thumbedFunds.value.has(fund.c)) thumbedFunds.value.delete(fund.c)
  if (dislikedFunds.value.has(fund.c)) {
    dislikedFunds.value.delete(fund.c)
  } else {
    dislikedFunds.value.add(fund.c)
  }
  dislikedFunds.value = new Set(dislikedFunds.value)
}

async function addToPortfolio(fund) {
  const result = await addFundToPortfolio(fund.c, fund.n)
  if (result.success) {
    toast(result.message, 'success')
  } else {
    toast(result.message || result.error || '添加失败', 'error')
  }
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
  const pureCode = code.replace(/\.of$/i, '').replace(/\.OF$/, '')
  return `http://fund.eastmoney.com/${pureCode}.html`
}

// ========== 份额类别提取（基于基金名称末尾大写字母） ==========
// 常见份额类别：A/B/C/D/E/F/H/I/R/Y
const SHARE_CLASS_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'R', 'Y']
const shareClassOptions = SHARE_CLASS_LETTERS

/** 从基金名称提取份额类别字母，如 "华夏成长混合A" → "A"，"某某精选C" → "C" */
function extractShareClass(name) {
  if (!name) return ''
  const match = name.match(/([A-Z])$/)
  return match ? match[1] : ''
}

// ========== 数据加载 ==========
// 天天基金 → 恒生聚源 t0 名称映射（DB 当前仅含恒生聚源分类数据）
const T0_MAP_TT = {
  '股票型': '股票型基金',
  '混合型': '混合型基金',
  '债券型': '债券型基金',
  'QDII': 'QDII基金',
  'FOF': 'FOF',
}

async function loadData(reset = true) {
  if (loading.value) return
  loading.value = true
  if (reset) page.value = 1

  try {
    // 确定 t0 过滤（FOF 类型筛选用 t0_eq）
    let t0Filter = filterT0.value || undefined
    if (filterFOF.value === '1') t0Filter = 'FOF'
    if (filterFOF.value === '0' && !filterT0.value) t0Filter = undefined // 不能简单过滤

    // 天天基金分类 → 恒生聚源分类映射
    if (classSource.value === 'tt' && t0Filter) {
      t0Filter = T0_MAP_TT[t0Filter] || t0Filter
    }

    const result = await fetchFundScores({
      t0: t0Filter,
      t1: filterT1.value || undefined,
      classSource: classSource.value,
      search: buildSearchText(),
      kKey: currentPeriod.value,
      sortAsc: sortAsc.value,
      page: page.value,
      pageSize,
      // 客户端附加筛选参数（后端不支持的由前端过滤）
      hp: filterHP.value || undefined,
      dailyLimit: filterDailyLimit.value || undefined,
      sg: filterSG.value || undefined,   // 申购状态
      etf: filterETF.value || undefined,
      lof: filterLOF.value || undefined,
      dk: filterDK.value || undefined,
      fof: filterFOF.value || undefined,
    })

    if (result.data) {
      // 存储后端总数（t0/t1/search 过滤后，ETF/LOF等前端过滤前的真实数）
      if (result.count != null) totalCount.value = result.count
      // 前端补充筛选（基于名称智能识别）
      let filtered = result.data
      if (filterSC.value) filtered = filtered.filter(f => extractShareClass(f.n) === filterSC.value)
      if (filterETF.value === '1') filtered = filtered.filter(f => /ETF/i.test(f.n))
      if (filterETF.value === '0') filtered = filtered.filter(f => !/ETF/i.test(f.n))
      if (filterLOF.value === '1') filtered = filtered.filter(f => /LOF/i.test(f.n))
      if (filterLOF.value === '0') filtered = filtered.filter(f => !/LOF/i.test(f.n))
      if (filterDK.value === '1') filtered = filtered.filter(f => /定开/.test(f.n))
      if (filterDK.value === '0') filtered = filtered.filter(f => !/定开/.test(f.n))
      if (filterFOF.value === '1') filtered = filtered.filter(f => f.t0 === 'FOF')
      if (filterFOF.value === '0') filtered = filtered.filter(f => f.t0 !== 'FOF')
      if (filterHP.value === 'no') filtered = filtered.filter(f => !f.hp)
      if (filterHP.value && filterHP.value !== 'no') {
        const hp = parseInt(filterHP.value)
        filtered = filtered.filter(f => f.hp && parseInt(f.hp) >= hp)
      }

      funds.value = reset ? filtered : funds.value.concat(filtered)
      hasMore.value = result.data.length >= pageSize
    }
  } catch (e) {
    console.error('[fund-rank] load error', e)
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
  } catch (e) { /* ignore */ }
}

function refreshData() {
  if (refreshing.value) return
  refreshing.value = true
  loadData(true)
  loadMeta()
  setTimeout(() => { refreshing.value = false }, 2000)
}

// ========== 交互 ==========
function setT0(val) {
  filterT0.value = val
  filterT1.value = ''
  loadData(true)
}

function setT1(val) {
  filterT1.value = val
  loadData(true)
}

function setSC(val) {
  filterSC.value = val
  loadData(true)
}

function setFlag(type, val) {
  if (type === 'ETF') filterETF.value = val
  else if (type === 'LOF') filterLOF.value = val
  else if (type === 'FOF') { filterFOF.value = val; if (val === '1') { filterT0.value = ''; filterT1.value = '' } }
  else if (type === 'DK') filterDK.value = val
  loadData(true)
}

function setHP(val) {
  filterHP.value = val
  loadData(true)
}

function setDailyLimit(val) {
  filterDailyLimit.value = val
  loadData(true)
}

function setSG(val) {
  filterSG.value = val
  loadData(true)
}

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
  detailFund.value = fund
}

onMounted(() => {
  document.title = '靠谱指数工具-评分 | ALLFUND.CN'
  loadData()
  loadMeta()
})
onUnmounted(() => {
  document.title = 'ALLFUND.CN - 投资工作助手'
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
.toggle-arrow { display: inline-block; transition: transform 0.2s; font-size: 16px; }
.toggle-arrow.open { transform: rotate(180deg); }
.more-filter-body { border-top: 1px solid var(--border); padding-bottom: var(--space-sm); }
.filter-tip { padding: var(--space-sm) var(--space-md); font-size: 14px; color: var(--text-secondary); }

/* 周期Tab */
.toolbar {
  display: flex; align-items: center; gap: var(--space-md);
  padding: var(--space-sm) var(--space-md); background: #ffffff;
  border-bottom: 1px solid var(--border);
}
.period-tabs { display: flex; gap: 0; overflow-x: auto; white-space: nowrap; flex: 1; }
.period-tab {
  flex-shrink: 0; padding: 8px 16px; font-size: 16px; color: var(--link);
  cursor: pointer; border-bottom: 4px solid transparent; text-decoration: none;
  font-weight: 400;
}
.period-tab:hover { border-bottom-color: var(--border); }
.period-tab.active {
  color: #1d70b8; font-weight: 700; border-bottom-color: #1d70b8;
}
.sort-arrow { font-size: 12px; margin-left: 4px; }

.filter-result-row {
  padding: var(--space-sm) var(--space-md); background: #f3f2f1;
  border-top: 1px solid var(--border);
}
.filter-result-count { font-size: 16px; color: var(--text-secondary); }
.filter-result-count strong { color: #0b0c0c; font-weight: 700; }

/* 基金列表 - 横向滚动表格 */
.fund-table-wrap {
  overflow-x: auto; -webkit-overflow-scrolling: touch;
  border-top: 1px solid var(--border);
}
.fund-table {
  width: 100%; border-collapse: collapse; font-size: 14px; white-space: nowrap;
  min-width: 1100px;
}
.fund-table thead { background: #f3f2f1; }
.fund-table th {
  padding: var(--space-sm) 8px; text-align: left;
  font-size: 13px; font-weight: 700; color: var(--text-primary);
  border-bottom: 2px solid var(--border);
  position: sticky; top: 0; background: #f3f2f1; z-index: 1;
}
.fund-table td {
  padding: 6px 8px; border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.fund-row:hover { background: #f8f8f8; }

.col-code { width: 80px; font-weight: 700; color: var(--text-secondary); font-family: monospace; font-size: 13px; }
.col-name { max-width: 180px; font-weight: 700; cursor: pointer; color: var(--link); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-name:hover { text-decoration: underline; }
.col-num { width: 80px; text-align: right; color: var(--text-secondary); }
.col-pct { width: 60px; text-align: right; color: var(--text-secondary); }
.col-score { width: 50px; text-align: center; }
.col-score .score-val { font-weight: 700; font-size: 13px; }
.col-sort { background: #e8f0fe; }
.col-actions { width: 90px; text-align: center; }

/* 可排序表头 */
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { background: #e0e7ef; }
.th-arrow { font-size: 11px; margin-left: 3px; color: #1d70b8; }

.score-hot  { color: #d4351c; }  /* >=85 红色 */
.score-warm { color: #f47738; }  /* >=70 橙色 */
.score-mid  { color: #505a5f; }  /* >=50 灰色 */
.score-cool { color: #00703c; }  /* <50  绿色 */

.action-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; cursor: pointer; color: var(--text-muted);
  vertical-align: middle; margin: 0 2px;
}
.action-btn:hover { color: var(--brand); }
.action-add:hover { color: #00703c; }

/* 加载更多 */
.load-more {
  text-align: center; padding: var(--space-lg);
  font-size: 16px; color: var(--link); cursor: pointer; text-decoration: underline;
}

/* 状态 */
.empty-state { text-align: center; padding: var(--space-2xl) var(--space-md); }
.empty-text { font-size: 19px; color: var(--text-primary); font-weight: 700; margin-bottom: var(--space-sm); }
.empty-hint { font-size: 16px; color: var(--text-secondary); }
.loading-wrap { display: flex; justify-content: center; padding: var(--space-2xl) 0; }
.loading-text { font-size: 16px; color: var(--text-secondary); }

/* 底部 */
.bottom-info {
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
  padding: var(--space-xl) var(--space-md) var(--space-2xl);
  font-size: 14px; color: var(--text-secondary);
  border-top: 1px solid var(--border); margin-top: var(--space-xl);
}

/* 颜色 */
.ret-up { color: var(--color-up); }
.ret-down { color: var(--color-down); }

/* ===== 弹窗 ===== */
.mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }

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
.help-color-row { display: flex; align-items: center; gap: var(--space-md); padding: 4px 0; }
.help-dot { width: 16px; height: 4px; flex-shrink: 0; }
.help-color-text { font-size: 16px; font-weight: 700; flex-shrink: 0; min-width: 100px; }
.score-hot-text { color: #d4351c; }
.score-warm-text { color: #f47738; }
.score-mid-text { color: #505a5f; }
.score-cool-text { color: #00703c; }
.help-color-desc { font-size: 16px; color: var(--text-secondary); }

/* 自定义权重面板 */
.weight-toggle {
  padding: var(--space-xs) var(--space-sm); font-size: 14px;
  color: var(--link); cursor: pointer; border: 1px solid var(--border);
  white-space: nowrap;
}
.weight-toggle:hover { background: #f3f2f1; }

.weight-panel {
  border: 1px solid var(--border); background: #ffffff;
  padding: var(--space-lg); margin-top: var(--space-sm);
}
.weight-panel-header {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 19px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-md);
}
.weight-panel-close { font-size: 20px; color: var(--text-secondary); cursor: pointer; }

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

.bottom-help { margin-top: var(--space-sm); padding-top: var(--space-sm); border-top: 1px solid var(--border); }
.bottom-help-title { font-size: 14px; color: var(--link); cursor: pointer; text-decoration: underline; margin-bottom: 4px; }
.bottom-help p { font-size: 13px; color: var(--text-secondary); margin: 0; line-height: 1.5; }
.weight-valid { background: #e6f7ee; color: #00703c; }
.weight-invalid { background: #fef0ef; color: #d4351c; }
.weight-warn { font-weight: 400; }
.weight-ok { color: #00703c; }

.weight-actions { text-align: center; margin-top: var(--space-sm); }
.btn-reset {
  background: none; border: 1px solid var(--border); color: var(--text-secondary);
  padding: var(--space-xs) var(--space-md); font-size: 14px; cursor: pointer;
}
.btn-reset:hover { background: #f3f2f1; }

/* 分类源禁用 */
.filter-chip.disabled { color: var(--text-secondary); opacity: 0.5; cursor: not-allowed; }
</style>
