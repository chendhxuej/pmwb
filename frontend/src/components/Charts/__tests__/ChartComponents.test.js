/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChartLine from '../ChartLine.vue'
import ChartBar from '../ChartBar.vue'
import ChartPie from '../ChartPie.vue'

describe('ChartLine', () => {
  it('renders with basic data', () => {
    const wrapper = mount(ChartLine, {
      props: {
        data: [
          { name: '周一', value: 120 },
          { name: '周二', value: 200 },
        ],
        height: '200px',
      },
      global: {
        stubs: { VChart: true },
      },
    })
    expect(wrapper.find('.chart-line').exists()).toBe(true)
    expect(wrapper.attributes('style')).toContain('height: 200px')
  })
})

describe('ChartBar', () => {
  it('renders with basic data', () => {
    const wrapper = mount(ChartBar, {
      props: {
        data: [
          { name: 'A', value: 30 },
          { name: 'B', value: 50 },
        ],
        height: '200px',
      },
      global: {
        stubs: { VChart: true },
      },
    })
    expect(wrapper.find('.chart-bar').exists()).toBe(true)
  })
})

describe('ChartPie', () => {
  it('renders with data and center text', () => {
    const wrapper = mount(ChartPie, {
      props: {
        data: [
          { name: '成功', value: 85 },
          { name: '失败', value: 15 },
        ],
        centerText: '85%',
        height: '200px',
      },
      global: {
        stubs: { VChart: true },
      },
    })
    expect(wrapper.find('.chart-pie').exists()).toBe(true)
  })
})
