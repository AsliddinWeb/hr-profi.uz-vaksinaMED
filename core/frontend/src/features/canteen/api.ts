export const KINDS = ['soup', 'main', 'salad', 'side', 'drink', 'dessert', 'other'] as const
export type DishKind = (typeof KINDS)[number]

export interface Dish {
  id: number
  name: string
  kind: DishKind
  description: string | null
  avg: number | null
  count: number
}

export interface Mine {
  overall: { stars: number; comment: string | null; anonymous: boolean; reply: string | null } | null
  dishes: Record<string, { stars: number }>
}

export interface Menu {
  id: number
  menu_date: string
  note: string | null
  dishes: Dish[]
  rating: { avg: number | null; count: number } | null
  can_rate?: boolean
  require_qr?: boolean
  mine?: Mine
}

export interface RatingRow {
  id: number
  menu_id: number
  menu_date: string
  stars: number
  comment: string | null
  anonymous: boolean
  via_qr: boolean
  employee: string | null
  reply: string | null
  replied_at: string | null
  created_at: string
}

export interface Page<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export interface Analytics {
  start: string
  end: string
  kpis: { menus: number; ratings: number; raters: number; active_employees: number; avg: number | null; low_share: number | null; via_qr: number; commented: number; unanswered: number }
  distribution: Record<string, number>
  trend: { date: string; avg: number | null; count: number }[]
  dishes: { name: string; kind: DishKind; avg: number; count: number; days: number }[]
}

export const avgText = (v: number | null | undefined): string => (v === null || v === undefined ? '—' : v.toFixed(1))
