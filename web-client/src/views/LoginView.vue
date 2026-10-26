<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
    <div class="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
      <div class="text-center mb-8">
        <div class="text-4xl mb-3"></div>
        <h1 class="text-2xl font-bold text-gray-800">高校智能问答助手</h1>
        <p class="text-gray-500 mt-2">登录以开始对话</p>
      </div>
      <form @submit.prevent="handleLogin">
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
          <input
            v-model="username"
            type="text"
            class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
            placeholder="请输入用户名"
            required
          />
        </div>
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-1">密码</label>
          <input
            v-model="password"
            type="password"
            class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
            placeholder="请输入密码"
            required
          />
        </div>
        <button
          type="submit"
          :disabled="loading"
          class="w-full py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition font-medium disabled:opacity-50"
        >
          {{ loading ? '登录中...' : '登 录' }}
        </button>
        <p v-if="error" class="text-red-500 text-sm mt-3 text-center">{{ error }}</p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('admin')
const password = ref('admin123456')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login(username.value, password.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>
