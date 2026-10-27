export interface Branch {
  id: number
  number: number | null
  name: string
  address: string | null
  district: string | null
  phone: string | null
  department_id: number | null
  department_name: string | null
  manager_user_id: number | null
  manager_name: string | null
  coordinator_user_id: number | null
  coordinator_name: string | null
  latitude: number | null
  longitude: number | null
  geofence_radius_m: number
  is_active: boolean
}

export interface BranchPage {
  total: number
  page: number
  size: number
  summary: { total: number; with_manager: number; with_geo: number; active: number }
  items: Branch[]
}

export interface BranchPoint {
  id: number
  number: number | null
  name: string
  latitude: number
  longitude: number
  radius: number
  manager_name: string | null
  coordinator_name: string | null
  is_active: boolean
}

export interface BulkResult {
  created: number
  updated: number
  errors: { row: number; code: string }[]
  applied: boolean
}
