<template>
  <div class="h-screen flex bg-white">
    <!-- 左侧边栏 -->
    <aside class="w-72 bg-[#f8fafc] border-r border-gray-200 flex flex-col flex-shrink-0">
      <!-- 新建会话按钮 -->
      <div class="p-3">
        <button
          @click="handleNewChat"
          class="w-full py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition font-medium flex items-center justify-center gap-2"
        >
          <span class="text-lg">+</span> 新会话
        </button>
      </div>

      <!-- 会话列表 -->
      <div class="flex-1 overflow-y-auto px-2 pb-2">
        <div
          v-for="conv in chatStore.conversations"
          :key="conv.id"
          @click="selectConversation(conv.id)"
          class="group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition mb-1"
          :class="chatStore.currentConvId === conv.id ? 'bg-blue-500 text-white' : 'hover:bg-gray-200 text-gray-700'"
        >
          <div class="flex items-center gap-2 min-w-0 flex-1">
            <span class="text-sm flex-shrink-0"></span>
            <span class="text-sm truncate">{{ conv.title || '空白会话' }}</span>
          </div>
          <button
            @click.stop="handleDelete(conv.id)"
            class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition flex-shrink-0 ml-1"
            title="删除会话"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 底部用户信息 -->
      <div class="p-3 border-t border-gray-200">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium">
              {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
            </div>
            <div>
              <div class="text-sm font-medium text-gray-700">{{ authStore.user?.username || '用户' }}</div>
              <div class="text-xs text-gray-400">{{ authStore.user?.role === 'sys_admin' ? '管理员' : '普通用户' }}</div>
            </div>
          </div>
          <button @click="handleLogout" class="text-gray-400 hover:text-red-500 transition" title="退出登录">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- 右侧聊天区域 -->
    <main class="flex-1 flex flex-col min-w-0">
      <!-- 消息列表 -->
      <div ref="messageContainer" class="flex-1 overflow-y-auto px-6 py-4">
        <div v-if="chatStore.messages.length === 0" class="h-full flex items-center justify-center">
          <div class="text-center text-gray-400">
            <div class="text-6xl mb-4"></div>
            <p class="text-lg">开始新的对话</p>
            <p class="text-sm mt-1">输入你的问题，我将基于知识库为你解答</p>
          </div>
        </div>

        <div v-for="(msg, index) in chatStore.messages" :key="msg.id" class="mb-6">
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="flex items-start gap-3 max-w-[70%]">
              <div class="bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-3">
                <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ msg.content }}</p>
              </div>
              <div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
              </div>
            </div>
          </div>

          <!-- AI 消息 -->
          <div v-else class="flex justify-start">
            <div class="flex items-start gap-3 max-w-[70%]">
              <div class="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 text-sm flex-shrink-0">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
              </div>
              <div>
                <!-- Agent 步骤指示 -->
                <div v-if="index === chatStore.messages.length - 1 && chatStore.agentSteps.length > 0" class="mb-2">
                  <div
                    v-for="(step, si) in chatStore.agentSteps"
                    :key="si"
                    class="text-xs text-gray-400 mb-1 flex items-center gap-1"
                  >
                    <span class="inline-block w-1.5 h-1.5 rounded-full bg-blue-400"></span>
                    {{ step.label || step.node }}
                  </div>
                </div>
                <div class="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  <p class="text-sm leading-relaxed whitespace-pre-wrap text-gray-800">
                    {{ msg.content || (chatStore.isStreaming && index === chatStore.messages.length - 1 ? '思考中...' : '') }}
                  </p>
                </div>
                <!-- 耗时信息 -->
                <div v-if="msg.latency_ms" class="text-xs text-gray-400 mt-1 ml-1">
                  耗时 {{ msg.latency_ms }}ms
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="border-t border-gray-200 px-6 py-4">
        <div class="flex items-end gap-3 max-w-4xl mx-auto">
          <div class="flex-1 relative">
            <textarea
              v-model="inputText"
              @keydown.enter.exact.prevent="handleSend"
              rows="1"
              class="w-full px-4 py-3 border border-gray-300 rounded-xl resize-none outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm max-h-32"
              placeholder="请输入消息..."
              :disabled="chatStore.isStreaming"
              style="min-height: 48px;"
            />
          </div>
          <button
            v-if="!chatStore.isStreaming"
            @click="handleSend"
            :disabled="!inputText.trim()"
            class="px-6 py-3 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition font-medium disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
          >
            发送
          </button>
          <button
            v-else
            @click="chatStore.stopStreaming()"
            class="px-6 py-3 bg-red-500 text-white rounded-xl hover:bg-red-600 transition font-medium flex-shrink-0"
          >
            停止
          </button>
        </div>
        <p class="text-xs text-gray-400 text-center mt-2">AI 生成内容仅供参考，请以官方文件为准</p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, useChatStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()

const inputText = ref('')
const messageContainer = ref<HTMLElement>()

onMounted(async () => {
  await chatStore.loadConversations()
})

function scrollToBottom() {
  nextTick(() => {
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  })
}

async function handleNewChat() {
  await chatStore.createNewConversation()
  inputText.value = ''
}

function selectConversation(id: number) {
  chatStore.loadMessages(id)
  inputText.value = ''
}

async function handleDelete(id: number) {
  if (confirm('确定删除该会话？')) {
    await chatStore.deleteConversation(id)
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.isStreaming) return

  if (!chatStore.currentConvId) {
    await chatStore.createNewConversation()
  }

  inputText.value = ''
  await chatStore.sendMessage(text)
  scrollToBottom()

  // 监听流式输出时持续滚动
  const timer = setInterval(() => {
    if (!chatStore.isStreaming) {
      clearInterval(timer)
      scrollToBottom()
    } else {
      scrollToBottom()
    }
  }, 100)
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>
