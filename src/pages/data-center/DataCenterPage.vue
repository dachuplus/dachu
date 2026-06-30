<template>
  <div class="page-placeholder">
    <!-- 页面标题 -->
    <h1 class="page-title">数据中心</h1>
    <p class="page-desc">ALLFUND.CN 数据库全部表一览。选择需要下载的数据表，点击下载 Excel 文件。数据每日 21:30（北京时间）自动更新。</p>

    <!-- 数据库表列表 -->
    <div class="card">
      <div class="card-title">数据库表 ({{ tables.length }} 张)</div>
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
            <td class="col-size">{{ t.size || '—' }}</td>
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

    <!-- API 接口文档 -->
    <div class="card">
      <div class="card-title">数据接口文档</div>
      <p class="section-desc">以下是 ALLFUND.CN 使用的所有外部数据接口，所有接口均来源于公开数据平台。</p>

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
          <tr><td class="meta-label">提取数据</td><td>基金管理人(公司名)、管理费率、托管费率、净资产规模、成立日期 — 通过正则表达式解析 HTML</td></tr>
        </table>
      </div>

      <!-- tsdata -->
      <div class="api-item">
        <h3 class="api-name">5. tsdata — 基金风险等级页面</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">URL</td><td><code>https://fundf10.eastmoney.com/tsdata_{基金代码}.html</code></td></tr>
          <tr><td class="meta-label">方法</td><td>GET</td></tr>
          <tr><td class="meta-label">返回</td><td>HTML</td></tr>
          <tr><td class="meta-label">提取数据</td><td>风险等级（low1~low5），通过 <code>chooseLow</code> CSS class 定位</td></tr>
        </table>
      </div>

      <!-- 东方财富 push2 -->
      <h2 class="api-group-title">二、东方财富行情 API</h2>
      <div class="api-item">
        <h3 class="api-name">6. push2 — 板块实时行情接口</h3>
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
        <h3 class="api-name">7. qt.gtimg.cn — 实时行情接口</h3>
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
        <h3 class="api-name">8. danjuanfunds — 指数估值接口</h3>
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

      <!-- value500 -->
      <h2 class="api-group-title">五、value500.com 宏观数据</h2>
      <div class="api-item">
        <h3 class="api-name">9. value500.com — 宏观指标页面</h3>
        <table class="api-meta-table">
          <tr><td class="meta-label">方法</td><td>GET（HTML 页面解析）</td></tr>
          <tr><td class="meta-label">用途</td><td>获取中国宏观指标数据，通过解析页面 ECharts title 文本提取数值</td></tr>
          <tr><td class="meta-label">代理方式</td><td>开发环境 Vite proxy；生产环境 Supabase Edge Function</td></tr>
        </table>
        <p class="api-subtitle">子页面及数据字段</p>
        <table class="field-table">
          <thead><tr><th>页面</th><th>URL</th><th>提取数据</th></tr></thead>
          <tbody>
            <tr><td>10年国债</td><td><code>/10Bond.html</code></td><td>1Y/5Y/10Y国债到期收益率 + 利差</td></tr>
            <tr><td>Shibor</td><td><code>/Shibor.asp</code></td><td>隔夜/1周/1月/1年 Shibor 利率</td></tr>
            <tr><td>M1/M2</td><td><code>/M1.asp</code></td><td>M1/M2 同比增速 + 剪刀差</td></tr>
            <tr><td>CPI</td><td><code>/CPI.asp</code></td><td>CPI 同比涨幅</td></tr>
            <tr><td>股债收益率比</td><td><code>/ep.asp</code></td><td>上交所/深交所 EP（1/PE）vs 10年国债收益率</td></tr>
            <tr><td>沪深300 PE/PB</td><td><code>/000300SHPEPB.asp</code></td><td>沪深300 PE/PB + 近5年历史百分位</td></tr>
          </tbody>
        </table>
      </div>

      <!-- akshare -->
      <h2 class="api-group-title">六、akshare 开源库</h2>
      <div class="api-item">
        <h3 class="api-name">10. akshare — 上证指数历史日线</h3>
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
        <h3 class="api-name">11. Supabase REST API + Management API + Edge Function</h3>
        <table class="field-table">
          <thead><tr><th>接口类型</th><th>URL</th><th>用途</th></tr></thead>
          <tbody>
            <tr><td>REST API</td><td><code>https://{PROJECT_REF}.supabase.co/rest/v1/{table}</code></td><td>前端/脚本读写数据库表</td></tr>
            <tr><td>Management API</td><td><code>https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query</code></td><td>Python 脚本执行 SQL（批量导入/更新/DDL）</td></tr>
            <tr><td>Edge Function</td><td><code>https://{PROJECT_REF}.supabase.co/functions/v1/value500</code></td><td>服务端代理 value500 + 蛋卷数据抓取，6小时 TTL 缓存</td></tr>
          </tbody>
        </table>
      </div>

      <!-- 接口汇总 -->
      <h2 class="api-group-title">接口汇总</h2>
      <table class="field-table summary-table">
        <thead><tr><th>#</th><th>接口名称</th><th>用途</th><th>方法</th></tr></thead>
        <tbody>
          <tr><td>1</td><td>rankhandler API</td><td>基金排行（含货币型）</td><td>GET/POST</td></tr>
          <tr><td>2</td><td>FundGuideapi</td><td>基金分类 + 收益数据（5大类）</td><td>GET</td></tr>
          <tr><td>3</td><td>pingzhongdata</td><td>净值历史/回撤/夏普/风险评级</td><td>GET</td></tr>
          <tr><td>4</td><td>fundf10 (jbgk)</td><td>公司/规模/费率详情</td><td>GET</td></tr>
          <tr><td>5</td><td>fundf10 (tsdata)</td><td>风险等级</td><td>GET</td></tr>
          <tr><td>6</td><td>push2 API</td><td>申万行业板块实时行情</td><td>GET</td></tr>
          <tr><td>7</td><td>qt.gtimg.cn</td><td>指数实时行情</td><td>GET</td></tr>
          <tr><td>8</td><td>danjuanfunds</td><td>指数估值评级</td><td>GET</td></tr>
          <tr><td>9</td><td>value500.com</td><td>宏观指标（6个子页面）</td><td>GET</td></tr>
          <tr><td>10</td><td>akshare</td><td>上证指数历史日线</td><td>库调用</td></tr>
          <tr><td>11</td><td>Supabase</td><td>数据库 + SQL + 代理函数</td><td>REST/SQL</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuth } from '../../composables/useAuth'

const { isLoggedIn } = useAuth()

const updateTime = ref('')
const tableData = ref({})

// 表定义
const tables = [
  { key: 'fund_combined', name: '基金综合数据表', desc: '基金分类(t0/t1)、详情(公司/规模/费率)、收益(ytd~r5y)、风险(dd1y/sr1y)、评分(k_all/score_grade/k0w~k10) — 核心合并表，20,677条', rows: 20677 },
  { key: 'fund_scores', name: '基金评分表', desc: 'CI每日更新核心评分表，11周期×3维度加权评分（k0w/k1m/k3m/k6m/k1/k2/k3/k5/k_all）、百分位评级、分类、份额类型', rows: 19325 },
  { key: 'fund_quarterly_scores', name: '季度评分表', desc: '基于季报数据的各时间窗口评分（3m/6m/1y/2y/3y/5y/7y/10y）+ 原始季度数据JSON', rows: 18584 },
  { key: 'macro_history', name: '宏观历史数据表', desc: '中国10年国债(cn10y)、美国10年国债(us10y)、Shibor、CPI、M2历史数据，覆盖1996-至今', rows: 24109 },
  { key: 'tougu_products', name: '投顾产品表', desc: '天天基金/华宝/盈米/新浪仓石四来源基金投顾产品，含收益率、最大回撤、标签分类', rows: 103 },
  { key: 'fund_scores_meta', name: '评分元数据表', desc: '评分更新时间、基金总数、有评分数、净值日期等元信息', rows: 2 },
  { key: 'config', name: '配置表', desc: '全站配置项（键值对，含meta/timestamp）', rows: 3 },
  { key: 'index_pe_history', name: '指数PE历史表', desc: '沪深300等指数的PE/PB历史估值数据', rows: 0 },
  { key: 'site_stats', name: '站点统计表', desc: '网站访问量统计', rows: 1 },
  { key: 'user_portfolios', name: '用户组合表', desc: '用户自建基金组合（含portfolio_data JSON）', rows: 3, sensitive: true },
  { key: 'user_profiles', name: '用户档案表', desc: '用户注册信息', rows: 0, sensitive: true },
]

const visibleTables = computed(() => {
  return tables.map(t => ({
    ...t,
    downloadable: t.sensitive ? isLoggedIn.value : true,
    downloadUrl: `/downloads/${t.key}.xlsx`,
    size: tableData.value[t.key]?.size || null,
  }))
})

function formatNum(n) {
  if (n === 0) return '0'
  if (n == null) return '—'
  return n.toLocaleString('zh-CN')
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

onMounted(loadIndex)
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

/* Card */
.card {
  background: #ffffff; border: 1px solid var(--border);
  padding: var(--space-lg); margin-bottom: var(--space-xl);
}
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-md); }
.section-desc { font-size: 16px; color: var(--text-secondary); margin-bottom: var(--space-lg); }

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

.table-footer { margin-top: var(--space-md); }
.update-time { font-size: 14px; color: var(--text-secondary); margin: 0; }

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
</style>
