import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, Conversation, Message } from '@/types'
import * as api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref(localStorage.getItem('token') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'sys_admin')

  async function login(username: string, password: string) {
    const { data } = await api.login(username, password)
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
  }

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('token')
  }

  return { user, token, isLoggedIn, isAdmin, login, logout }
})

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const currentConvId = ref<number | null>(null)
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const streamingContent = ref('')
  const agentSteps = ref<any[]>([])
  let abortController: AbortController | null = null

  async function loadConversations() {
    const { data } = await api.getConversations()
    conversations.value = data
  }

  async function loadMessages(convId: number) {
    currentConvId.value = convId
    const { data } = await api.getMessages(convId)
    messages.value = data
  }

  async function createNewConversation() {
    const { data } = await api.createConversation({})
    conversations.value.unshift(data)
    currentConvId.value = data.id
    messages.value = []
    return data.id
  }

  async function deleteConversation(id: number) {
    await api.deleteConversation(id)
    conversations.value = conversations.value.filter(c => c.id !== id)
    if (currentConvId.value === id) {
      currentConvId.value = null
      messages.value = []
    }
  }

  async function sendMessage(question: string) {
    if (isStreaming.value) return

    // 添加用户消息到列表
    const userMsg: Message = {
      id: Date.now(),
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 创建助手消息占位
    const aiMsg: Message = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    }
    messages.value.push(aiMsg)

    isStreaming.value = true
    streamingContent.value = ''
    agentSteps.value = []

    abortController = api.sendChatMessage(
      question,
      currentConvId.value || undefined,
      undefined,
      (type, data) => {
        switch (type) {
          case 'step':
            agentSteps.value.push(data)
            break
          case 'delta':
            streamingContent.value += data.text
            // 更新最后一条助手消息
            const lastMsg = messages.value[messages.value.length - 1]
            if (lastMsg) lastMsg.content = streamingContent.value
            break
          case 'done':
            isStreaming.value = false
            // 刷新会话列表
            loadConversations()
            break
          case 'error':
            isStreaming.value = false
            const errMsg = messages.value[messages.value.length - 1]
            if (errMsg) errMsg.content = `出错了：${data.error}`
            break
        }
      },
    )
  }

  function stopStreaming() {
    abortController?.abort()
    isStreaming.value = false
  }

  return {
    conversations, currentConvId, messages, isStreaming,
    streamingContent, agentSteps,
    loadConversations, loadMessages, createNewConversation,
    deleteConversation, sendMessage, stopStreaming,
  }
})
