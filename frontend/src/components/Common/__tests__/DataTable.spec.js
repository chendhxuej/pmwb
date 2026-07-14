import { describe, it, expect } from 'vitest'
import { h } from 'vue'
import { mount } from '@vue/test-utils'
import DataTable from '@/components/Common/DataTable.vue'

// 用桩组件隔离 el-table 在 jsdom 下的渲染脆弱性，直接验证 DataTable 是否正确转发 #columns 插槽
const StubTable = {
  name: 'ElTable',
  template: '<div class="stub-table"><slot /></div>',
}
const StubTableColumn = {
  name: 'ElTableColumn',
  props: ['label', 'prop'],
  template: '<div class="stub-col">{{ label }}</div>',
}

describe('DataTable', () => {
  it('通过 #columns 插槽传入的列应当被渲染（回归：曾因组件丢弃插槽导致 4 个页面表格只显示操作列）', () => {
    const wrapper = mount(DataTable, {
      props: { data: [], columns: [] },
      slots: {
        columns: () => [
          h(StubTableColumn, { prop: 'name', label: '姓名' }),
          h(StubTableColumn, { prop: 'age', label: '年龄' }),
        ],
      },
      global: { components: { ElTable: StubTable, ElTableColumn: StubTableColumn } },
    })
    const text = wrapper.text()
    expect(text).toContain('姓名')
    expect(text).toContain('年龄')
    expect(text).toContain('操作') // 默认操作列仍存在
  })

  it('未传 columns 时不应渲染数据列（仅操作列）', () => {
    const wrapper = mount(DataTable, {
      props: { data: [], columns: [] },
      global: { components: { ElTable: StubTable, ElTableColumn: StubTableColumn } },
    })
    const text = wrapper.text()
    expect(text).not.toContain('姓名')
  })
})
