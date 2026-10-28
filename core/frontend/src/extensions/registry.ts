import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router-dom'

export type Lang = 'uz' | 'ru'

export interface NavItem {
  id: string
  label: Record<Lang, string>
  to: string
  /** lucide-react ikonka nomi emas, tayyor komponent */
  icon?: ComponentType<{ className?: string }>
  /** Shu modul yoqilgan bo'lsagina ko'rinadi (backend /v1/meta -> modules) */
  module?: string
  /** Shu ruxsat bo'lsagina ko'rinadi (masalan 'users.read') */
  permission?: string
  /** Shu ruxsatlardan kamida bittasi bo'lsa ko'rinadi */
  anyPermission?: string[]
  /** Yon paneldagi bo'lim sarlavhasi (bir xil `group` ketma-ket joylashadi) */
  group?: 'main' | 'people' | 'org' | 'schedule' | 'attendance' | 'requests' | 'tasks' | 'needs' | 'checklists' | 'recruit' | 'internship' | 'payroll' | 'canteen' | 'logistics' | 'warehouse' | 'mobile' | 'reception' | 'helpdesk' | 'calls' | 'ai' | 'reports' | 'migration' | 'pharmacy' | 'admin' | 'system'
}

/** Mijoz extension shu API orqali core'ga ulanadi. */
export interface ExtensionApi {
  addRoute(route: RouteObject): void
  addNavItem(item: NavItem): void
  /** Core sahifalaridagi nomlangan joyga komponent qo'shish (masalan 'status.after') */
  slot(name: string, component: ComponentType): void
}

export type ExtensionRegister = (api: ExtensionApi) => void

const routes: RouteObject[] = []
const navItems: NavItem[] = []
const slots = new Map<string, ComponentType[]>()

export const extensionApi: ExtensionApi = {
  addRoute: (route) => void routes.push(route),
  addNavItem: (item) => void navItems.push(item),
  slot: (name, component) => {
    slots.set(name, [...(slots.get(name) ?? []), component])
  },
}

export const getExtensionRoutes = () => routes
export const getExtensionNavItems = () => navItems
export const getSlot = (name: string) => slots.get(name) ?? []
