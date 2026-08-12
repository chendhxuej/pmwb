import mitt from 'mitt'

// 全局轻量事件总线：用于跨模块数据联动（如业务领域增删改后通知所有选择器刷新）
export const bus = mitt()

// 事件名约定
export const EVT_DOMAINS_CHANGED = 'business-domains:changed'
