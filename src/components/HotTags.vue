<template>
  <div class="hot-tags-section">
    <!-- Tab 切换：热门基金（行业）/ 热门基金（概念） -->
    <div class="tags-header">
      <span class="tags-title">热门基金</span>
      <div class="tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'all' }"
          @click="activeTab = 'all'"
        >全部</button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'concept' }"
          @click="activeTab = 'concept'"
        >概念</button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'industry' }"
          @click="activeTab = 'industry'"
        >行业</button>
      </div>
    </div>

    <!-- 新增：排序类别 + 阶段选择控件（参考天天基金 ztjj 页面） -->
    <div class="hot-controls" v-if="displayTags.length > 0">
      <!-- 排序类别：按涨幅 / 按资金流入（资金流入数据源待接入，暂禁用） -->
      <div class="control-row">
        <span class="control-label">排序类别</span>
        <div class="sort-group" role="group" aria-label="排序类别">
          <button
            class="sort-btn"
            :class="{ active: sortMode === 'byReturn' }"
            @click="sortMode = 'byReturn'"
          >按涨幅</button>
          <button
            class="sort-btn"
            :class="{ active: sortMode === 'byInflow' }"
            :disabled="true"
            :title="inflowDisabledHint"
            @click="sortMode = 'byInflow'"
          >按资金流入（开发中）</button>
        </div>
      </div>
      <!-- 阶段选择：实时 / 近1周 / 近1月 / 近3月 / 近1年 / 今年来 -->
      <div class="control-row">
        <span class="control-label">阶段</span>
        <div class="stage-tabs" role="tablist" aria-label="阶段选择">
          <button
            v-for="s in STAGES"
            :key="s.key"
            class="stage-tab"
            :class="{ active: activeStage === s.key, disabled: !stageAvailable(s.key) }"
            :disabled="!stageAvailable(s.key)"
            @click="activeStage = s.key"
          >{{ s.label }}</button>
        </div>
      </div>
    </div>

    <!-- 标签网格 -->
    <div class="tags-grid" v-if="displayTags.length > 0">
      <div
        v-for="tag in displayTags"
        :key="tag.name"
        class="tag-cell"
        :class="cellReturnClass(tag)"
        :style="{ background: tagColor(cellReturn(tag)) }"
        @click="openTagDetail(tag)"
      >
        <span class="tag-name">{{ tag.name }}</span>
        <!-- 新增：数值跟随所选阶段变化；正收益红色、负收益绿色（中国股市惯例） -->
        <span
          class="tag-return"
          v-if="cellReturn(tag) != null"
        >{{ fmtPctSigned(cellReturn(tag)) }}</span>
        <span class="tag-return" v-else>—</span>
      </div>
    </div>

    <!-- 数据来源说明（随阶段动态变化） -->
    <div class="tags-footnote" v-if="displayTags.length > 0">
      {{ stageFootnote }}数据来源：ALLFUND.CN
    </div>

    <!-- 加载中 -->
    <div class="tags-loading" v-if="loading && displayTags.length === 0">标签加载中...</div>

    <!-- 标签详情弹窗：关联基金列表 -->
    <Teleport to="body">
      <template v-if="selectedTag">
        <div class="mask" @click="selectedTag = null"></div>
        <div class="tag-detail-panel">
          <div class="detail-header">
            <div class="detail-title-wrap">
              <span class="detail-title">
                {{ selectedTag.name }}
                <span class="detail-type-badge" :class="selectedTag.tag_type">{{ selectedTag.tag_type === 'concept' ? '概念' : '行业' }}</span>
              </span>
              <span class="detail-return" :class="selectedTag.return_pct >= 0 ? 'positive' : 'negative'" v-if="selectedTag.return_pct != null">近1年收益 {{ fmtPct(selectedTag.return_pct) }}</span>
            </div>
            <div class="detail-header-actions">
              <button
                class="detail-share"
                v-if="tagFunds.length > 0"
                :disabled="shareGenerating"
                @click="generateShareImage"
                title="生成分享图片"
              >分享</button>
              <span class="detail-close" @click="selectedTag = null">&#x2715;</span>
            </div>
          </div>
          <div class="detail-body">
            <!-- 关联基金列表（前3只） -->
            <div class="funds-loading" v-if="tagFundsLoading">加载中...</div>
            <template v-else-if="tagFunds.length > 0">
              <div class="funds-count">相关基金（共 {{ tagFunds.length }} 只）</div>
              <div class="fund-tag-list">
                <div
                  v-for="f in tagFunds"
                  :key="f.c"
                  class="fund-tag-item"
                >
                  <div class="ft-main">
                    <div class="ft-line1">
                      <a class="ft-code" :href="eastMoneyUrl(f.c)" target="_blank">{{ f.c }}</a>
                      <a class="ft-name" :href="eastMoneyUrl(f.c)" target="_blank">{{ f.n || ('基金' + f.c) }}</a>
                    </div>
                    <div class="ft-line2">
                      <span
                        class="ft-manager"
                        :class="{ 'ft-empty': !f.fund_manager }"
                        :title="f.fund_manager ? '' : '暂无基金经理数据'"
                      >经理：{{ f.fund_manager || '—' }}</span>
                    </div>
                  </div>
                  <div class="ft-right">
                    <span class="ft-ret-label">近1年收益</span>
                    <span class="ft-ret" :style="{ color: retColor(f.r1y) }" v-if="f.r1y != null">{{ fmtRetPlain(f.r1y) }}%</span>
                    <span class="ft-ret" v-else>—</span>
                  </div>
                </div>
              </div>
            </template>
            <div class="funds-empty" v-else>
              <p>暂无关联基金数据</p>
              <p class="funds-empty-hint">可前往<a :href="eastmoneyTopicUrl(selectedTag.name)" target="_blank">天天基金</a>查看完整列表</p>
            </div>
            <!-- 数据来源 -->
            <div class="data-source-line">
              数据来源：ALLFUND.CN &nbsp;|&nbsp; 截止时间：{{ bottomUpdateTime || '—' }}
            </div>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 分享图片预览弹窗 -->
    <Teleport to="body">
      <template v-if="shareImage">
        <div class="mask" @click="shareImage = null"></div>
        <div class="share-panel">
          <div class="share-header">
            <span class="share-title">分享到朋友圈</span>
            <span class="detail-close" @click="shareImage = null">&#x2715;</span>
          </div>
          <div class="share-body">
            <img class="share-img" :src="shareImage" alt="分享图" />
            <p class="share-source">数据来源：ALLFUND.CN &nbsp;|&nbsp; 截止时间：{{ shareUpdateTime || '—' }}</p>
            <p class="share-hint">长按图片可保存到相册，或分享到朋友圈</p>
            <button class="share-save-btn" @click="saveShareImage">保存图片</button>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import QRCode from 'qrcode'
import { fetchFundTags, fetchFundMeta } from '../api/data.js'
import { fmtRetPlain } from '../utils/format.js'

const props = defineProps({
  /** 最大展示行数，默认显示全部 */
  maxRows: { type: Number, default: 0 },
})

// ========== 阶段与排序配置（数据来源：东财 ZTJJ GetBKDetailInfoNew 板块级接口） ==========
// 每个阶段映射到 fund_tag_perf 表字段：
//   d=日涨幅, w=近1周, m=近1月, q=近3月, y=近1年, sy=今年来
const STAGES = [
  { key: 'd',   label: '实时',   field: 'd' },
  { key: 'w1',  label: '近1周',  field: 'w' },
  { key: 'm1',  label: '近1月',  field: 'm' },
  { key: 'm3',  label: '近3月',  field: 'q' },
  { key: 'y1',  label: '近1年',  field: 'y' },
  { key: 'ytd', label: '今年来',  field: 'sy' },
]

// ========== 状态 ==========
const activeTab = ref('all') // 'all' | 'concept' | 'industry'
const allTags = ref([]) // [{ name, tag_type, return_pct, sort_order }]
const loading = ref(false)
const selectedTag = ref(null) // 当前选中的标签
const tagFunds = ref([]) // 标签关联基金列表（按主代码去重，≤7 只或展示实际数量）
const tagFundsLoading = ref(false)
const shareImage = ref(null) // 生成的分享图 dataURL
const shareGenerating = ref(false)
const shareUpdateTime = ref('') // 分享图数据截止时间（弹窗可见）
const fundMetaUpdateTime = ref('') // fund_scores 更新时间

// ========== 新增：排序/阶段状态 ==========
const sortMode = ref('byReturn') // 'byReturn'（按涨幅，默认）| 'byInflow'（按资金流入，开发中）
const activeStage = ref('y1')    // 默认选中阶段：近1年
const tagStageReturns = ref({})  // { [tagName]: { d, w1, m1, m3, y1, ytd } } 各阶段均值
const stageReturnsReady = ref(false) // 阶段聚合数据是否加载完成
const inflowDisabledHint = '资金流入排序开发中（数据源待接入）'

// ========== 计算属性 ==========
const displayTags = computed(() => {
  let list
  if (activeTab.value === 'all') {
    // 全部：概念 + 行业 合并
    list = allTags.value.slice()
  } else {
    list = allTags.value.filter(t => t.tag_type === activeTab.value)
  }
  // 新增：按涨幅排序（默认）——按当前选中阶段的收益值降序，缺失值排末尾
  // 注：阶段聚合数据未加载完成前，近1年阶段回退使用 fund_tags.return_pct，避免闪烁
  if (sortMode.value === 'byReturn') {
    list.sort((a, b) => (stageSortVal(b) ?? -Infinity) - (stageSortVal(a) ?? -Infinity))
  }
  // 按资金流入排序：当前 fund_tag_funds 无 relation 字段，按钮已禁用，暂未实现
  // 去重：同名标签只保留一个。all tab 已按收益降序，保留收益最高的；概念/行业 tab 保持原序保留首个
  const seen = new Set()
  const deduped = []
  for (const t of list) {
    if (!t || !t.name || seen.has(t.name)) continue
    seen.add(t.name)
    deduped.push(t)
  }
  list = deduped
  if (props.maxRows > 0) {
    return list.slice(0, props.maxRows * 8) // 每行8个
  }
  return list
})

// ========== 新增：阶段收益取值 / 展示辅助 ==========
// 当前阶段中文名（用于脚注）
const stageLabel = computed(() => STAGES.find(s => s.key === activeStage.value)?.label || '近1年')
// 动态脚注文案
const stageFootnote = computed(() => `板块收益为东财主题板块${stageLabel.value}涨跌幅，`)

// 取某标签在当前阶段的聚合均值（无数据返回 null）
function stageValue(name) {
  const m = tagStageReturns.value[name]
  if (!m) return null
  const v = m[activeStage.value]
  return (v == null || isNaN(v)) ? null : v
}

// 网格展示用的收益值：优先用阶段聚合值；近1年阶段若聚合缺失则回退 fund_tags.return_pct
function cellReturn(tag) {
  const v = stageValue(tag.name)
  if (v != null) return v
  if (activeStage.value === 'y1' && tag.return_pct != null) return tag.return_pct
  return null
}

// 排序用取值（与 cellReturn 逻辑一致，但仅用于排序比较）
function stageSortVal(tag) {
  return cellReturn(tag)
}

// 标签格子的涨跌CSS类（控制文字颜色：正=红字、负=绿字、空=灰字）
function cellReturnClass(tag) {
  const v = cellReturn(tag)
  if (v == null) return 'cell-null'
  return v >= 0 ? 'cell-pos' : 'cell-neg'
}

// 某阶段是否可用（有任一标签含该阶段数据）；数据未就绪前先放行避免闪烁
// fund_tag_perf 表对所有标签均含6周期数据，始终可用
function stageAvailable(_key) {
  return true
}

// 带正负号的百分比格式化（如 +2.79% / -1.00%）
function fmtPctSigned(v) {
  if (v == null) return ''
  const n = parseFloat(v)
  if (isNaN(n)) return ''
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}

/**
 * 从 fund_tag_perf 表加载所有标签的板块级各周期涨跌幅
 * 数据来源：东财 ZTJJ::GetBKDetailInfoNew 接口，由 ETL 脚本 sync_tag_performance.py 定时拉取
 * 字段：d(日涨幅), w(近1周), m(近1月), q(近3月), y(近1年), sy(今年来)
 */
async function loadTagStageReturns() {
  try {
    const { supabase } = await import('../api/supabase.js')
    if (!supabase) { stageReturnsReady.value = true; return }

    const { data, error } = await supabase
      .from('fund_tag_perf')
      .select('tag_index_code,tag_name,d,w,m,q,y,sy')

    if (error || !data || data.length === 0) {
      console.warn('[HotTags] fund_tag_perf 无数据（ETL可能未运行），阶段排序将降级', error)
      stageReturnsReady.value = true
      return
    }

    // 按 tag_name 建索引，供 cellReturn / displayTags 排序使用
    const fieldToKey = Object.fromEntries(STAGES.map(s => [s.field, s.key]))
    const result = {}
    for (const row of data) {
      const name = row.tag_name
      if (!name) continue
      result[name] = {}
      for (const s of STAGES) {
        const v = row[s.field]
        result[name][s.key] = (v == null || v === '') ? null : Number(v)
      }
    }
    tagStageReturns.value = result
    console.log(`[HotTags] fund_tag_perf 加载完成: ${data.length} 个标签`)
  } catch (e) {
    console.error('[HotTags] loadTagStageReturns error', e)
  } finally {
    stageReturnsReady.value = true
  }
}

// 底部「截止时间」展示值：
// 优先用系统级 meta 时间（fund_scores_meta 的 tsq/update_time/nav_date，由 openTagDetail 写入 fundMetaUpdateTime）；
// 若系统 meta 取不到，则兜底取该标签下「有数据的基金」（.OF 类）的最新净值日期 nav_date，避免显示「—」。
const bottomUpdateTime = computed(() => {
  if (fundMetaUpdateTime.value) return fundMetaUpdateTime.value
  const dates = tagFunds.value.map(f => f.nav_date).filter(Boolean)
  if (dates.length === 0) return ''
  let max = dates[0]
  for (const d of dates) if (d > max) max = d
  return max
})

// ========== 方法 ==========
async function loadTags() {
  loading.value = true
  try {
    const data = await fetchFundTags()
    if (Array.isArray(data)) {
      allTags.value = data
    }
  } catch (e) {
    console.error('[HotTags] load error', e)
  } finally {
    loading.value = false
  }
}

function openTagDetail(tag) {
  selectedTag.value = tag
  tagFunds.value = []
  loadTagFunds(tag)
  // 获取 fund_scores 更新时间（优先 tsq，其次 update_time / nav_date）
  fetchFundMeta().then(m => {
    if (!m) return
    // 后备链：tsq → update_time → nav_date
    const raw = m.tsq || m.update_time || m.nav_date || ''
    if (raw) {
      try {
        const d = new Date(raw)
        if (!isNaN(d.getTime())) {
          fundMetaUpdateTime.value = d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
        }
      } catch { /* ignore */ }
    }
  }).catch(e => {
    console.warn('[HotTags] fetchFundMeta failed', e)
  })
}

/** 从 fund_tag_funds 表查询标签关联基金（东财 ZTJJ 真实映射），按主代码去重后展示（≤7 只；关联不足 10 只则展示全部） */
async function loadTagFunds(tag) {
  tagFundsLoading.value = true
  try {
    const { supabase } = await import('../api/supabase.js')
    if (!supabase) { tagFundsLoading.value = false; return }

    // 1) 拉取该标签关联的全部基金（东财 ZTJJ 全量映射，sync_tag_funds_full.py 分页重拉）
    const { data: mappings, error: err1 } = await supabase
      .from('fund_tag_funds')
      .select('fund_code,fund_name,fund_type,syl_1n,sort_order,fund_manager')
      .eq('tag_name', tag.name)
      .order('sort_order', { ascending: true })
    // 无数据时直接显示空状态，不做任何兜底
    if (err1 || !mappings || mappings.length === 0) {
      tagFunds.value = []
      return
    }

    // 2) 用基金代码从 fund_scores 补充经理/规模/收益字段（一次性查全部，供去重时比规模）
    const allMapCodes = [...new Set(mappings.map(m => m.fund_code).filter(Boolean))]
    const codesWithOF = allMapCodes.map(c => c.endsWith('.OF') ? c : c + '.OF')
    const { data: scores } = await supabase
      .from('fund_scores')
      .select('c,n,fund_manager,r1y,k1,fund_scale,date')
      .in('c', [...allMapCodes, ...codesWithOF])
    const scoreMap = {}
    if (scores) {
      for (const s of scores) {
        // 去掉 .OF 后缀作为 key，确保与 fund_tag_funds 的代码匹配
        const key = s.c.replace(/\.OF$/i, '')
        scoreMap[key] = s
      }
    }

    // 3) 按主代码去重：同一基金的 A/C/E 多份额归为一组，每组保留主份额
    //    规则：A 类优先；无 A 类时取 fund_scale 最大者；同组取热度最高（sort_order 最小）
    const groups = new Map() // baseKey -> { m, share, sortOrder, scale }
    for (const m of mappings) {
      const key = baseFundKey(m.fund_name)
      const share = shareClassOf(m.fund_name)
      const so = m.sort_order ?? 999
      const sc = scoreMap[m.fund_code] || {}
      const scale = (typeof sc.fund_scale === 'number') ? sc.fund_scale : -1
      let g = groups.get(key)
      if (!g) {
        groups.set(key, { m, share, sortOrder: so, scale })
        continue
      }
      if (so < g.sortOrder) g.sortOrder = so // 热度最高（sort_order 最小）
      if (share === 'A' && g.share !== 'A') {
        g.m = m; g.share = 'A'; g.scale = scale // 主份额 A 优先
      } else if (share !== 'A' && g.share !== 'A' && scale > g.scale) {
        g.m = m; g.scale = scale // 无 A 时取规模更大者
      }
    }
    // 关联基金不足 10 只则全部展示，否则取热度前 7
    const distinct = [...groups.values()].sort((a, b) => a.sortOrder - b.sortOrder)
    const cap = distinct.length < 10 ? distinct.length : 7
    const kept = distinct.slice(0, cap).map(g => g.m)

    // 4) 合并输出
    tagFunds.value = kept.map(m => {
      const sc = scoreMap[m.fund_code] || {}
      return {
        c: m.fund_code,
        n: m.fund_name,  // 直接使用东财官方名称（已为主份额）
        t0: sc.t0,
        t1: sc.t1,
        t1_tt: sc.t1_tt,
        k1: sc.k1,
        r1y: sc.r1y ?? m.syl_1n,  // fund_scores优先，否则用东财近1年收益
        fund_manager: m.fund_manager || sc.fund_manager || '',  // 优先用 fund_tag_funds 已回填的经理（覆盖 ETF）；否则兜底 fund_scores
        fund_scale: sc.fund_scale,
        nav_date: sc.date || '',  // fund_scores 的净值日期，作为底部「截止时间」的兜底来源
        _ftype: m.fund_type,
      }
    })
  } catch (e) {
    console.error('[HotTags] loadTagFunds error', e)
  } finally {
    tagFundsLoading.value = false
  }
}

/** 颜色映射：根据收益率返回颜色（正=红粉渐变，负=绿渐变，参考天天基金） */
function tagColor(ret) {
  if (ret == null) return '#e8e8e8'
  const r = parseFloat(ret)
  if (isNaN(r)) return '#e8e8e8'
  if (r >= 0) {
    // 正收益：红→粉渐变（0%=浅粉, 600%+=深红）
    const v = Math.min(r, 600)
    const ratio = v / 600
    const rv = Math.round(255 - ratio * 60)
    const gv = Math.round(224 - ratio * 200)
    const bv = Math.round(224 - ratio * 210)
    return `rgb(${rv},${gv},${bv})`
  } else {
    // 负收益：绿渐变（0%=浅绿, -25%+=深绿）
    const v = Math.max(r, -25)
    const ratio = v / -25  // 0~1
    const rv = Math.round(190 - ratio * 130)   // 190→60
    const gv = Math.round(235 - ratio * 125)   // 235→110
    const bv = Math.round(200 - ratio * 145)   // 200→55
    return `rgb(${rv},${gv},${bv})`
  }
}

function fmtPct(v) {
  if (v == null) return ''
  const n = parseFloat(v)
  if (isNaN(n)) return ''
  return n.toFixed(2) + '%'
}

function retColor(v) {
  if (v == null) return 'var(--text-secondary)'
  const n = parseFloat(v)
  if (isNaN(n) || n === 0) return 'var(--text-secondary)'
  return n > 0 ? '#d4351c' : '#00703c'
}

function eastMoneyUrl(code) {
  if (!code) return '#'
  const pureCode = code.replace(/\.of$/i, '').replace(/\.OF$/, '')
  return `https://fund.eastmoney.com/${pureCode}.html`
}

function eastmoneyTopicUrl(topicName) {
  return `https://fund.eastmoney.com/ztjj/#!syl/Y/curr/zf-${encodeURIComponent(topicName)}/fst/DESC`
}

// 份额类别：取基金名末尾的 A/C/E/B/D/I/H/F/Y（前一位须为中文/数字/)/空格，避免误伤 ETF/LOF/QDII 等缩写）
function shareClassOf(name) {
  if (!name) return ''
  const m = name.trim().replace(/类$/, '').match(/^(.+[一-龥0-9)\s])\s*([ACEFBDHIY])$/)
  return m ? m[2] : ''
}
// 主基金 key：去掉末尾份额字母，把 A/C/E 等多份额归为同一只基金
function baseFundKey(name) {
  if (!name) return ''
  const s = name.trim().replace(/类$/, '')
  const m = s.match(/^(.+[一-龥0-9)\s])\s*([ACEFBDHIY])$/)
  return m ? m[1] : s
}

/** 截断文本（canvas 绘制用） */
function truncateText(ctx, text, maxWidth) {
  if (!text) return ''
  if (ctx.measureText(text).width <= maxWidth) return text
  let t = text
  while (t.length > 1 && ctx.measureText(t + '…').width > maxWidth) {
    t = t.slice(0, -1)
  }
  return t + '…'
}

/** 文字自动换行（canvas 用） */
function wrapText(ctx, text, maxWidth) {
  if (!text) return []
  const lines = []
  let current = ''
  for (const ch of text) {
    const test = current + ch
    if (ctx.measureText(test).width <= maxWidth) {
      current = test
    } else {
      if (current) lines.push(current)
      current = ch
    }
  }
  if (current) lines.push(current)
  return lines
}

/** 调用 DeepSeek 生成标签相关金句 */
async function generateTagline(tagName, tagReturnPct, isPositive, funds) {
  const apiKey = import.meta.env.VITE_DEEPSEEK_API_KEY || ''
  if (!apiKey) return ''

  // 构建基金表现摘要
  const fundSummary = funds.slice(0, 3).map(f => {
    const ret = f.r1y != null ? (f.r1y >= 0 ? '+' : '') + f.r1y.toFixed(2) + '%' : '—'
    return `${f.n || f.c}(${ret})`
  }).join('、')

  const direction = isPositive ? '大涨' : '下跌'
  const toneInstruction = isPositive
    ? '写一句正向的、张扬的、充满斗志和激情的金句，让读者看了热血沸腾想立刻买入或持有'
    : '写一句鼓励的、温暖的、给人坚持力量的金句，让读者在亏损中不放弃、相信长期价值'

  // 板块收益格式化：必须使用这个真实数据
  const retStr = tagReturnPct != null ? (tagReturnPct >= 0 ? '+' : '') + tagReturnPct.toFixed(2) + '%' : ''

  const prompt = `你是一个有感染力的基金投资博主。请根据以下信息，${toneInstruction}。

要求：
- 金句必须与标签「${tagName}」强相关，体现该赛道的行业特征
- ${isPositive ? `要体现涨幅的亮眼程度。如果金句里包含收益率数字，必须且只能用「${retStr}」这个板块近1年收益数据，禁止编造其他数字` : '要体现当前困难是暂时的，该赛道长期逻辑未变'}
- 一句话，不超过30个字
- 不要用emoji，不要引号，直接输出金句正文

标签：${tagName}
板块方向：${direction}
板块近1年收益（唯一权威数字）：${retStr || '—'}
代表性基金：${fundSummary || '无'}`

  const response = await fetch('https://api.deepseek.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        { role: 'system', content: '你是擅长写短小有力投资金句的高手。只输出金句正文，不要任何解释、前缀、后缀。' },
        { role: 'user', content: prompt }
      ],
      temperature: 0.85,
      max_tokens: 100
    })
  })
  if (!response.ok) return ''
  const result = await response.json()
  let content = result.choices?.[0]?.message?.content || ''
  // 清理可能的引号和换行
  content = content.replace(/^["'「『]|["'」』]$/g, '').replace(/\n/g, ' ').trim()
  return content.slice(0, 60) // 安全截断
}

/** 生成分享图片：含标签 + 基金 + 金句 + 二维码 */
async function generateShareImage() {
  if (shareGenerating.value) return
  shareGenerating.value = true
  try {
    const scale = 2
    const W = 750
    const pad = 30
    const headerH = 150
    const titleGap = 110
    const fundH = 150
    const fundGap = 16
    const qrSize = 190
    const qrBottomGap = 70

    const list = tagFunds.value
    // 计算平均收益用于判断涨跌方向
    const avgReturn = list.length > 0
      ? list.reduce((s, f) => s + (f.r1y ?? 0), 0) / list.length
      : 0
    const isPositive = avgReturn >= 0

    // 获取金句（DeepSeek）
    let tagline = ''
    try {
      tagline = await generateTagline(selectedTag.value.name, selectedTag.value.return_pct, isPositive, list)
    } catch { /* 静默失败，不显示金句 */ }

    // 获取更新时间
    let updateTimeStr = ''
    try {
      const meta = await fetchFundMeta()
      const rawTime = meta?.tsq || meta?.update_time || meta?.nav_date
      if (rawTime) {
        const d = new Date(rawTime)
        if (!isNaN(d.getTime())) {
          updateTimeStr = d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
        }
      }
      // 兜底：系统 meta 无时间时，取标签下「有数据的基金」(.OF 类) 的最新净值日期
      if (!updateTimeStr) {
        const dates = list.map(f => f.nav_date).filter(Boolean)
        if (dates.length > 0) {
          let max = dates[0]
          for (const d of dates) if (d > max) max = d
          updateTimeStr = max
        }
      }
    } catch { /* ignore */ }
    shareUpdateTime.value = updateTimeStr

    let H = headerH + titleGap + 20
    H += list.length * (fundH + fundGap)
    H += 30 // 与金句间距
    if (tagline) H += 50 // 金句高度
    H += 20 // 金句与二维码间距
    const qrY = H
    H += qrSize + qrBottomGap
    H += 30 // 来源行高度

    const canvas = document.createElement('canvas')
    canvas.width = W * scale
    canvas.height = H * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.textBaseline = 'top'

    // 背景
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, W, H)

    // 顶部品牌蓝条
    ctx.fillStyle = '#1d70b8'
    ctx.fillRect(0, 0, W, headerH)
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'left'
    ctx.font = 'bold 38px sans-serif'
    ctx.fillText('ALLFUND.CN', pad, 34)
    ctx.font = '24px sans-serif'
    ctx.fillStyle = 'rgba(255,255,255,0.92)'
    ctx.fillText('靠谱指数 · 热门基金', pad, 86)

    // 标签标题
    let y = headerH + 30
    ctx.textAlign = 'left'
    ctx.fillStyle = '#1a1a1a'
    ctx.font = 'bold 40px sans-serif'
    ctx.fillText(truncateText(ctx, selectedTag.value.name, W - pad * 2 - 160), pad, y)
    // 标签类型徽标
    const badgeText = selectedTag.value.tag_type === 'concept' ? '概念' : '行业'
    ctx.font = 'bold 22px sans-serif'
    const bw = ctx.measureText(badgeText).width + 24
    ctx.fillStyle = badgeText === '概念' ? '#d4351c' : '#1d70b8'
    roundRect(ctx, W - pad - bw, y + 6, bw, 36, 6)
    ctx.fill()
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'center'
    ctx.fillText(badgeText, W - pad - bw / 2, y + 13)
    // 标签收益率（根据涨跌变色）
    const tagRet = parseFloat(selectedTag.value.return_pct)
    const isTagPositive = !isNaN(tagRet) && tagRet >= 0
    ctx.textAlign = 'left'
    ctx.fillStyle = isTagPositive ? '#d4351c' : '#00703c'
    ctx.font = 'bold 26px sans-serif'
    ctx.fillText('近1年收益 ' + fmtPct(selectedTag.value.return_pct), pad, y + 56)

    // 基金卡片
    y = headerH + titleGap
    for (const f of list) {
      // 卡片底
      ctx.fillStyle = '#f6f8fb'
      roundRect(ctx, pad, y, W - pad * 2, fundH, 12)
      ctx.fill()
      ctx.strokeStyle = '#e3e8ef'
      ctx.lineWidth = 1
      roundRect(ctx, pad + 0.5, y + 0.5, W - pad * 2 - 1, fundH - 1, 12)
      ctx.stroke()

      const innerX = pad + 20
      // 代码
      ctx.textAlign = 'left'
      ctx.fillStyle = '#1d70b8'
      ctx.font = 'bold 22px sans-serif'
      ctx.fillText(f.c || '', innerX, y + 18)
      // 名称
      ctx.fillStyle = '#1a1a1a'
      ctx.font = 'bold 26px sans-serif'
      ctx.fillText(truncateText(ctx, f.n || ('基金' + f.c), W - pad * 2 - 40 - 150), innerX, y + 50)
      // 经理
      ctx.fillStyle = '#666666'
      ctx.font = '19px sans-serif'
      ctx.fillText('经理：' + (f.fund_manager || '—'), innerX, y + 92)

      // 区间收益（右侧）
      ctx.textAlign = 'right'
      const r1y = f.r1y
      ctx.fillStyle = (r1y == null || r1y >= 0) ? '#d4351c' : '#00703c'
      ctx.font = 'bold 32px sans-serif'
      const retStr = r1y == null ? '—' : (r1y >= 0 ? '+' : '') + r1y.toFixed(2) + '%'
      ctx.fillText(retStr, W - pad - 20, y + 44)
      ctx.fillStyle = '#999999'
      ctx.font = '17px sans-serif'
      ctx.fillText('近1年收益', W - pad - 20, y + 92)

      y += fundH + fundGap
    }

    // 金句（DeepSeek 生成，在二维码上方）
    if (tagline) {
      ctx.textAlign = 'center'
      ctx.fillStyle = isPositive ? '#d4351c' : '#1d70b8'
      ctx.font = 'bold 24px sans-serif'
      // 自动换行：金句较长时分行
      const maxTaglineW = W - pad * 2
      const lines = wrapText(ctx, tagline, maxTaglineW)
      let lineY = qrY - lines.length * 32 - 10
      for (const line of lines) {
        ctx.fillText(line, W / 2, lineY)
        lineY += 30
      }
    }

    // 二维码
    const qrCanvas = document.createElement('canvas')
    await QRCode.toCanvas(qrCanvas, 'https://www.allfund.cn', {
      width: qrSize * scale,
      margin: 1,
      color: { dark: '#000000', light: '#ffffff' },
    })
    ctx.drawImage(qrCanvas, (W - qrSize) / 2, qrY, qrSize, qrSize)
    // 二维码说明
    ctx.textAlign = 'center'
    ctx.fillStyle = '#1d70b8'
    ctx.font = 'bold 26px sans-serif'
    ctx.fillText('微信扫一扫 · 访问 www.allfund.cn', W / 2, qrY + qrSize + 18)
    ctx.fillStyle = '#999999'
    ctx.font = '18px sans-serif'
    ctx.fillText('识别二维码，查看靠谱指数与更多热门基金', W / 2, qrY + qrSize + 52)

    // 来源信息
    if (updateTimeStr) {
      ctx.fillStyle = '#bbbbbb'
      ctx.font = '15px sans-serif'
      ctx.fillText('来源：ALLFUND.CN  |  ' + updateTimeStr, W / 2, qrY + qrSize + 80)
    } else {
      ctx.fillStyle = '#bbbbbb'
      ctx.font = '15px sans-serif'
      ctx.fillText('来源：ALLFUND.CN', W / 2, qrY + qrSize + 80)
    }

    shareImage.value = canvas.toDataURL('image/png')
  } catch (e) {
    console.error('[HotTags] generateShareImage error', e)
    alert('生成分享图片失败，请重试')
  } finally {
    shareGenerating.value = false
  }
}

/** 圆角矩形路径 */
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

/** 保存分享图片 */
function saveShareImage() {
  if (!shareImage.value) return
  const a = document.createElement('a')
  a.href = shareImage.value
  const safeName = (selectedTag.value?.name || 'fund') + '-allfund.png'
  a.download = safeName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// ========== 生命周期 ==========
onMounted(() => {
  loadTags()
  loadTagStageReturns()
})

defineExpose({ refresh: loadTags })
</script>

<style scoped>
.hot-tags-section {
  background: #ffffff;
  border-bottom: 1px solid var(--border);
}

/* 头部 */
.tags-header {
  display: flex;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  gap: var(--space-md);
}
.tags-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  flex-shrink: 0;
}
.tabs {
  display: flex;
  gap: 0;
}
.tab-btn {
  padding: 4px 14px;
  font-size: 14px;
  color: var(--link);
  cursor: pointer;
  border: 1px solid var(--border);
  background: #fff;
  text-decoration: none;
  transition: all 0.15s;
}
.tab-btn:hover { border-color: #1d70b8; }
.tab-btn.active {
  color: #fff;
  background: #1d70b8;
  border-color: #1d70b8;
  font-weight: 700;
}

/* ===== 新增：排序类别 + 阶段选择控件（gov.uk 风格，品牌色 #1d70b8） ===== */
.hot-controls {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-top: 1px solid var(--border);
}
.control-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.control-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  flex-shrink: 0;
}
/* 排序类别按钮组 */
.sort-group {
  display: inline-flex;
  gap: 8px;
}
.sort-btn {
  padding: 4px 12px;
  font-size: 13px;
  color: var(--text-primary);
  background: #f3f2f1;       /* 未选中：灰底黑字 */
  border: 1px solid var(--border);
  border-radius: 2px;        /* 小圆角 */
  cursor: pointer;
  transition: all 0.15s;
}
.sort-btn:hover:not(:disabled) {
  border-color: #1d70b8;
}
.sort-btn.active {
  color: #fff;               /* 选中：蓝底白字 */
  background: #1d70b8;
  border-color: #1d70b8;
  font-weight: 700;
}
.sort-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
/* 阶段 tabs */
.stage-tabs {
  display: flex;
  gap: 16px;                 /* tab 间距 16px */
  flex-wrap: wrap;
}
.stage-tab {
  position: relative;
  padding: 4px 0;
  font-size: 13px;
  color: var(--text-secondary);  /* 未选中：灰字 */
  background: transparent;
  border: none;
  cursor: pointer;
  transition: color 0.15s;
}
.stage-tab:hover:not(:disabled) {
  color: #1d70b8;
}
.stage-tab.active {
  color: #1d70b8;            /* 选中：蓝字 */
  font-weight: 700;
}
/* 选中态底部 2px 蓝色横线 */
.stage-tab.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 2px;
  background: #1d70b8;
}
.stage-tab.disabled {
  color: #b1b4b6;            /* 无数据源时灰置 */
  cursor: not-allowed;
}
.stage-tab:disabled {
  cursor: not-allowed;
}
@media (max-width: 767px) {
  .control-row { gap: 8px; }
  .stage-tabs { gap: 12px; }
  .stage-tab { font-size: 12px; }
}

/* 标签格子文字颜色：参考天天基金（正=深红字、负=深绿字、空=灰色） */
.tag-cell.cell-pos { color: #b01e1e; }   /* 正收益：深红（对标天天基金红字） */
.tag-cell.cell-neg { color: #0a6e31; }   /* 负收益：深绿（对标天天基金绿字） */
.tag-cell.cell-null { color: #999999; }  /* 无数据：灰色 */

/* 标签数值：继承父级颜色，不再单独设色 */
.tag-return.positive, .tag-return.negative { color: inherit; }

/* 标签网格：8列布局 */
.tags-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  padding: var(--space-sm) var(--space-md) var(--space-md);
}
@media (max-width: 767px) {
  /* 手机版固定四列，保持均衡舒适的点按区域 */
  .tags-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
    padding: var(--space-sm) var(--space-sm) var(--space-md);
  }
  .tag-cell {
    padding: 7px 2px;
    min-height: 48px;
  }
  .tag-name { font-size: 12px; }
  .tag-return { font-size: 10px; }
}

.tag-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
  min-height: 52px;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  border-radius: 2px;
  text-align: center;
}
.tag-cell:hover {
  opacity: 0.85;
  transform: scale(1.03);
}
.tag-cell:active {
  transform: scale(0.97);
}
.tag-name {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  word-break: keep-all;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.tag-return {
  font-size: 11px;
  margin-top: 2px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.tags-loading {
  text-align: center;
  padding: var(--space-md);
  font-size: 14px;
  color: var(--text-secondary);
}
.tags-footnote {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  padding: 6px var(--space-md) var(--space-sm);
  line-height: 1.4;
}

/* ===== 标签详情弹窗（垂直居中，保证完整展示） ===== */
.tag-detail-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: calc(100% - 32px);
  max-width: 560px;
  max-height: 88vh;
  background: #ffffff;
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 101;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 2px solid var(--border);
  background: #f3f2f1;
  flex-shrink: 0;
}
.detail-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-type-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  color: #fff;
  flex-shrink: 0;
}
.detail-type-badge.concept { background: #d4351c; }
.detail-type-badge.industry { background: #1d70b8; }
.detail-return {
  font-size: 15px;
  font-weight: 700;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
/* 正收益红色，负收益绿色 */
.detail-return.positive { color: #d4351c; }
.detail-return.negative { color: #00703c; }
.detail-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-shrink: 0;
}
.detail-share {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: #1d70b8;
  border: none;
  border-radius: 2px;
  padding: 5px 14px;
  cursor: pointer;
}
.detail-share:disabled {
  opacity: 0.6;
  cursor: default;
}
.detail-close {
  font-size: 24px;
  color: var(--text-primary);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
  flex-shrink: 0;
}
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md) var(--space-lg);
}
.funds-count {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}
.fund-tag-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.fund-tag-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.fund-tag-item:last-child { border-bottom: none; }
.ft-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ft-line1 {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
}
.ft-code {
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
  color: var(--text-primary);
  text-decoration: none;
  flex-shrink: 0;
}
.ft-code:hover { color: var(--link); text-decoration: underline; }
.ft-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
  flex: 1;
  min-width: 0;
}
.ft-name:hover { color: var(--link); text-decoration: underline; }
.ft-line2 {
  display: flex;
  align-items: center;
}
.ft-manager {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 场内 ETF/LOF 基金暂无经理数据：灰色斜体，不显眼，不报异常 */
.ft-manager.ft-empty {
  font-style: italic;
  color: #9b9b9b;
  cursor: help;
}
.ft-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
  min-width: 88px;
}
.ft-ret-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}
.ft-ret {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.funds-loading, .funds-empty {
  text-align: center;
  padding: var(--space-xl) 0;
  color: var(--text-secondary);
  font-size: 15px;
}
.funds-empty p { margin: var(--space-xs) 0; }
.funds-empty-hint { font-size: 13px; }
.funds-empty a { color: var(--link); text-decoration: underline; }
.data-source-line {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  padding-top: var(--space-sm);
  margin-top: var(--space-xs);
  border-top: 1px solid #f0f0f0;
}

.mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }

/* ===== 分享图片预览弹窗 ===== */
.share-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: calc(100% - 32px);
  max-width: 420px;
  background: #ffffff;
  border: 1px solid var(--border);
  z-index: 102;
  display: flex;
  flex-direction: column;
  max-height: 92vh;
}
.share-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-lg);
  border-bottom: 1px solid var(--border);
  background: #f3f2f1;
  flex-shrink: 0;
}
.share-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.share-body {
  padding: var(--space-md);
  overflow-y: auto;
  text-align: center;
}
.share-img {
  width: 100%;
  height: auto;
  border: 1px solid #eee;
  display: block;
}
.share-source {
  font-size: 12px;
  color: var(--text-secondary);
  margin: var(--space-sm) 0 4px;
  text-align: center;
}
.share-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 4px 0 var(--space-sm);
}
.share-save-btn {
  display: block;
  width: 100%;
  padding: 10px;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: #1d70b8;
  border: none;
  border-radius: 2px;
  cursor: pointer;
}
</style>
