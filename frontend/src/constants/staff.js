// 运营工单责任人固定名单（政企业务分工表，对象基本固定，录单页多选）
// 按团队分组，供 el-select 多选下拉使用。

const RAW_GROUPS = [
  {
    label: '政企客户部',
    members: ['邵建', '顾宏明', '张舒明', '张振', '戴燕', '黄何', '金韡', '李能禾', '方舟'],
  },
  { label: 'CRM', members: ['郑文东', '吴雨霜', '张茜'] },
  { label: 'BOSS', members: ['陈增明', '叶振宇', '李蕊'] },
  { label: '订单中心', members: ['王辅松', '陈山'] },
  { label: '生产运营平台', members: ['戴晓飞'] },
  { label: '电子协议', members: ['秦新'] },
  { label: '系统维护(CRM)', members: ['毛天羿', '陈靖坤', '王宏伟', '李培龙'] },
  { label: '系统维护(BOSS)', members: ['凌玉祥', '吕凤云'] },
  { label: '系统维护(订单)', members: ['孟华'] },
  { label: '系统维护(生产运营)', members: ['李瑞'] },
]

export const HANDLER_GROUPS = RAW_GROUPS.map((g) => ({
  label: g.label,
  options: g.members.map((m) => ({ value: m, label: m })),
}))

export const HANDLER_OPTIONS = HANDLER_GROUPS.flatMap((g) => g.options)
