/**
 * 统一格式化工具（单一来源）
 * 消除各页面重复的 fmt* 与 scoreColor 定义。
 *
 * 约定：
 * - 收益率类字段在数据库里通常存为「小数」（0.0823 表示 8.23%），
 *   故 fmtPct / fmtPctSigned 默认 asDecimal=true（×100）。
 * - PE 百分位等已是 0~100 的数值，调用时传 asDecimal=false。
 */

// 靠谱分（评分值）展示：0/空 → '--'
export function fmtScore(v) {
  const n = parseFloat(v)
  if (!n || n <= 0) return '--'
  return n.toFixed(2)
}

// 收益率展示（小数→百分比，带正负号）：0.0823 → '+8.23%'
export function fmtRet(v) {
  if (v == null) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
}

// 回撤展示（已是百分比数值）：-15.23 → '-15.23%'
export function fmtDD(v) {
  if (v == null) return '--'
  return parseFloat(v).toFixed(2) + '%'
}

// 夏普比率展示：1.2345 → '1.2345'
export function fmtSR(v) {
  if (v == null) return '--'
  return parseFloat(v).toFixed(4)
}

// 数字展示（0/空 → '--'）
export function fmtNum(v) {
  if (v == null || v === 0) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  return n.toFixed(2)
}

// 份额规模展示：12345 → '1.23万亿份' / 8.5 → '8.50亿份'
export function fmtScale(v) {
  if (v == null) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  if (n >= 10000) return (n / 10000).toFixed(2) + '万亿份'
  if (n >= 1) return n.toFixed(2) + '亿份'
  return (n * 10000).toFixed(0) + '万份'
}

// 基金净值规模展示（单位：亿元，调用方表头加"（亿）"）：402.21 → '402.21' / 0.9769 → '0.9769'
// 不满 1 亿时使用小数（与表头单位一致，不再换算成「万」）
export function fmtFundScale(v) {
  if (v == null) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  if (n >= 1) return n.toFixed(2)
  return parseFloat(n.toFixed(4))
}

/**
 * 百分比展示
 * @param {number|string|null} v
 * @param {boolean} asDecimal 默认 true：输入为小数（×100）；false：输入已是百分数数值
 */
export function fmtPct(v, asDecimal = true) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  if (isNaN(n)) return '--'
  const val = asDecimal ? n * 100 : n
  return val.toFixed(2) + '%'
}

// 带正负号的百分比（收益率场景）：0.0823 → '+8.23%'，-0.05 → '-5.00%'
export function fmtPctSigned(v, asDecimal = true) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  if (isNaN(n)) return '--'
  const val = asDecimal ? n * 100 : n
  return (val > 0 ? '+' : '') + val.toFixed(2) + '%'
}

// 靠谱分等级（全市场百分位）：≥85 gold, ≥75 orange, ≥65 cyan, 其余 gray
export function scoreLevel(k) {
  if (k == null) return ''
  if (k >= 85) return 'gold'
  if (k >= 75) return 'orange'
  if (k >= 65) return 'cyan'
  return 'gray'
}

// 靠谱分连续色：低分→绿(120°)，高分→红(0°)，返回 { color }
export function scoreColor(v) {
  const n = parseFloat(v)
  if (isNaN(n) || n == null) return { color: '#8B949E' }
  const hue = 120 * (1 - n / 100)
  return { color: `hsl(${Math.round(hue)}, 85%, 45%)` }
}
