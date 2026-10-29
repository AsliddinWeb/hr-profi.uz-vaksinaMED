export const CATEGORIES = ['strategy', 'policy', 'process', 'system', 'culture'] as const
export type Category = (typeof CATEGORIES)[number]

export interface HrDoc {
  id: number
  key: string | null
  category: Category
  title: string
  summary: string | null
  status: 'draft' | 'published'
  version: number
  requires_ack: boolean
  roles: string[]
  has_file: boolean
  file_name: string | null
  file_size: number | null
  has_body: boolean
  body?: string
  published_at: string | null
  ack: { version: number; at: string } | null
  needs_ack: boolean
  ack_count?: number
}

export interface StaffDoc {
  id: number
  kind: 'application' | 'order'
  subtype: string
  number: string | null
  title: string
  body: string
  status: 'submitted' | 'approved' | 'rejected' | 'cancelled' | 'draft' | 'issued'
  employee: { id: number; name: string }
  start_date: string | null
  end_date: string | null
  related_id: number | null
  created_by: string | null
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  signed_by: string | null
  signed_at: string | null
  acknowledged_at: string | null
  created_at: string
  has_pdf: boolean
  can: { decide: boolean; edit: boolean; sign: boolean; ack: boolean; cancel: boolean; make_order: boolean }
}

export const APP_TYPES = ['vacation', 'unpaid', 'resign', 'transfer', 'other'] as const
export const ORDER_TYPES = ['hire', 'transfer', 'vacation', 'dismiss', 'other'] as const
export const STAFF_TONE = { submitted: 'warning', approved: 'success', rejected: 'danger', cancelled: 'neutral', draft: 'neutral', issued: 'success' } as const
