<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="onDialogUpdate"
    :fullscreen="fullscreen"
    title="放大编辑输入框"
    width="min(900px, 80vw)"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    class="enlarge-dialog"
    @opened="onOpened"
  >
    <div class="enlarge-dialog-body">
      <ElInput
        ref="inputRef"
        v-model="value"
        type="textarea"
        :autosize="{ minRows: 10, maxRows: 30 }"
        placeholder="可在此大号区域查看与编辑，保存后内容写回原输入框"
      />
    </div>
    <template #footer>
      <div class="enlarge-dialog-footer">
        <el-button text @click="toggleFullscreen">
          <el-icon class="mr-4">
            <FullScreen v-if="!fullscreen" />
            <ScaleToOriginal v-else />
          </el-icon>
          {{ fullscreen ? '退出全屏' : '全屏' }}
        </el-button>
        <span class="spacer" />
        <el-button @click="requestClose">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { ElInput } from 'element-plus'
import { FullScreen, ScaleToOriginal } from '@element-plus/icons-vue'
import { useEnlargeInput } from '@/composables/useEnlargeInput'

const { visible, value, save, close } = useEnlargeInput()

const fullscreen = ref(false)
const inputRef = ref(null)

function toggleFullscreen() {
  fullscreen.value = !fullscreen.value
}

// 用户主动关闭（点 X / 遮罩 / ESC）时走「是否放弃修改」确认
function onDialogUpdate(v) {
  if (!v) requestClose()
}

function requestClose() {
  close()
}

function onOpened() {
  nextTick(() => {
    const inst = inputRef.value
    if (inst && typeof inst.focus === 'function') inst.focus()
  })
}
</script>

<style scoped>
.enlarge-dialog-body {
  padding: 4px 2px;
}
.enlarge-dialog :deep(.el-textarea__inner) {
  font-size: 15px;
  line-height: 1.7;
  box-shadow: none;
}
.enlarge-dialog-footer {
  display: flex;
  align-items: center;
}
.enlarge-dialog-footer .spacer {
  flex: 1;
}
.mr-4 {
  margin-right: 4px;
}
</style>
