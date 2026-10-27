export const DOC_KINDS = ['tech_passport', 'insurance', 'osago', 'inspection', 'permit', 'other'] as const
export const VKINDS = ['car', 'van', 'truck', 'moto', 'other'] as const
export const FUELS = ['petrol', 'diesel', 'gas', 'propane', 'electric'] as const
export type TStatus = 'planned' | 'active' | 'completed' | 'cancelled'

export interface Vehicle {
  id: number
  plate: string
  name: string
  kind: string
  fuel_type: string
  fuel_norm: number
  tank_l: number | null
  odometer_km: number
  branch: { id: number; name: string | null } | null
  status: 'active' | 'service' | 'retired'
  note: string | null
  docs?: { expired: number; soon: number }
  active_trip_id?: number | null
}

export interface Doc {
  id: number
  vehicle_id: number
  kind: string
  number: string | null
  issued_at: string | null
  expires_at: string
  note: string | null
  days_left: number
  stage: number
}

export interface Driver {
  employee: { id: number; name: string; phone: string | null; has_account: boolean; status: string }
  has_profile: boolean
  license_no: string | null
  categories: string | null
  license_expires: string | null
  note: string | null
  license_days_left: number | null
  license_stage: number
  active_trip_id?: number | null
}

export interface Trip {
  id: number
  status: TStatus
  purpose: string
  origin: string | null
  destination: string | null
  planned_start: string | null
  vehicle: { id: number; plate: string; name: string; odometer_km?: number }
  driver: { id: number; name: string | null }
  started_at: string | null
  finished_at: string | null
  start_odometer: number | null
  end_odometer: number | null
  distance_km: number | null
  gps_km: number | null
  fuel_norm_l: number | null
  note: string | null
}

export interface TripDetail extends Trip {
  points: number
  can: { edit: boolean; start: boolean; finish: boolean; cancel: boolean; mine: boolean }
}

export interface Page<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export interface Live {
  trip_id: number
  vehicle: { id: number; plate: string; name: string }
  driver: { id: number; name: string | null }
  purpose: string
  lat: number | null
  lng: number | null
  speed: number | null
  at: string | null
  stale: boolean
}

export interface Fuel {
  id: number
  vehicle: { id: number; plate: string | null }
  trip_id: number | null
  driver: { id: number; name: string | null } | null
  fueled_at: string
  liters: number
  price_per_liter: number | null
  total: number | null
  odometer_km: number | null
  station: string | null
  full_tank: boolean
}

export interface FuelReport {
  start: string
  end: string
  items: { vehicle: { id: number; plate: string; name: string }; norm_per_100: number; trips: number; km: number; gps_km: number; norm_liters: number; fills: number; liters: number; cost: number; variance: number; actual_per_100: number | null }[]
  totals: { trips: number; km: number; norm_liters: number; fills: number; liters: number; cost: number; variance: number }
}

export const TSTATUS_TONE: Record<TStatus, 'neutral' | 'success' | 'warning' | 'danger'> = { planned: 'neutral', active: 'warning', completed: 'success', cancelled: 'danger' }
export const stageTone = (s: number): 'neutral' | 'warning' | 'danger' => (s >= 3 ? 'danger' : s >= 1 ? 'warning' : 'neutral')
export const num = (n: number | null | undefined, d = 0): string => (n === null || n === undefined ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: d }).format(n))
