/**
 * utils/market-data.js - 实时市场数据服务 v2
 *
 * 移植自 asset-config-miniapp，ES Module 版本
 * wx.request → fetch()
 *
 * 数据来源（全部公开合规）：
 * 1. 腾讯股票API（qt.gtimg.cn）→ 指数实时行情 + PE/PB
 * 2. 东财 push2 API → 申万行业板块
 * 3. 新浪行业API → 申万行业（降级方案）
 */

import { calcPercentile } from './calc.js'

// ===== 工具函数 =====

/**
 * 通用请求封装（fetch 版）
 * @param {string} url
 * @param {number} timeout - 超时毫秒数，默认 5000
 * @returns {Promise<string>}
 */
function request(url, timeout = 5000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  return fetch(url, { signal: controller.signal })
    .then(res => {
      clearTimeout(timer)
      if (!res.ok) throw new Error('HTTP ' + res.status)
      return res.text()
    })
    .catch(err => {
      clearTimeout(timer)
      throw err
    })
}

// ===== 1. 指数实时行情 =====

export const INDEX_CODES = {
  '上证指数': 'sh000001',
  '深证成指': 'sz399001',
  '创业板指': 'sz399006',
  '沪深300': 'sh000300',
  '上证50': 'sh000016',
  '中证500': 'sh000905',
  '中证1000': 'sh000852',
  '中证800': 'sh000906',
  '创业板50': 'sz399673',
  '上证国债': 'sh000012',
  '中证红利': 'sh000922',
  '国证价值': 'sz399371',
  '国证成长': 'sz399370',
  '黄金ETF': 'sh518880',
  '商品ETF': 'sz159934',
  '豆粕ETF': 'sz159985'
}

/**
 * 获取主要指数实时行情（腾讯API）
 * @returns {Promise<Object>} { 指数名/sh代码: { name, code, price, change, changePct, pe, pb, ... } }
 */
export function getIndexQuotes() {
  const codes = Object.values(INDEX_CODES).join(',')
  const url = 'https://qt.gtimg.cn/q=' + codes

  return request(url).then(text => {
    const result = {}
    const lines = text.split(';')
    for (const line of lines) {
      if (!line.trim()) continue
      const parts = line.split('~')
      if (parts.length < 5) continue

      let fullCode = ''
      const p0 = parts[0] || ''
      const m = p0.match(/v_(sh|sz)(\d+)/i)
      if (m) {
        fullCode = m[1].toLowerCase() + m[2]
      }
      const shortCode = (parts[2] || '').trim()
      if (!shortCode && !fullCode) continue

      const high52w = parts.length > 67 ? (parseFloat(parts[67]) || 0) : 0
      const low52w  = parts.length > 68 ? (parseFloat(parts[68]) || 0) : 0
      const highToday = parts.length > 33 ? (parseFloat(parts[33]) || 0) : 0
      const lowToday  = parts.length > 34 ? (parseFloat(parts[34]) || 0) : 0

      const data = {
        name: parts[1],
        code: fullCode || shortCode,
        price: parts.length > 3 ? (parseFloat(parts[3]) || 0) : 0,
        preClose: parts.length > 4 ? (parseFloat(parts[4]) || 0) : 0,
        open: parts.length > 5 ? (parseFloat(parts[5]) || 0) : 0,
        volume: parts.length > 6 ? (parseInt(parts[6]) || 0) : 0,
        amount: parts.length > 7 ? (parseFloat(parts[7]) || 0) : 0,
        change: parts.length > 31 ? (parseFloat(parts[31]) || 0) : 0,
        changePct: parts.length > 32 ? (parseFloat(parts[32]) || 0) : 0,
        pe: parts.length > 39 ? (parseFloat(parts[39]) || 0) : 0,
        pb: parts.length > 62 ? (parseFloat(parts[62]) || 0) : 0,
        high: high52w || highToday,
        low: low52w || lowToday,
        high52w,
        low52w,
        updateTime: parts.length > 30 ? (parts[30] || '') : ''
      }

      if (fullCode) result[fullCode] = data
      if (shortCode) result[shortCode] = data
      if (parts[1]) result[parts[1]] = data
    }
    return result
  })
}

// ===== 2. 申万行业板块数据 =====

export const SW_L1_STANDARD = [
  '农林牧渔', '基础化工', '钢铁', '有色金属', '电子',
  '家用电器', '食品饮料', '纺织服饰', '轻工制造', '医药生物',
  '公用事业', '交通运输', '房地产', '商贸零售', '社会服务',
  '银行', '非银金融', '建筑材料', '建筑装饰', '电力设备',
  '国防军工', '计算机', '传媒', '通信', '煤炭',
  '石油石化', '环保', '美容护理', '机械设备', '汽车',
  '综合'
]

const EM_NAME_MAP = {
  '玻璃玻纤': '建筑材料', '航运港口': '交通运输', '电网设备': '电力设备',
  '电力': '公用事业', '电子化学品': '基础化工', '非金属材料': '建筑材料',
  '非银金融': '非银金融', '纺织服饰': '纺织服饰', '钢铁': '钢铁',
  '工程机械': '机械设备', '工业金属': '有色金属', '光伏设备': '电力设备',
  '航空机场': '交通运输', '航天装备': '国防军工', '环保': '环保',
  '化学纤维': '基础化工', '化学原料': '基础化工', '环境治理': '环保',
  '火电': '公用事业', '家居用品': '轻工制造', '家电': '家用电器',
  '建材': '建筑材料', '建筑装饰': '建筑装饰', '交运设备': '汽车',
  '交通设施': '交通运输', '交通运输': '交通运输', '教育': '社会服务',
  '贵金属': '有色金属', '金融服务': '银行', '酒店餐饮': '社会服务',
  '军工电子': '国防军工', '酒类': '食品饮料', '游戏': '传媒',
  '汽车': '汽车', '汽车零部件': '汽车', '汽车整车': '汽车',
  '轻工制造': '轻工制造', '农牧饲渔': '农林牧渔', '能源金属': '有色金属',
  '农产品加工': '农林牧渔', '农化制品': '基础化工', '燃气': '公用事业',
  '汽车服务': '社会服务', '其他建材': '建筑材料', '石油石化': '石油石化',
  '食品饮料': '食品饮料', '水泥建材': '建筑材料', '塑料': '基础化工',
  '通信设备': '通信', '通信服务': '通信', '文娱用品': '轻工制造',
  '消费电子': '电子', '小金属': '有色金属', '橡胶': '基础化工',
  '医疗服务': '医药生物', '医疗器械': '医药生物', '医药商业': '医药生物',
  '仪器仪表': '机械设备', '银行': '银行', '印包': '轻工制造',
  '影视院线': '传媒', '有色金属': '有色金属', '饲料': '农林牧渔',
  '养殖': '农林牧渔', '营销传播': '传媒', '造纸': '轻工制造',
  '证券': '非银金融', '中药': '医药生物', '装修建材': '建筑材料',
  '贵金属': '有色金属', '半导体': '电子', '计算机设备': '计算机',
  '计算机应用': '计算机', '软件开发': '计算机', 'IT服务': '计算机',
  '化妆品': '美容护理', '个护用品': '美容护理', '白酒': '食品饮料',
  '啤酒': '食品饮料', '乳品': '食品饮料', '调味品': '食品饮料',
  '休闲食品': '食品饮料', '保险': '非银金融', '多元金融': '非银金融',
  '国有大型银行': '银行', '股份制银行': '银行', '城商行': '银行',
  '农商行': '银行', '炼化及贸易': '石油石化', '油气开采': '石油石化',
  '油服工程': '石油石化', '煤炭开采': '煤炭', '焦炭': '煤炭',
  '火电': '公用事业', '水电': '公用事业', '核电': '公用事业',
  '风电': '电力设备', '光伏': '电力设备', '电池': '电力设备',
  '电机': '电力设备', '输变电设备': '电力设备',
  '工程机械': '机械设备', '通用设备': '机械设备', '专用设备': '机械设备',
  '轨交设备': '机械设备', '机床工具': '机械设备',
  '商用车': '汽车', '乘用车': '汽车', '摩托车及其他': '汽车',
  '锂电池': '电力设备', '光伏设备': '电力设备', '风电设备': '电力设备',
  '储能': '电力设备', '综合': '综合',
  '其他': '综合', '房产服务': '房地产', '房地产开发': '房地产',
  '互联网电商': '商贸零售', '百货零售': '商贸零售', '超市及便利店': '商贸零售',
  '专业连锁': '商贸零售', '贸易': '商贸零售',
  '旅游及景区': '社会服务', '教育出版': '传媒', '体育': '社会服务',
  '博彩': '社会服务', '互联网传媒': '传媒', '出版': '传媒',
  '电视广播': '传媒', '数字媒体': '传媒',
  '化学制药': '医药生物', '生物制品': '医药生物', '原料药': '医药生物',
  '药房': '医药生物', '血制品': '医药生物', '疫苗': '医药生物',
  '种植': '农林牧渔', '渔业': '农林牧渔', '种子': '农林牧渔',
  '动保': '农林牧渔',
  '航空发动机': '国防军工', '地面兵装': '国防军工', '航海装备': '国防军工',
  '军工行业': '国防军工',
  '水务及水治理': '环保', '环保设备': '环保', '固废治理': '环保',
  '大气治理': '环保', '园林工程': '建筑装饰', '房屋建设': '建筑装饰',
  '基础建设': '建筑装饰', '专业工程': '建筑装饰',
  '消费电子': '电子', '元件': '电子', '光学光电子': '电子',
  '面板': '电子', 'LED': '电子', '其他电子': '电子',
  '集成电路': '电子', '模拟芯片': '电子', '数字芯片': '电子',
  '分立器件': '电子', '半导体材料': '电子', '半导体设备': '电子',
  '被动元件': '电子', 'PCB': '电子',
  '服务器': '计算机', '网络安全': '计算机', '智慧城市': '计算机',
  '人工智能': '计算机', '大数据': '计算机', '云计算': '计算机',
  '运营商': '通信', '通信工程': '通信', '通信线缆': '通信',
  '通信终端及配件': '通信', '通信设备': '通信',
  '装饰材料': '建筑材料', '管材': '建筑材料', '防水材料': '建筑材料',
  '耐火材料': '建筑材料', '碳纤维': '建筑材料',
  '炼化及贸易': '石油石化', '油气开采及服务': '石油石化',
  '石油加工贸易': '石油石化', '油服及装备': '石油石化',
  '焦煤': '煤炭', '动力煤': '煤炭', '焦炭及其他': '煤炭',
  '煤炭开采洗选': '煤炭',
  '铜': '有色金属', '铝': '有色金属', '铅锌': '有色金属',
  '钴镍': '有色金属', '稀土及材料': '有色金属', '钨': '有色金属',
  '锂': '有色金属', '黄金': '有色金属',
  '合成树脂': '基础化工', '农药': '基础化工', '肥料': '基础化工',
  '民爆用品': '基础化工', '氟化工': '基础化工', '纯碱': '基础化工',
  '氯碱': '基础化工', '钛白粉': '基础化工', '有机硅': '基础化工',
  '轮胎': '基础化工', '涤纶': '基础化工', '氨纶': '基础化工',
  '锦纶': '基础化工', '粘胶': '基础化工',
  '白酒II': '食品饮料', '非白酒': '食品饮料',
  '白色家电': '家用电器', '黑色家电': '家用电器', '小家电': '家用电器',
  '照明设备': '家用电器', '厨卫电器': '家用电器',
  '女装': '纺织服饰', '男装': '纺织服饰', '休闲服饰': '纺织服饰',
  '鞋帽及其他': '纺织服饰',
  '家居用品': '轻工制造', '造纸': '轻工制造', '包装印刷': '轻工制造',
  '文娱用品': '轻工制造',
  '券商': '非银金融'
}

function mapEmToSw1(emName) {
  return EM_NAME_MAP[emName] || null
}

/**
 * 从东财 push2 API 获取申万一级行业数据
 */
function getSwIndustriesFromEastmoney() {
  const url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50&fields=f3,f12,f14,f24,f25,f128,f136'

  return request(url, 8000).then(text => {
    const data = JSON.parse(text)
    const diff = (data.data && data.data.diff) || []
    if (diff.length === 0) throw new Error('东财行业数据为空')

    const sw1Map = {}
    for (const item of diff) {
      const emName = (item.f14 || '').trim()
      if (!emName) continue

      const sw1Name = mapEmToSw1(emName)
      if (!sw1Name || !SW_L1_STANDARD.includes(sw1Name)) continue

      let pe = parseFloat(item.f24) || 0
      if (pe <= 0) pe = parseFloat(item.f25) || 0
      const changePct = parseFloat(item.f3) || 0
      const leaderName = (item.f128 || '').trim()
      const leaderChangePct = parseFloat(item.f136) || 0

      if (!sw1Map[sw1Name]) {
        sw1Map[sw1Name] = { peValues: [], changePctSum: 0, count: 0, leaderName: '', leaderChangePct: 0 }
      }
      const bucket = sw1Map[sw1Name]
      if (pe > 0 && pe < 1000) bucket.peValues.push(pe)
      bucket.changePctSum += changePct
      bucket.count += 1
      if (leaderChangePct > bucket.leaderChangePct) {
        bucket.leaderName = leaderName
        bucket.leaderChangePct = leaderChangePct
      }
    }

    const result = []
    for (const [name, b] of Object.entries(sw1Map)) {
      let avgPe = 0
      if (b.peValues.length > 0) {
        avgPe = b.peValues.reduce((s, v) => s + v, 0) / b.peValues.length
      }
      const avgChangePct = b.count > 0 ? (b.changePctSum / b.count) : 0

      let score = null
      // 暂无行业PE百分位历史数据
      score = null

      result.push({
        name, code: '', pe: Math.round(avgPe * 100) / 100,
        changePct: Math.round(avgChangePct * 100) / 100,
        pePercentile: null, leaderName: b.leaderName, leaderCode: '',
        leaderChangePct: Math.round(b.leaderChangePct * 100) / 100, leaderPrice: 0,
        score, stockCount: b.count
      })
    }

    result.sort((a, b) => (b.score || 0) - (a.score || 0))
    return result
  })
}

// 新浪旧版申万行业API（降级方案）
const SW_NAME_MAP_SINA = {
  'new_blhy': '建筑材料', 'new_cbzz': '国防军工', 'new_cmyl': '传媒', 'new_dlhy': '公用事业',
  'new_dqhy': '电力设备', 'new_dzqj': '电子', 'new_dzxx': '电子', 'new_fdc': '房地产',
  'new_fdsb': '电力设备', 'new_fjzz': '国防军工', 'new_fzhy': '纺织服饰', 'new_fzjx': '机械设备',
  'new_fzxl': '纺织服饰', 'new_glql': '交通运输', 'new_gsgq': '公用事业', 'new_gthy': '钢铁',
  'new_hbhy': '环保', 'new_hghy': '基础化工', 'new_hqhy': '基础化工', 'new_jdhy': '轻工制造',
  'new_jdly': '社会服务', 'new_jjhy': '轻工制造', 'new_jrhy': '非银金融', 'new_jtys': '交通运输',
  'new_jxhy': '机械设备', 'new_jzjc': '建筑材料', 'new_kfq': '房地产', 'new_ljhy': '食品饮料',
  'new_mtc': '汽车', 'new_mthy': '煤炭', 'new_nlmy': '农林牧渔', 'new_nyhf': '基础化工',
  'new_qczz': '汽车', 'new_qtxy': '汽车', 'new_slzp': '食品饮料', 'new_snhy': '建筑材料',
  'new_sphy': '食品饮料', 'new_stock': '新股', 'new_swzz': '医药生物', 'new_sybh': '商贸零售',
  'new_syhy': '石油石化', 'new_tchy': '建筑材料', 'new_wzwm': '商贸零售', 'new_ylqx': '医药生物',
  'new_yqyb': '机械设备', 'new_ysbz': '轻工制造', 'new_ysjs': '有色金属', 'new_zhhy': '综合',
  'new_zzhy': '轻工制造',
  'new_yh': '银行', 'new_bank': '银行',
  'new_zjhy': '非银金融', 'new_insurance': '非银金融',
  'new_yyyw': '医药生物', 'new_swbz': '医药生物',
  'new_jzjz': '建筑装饰', 'new_jzzs': '建筑装饰',
  'new_gfgj': '国防军工',
  'new_mrghl': '美容护理',
  'new_shjfw': '社会服务',
  'new_smls': '商贸零售'
}

function getSwIndustriesFromSina() {
  const url = 'https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php?industry=sw1'

  return request(url).then(text => {
    const result = []
    const nameExist = {}
    let dataStr = ''
    for (const line of text.split('\n')) {
      if (line.indexOf('{') >= 0) { dataStr = line; break }
    }

    const entries = []
    const regex = /"(\w+)":"([^"]+)"/g
    let match
    while ((match = regex.exec(dataStr)) !== null) {
      entries.push({ key: match[1], value: match[2] })
    }

    for (const entry of entries) {
      const parts = entry.value.split(',')
      if (parts.length < 13) continue

      const code = entry.key
      const name = SW_NAME_MAP_SINA[code] || (parts[1] || '').trim()
      if (code === 'new_stock') continue
      if (!SW_L1_STANDARD.includes(name)) continue
      if (nameExist[name]) continue
      nameExist[name] = true

      const stockCount = parseInt(parts[2]) || 0
      const pe = parseFloat(parts[3]) || 0
      const changePct = parseFloat(parts[5]) || 0
      const leaderName = (parts[12] || '').trim()
      const leaderCode = (parts[8] || '').trim()
      const leaderChangePct = parseFloat(parts[9]) || 0
      const leaderPrice = parseFloat(parts[10]) || 0

      result.push({
        name, code, pe, changePct,
        pePercentile: null, leaderName, leaderCode,
        leaderChangePct, leaderPrice,
        score: null, stockCount
      })
    }

    result.sort((a, b) => (b.score || 0) - (a.score || 0))
    return result
  })
}

/**
 * 获取申万一级行业板块数据
 * 优先东财 push2，失败降级新浪
 */
export function getSwIndustries() {
  return getSwIndustriesFromEastmoney().catch(err => {
    console.warn('[market-data] 东财行业API失败，降级新浪:', err.message)
    return getSwIndustriesFromSina()
  })
}

// ===== 3. 原始市场数据构建 =====

/**
 * 构建用于 calcAllExpectedReturns 的原始数据
 * @param {Object} quotes - getIndexQuotes 返回
 * @param {Object} peData - { pePercentile: number }（value500 来源）或 { peHistory, latestDate }
 * @param {Object} options - { shibor: {on, date}, yield10y: number }
 */
export function buildMarketData(quotes, peData, options) {
  options = options || {}
  const hs300 = quotes['沪深300'] || quotes['sh000300'] || {}

  // ===== 股票 =====
  let stockPE = (hs300.pe && hs300.pe > 0) ? hs300.pe : 0
  let stockPEPercentile = null
  let peHistoryCount = 0
  let peHistoryDate = ''

  if (peData) {
    if (peData.pePercentile != null) {
      stockPEPercentile = peData.pePercentile
      peHistoryCount = -1
    } else if (peData.peHistory && peData.peHistory.length > 0 && stockPE > 0) {
      stockPEPercentile = calcPercentile(stockPE, peData.peHistory)
      peHistoryCount = peData.peHistory.length
      peHistoryDate = peData.latestDate || ''
    }
  }

  const goldETF = quotes['黄金ETF'] || quotes['sh518880'] || {}
  const commodityETF = quotes['商品ETF'] || quotes['sz159934'] || {}
  const shiborData = options.shibor || {}

  return {
    stock: {
      pe: stockPE,
      pePercentile: stockPEPercentile,
      peHistoryCount,
      peHistoryDate,
      price: hs300.price || 0,
      changePct: hs300.changePct || 0
    },
    bond: {
      yield10y: options.yield10y || 0
    },
    commodity: {
      price: commodityETF.price || 0,
      changePct: commodityETF.changePct || 0,
      source: '易方达商品ETF'
    },
    gold: {
      price: goldETF.price || 0,
      changePct: goldETF.changePct || 0,
      source: '华安黄金ETF'
    },
    reit: {
      price: 0,
      changePct: 0,
      source: '暂无实时数据'
    },
    cash: {
      shiborOn: shiborData.on || 0,
      shiborDate: shiborData.date || ''
    }
  }
}
