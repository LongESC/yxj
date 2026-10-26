import axios from 'axios'
import type {
  User, Conversation, Message, KnowledgeBase, Feedback,
  ChatDoneData, ApiResponse,
} from '@/types'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 请求拦截器：附加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一错误处理
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

// ============================================================
// 认证
// ============================================================

export function login(username: string, password: string) {
  return api.post<{ access_token: string; user: User }>('/auth/login', { username, password })
}

export function getMe() {
  return api.get<User>('/auth/me')
}

// ============================================================
// 会话
// ============================================================

export function getConversations() {
  return api.get<Conversation[]>('/conversations')
}

export function createConversation(data: { title?: string; kb_ids?: number[] }) {
  return api.post<Conversation>('/conversations', data)
}

export function deleteConversation(id: number) {
  return api.delete(`/conversations/${id}`)
}

export function renameConversation(id: number, title: string) {
  return api.put(`/conversations/${id}`, { title })
}

// ============================================================
// 消息
// ============================================================

export function getMessages(convId: number) {
  return api.get<Message[]>(`/conversations/${convId}/messages`)
}

// ============================================================
// 问答（SSE）
// ============================================================

export function sendChatMessage(
  question: string,
  conversationId?: number,
  kbIds?: number[],
  onEvent?: (type: string, data: any) => void,
): AbortController {
  const controller = new AbortController()

  fetch('/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      question,
      kb_ids: kbIds,
      stream: true,
      show_steps: true,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      const reader = response.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              onEvent?.(currentEvent, data)
            } catch {
              // 忽略解析错误
            }
          } else if (line === '') {
            currentEvent = ''
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onEvent?.('error', { error: err.message })
      }
    })

  return controller
}

// ============================================================
// 反馈
// ============================================================

export function submitFeedback(data: { message_id: number; rating: number; reason_tags?: string[]; comment?: string }) {
  return api.post<Feedback>('/feedback', data)
}

// ============================================================
// 知识库
// ============================================================

export function getKnowledgeBases() {
  return api.get<KnowledgeBase[]>('/knowledge-bases')
}

export function createKnowledgeBase(data: { name: string; code: string; owner_dept?: string; description?: string }) {
  return api.post<KnowledgeBase>('/knowledge-bases', data)
}
