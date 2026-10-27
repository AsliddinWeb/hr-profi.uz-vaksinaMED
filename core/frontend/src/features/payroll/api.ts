export const KINDS = ['sales', 'plan', 'kpi', 'bonus', 'advance', 'deduction'] as const
export type Kind = (typeof KINDS)[number]
export type RStatus = 'draft' | 'approved' | 'paid'

export interface EmpRef {
  id: number
  name: string | null
  employee_no: number | null
}

export interface Scheme {
  id: number
  employee: EmpRef
  effective_from: string
  fixed_amount: number
  commission_percent: number
  plan_bonus: number
  kpi_amount: number
  note: string | null
}

export interface Item {
  id: number
  employee: EmpRef
  period: string
  kind: Kind
  amount: number
  note: string | null
  created_at: string
}

export interface Page<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export interface Totals {
  employees: number
  fixed: number
  commission: number
  plan_bonus: number
  kpi_bonus: number
  bonus: number
  gross: number
  penalties: number
  deductions: number
  tax: number
  inps: number
  net: number
  advance: number
  to_pay: number
}

export interface Run {
  id: number
  period: string
  status: RStatus
  settings: { tax_percent: string; inps_percent: string; paid_leave: boolean }
  note: string | null
  calculated_at: string | null
  approved_at: string | null
  paid_at: string | null
}

export interface RunRow extends Run {
  employees: number
  gross: number
  to_pay: number
}

export interface RunDetail extends Run {
  totals: Totals
  missing_scheme: number
  flagged: number
}

export interface Line {
  id: number
  employee: EmpRef
  branch: string | null
  department: string | null
  plan_days: number
  paid_days: number
  warnings: string[]
  fixed: number
  commission: number
  plan_bonus: number
  kpi_bonus: number
  bonus: number
  gross: number
  penalties: number
  deductions: number
  taxable: number
  tax: number
  inps: number
  net: number
  advance: number
  to_pay: number
}

export interface LineDetail extends Line {
  period: string
  status: RStatus
  details: {
    absent_days: number
    unpaid_leave_days: number
    day_counts: Record<string, number>
    sales: string
    plan: string
    kpi_score: string | null
    scheme: { id: number; effective_from: string; fixed_amount: string; commission_percent: string; plan_bonus: string; kpi_amount: string }
    settings: { tax_percent: string; inps_percent: string; paid_leave: boolean | string }
    warnings: string[]
  }
}

export interface MyRow {
  id: number
  period: string
  status: RStatus
  gross: number
  net: number
  to_pay: number
}

export const RSTATUS_TONE: Record<RStatus, 'neutral' | 'success' | 'warning'> = { draft: 'warning', approved: 'neutral', paid: 'success' }
export const som = (n: number): string => new Intl.NumberFormat('ru-RU').format(n)
export const currentPeriod = (): string => new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Tashkent' }).slice(0, 7)
