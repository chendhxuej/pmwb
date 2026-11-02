<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <span class="logo-mark">PMWB</span>
        <span class="logo-sub">产品经理个人工作台</span>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        size="large"
        @keyup.enter="submit"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            :prefix-icon="User"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            class="login-btn"
            type="primary"
            :loading="loading"
            @click="submit"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await authStore.login(form.username.trim(), form.password)
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (e) {
    // 错误文案：优先后端 message（含限速/密码错误），其次异常本身
    ElMessage.error(e?.message || '登录失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #eef3fb 0%, #f7f9fc 60%, #eaf1ff 100%);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--surface, #fff);
  border: 1px solid var(--border-subtle, #eef0f4);
  border-radius: 16px;
  box-shadow: var(--shadow-elevated, 0 8px 30px rgba(31, 45, 61, 0.08));
  padding: 36px 32px 28px;
}

.login-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin-bottom: 28px;
}
.logo-mark {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #2f6fed, #06b6d4);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.logo-sub {
  font-size: 13px;
  color: var(--text-secondary, #64748b);
}

.login-btn {
  width: 100%;
  font-weight: 600;
  letter-spacing: 4px;
}
</style>
