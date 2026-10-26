// 类型定义

export interface User {
  id: number
  username: string
  real_name?: string
  email?: string
  department?: string
  role: string
}

export interface Conversation {
  id: number
  title?: string
  source: string
  kb_ids?: number[]
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export interface Citation {
  cite_no: number
  chunk_id: number
  doc_title?: string
  version?: number
  page?: number
  snippet?: string
  score?: number
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  agent_steps?: AgentStep[]
  answer_type?: string
  latency_ms?: number
  created_at: string
}

export interface AgentStep {
  node: string
  tool?: string
  hits?: number
  duration_ms?: number
}

export interface SSEEvent {
  type: 'step' | 'tool_call' | 'tool_result' | 'delta' | 'citation' | 'done' | 'error'
  data: Record<string, any>
}

export interface ChatDoneData {
  message_id: number
  answer_type: string
  iteration?: number
  latency_ms?: number
  first_token_ms?: number
  model?: string
  graph_version?: string
  trace_id?: string
}

export interface KnowledgeBase {
  id: number
  name: string
  code: string
  owner_dept?: string
  description?: string
  status: number
  created_at: string
}

export interface Feedback {
  id: number
  message_id: number
  rating: number
  reason_tags?: string[]
  comment?: string
  handled: boolean
  created_at: string
}

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
  trace_id?: string
}
