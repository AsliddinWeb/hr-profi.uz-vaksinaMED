export interface HeadRef {
  id: number
  full_name: string
  is_active: boolean
}

export interface DepartmentNode {
  id: number
  name: string
  parent_id: number | null
  kind: 'office' | 'pharmacy' | 'warehouse' | 'other'
  color: string | null
  is_active: boolean
  head: HeadRef | null
  positions: number
  branches: number
  employees: number
  children: DepartmentNode[]
  children_count: number
}

export interface OrgTree {
  company: string
  leadership: { id: number; full_name: string; role_key: string; role_name_uz: string; role_name_ru: string }[]
  roots: DepartmentNode[]
}

export interface DepartmentRow {
  id: number
  name: string
  parent_id: number | null
  kind: DepartmentNode['kind']
  color: string | null
  sort_order: number
  is_active: boolean
  yqm?: string | null
  reports_to_position_id?: number | null
  head: HeadRef | null
  positions: number
  branches: number
  children: number
  depth: number
}

export interface PositionRow {
  id: number
  name: string
  department_id: number | null
  sort_order: number
  is_active: boolean
  yqm?: string | null
  parent_id?: number | null
  slots?: number
  is_head?: boolean
  duties?: string[]
}

export interface OrgStructureRow {
  id: number
  name: string
  description: string | null
  is_default: boolean
}

export interface OrgStructureDetail extends OrgStructureRow {
  positions: { id: number; name: string; department_id: number | null; parent_position_id: number | null; is_active: boolean }[]
  departments: { id: number; name: string; parent_department_id: number | null; reports_to_position_id: number | null; is_active: boolean }[]
}

export const KINDS = ['office', 'pharmacy', 'warehouse', 'other'] as const
