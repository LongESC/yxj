import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, Conversation, Message, Citation } from '@/types'
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
  const currentCitations = ref<Citation[]>([])
  const doneData = ref<any>(null)
  let abortController: AbortController | null = null

  async function loadConversations() {
    try {
      const { data } = await api.getConversations()
      conversations.value = data
    } catch { /* ignore */ }
  }

  async function loadMessages(convId: number) {
    currentConvId.value = convId
    try {
      const { data } = await api.getMessages(convId)
      messages.value = data
    } catch {
      messages.value = []
    }
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

    // 添加用户消息
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
    currentCitations.value = []
    doneData.value = null

    abortController = api.sendChatMessage(
      question,
      currentConvId.value || undefined,
      undefined,
      (type, data) => {
        switch (type) {
          case 'step':
            agentSteps.value.push(data)
            break
          case 'tool_call':
            agentSteps.value.push({ node: 'tool_call', label: `检索：${data.args?.query || data.tool}`, tool: data.tool })
            break
          case 'tool_result':
            agentSteps.value.push({ node: 'tool_result', label: `找到 ${data.hits} 条相关依据`, hits: data.hits })
            break
          case 'delta':
            streamingContent.value += data.text
            {
              const lastMsg = messages.value[messages.value.length - 1]
              if (lastMsg) lastMsg.content = streamingContent.value
            }
            break
          case 'citation':
            currentCitations.value.push(data)
            break
          case 'done':
            isStreaming.value = false
            doneData.value = data
            {
              const lastMsg = messages.value[messages.value.length - 1]
              if (lastMsg) {
                lastMsg.id = data.message_id || lastMsg.id
                lastMsg.answer_type = data.answer_type
                lastMsg.latency_ms = data.latency_ms
                lastMsg.citations = [...currentCitations.value]
              }
            }
            loadConversations()
            break
          case 'error':
            isStreaming.value = false
            {
              const errMsg = messages.value[messages.value.length - 1]
              if (errMsg) errMsg.content = `出错了：${data.message || data.error || '未知错误'}`
            }
            break
        }
      },
    )
  }

  function stopStreaming() {
    abortController?.abort()
    isStreaming.value = false
  }

  async function submitFeedback(messageId: number, rating: number, reasonTags?: string[], comment?: string) {
    await api.submitFeedback({ message_id: messageId, rating, reason_tags: reasonTags, comment })
  }

  return {
    conversations, currentConvId, messages, isStreaming,
    streamingContent, agentSteps, currentCitations, doneData,
    loadConversations, loadMessages, createNewConversation,
    deleteConversation, sendMessage, stopStreaming, submitFeedback,
  }
})
