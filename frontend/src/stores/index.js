import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const title = ref('产品经理个人工作台')
  const collapsed = ref(false)

  const toggleCollapsed = () => {
    collapsed.value = !collapsed.value
  }

  return {
    title,
    collapsed,
    toggleCollapsed,
  }
})
