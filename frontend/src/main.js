import { createApp } from 'vue'
import dayjs from 'dayjs'
import isoWeek from 'dayjs/plugin/isoWeek'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import VChart from 'vue-echarts'
import EnlargeInput from './components/Common/EnlargeInput.vue'
import { countup } from './composables/countup.js'
import { loadStatusMeta, subscribeStatusMeta } from './api/statusMeta.js'
import { hydrateStatusMeta } from './constants/statusConfig.js'
import './styles/design.css'

// Element Plus week picker 依赖 dayjs isoWeek 插件
dayjs.extend(isoWeek)

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.component('VChart', VChart)
app.component('EnlargeInput', EnlargeInput)
app.directive('countup', countup)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 状态元数据（状态注册表）预加载：唯一真相源在后端，hydrate 后
// 全站徽标 label/tone、筛选下拉、流转下拉、总览矩阵自动以注册表为准。
// 后端不可达时静默降级到 constants/statusConfig.js 的 seed，不阻塞应用启动。
subscribeStatusMeta((meta) => hydrateStatusMeta(meta))
loadStatusMeta()
  .then((meta) => hydrateStatusMeta(meta))
  .catch((e) => console.warn('[statusMeta] 预加载失败，降级为内置 seed：', e && e.message))

app.mount('#app')
