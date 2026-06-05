/**
 * utils/value500.js - value500.com 页面解析工具
 *
 * 移植自 asset-config-miniapp cloudfunctions/fetchValue500
 * 各解析函数从 value500.com HTML 中提取关键数据
 */

// ========== 各页面解析函数 ==========

export function parseBondYield(html) {
  const S = '[\\s\\u3000]*'
  const match = html.match(new RegExp(
    "(\\d{4}年\\d{1,2}月\\d{1,2}日)" + S + "国债到期收益率" + S +
    "1年期[：:]([\\d.]+)％[；;][^]*?5年期[：:]([\\d.]+)％[；;][^]*?10年期[：:]([\\d.]+)％"
  ))
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  const y1 = parseFloat(match[2]) / 100
  const y5 = parseFloat(match[3]) / 100
  const y10 = parseFloat(match[4]) / 100
  return {
    code: 0,
    data: { date: match[1], yield1y: y1, yield5y: y5, yield10y: y10, spread: Math.round((y10 - y1) * 10000) / 100 },
    msg: 'success'
  }
}

export function parseShibor(html) {
  const match = html.match(/(\d{4}年\d{1,2}月\d{1,2}日)\s*O\/N[：:]([\d.]+)％\s*1W[：:]([\d.]+)％\s*1M[：:]([\d.]+)％\s*1Y[：:]([\d.]+)％/)
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  return {
    code: 0,
    data: {
      date: match[1],
      on: parseFloat(match[2]) / 100,
      w1: parseFloat(match[3]) / 100,
      m1: parseFloat(match[4]) / 100,
      y1: parseFloat(match[5]) / 100
    },
    msg: 'success'
  }
}

export function parseM2(html) {
  const match = html.match(/(\d{4}年\d{1,2}月)\s*M1增速[：:]([\d.\-]+)％[；;]\s*M2增速[：:]([\d.\-]+)％/)
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  const m1yoy = parseFloat(match[2])
  const m2yoy = parseFloat(match[3])
  return {
    code: 0,
    data: { date: match[1], m1yoy, m2yoy, m1m2diff: Math.round((m1yoy - m2yoy) * 10) / 10 },
    msg: 'success'
  }
}

export function parseCPI(html) {
  const match = html.match(/(\d{4}年\d{1,2}月)\s*CPI同比[：:]([\d.\-]+)%/)
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  return {
    code: 0,
    data: { date: match[1], cpi: parseFloat(match[2]) / 100 },
    msg: 'success'
  }
}

export function parsePE300(html) {
  const S = '[\\s\\u3000]*'
  const peMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300滚动市盈率[：:]([\\d.]+)"))
  const pePctMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300市盈率百分位（近五年）[：:]([\\d.]+)%?\\s*'"))
  const pbMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300市净率[：:]([\\d.]+)"))
  const pbPctMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300市净率百分位（近五年）[：:]([\\d.]+)%?\\s*'"))
  const dateMatch = html.match(new RegExp("(\\d{4}年\\d{1,2}月\\d{1,2}日)" + S + "沪深300滚动市盈率"))

  if (!peMatch) return { code: -1, data: null, msg: '解析失败' }
  return {
    code: 0,
    data: {
      date: dateMatch ? dateMatch[1] : '',
      pe: parseFloat(peMatch[1]),
      pePercentile: pePctMatch ? parseFloat(pePctMatch[1]) : null,
      pb: pbMatch ? parseFloat(pbMatch[1]) : null,
      pbPercentile: pbPctMatch ? parseFloat(pbPctMatch[1]) : null
    },
    msg: 'success'
  }
}

export function parseEP(html) {
  const dateMatch = html.match(/(\d{4}年\d{1,2}月\d{1,2}日)\s*上交所股债收益率比[：:]([\d.]+)/)
  const szMatch = html.match(/深交所股债收益率比[：:]([\d.]+)/)
  if (!dateMatch) return { code: -1, data: null, msg: '解析失败' }

  return {
    code: 0,
    data: {
      date: dateMatch[1],
      shRatio: parseFloat(dateMatch[2]),
      szRatio: szMatch ? parseFloat(szMatch[1]) : null
    },
    msg: 'success'
  }
}

// ========== 页面配置 ==========

export const VALUE500_PAGES = {
  bond:  { path: '/10Bond.html',         parse: parseBondYield },
  shibor:{ path: '/Shibor.asp',          parse: parseShibor },
  m2:    { path: '/M1.asp',              parse: parseM2 },
  cpi:   { path: '/CPI.asp',             parse: parseCPI },
  ep:    { path: '/ep.asp',              parse: parseEP },
  pe300: { path: '/000300SHPEPB.asp',    parse: parsePE300 }
}
