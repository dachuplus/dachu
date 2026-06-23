/**
 * ECharts 按需导入配置
 * 替代 import * as echarts from 'echarts'，减少约 60-70% bundle 体积
 * 
 * 使用的组件：
 * - 图表类型：Line（折线）、Gauge（仪表盘）、Pie（饼图）、Radar（雷达图）
 * - 组件：Grid、Tooltip、DataZoom、Legend、Dataset、Transform
 * - 渲染器：Canvas
 */

import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  LineChart,
  GaugeChart,
  PieChart,
  RadarChart,
} from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  DataZoomInsideComponent,
  DataZoomSliderComponent,
  LegendComponent,
  DatasetComponent,
  TransformComponent,
  TitleComponent,
  ToolboxComponent,
} from 'echarts/components'

echarts.use([
  CanvasRenderer,
  LineChart,
  GaugeChart,
  PieChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  DataZoomInsideComponent,
  DataZoomSliderComponent,
  LegendComponent,
  DatasetComponent,
  TransformComponent,
  TitleComponent,
  ToolboxComponent,
])

export default echarts
