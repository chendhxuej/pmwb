import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElTag } from 'element-plus'
import StatusBadge from '@/components/Common/StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders correct label and type for pending value', () => {
    const wrapper = mount(StatusBadge, {
      props: {
        value: 'pending',
        options: {
          pending: { label: '待处理', type: 'danger' },
        },
      },
      global: {
        components: { ElTag },
      },
    })
    expect(wrapper.text()).toContain('待处理')
  })

  it('renders raw value when not in options', () => {
    const wrapper = mount(StatusBadge, {
      props: {
        value: 'unknown',
        options: {
          pending: { label: '待处理', type: 'danger' },
        },
      },
      global: {
        components: { ElTag },
      },
    })
    expect(wrapper.text()).toContain('unknown')
  })
})
