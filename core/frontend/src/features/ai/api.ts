export interface AiStatus {
  configured: boolean
  enabled: boolean
  features: { summary: boolean; resume: boolean; ticket: boolean }
  remaining: number
  limit: number
}

export interface AiSettings {
  configured: boolean
  enabled: boolean
  model: string
  daily_limit: number
  features: { summary: boolean; resume: boolean; ticket: boolean }
  updated_at: string
}

export interface AiUsage {
  days: number
  requests: number
  input_tokens: number
  output_tokens: number
  failed: number
  by_feature: { feature: string; count: number; tokens: number }[]
  by_user: { name: string | null; count: number; tokens: number }[]
  recent: { id: number; feature: string; entity: string | null; entity_id: number | null; model: string; tokens: number; ok: boolean; error: string | null; duration_ms: number; created_at: string; user_id: number | null }[]
}

export interface SearchGroup {
  type: string
  items: { id: number; title: string; subtitle: string | null; link: string }[]
}

export interface SearchResult {
  q: string
  total: number
  groups: SearchGroup[]
}
