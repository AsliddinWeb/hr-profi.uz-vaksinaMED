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
}

export const KINDS = ['office', 'pharmacy', 'warehouse', 'other'] as const
