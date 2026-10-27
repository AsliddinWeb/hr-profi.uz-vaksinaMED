export interface UserRow {
  id: number
  login: string
  full_name: string
  phone: string | null
  role_key: string
  role_name_uz: string
  role_name_ru: string
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
  created_at: string
}

export interface UsersPage {
  items: UserRow[]
  total: number
  page: number
  size: number
}

export interface RoleRow {
  id: number
  key: string
  name_uz: string
  name_ru: string
  is_system: boolean
  locked: boolean
  users: number
  permissions: string[]
}

/** `/api/v1/users/assignable-roles`: roles.read talab qilmaydi. */
export interface RoleOption {
  key: string
  name_uz: string
  name_ru: string
  assignable: boolean
}

export const roleName = (r: { name_uz: string; name_ru: string }, lang: string) =>
  lang === 'ru' ? r.name_ru : r.name_uz
