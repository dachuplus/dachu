/**
 * gov.uk 风格 ECharts 统一主题
 *
 * 原则：
 * - 白底黑轴，无渐变填充
 * - 颜色极简：数据标记用少量清晰色
 * - 无装饰性元素（阴影、渐变、圆角）
 */

// 图表色板 — 基于 gov.uk 调色板
const COLORS = [
  '#1d70b8',  // gov.uk blue
  '#d4351c',  // gov.uk red
  '#00703c',  // gov.uk green
  '#f47738',  // gov.uk orange
  '#4c2c92',  // gov.uk purple
  '#5694ca',  // light blue
  '#d53880',  // gov.uk pink
  '#28a197',  // gov.uk turquoise
  '#0b0c0c',  // black
  '#505a5f',  // dark grey
]

const AXIS_STYLE = {
  color: '#505a5f',
  fontSize: 12,
  fontFamily: 'inherit',
}

export function createGovukChart(dom, option) {
  const baseOption = {
    backgroundColor: '#ffffff',
    color: COLORS,
    animation: true,
    animationDuration: 300,
    textStyle: {
      fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif',
      color: '#0b0c0c',
    },
    grid: {
      left: 50,
      right: 20,
      top: 20,
      bottom: 30,
      containLabel: false,
    },
    legend: {
      textStyle: { ...AXIS_STYLE },
      itemWidth: 20,
      itemHeight: 3,
      itemGap: 20,
    },
    tooltip: {
      backgroundColor: '#0b0c0c',
      borderWidth: 0,
      textStyle: { color: '#ffffff', fontSize: 14 },
      extraCssText: 'border-radius: 0; padding: 8px 12px;',
    },
  }

  // Merge axis styles
  const mergeAxis = (obj) => {
    if (!obj) return
    if (obj.xAxis) {
      if (Array.isArray(obj.xAxis)) {
        obj.xAxis.forEach(a => Object.assign(a, { axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false }, axisLabel: { ...AXIS_STYLE }, splitLine: { show: false } }))
      } else {
        Object.assign(obj.xAxis, { axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false }, axisLabel: { ...AXIS_STYLE }, splitLine: { show: false } })
      }
    }
    if (obj.yAxis) {
      if (Array.isArray(obj.yAxis)) {
        obj.yAxis.forEach(a => Object.assign(a, { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { ...AXIS_STYLE }, splitLine: { lineStyle: { color: '#f3f2f1' } } }))
      } else {
        Object.assign(obj.yAxis, { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { ...AXIS_STYLE }, splitLine: { lineStyle: { color: '#f3f2f1' } } })
      }
    }
    if (obj.series) {
      obj.series.forEach(s => {
        if (s.type === 'line') {
          s.lineStyle = s.lineStyle || {}
          s.lineStyle.width = 2
          s.symbol = s.symbol || 'none'
          s.smooth = s.smooth !== undefined ? s.smooth : false
        }
        if (s.type === 'bar') {
          s.barWidth = s.barWidth || '60%'
          s.itemStyle = s.itemStyle || {}
          s.itemStyle.borderRadius = 0
        }
      })
    }
  }

  mergeAxis(option)

  // Deep merge base into option
  const result = { ...baseOption, ...option }
  return result
}

export { COLORS }
