import { useQuery } from '@tanstack/react-query'

import { api, ApiError } from '../../lib/api'

export interface Me {
  id: number
  login: string
  full_name: string
  phone: string | null
  locale: 'uz' | 'ru'
  must_change_password: boolean
  role: { key: string; name_uz: string; name_ru: string }
  permissions: string[]
}

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api<Me>('/api/auth/me')
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: 60_000,
    retry: false,
  })
}

/** Backend rbac.matches bilan bir xil mantiq (aniq, `a.*` va `*`). */
export function hasPermission(granted: string[] | undefined, needed: string): boolean {
  if (!granted) return false
  if (granted.includes('*') || granted.includes(needed)) return true
  const parts = needed.split('.')
  for (let i = 1; i < parts.length; i++) {
    if (granted.includes(`${parts.slice(0, i).join('.')}.*`)) return true
  }
  return false
}

export function useCan() {
  const { data } = useMe()
  return (perm: string) => hasPermission(data?.permissions, perm)
}
