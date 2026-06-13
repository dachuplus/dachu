<template>
  <div class="page-fund-rank">
    <!-- 顶部：标题 + 搜索 -->
    <div class="top-bar">
      <div class="search-box">
        <input
          class="search-input"
          placeholder="搜基金名/代码"
          v-model="searchText"
          @keyup.enter="doSearch"
        />
        <span class="search-clear" v-if="searchText" @click="clearSearch"><SvgIcon name="close" size="14" /></span>
      </div>
    </div>

    <!-- 筛选区（可展开/收起） -->
    <div class="filter-section">
      <!-- 分类数据源（标签式） -->
      <div class="filter-row filter-row-source">
        <span class="filter-label">分类数据源</span>
        <div class="source-tags">
          <button
            v-for="src in visibleClassSources"
            :key="src.key"
            class="source-tag"
            :class="{ active: classSource === src.key }"
            @click="setClassSource(src.key)"
            :disabled="!src.available"
          >
            {{ src.label }}
            <span v-if="!src.available" class="source-tag-badge">接入中</span>
          </button>
          <button
            v-if="!showAllSources && hiddenClassSources.length > 0"
            class="source-tag source-tag--more"
            @click="showAllSources = true"
          >更多</button>
          <button
            v-if="showAllSources"
            class="source-tag source-tag--collapse"
            @click="showAllSources = false"
          >收起</button>
        </div>
      </div>

      <!-- 一级分类（下拉选择） -->
      <div class="filter-row">
        <span class="filter-label">一级分类</span>
        <div class="filter-select-wrap">
          <select class="filter-select" v-model="filterT0" @change="onT0Change">
            <option value="">全部</option>
            <option v-for="t0 in t0List" :key="t0" :value="t0">{{ t0 }}</option>
          </select>
        </div>
      </div>

      <!-- 二级分类（下拉选择，依赖一级） -->
      <div class="filter-row" v-if="t1List.length > 0">
        <span class="filter-label">二级分类</span>
        <div class="filter-select-wrap">
          <select class="filter-select" v-model="filterT1" @change="onT1Change">
            <option value="">全部</option>
            <option v-for="t1 in t1List" :key="t1" :value="t1">{{ t1Short(t1) }}</option>
          </select>
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
          <div class="filter-chips scroll-x">
            <div class="filter-chip" :class="{ active: filterSC === '' }" @click="setSC('')">全部</div>
            <div v-for="sc in shareClassOptions" :key="sc" class="filter-chip" :class="{ active: filterSC === sc }" @click="setSC(sc)">{{ sc }}类</div>
          </div>
        </div>

        <!-- 是否ETF -->
        <div class="filter-row">
          <span class="filter-label">ETF</span>
          <div class="filter-chips scroll-x">
            <div class="filter-chip" :class="{ active: filterETF === '' }" @click="setFlag('ETF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterETF === '1' }" @click="setFlag('ETF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterETF === '0' }" @click="setFlag('ETF', '0')">否</div>
          </div>
        </div>

        <!-- 是否LOF -->
        <div class="filter-row">
          <span class="filter-label">LOF</span>
          <div class="filter-chips scroll-x">
            <div class="filter-chip" :class="{ active: filterLOF === '' }" @click="setFlag('LOF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterLOF === '1' }" @click="setFlag('LOF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterLOF === '0' }" @click="setFlag('LOF', '0')">否</div>
          </div>
        </div>

        <!-- 是否FOF -->
        <div class="filter-row">
          <span class="filter-label">FOF</span>
          <div class="filter-chips scroll-x">
            <div class="filter-chip" :class="{ active: filterFOF === '' }" @click="setFlag('FOF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterFOF === '1' }" @click="setFlag('FOF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterFOF === '0' }" @click="setFlag('FOF', '0')">否</div>
          </div>
        </div>

        <!-- 是否定开 -->
        <div class="filter-row">
          <span class="filter-label">定开</span>
          <div class="filter-chips scroll-x">
            <div class="filter-chip" :class="{ active: filterDK === '' }" @click="setFlag('DK', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterDK === '1' }" @click="setFlag('DK', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterDK === '0' }" @click="setFlag('DK', '0')">否</div>
          </div>
        </div>

        <!-- 申购状态 -->
        <div class="filter-row">
          <span class="filter-label">申购状态</span>
          <div class="filter-chips scroll-x">
            <div class="filter-chip" :class="{ active: filterSG === '' }" @click="setSG('')">全部</div>
            <div class="filter-chip" :class="{ active: filterSG === '1' }" @click="setSG('1')">可申购</div>
            <div class="filter-chip" :class="{ active: filterSG === '0' }" @click="setSG('0')">暂停申购</div>
          </div>
        </div>

        <!-- 单日涨跌≥20%（涨停/跌停基金，如T+2） -->
        <div class="filter-row">
          <span class="filter-label">单日±20%</span>
          <div class="filter-chips scroll-x">
            <div class="filter-chip" :class="{ active: filterDailyLimit === '' }" @click="setDailyLimit('')">全部</div>
            <div class="filter-chip" :class="{ active: filterDailyLimit === '0' }" @click="setDailyLimit('0')">否</div>
            <div class="filter-chip" :class="{ active: filterDailyLimit === '1' }" @click="setDailyLimit('1')">是</div>
          </div>
        </div>

        <!-- 持有期 -->
        <div class="filter-row">
          <span class="filter-label">持有期</span>
          <div class="filter-chips scroll-x">
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
          注：ETF/LOF/FOF/定开/持有期/±20%等属性基于基金名称智能识别，可能存在误判。
        </div>
      </div>

      <!-- 筛选结果数量（始终显示在筛选区底部） -->
      <div class="filter-result-row" v-if="dataLoaded">
        <span class="filter-result-count">
          筛选结果：<strong>{{ totalCount != null ? totalCount : funds.length }}</strong> 只
          <template v-if="funds.length > 0">
            · 已加载 <strong>{{ funds.length }}</strong> 只
          </template>
        </span>
        <button class="data-refresh-btn" :class="{ refreshing }" @click="refreshData" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 周期Tab + 排序箭头 + 自定义权重 -->
    <div class="toolbar">
      <div class="period-tabs scroll-x">
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
          <SvgIcon name="gear" size="16" /> 自定义权重
        </div>
      </div>
    </div>

    <!-- 自定义权重面板 -->
    <div class="weight-panel" v-if="showWeightPanel">
      <div class="weight-panel-header">
        <span>自定义靠谱指数权重</span>
        <span class="weight-panel-close" @click="showWeightPanel = false"><SvgIcon name="close" size="16" /></span>
      </div>
      <div class="weight-sliders">
        <div class="weight-slider-item">
          <label>阶段收益权重 <span class="ws-val">{{ customWeights.ret }}%</span></label>
          <input type="range" min="0" max="100" step="5" v-model.number="customWeights.ret" @input="onWeightInput('ret')" />
        </div>
        <div class="weight-slider-item">
          <label>最大回撤权重 <span class="ws-val">{{ customWeights.dd }}%</span></label>
          <input type="range" min="0" max="100" step="5" v-model.number="customWeights.dd" @input="onWeightInput('dd')" />
        </div>
        <div class="weight-slider-item">
          <label>夏普比率权重 <span class="ws-val">{{ customWeights.sr }}%</span></label>
          <input type="range" min="0" max="100" step="5" v-model.number="customWeights.sr" @input="onWeightInput('sr')" />
        </div>
        <div class="weight-slider-item">
          <label>卡玛比率权重 <span class="ws-val">{{ customWeights.calmar }}%</span></label>
          <input type="range" min="0" max="100" step="5" v-model.number="customWeights.calmar" @input="onWeightInput('calmar')" />
        </div>
        <div class="weight-slider-item">
          <label>信息比率权重 <span class="ws-val">{{ customWeights.ir }}%</span></label>
          <input type="range" min="0" max="100" step="5" v-model.number="customWeights.ir" @input="onWeightInput('ir')" />
        </div>
        <div class="weight-slider-item">
          <label>跟踪误差权重 <span class="ws-val">{{ customWeights.te }}%</span></label>
          <input type="range" min="0" max="100" step="5" v-model.number="customWeights.te" @input="onWeightInput('te')" />
        </div>
      </div>
      <div class="weight-total" :class="{ 'weight-valid': weightSum === 100, 'weight-invalid': weightSum !== 100 }">
        合计：{{ weightSum }}%
        <span v-if="weightSum !== 100" class="weight-warn">（必须等于 100%）</span>
        <span v-else class="weight-ok"><SvgIcon name="check" size="16" /> 已应用自定义权重</span>
      </div>
      <div class="weight-actions">
        <button class="btn-confirm" @click="confirmWeights" :disabled="weightSum !== 100">确认</button>
        <button class="btn-reset" @click="resetWeights">恢复默认 50/25/25/0/0/0</button>
      </div>
    </div>

    <!-- 组合选择器弹窗 -->
    <div class="modal-mask" v-if="showPortfolioPicker" @click.self="showPortfolioPicker = false">
      <div class="modal-box modal-box--sm">
        <div class="modal-hd">
          添加到组合
          <a class="modal-close" @click="showPortfolioPicker = false">×</a>
        </div>
        <div class="modal-bd">
          <p class="pf-picker-fund" v-if="pendingFund">
            <strong>{{ pendingFund.code }}</strong> {{ pendingFund.name }}
          </p>
          <div v-if="portfolioPickerLoading" class="pf-picker-loading">加载中...</div>
          <template v-else>
            <div v-if="userPortfolios.length === 0" class="pf-picker-empty">
              还没有组合，
              <a class="link" @click="createAndAddFund">新建一个</a>
            </div>
            <div
              v-for="p in userPortfolios" :key="p.id"
              class="pf-picker-item"
              @click="selectPortfolioForFund(p.id)"
            >
              <span>{{ p.portfolio_data?.name || '未命名组合' }}</span>
              <span class="pf-picker-count">{{ (p.portfolio_data?.funds || []).length }} 只基金</span>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- 基金列表（2行卡片布局） -->
    <div class="fund-list" ref="fundListRef" v-if="funds.length > 0">
      <div class="fund-card" v-for="(fund, idx) in funds" :key="fund.c" @click="openDetail(fund)">
        <!-- 第一行：基金代码 + 基金名称 -->
        <div class="fund-row1">
          <span class="fund-code">{{ fund.c }}</span>
          <span class="fund-name" @click.stop="openDetail(fund)">{{ fund.n }}</span>
        </div>
        <!-- 第二行：规模/持仓 + 操作按钮 -->
        <div class="fund-row2">
          <div class="fund-row2-data">
            <span class="fund-data-item" v-if="fund.scale != null">
              <span class="fund-data-val">{{ fmtScale(fund.scale) }}</span>
              <span class="fund-data-label">规模(亿)</span>
            </span>
            <span class="fund-data-item" v-if="fund.stock_pct != null">
              <span class="fund-data-val">{{ fund.stock_pct }}%</span>
              <span class="fund-data-label">股票占比</span>
            </span>
            <span class="fund-data-item" v-if="fund.bond_pct != null">
              <span class="fund-data-val">{{ fund.bond_pct }}%</span>
              <span class="fund-data-label">债券占比</span>
            </span>
            <span class="fund-data-item fund-data-item--na" v-if="fund.scale == null && fund.stock_pct == null && fund.bond_pct == null">
              <span class="fund-data-val">--</span>
              <span class="fund-data-label">规模/持仓</span>
            </span>
          </div>
          <div class="fund-actions">
            <span class="action-btn" :class="{ active: likedFunds.has(fund.c) }" @click.stop="toggleLike(fund.c)" :title="likedFunds.has(fund.c) ? '已点赞' : '点赞'">
              <SvgIcon name="thumbs-up" size="16" />
              <span class="action-count" v-if="likedFunds.has(fund.c)">1</span>
            </span>
            <span class="action-btn" :class="{ active: dislikedFunds.has(fund.c) }" @click.stop="toggleDislike(fund.c)" :title="dislikedFunds.has(fund.c) ? '已吐槽' : '吐槽'">
              <SvgIcon name="thumbs-down" size="16" />
              <span class="action-count" v-if="dislikedFunds.has(fund.c)">1</span>
            </span>
            <span class="action-btn" :class="{ active: portfolioFunds.has(fund.c) }" @click.stop="togglePortfolio(fund.c)" :title="portfolioFunds.has(fund.c) ? '已添加' : '添加到组合'">
              <SvgIcon name="plus-circle" size="16" />
            </span>
          </div>
        </div>
        <!-- 第三行：各周期靠谱指数 -->
        <div class="fund-row3">
          <div class="period-scores scroll-x">
            <div class="period-score-item" v-for="p in periods" :key="p.key" @click.stop="switchPeriod(p.key)"
              :class="{ active: currentPeriod === p.key, 'period-selected': currentPeriod === p.key }">
              <span class="ps-label">{{ p.label }}</span>
              <span class="ps-score" :class="[scoreCls(fund[p.key]), { 'ps-score-centered': currentPeriod === p.key }]">{{ fmtScore(fund[p.key]) }}</span>
            </div>
          </div>
        </div>
      </div>
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

    <!-- 底部说明（靠谱指数说明 + 评分说明入口） -->
    <div class="bottom-info" v-if="dataLoaded">
      <div class="bottom-disclaimer">
        <p>数据来源：FundGuideAPI。</p>
        <p>截止时间：{{ meta.nav_date ? meta.nav_date + ' 21:30' : '上一次数据更新日 21:30' }}。</p>
        <p>相关指标根据基金历史净值计算，不保证数据的及时性，准确性，完整性，有效性。</p>
        <p>数据仅供娱乐，不对因此产生的任何结果承担责任。</p>
      </div>
      <div class="bottom-help-entry">
        <span class="help-link" @click="showScoreHelp = true">
          <SvgIcon name="help" size="14" /> 靠谱指数评分说明
        </span>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <Teleport to="body">
      <template v-if="detailFund">
        <div class="mask" @click="detailFund = null"></div>
        <div class="panel-slide detail-panel">
          <div class="panel-hd detail-header">
            <span class="detail-name">{{ detailFund.n }}</span>
            <span class="panel-close" @click="detailFund = null"><SvgIcon name="close" size="20" /></span>
          </div>
          <div class="panel-bd detail-body">
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
              <div class="attr-row" v-if="meta.nav_date">
                <span class="attr-label">数据更新</span>
                <span class="attr-value">{{ meta.nav_date }} 21:30 更新</span>
              </div>
              <div class="attr-row" v-if="detailFund.scale != null">
                <span class="attr-label">基金规模</span>
                <span class="attr-value">{{ fmtScale(detailFund.scale) }}</span>
              </div>
              <div class="attr-row" v-if="detailFund.stock_pct != null">
                <span class="attr-label">股票占比</span>
                <span class="attr-value">{{ detailFund.stock_pct }}%</span>
              </div>
              <div class="attr-row" v-if="detailFund.bond_pct != null">
                <span class="attr-label">债券占比</span>
                <span class="attr-value">{{ detailFund.bond_pct }}%</span>
              </div>
            </div>

            <!-- 综合数据表（靠谱指数 + 阶段收益 + 风险指标合并） -->
            <div class="detail-section">
              <span class="detail-section-title">综合数据</span>
              <div class="unified-table">
                <div class="unified-head">
                  <span class="unified-th" style="width:48px">周期</span>
                  <span class="unified-th" style="flex:1.2;text-align:center">靠谱指数</span>
                  <span class="unified-th" style="flex:1;text-align:center">阶段收益</span>
                  <span class="unified-th" style="flex:1;text-align:center">最大回撤</span>
                  <span class="unified-th" style="flex:1;text-align:center">夏普比率</span>
                </div>
                <div v-for="rp in unifiedPeriods" :key="rp.label" class="unified-row"
                  v-show="detailFund[rp.k] != null || detailFund[rp.ret] != null || detailFund[rp.dd] != null || detailFund[rp.sr] != null">
                  <span class="unified-label">{{ rp.label }}</span>
                  <span class="unified-val" :class="scoreCls(detailFund[rp.k])">
                    {{ fmtScore(detailFund[rp.k]) }}
                  </span>
                  <span class="unified-val" :class="retCls(detailFund[rp.ret])">
                    {{ fmtRet(detailFund[rp.ret]) }}
                  </span>
                  <span class="unified-val" :class="ddCls(detailFund[rp.dd])">
                    {{ fmtDD(detailFund[rp.dd]) }}
                  </span>
                  <span class="unified-val">
                    {{ fmtSR(detailFund[rp.sr]) }}
                  </span>
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
        <div class="panel-slide help-panel">
          <div class="panel-hd help-header">
            <span class="help-title">靠谱指数评分说明</span>
            <span class="panel-close" @click="showScoreHelp = false"><SvgIcon name="close" size="20" /></span>
          </div>
          <div class="panel-bd help-body">
            <div class="help-section">
              <span class="help-desc">
                所有基金均参与无差异评分排名。靠谱指数综合考虑基金的收益率、最大回撤、夏普比率、卡玛比率、信息比率、跟踪误差、基金规模、综合费率等指标。在全市场中进行百分位排名后加权计算，分值越高代表该周期内综合表现越优秀。分值介于 0 - 100 分（分值最低为绿色，分值最高为红色）。
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">颜色等级</span>
              <div class="help-color-row">
                <span class="help-dot" style="background:#d4351c;"></span>
                <span class="help-color-text score-hot-text">高分（红色）</span>
                <span class="help-color-desc">综合表现优秀</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#f47738;"></span>
                <span class="help-color-text score-warm-text">中高分（橙色）</span>
                <span class="help-color-desc">综合表现良好</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#505a5f;"></span>
                <span class="help-color-text score-mid-text">中等（灰色）</span>
                <span class="help-color-desc">综合表现一般</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#00703c;"></span>
                <span class="help-color-text score-cool-text">低分（绿色）</span>
                <span class="help-color-desc">综合表现较差</span>
              </div>
            </div>
            <div class="help-section">
              <span class="help-section-label">数据更新</span>
              <span class="help-desc">
                靠谱指数评分每个交易日 21:30 后自动更新。
              </span>
            </div>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch, nextTick } from 'vue'
import SvgIcon from '../../components/SvgIcon.vue'
import { fetchFundScores, fetchFundMeta } from '../../api/data.js'
import { useAuth } from '../../composables/useAuth'
import { getMyPortfolios, addFundToPortfolio, savePortfolio } from '../../api/user-data'

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

// 详情页综合数据表（靠谱指数 + 阶段收益 + 风险指标合并）
const unifiedPeriods = [
  { label: '1周',   k: 'k0w', ret: 'r0w', dd: null,   sr: null },
  { label: '1月',   k: 'k1m', ret: 'r1m', dd: null,   sr: null },
  { label: '3月',   k: 'k3m', ret: 'r3m', dd: null,   sr: null },
  { label: '6月',   k: 'k6m', ret: 'r6m', dd: null,   sr: null },
  { label: '1年',   k: 'k1',  ret: 'r1y', dd: 'dd1y', sr: 'sr1y' },
  { label: '2年',   k: 'k2',  ret: 'r2y', dd: 'dd2y', sr: 'sr2y' },
  { label: '3年',   k: 'k3',  ret: 'r3y', dd: 'dd3y', sr: 'sr3y' },
  { label: '5年',   k: 'k5',  ret: 'r5y', dd: 'dd5y', sr: 'sr5y' },
  { label: '7年',   k: 'k7',  ret: null,  dd: null,   sr: null },
  { label: '10年',  k: 'k10', ret: null,  dd: null,   sr: null },
  { label: '今年来', k: null,  ret: 'ytd', dd: null,   sr: null },
  { label: '成立来', k: null,  ret: 'return_all', dd: null, sr: null },
]

// 三级分类树（基于天天基金 FundGuideapi 实际 t0/t1 值，与数据库保持一致）
const CAT_TREE = {
  'FOF': {
    'FOF-进取型': ['FOF-进取型'],
    'FOF-稳健型': ['FOF-稳健型'],
    'FOF-均衡型': ['FOF-均衡型'],
  },
  'QDII基金': {
    'QDII-普通股票': ['QDII-普通股票'],
    'QDII-混合偏股': ['QDII-混合偏股'],
    'QDII-纯债': ['QDII-纯债'],
    'QDII-混合灵活': ['QDII-混合灵活'],
    'QDII-混合债': ['QDII-混合债'],
    'QDII-商品': ['QDII-商品'],
    'QDII-FOF': ['QDII-FOF'],
    'QDII-REITs': ['QDII-REITs'],
    'QDII-混合平衡': ['QDII-混合平衡'],
    '指数型-股票': ['指数型-股票'],
    '指数型-海外股票': ['指数型-海外股票'],
  },
  '债券型基金': {
    '债券型-长债': ['债券型-长债'],
    '债券型-混合二级': ['债券型-混合二级'],
    '债券型-混合一级': ['债券型-混合一级'],
    '债券型-中短债': ['债券型-中短债'],
    '指数型-固收': ['指数型-固收'],
  },
  '混合型基金': {
    '混合型-偏股': ['混合型-偏股'],
    '混合型-灵活': ['混合型-灵活'],
    '混合型-平衡': ['混合型-平衡'],
    '混合型-偏债': ['混合型-偏债'],
    '混合型-绝对收益': ['混合型-绝对收益'],
    '指数型-其他': ['指数型-其他'],
    '指数型-固收': ['指数型-固收'],
  },
  '股票型基金': {
    '指数型-股票': ['指数型-股票'],
    '股票型': ['股票型'],
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
const classSource = ref('hspj')
const showAllSources = ref(false)
// 主展示数据源（恒生聚源/天天分类）
const mainSourceKeys = ['hspj', 'tt']
const visibleClassSources = computed(() => {
  const mains = classSources.filter(s => mainSourceKeys.includes(s.key))
  if (classSource.value && !mainSourceKeys.includes(classSource.value)) {
    const extra = classSources.find(s => s.key === classSource.value)
    if (extra) mains.push(extra)
  }
  return mains
})
const hiddenClassSources = computed(() => classSources.filter(s => !mainSourceKeys.includes(s.key)))

const classSources = [
  { key: 'hspj',   label: '恒生聚源', available: true },
  { key: 'tt',     label: '天天分类', available: true },
  { key: 'mstar',  label: 'Morningstar', available: false },
  { key: 'wind',   label: 'Wind',     available: false },
  { key: 'ifind',  label: 'iFinD',   available: false },
  { key: 'choice', label: 'Choice',   available: false },
  { key: 'jajx',   label: '济安金信', available: false },
  { key: 'yhfl',   label: '银河分类', available: false },
  { key: 'htfl',   label: '海通',     available: false },
  { key: 'zsyy',   label: '招商',     available: false },
]

// 自定义权重
const showWeightPanel = ref(false)
const customWeights = reactive({ ret: 50, dd: 25, sr: 25, calmar: 0, ir: 0, te: 0 })
const weightSum = computed(() => customWeights.ret + customWeights.dd + customWeights.sr + customWeights.calmar + customWeights.ir + customWeights.te)
const weightsValid = computed(() => weightSum.value === 100)

// 权重滑块输入：限制合计不超过100%
function onWeightInput(changedKey) {
  const keys = ['ret', 'dd', 'sr', 'calmar', 'ir', 'te']
  const sum = keys.reduce((acc, k) => acc + customWeights[k], 0)
  if (sum > 100) {
    // 将超出部分从除当前外最大的项中扣除
    const excess = sum - 100
    const otherKeys = keys.filter(k => k !== changedKey).sort((a, b) => customWeights[b] - customWeights[a])
    let remaining = excess
    for (const k of otherKeys) {
      if (remaining <= 0) break
      const reduce = Math.min(customWeights[k], remaining)
      customWeights[k] -= reduce
      remaining -= reduce
    }
  }
}

function checkWeights() {
  // Auto-trigger recalculation handled by computed
}

function resetWeights() {
  customWeights.ret = 50
  customWeights.dd = 25
  customWeights.sr = 25
  customWeights.calmar = 0
  customWeights.ir = 0
  customWeights.te = 0
}

function confirmWeights() {
  if (weightSum.value !== 100) return
  // 关闭权重面板并刷新排序（weightSum computed 为 100 时自动触发）
  showWeightPanel.value = false
  sortFunds()
}

function setClassSource(key) {
  const src = classSources.find(s => s.key === key)
  if (!src || !src.available) return
  classSource.value = key
  // 如果选中的是隐藏数据源，自动收起"更多"
  if (!mainSourceKeys.includes(key)) {
    showAllSources.value = false
  }
  filterT0.value = ''
  filterT1.value = ''
  loadData(true)
}

function onSourceChange() {
  setClassSource(classSource.value)
}

// 搜索/周期/分页/排序
const searchText = ref('')
const currentPeriod = ref('k1')
const sortAsc = ref(false)        // 靠谱指数排序方向（false=降序，true=升序）
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

// 点赞/吐槽/添加组合
const likedFunds = reactive(new Set())
const dislikedFunds = reactive(new Set())
const portfolioFunds = reactive(new Set())

// Auth
const { isLoggedIn } = useAuth()
const showPortfolioPicker = ref(false)
const pendingFund = ref(null)       // 待添加基金 { code, name }
const userPortfolios = ref([])
const portfolioPickerLoading = ref(false)

function toggleLike(code) {
  if (likedFunds.has(code)) { likedFunds.delete(code) }
  else { likedFunds.add(code); dislikedFunds.delete(code) }
}
function toggleDislike(code) {
  if (dislikedFunds.has(code)) { dislikedFunds.delete(code) }
  else { dislikedFunds.add(code); likedFunds.delete(code) }
}
async function togglePortfolio(code) {
  // 如果没有登录，直接本地标记
  if (!isLoggedIn.value) {
    if (portfolioFunds.has(code)) portfolioFunds.delete(code)
    else portfolioFunds.add(code)
    return
  }
  // 已登录：打开组合选择器
  const fund = funds.value.find(f => f.c === code)
  if (!fund) return
  pendingFund.value = { code: fund.c, name: fund.n || '' }
  portfolioPickerLoading.value = true
  try {
    userPortfolios.value = await getMyPortfolios()
  } finally {
    portfolioPickerLoading.value = false
  }
  showPortfolioPicker.value = true
}
async function selectPortfolioForFund(portfolioId) {
  if (!pendingFund.value) return
  await addFundToPortfolio(portfolioId, { c: pendingFund.value.code, n: pendingFund.value.name })
  portfolioFunds.add(pendingFund.value.code)
  showPortfolioPicker.value = false
  pendingFund.value = null
}
async function createAndAddFund() {
  const name = window.prompt('请输入新组合名称：')
  if (!name?.trim()) return
  await savePortfolio({ name: name.trim(), funds: [] })
  // 重新获取列表
  userPortfolios.value = await getMyPortfolios()
}

// ========== 计算属性：分类联动 ==========
const t0List = computed(() => Object.keys(CAT_TREE))

const t1List = computed(() => {
  if (!filterT0.value || !CAT_TREE[filterT0.value]) return []
  return Object.keys(CAT_TREE[filterT0.value])
})

// ========== 格式化 ==========
function fmtScore(v) {
  const n = parseFloat(v)
  if (!n || n <= 0) return '--'
  return n.toFixed(2)
}

function fmtScale(v) {
  if (v == null || v === '') return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万亿'
  if (n >= 1) return n.toFixed(2) + '亿'
  return (n * 10000).toFixed(0) + '万'
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

// 分类名去掉前缀（显示用）
function t1Short(t1) {
  if (!filterT0.value) return t1
  const prefix = filterT0.value.replace(/基金$/, '') + '-'
  return t1.startsWith(prefix) ? t1.slice(prefix.length) : t1
}

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

// ========== 智能识别筛选（基于基金名称） ==========
function buildNameFilter() {
  const filters = []
  if (filterETF.value === '1') filters.push({ type: 'name_contains', val: 'ETF' })
  if (filterETF.value === '0') filters.push({ type: 'name_not_contains', val: 'ETF' })
  if (filterLOF.value === '1') filters.push({ type: 'name_contains', val: 'LOF' })
  if (filterLOF.value === '0') filters.push({ type: 'name_not_contains', val: 'LOF' })
  if (filterFOF.value === '1') filters.push({ type: 't0_eq', val: 'FOF' })
  if (filterFOF.value === '0') filters.push({ type: 't0_neq', val: 'FOF' })
  if (filterDK.value === '1') filters.push({ type: 'name_contains', val: '定开' })
  if (filterDK.value === '0') filters.push({ type: 'name_not_contains', val: '定开' })
  return filters
}

// ========== 数据加载 ==========
async function loadData(reset = true) {
  if (loading.value) return
  loading.value = true
  if (reset) page.value = 1

  try {
    // 确定 t0 过滤（FOF 类型筛选用 t0_eq）
    let t0Filter = filterT0.value || undefined
    if (filterFOF.value === '1') t0Filter = 'FOF'
    if (filterFOF.value === '0' && !filterT0.value) t0Filter = undefined // 不能简单过滤

    const result = await fetchFundScores({
      t0: t0Filter,
      t1: filterT1.value || undefined,
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

function onT0Change() {
  filterT1.value = ''
  loadData(true)
}

function setT1(val) {
  filterT1.value = val
  loadData(true)
}

function onT1Change() {
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

// ========== 周期评分行横向滚动联动 ==========
const fundListRef = ref(null)
let syncScrollFlag = false

function setupScrollSync() {
  nextTick(() => {
    const container = fundListRef.value
    if (!container) return
    const scoreRows = container.querySelectorAll('.period-scores')
    if (scoreRows.length < 2) return

    const sync = (source) => {
      if (syncScrollFlag) return
      syncScrollFlag = true
      scoreRows.forEach(row => {
        if (row !== source) row.scrollLeft = source.scrollLeft
      })
      syncScrollFlag = false
    }

    scoreRows.forEach(row => {
      row.removeEventListener('scroll', row._scrollHandler)
      row._scrollHandler = () => sync(row)
      row.addEventListener('scroll', row._scrollHandler, { passive: true })
    })
  })
}

// 数据变化时重新绑定滚动联动
watch(() => funds.value.length, () => {
  if (funds.value.length > 0) setupScrollSync()
})

onMounted(() => {
  loadData()
  loadMeta()
})
</script>

<style scoped>
/* ========== gov.uk 风格靠谱指数 ========== */
.page-fund-rank { min-height: 100vh; }

/* 顶部栏 */
.top-bar {
  display: flex; align-items: center; gap: var(--space-md);
  padding: var(--space-md); border-bottom: 1px solid var(--border);
  background: var(--bg-card);
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
.search-box { flex: 1; position: relative; }
.search-input {
  width: 100%; padding: 8px 36px 8px 8px;
  border: 2px solid var(--brand); font-size: 16px;
  color: var(--text-primary); outline: none; box-sizing: border-box;
}
.search-input:focus { outline: 3px solid #ffdd00; outline-offset: 0; }
.search-input::placeholder { color: var(--text-secondary); }
.search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  color: var(--text-secondary); font-size: 14px; cursor: pointer;
}

/* 筛选区 */
.filter-section { background: var(--bg-card); border-bottom: 1px solid var(--border); }
.filter-row {
  display: flex; align-items: center; padding: var(--space-sm) var(--space-md);
  gap: var(--space-sm); flex-wrap: nowrap;
}
.filter-row-source { border-bottom: 1px solid var(--border); flex-wrap: nowrap; align-items: center; }
.source-tags { display: flex; align-items: center; gap: 8px; flex: 1; flex-wrap: wrap; }
.source-tag {
  padding: 4px 14px; font-size: 15px; color: var(--text-primary);
  background: var(--bg-body); border: 2px solid var(--bg-body);
  cursor: pointer; font-weight: 400; white-space: nowrap;
}
.source-tag:hover, .filter-select:hover { border-color: var(--brand); }
.source-tag.active {
  color: var(--brand); font-weight: 700;
  background: var(--bg-card); border-color: var(--brand);
}
.source-tag:disabled { color: var(--text-secondary); cursor: not-allowed; opacity: 0.6; }
.source-tag-badge { margin-left: 4px; font-size: 12px; color: var(--text-secondary); }
.source-tag--more {
  color: var(--brand); background: transparent; border-style: dashed;
  text-decoration: underline; text-underline-offset: 3px;
}
.source-tag--collapse { color: var(--brand); background: transparent; border-style: dashed; }
.filter-label {
  font-size: 14px; color: var(--text-secondary); font-weight: 700;
  flex-shrink: 0; white-space: nowrap; padding-top: 4px;
}
.filter-select-wrap { flex: 1; max-width: 360px; }
.filter-select {
  width: 100%; padding: 6px 32px 6px 8px;
  font-size: 16px; color: var(--text-primary);
  border: 2px solid var(--border); background: var(--bg-card);
  appearance: none; -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%230b0c0c' stroke-width='2' fill='none'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
  cursor: pointer; outline: none;
}
.filter-select:focus { border-color: var(--brand); outline: 3px solid #ffdd00; outline-offset: 0; }

/* 通用横向滚动 */
.scroll-x { overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: thin; }
.filter-chips { display: flex; flex-wrap: nowrap; gap: 0; flex: 1; }
.filter-chip {
  padding: 4px 12px; font-size: 16px; color: var(--link);
  cursor: pointer; text-decoration: underline; text-underline-offset: 4px;
  text-decoration-color: transparent; transition: text-decoration-color 0.15s;
  white-space: nowrap;
}
.filter-chip:hover { text-decoration-color: var(--link); }
.filter-chip.active {
  color: var(--brand); font-weight: 700; text-decoration: none;
  border-bottom: 4px solid var(--brand); padding-bottom: 0;
}
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
  padding: var(--space-sm) var(--space-md); background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}
.period-tabs { display: flex; gap: 0; white-space: nowrap; flex: 1; }
.period-tab {
  flex-shrink: 0; padding: 8px 16px; font-size: 16px; color: var(--link);
  cursor: pointer; border-bottom: 4px solid transparent; font-weight: 400;
  text-decoration: none;
}
.period-tab:hover { border-bottom-color: var(--border); }
.period-tab.active {
  color: var(--brand); font-weight: 700; border-bottom-color: var(--brand);
}
.sort-arrow { font-size: 12px; margin-left: 4px; }

.filter-result-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-sm) var(--space-md); background: var(--bg-body);
  border-top: 1px solid var(--border);
}
.filter-result-count { font-size: 16px; color: var(--text-secondary); }
.filter-result-count strong { color: var(--text-primary); font-weight: 700; }

.data-refresh-btn {
  padding: 6px 16px; border: none;
  background: var(--brand); color: #fff;
  font-size: 14px; font-weight: 500; cursor: pointer;
}
.data-refresh-btn:hover, .btn-confirm:hover { background: var(--brand-dark); }
.data-refresh-btn:disabled, .btn-confirm:disabled { opacity: 0.6; cursor: not-allowed; }

/* 基金列表（2行卡片布局） */
.fund-list { background: var(--bg-card); }
.fund-card {
  border-bottom: 1px solid var(--border);
  padding: var(--space-sm) var(--space-md);
  cursor: pointer; transition: background 0.1s;
}
.fund-card:hover { background: #f8f8f8; }

/* 第一行：基金代码 + 基金名称 */
.fund-row1 { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.fund-code { font-size: 13px; font-weight: 700; color: var(--text-primary); white-space: nowrap; }
.fund-name {
  font-size: 14px; color: var(--text-primary);
  cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fund-name:hover { text-decoration: underline; }

/* 第二行：规模/持仓 + 操作按钮 */
.fund-row2 {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--space-sm); margin-top: 6px; flex-wrap: wrap;
}
.fund-row2-data { display: flex; align-items: center; gap: var(--space-md); flex-shrink: 0; }
.fund-data-item { display: flex; flex-direction: column; align-items: center; min-width: 48px; }
.fund-data-item--na { opacity: 0.4; }
.fund-data-val { font-size: 13px; font-weight: 700; color: var(--text-primary); }
.fund-data-label { font-size: 11px; color: var(--text-secondary); }
.fund-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.action-btn {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 4px 6px; cursor: pointer;
  color: var(--text-secondary); border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}
.action-btn:hover { color: var(--brand); background: var(--bg-hover); }
.action-btn.active { color: var(--brand); background: #e6f7ee; }
.action-count { font-size: 11px; font-weight: 700; }

/* 第三行：各周期靠谱指数 */
.fund-row3 { margin-top: 6px; }
.period-scores { display: flex; gap: 2px; }
.period-score-item {
  display: flex; flex-direction: column; align-items: center;
  min-width: 52px; padding: 4px 6px;
  border: 1px solid var(--border); border-radius: 2px;
  cursor: pointer; transition: background 0.1s; flex-shrink: 0;
}
.period-score-item:hover { background: var(--bg-hover); }
.period-score-item.active {
  border-color: var(--brand); border-width: 2px; background: #f0f6ff;
}
.period-score-item.active .ps-label { color: var(--brand); font-weight: 700; }
.ps-label { font-size: 11px; color: var(--text-secondary); white-space: nowrap; }
.ps-score { font-size: 13px; font-weight: 700; }
.ps-score-centered { font-size: 15px; font-weight: 800; }

/* 统一评分颜色（列表 & 详情弹窗共用） */
.score-hot, .score-hot-text, .unified-val.risk-high { color: #d4351c; }
.score-warm, .score-warm-text, .unified-val.risk-mid { color: #f47738; }
.score-mid, .score-mid-text { color: #505a5f; }
.score-cool, .score-cool-text, .unified-val.risk-low { color: #00703c; }
.ret-up { color: var(--color-up); }
.ret-down { color: var(--color-down); }

/* 加载更多 */
.load-more {
  text-align: center; padding: var(--space-lg);
  font-size: 16px; color: var(--brand); cursor: pointer;
  text-decoration: underline; text-underline-offset: 4px;
}
.load-more:hover, .help-link:hover { color: var(--link-hover); }

/* 状态 */
.empty-state { text-align: center; padding: var(--space-2xl) var(--space-md); }
.empty-text {
  font-size: 19px; color: var(--text-primary); font-weight: 700;
  margin-bottom: var(--space-sm);
}
.empty-hint { font-size: 16px; color: var(--text-secondary); }
.loading-wrap { display: flex; justify-content: center; padding: var(--space-2xl) 0; }
.loading-text { font-size: 16px; color: var(--text-secondary); }

/* 底部说明区 */
.bottom-info {
  padding: var(--space-xl) var(--space-md) var(--space-2xl);
  border-top: 1px solid var(--border); margin-top: var(--space-xl);
  background: var(--bg-body);
}
.bottom-disclaimer { text-align: center; margin: 0 auto var(--space-md); max-width: 600px; }
.bottom-disclaimer p {
  margin: 3px 0; font-size: 14px; color: var(--text-secondary); line-height: 1.7;
}
.bottom-help-entry { text-align: center; }
.help-link {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 14px; color: var(--brand); cursor: pointer;
  text-decoration: underline; text-underline-offset: 3px;
}

/* ===== 弹窗通用基类 ===== */
.mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }
.panel-slide {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 600px; background: var(--bg-card);
  border: 1px solid var(--border);
  overflow: hidden; display: flex; flex-direction: column; z-index: 101;
}
.detail-panel { max-height: 88vh; }
.help-panel { max-height: 70vh; }
.panel-hd {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border);
  background: var(--bg-body); flex-shrink: 0;
}
.detail-name { font-size: 19px; font-weight: 700; flex: 1; margin-right: var(--space-md); line-height: 1.3; }
.help-title { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.panel-close { font-size: 24px; color: var(--text-primary); cursor: pointer; padding: 4px; line-height: 1; }
.panel-bd { flex: 1; overflow-y: auto; padding: var(--space-lg); }
.detail-section { margin-bottom: var(--space-xl); }
.detail-section-title {
  display: block; font-size: 19px; font-weight: 700; color: var(--text-primary);
  margin-bottom: var(--space-md);
  border-bottom: 2px solid var(--border); padding-bottom: 4px;
}
.attr-row {
  display: flex; justify-content: space-between; padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--border);
}
.attr-label { font-size: 16px; color: var(--text-secondary); flex-shrink: 0; width: 80px; }
.attr-value { font-size: 16px; color: var(--text-primary); text-align: right; flex: 1; line-height: 1.4; }
.attr-date { font-size: 14px; color: var(--text-secondary); }

/* 综合数据表 */
.unified-table { border: 1px solid var(--border); margin-top: var(--space-sm); }
.unified-head {
  display: flex; padding: var(--space-sm) var(--space-sm);
  border-bottom: 2px solid var(--border); background: var(--bg-body);
}
.unified-th { font-size: 13px; color: var(--text-secondary); font-weight: 700; text-align: center; }
.unified-row {
  display: flex; align-items: center; padding: 6px var(--space-sm);
  border-bottom: 1px solid var(--border);
}
.unified-row:last-child { border-bottom: none; }
.unified-label {
  width: 48px; font-size: 14px; color: var(--text-secondary);
  flex-shrink: 0; font-weight: 700;
}
.unified-val {
  flex: 1; text-align: center; font-size: 14px; font-weight: 700;
  color: var(--text-primary);
}
.unified-val:first-of-type { flex: 1.2; }

.detail-goto {
  display: block; text-align: center; padding: var(--space-md) 0 var(--space-sm);
  margin-top: var(--space-lg); border-top: 1px solid var(--border);
  font-size: 16px; color: var(--link); font-weight: 700; text-decoration: underline;
}

/* 帮助弹窗内容 */
.help-section { margin-bottom: var(--space-lg); }
.help-section-label {
  display: block; font-size: 19px; font-weight: 700; color: var(--text-primary);
  margin-bottom: var(--space-sm);
  border-bottom: 2px solid var(--border); padding-bottom: 4px;
}
.help-desc { display: block; font-size: 16px; color: var(--text-primary); line-height: 1.7; }
.help-color-row { display: flex; align-items: center; gap: var(--space-md); padding: 4px 0; }
.help-dot { width: 16px; height: 4px; flex-shrink: 0; }
.help-color-text { font-size: 16px; font-weight: 700; flex-shrink: 0; min-width: 100px; }
.help-color-desc { font-size: 16px; color: var(--text-secondary); }

/* 自定义权重面板 */
.weight-toggle {
  padding: var(--space-xs) var(--space-sm); font-size: 14px;
  color: var(--link); cursor: pointer; border: 1px solid var(--border);
  white-space: nowrap; display: flex; align-items: center; gap: 4px;
}
.weight-toggle:hover { background: var(--bg-hover); }
.weight-panel {
  border: 1px solid var(--border); background: var(--bg-card);
  padding: var(--space-lg); margin-top: var(--space-sm);
}
.weight-panel-header {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 19px; font-weight: 700; color: var(--text-primary);
  margin-bottom: var(--space-md);
}
.weight-panel-close { font-size: 20px; color: var(--text-secondary); cursor: pointer; }
.weight-sliders { display: flex; flex-direction: column; gap: var(--space-md); }
.weight-slider-item label {
  display: flex; justify-content: space-between;
  font-size: 16px; color: var(--text-primary); margin-bottom: var(--space-xs);
}
.ws-val { font-weight: 700; color: var(--brand); }
.weight-slider-item input[type="range"] {
  width: 100%; height: 8px; -webkit-appearance: none; background: var(--bg-body); outline: none;
}
.weight-slider-item input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 24px; height: 24px; background: var(--brand); cursor: pointer;
}
.weight-total {
  margin-top: var(--space-md); padding: var(--space-sm);
  font-size: 16px; font-weight: 700; text-align: center;
}
.weight-valid { background: #e6f7ee; color: #00703c; }
.weight-invalid { background: #fef0ef; color: #d4351c; }
.weight-warn { font-weight: 400; }
.weight-ok { color: #00703c; }
.weight-actions { text-align: center; margin-top: var(--space-sm); }
.btn-reset {
  background: none; border: 1px solid var(--border); color: var(--text-secondary);
  padding: var(--space-xs) var(--space-md); font-size: 14px; cursor: pointer;
}
.btn-reset:hover { background: var(--bg-hover); }
.btn-confirm {
  padding: var(--space-xs) var(--space-lg); margin-right: var(--space-sm);
  background: var(--brand); color: #fff; border: none;
  font-size: 14px; font-weight: 500; cursor: pointer;
}

/* 分类源禁用 */
.filter-chip.disabled { color: var(--text-secondary); opacity: 0.5; cursor: not-allowed; }

/* ===== 模态弹窗 ===== */
.modal-mask {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center;
}
.modal-box { background: #fff; padding: var(--space-lg); max-width: 520px; width: 90vw; }
.modal-box--sm { max-width: 400px; }
.modal-hd {
  font-size: 19px; font-weight: 700; color: var(--text-primary);
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: var(--space-md);
}
.modal-close {
  font-size: 24px; cursor: pointer; color: var(--text-secondary);
  text-decoration: none; line-height: 1;
}
.modal-bd { font-size: 16px; color: var(--text-primary); }

/* 组合选择器 */
.pf-picker-fund { padding: var(--space-sm); background: var(--bg-body); margin-bottom: var(--space-sm); }
.pf-picker-loading, .pf-picker-empty {
  padding: var(--space-lg) 0; text-align: center; color: var(--text-secondary);
}
.pf-picker-empty .link { color: var(--brand); cursor: pointer; text-decoration: underline; }
.pf-picker-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-sm); border: 1px solid var(--border);
  margin-bottom: 6px; cursor: pointer;
}
.pf-picker-item:hover { background: var(--bg-hover); }
.pf-picker-count { font-size: 14px; color: var(--text-secondary); }
</style>
