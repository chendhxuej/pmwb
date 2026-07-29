/* PMWB 图表按需引入 + 统一配色主题。
 * 主色：#2f6fed(蓝)  #0f9d6b(绿)  #d98a1f(橙)  #e02424(红)
 */

import { use } from 'echarts/core'
import { LineChart, BarChart, PieChart, GaugeChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  LineChart,
  BarChart,
  PieChart,
  GaugeChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  CanvasRenderer,
])

// PMWB 配色方案
export const PMWB_COLORS = ['#2f6fed', '#0f9d6b', '#d98a1f', '#e02424', '#2fc9a0', '#946ce6', '#e46c6c']

/** 浅色主题系列色（按数据项自动循环） */
export function colorPalette(index) {
  return PMWB_COLORS[index % PMWB_COLORS.length]
}
