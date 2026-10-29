export const CHANNELS = ['hh_uz', 'olx', 'telegram', 'site', 'instagram', 'billboard', 'target', 'referral', 'other'] as const

export interface SourceLink {
  id: number
  code: string
  url: string
  channel: string
  label: string | null
  owner: { id: number; name: string } | null
  clicks: number
  applications: number
  hired: number
  is_active: boolean
}
export interface Promo {
  vacancy: { id: number; title: string; status: string; branch: string | null }
  ad: string
  channels: { id: number; channel: string; url: string | null; note: string | null; posted_by: string | null; posted_at: string; closed_at: string | null }[]
  links: SourceLink[]
}
export interface SourcesReport {
  total: number
  by_channel: { channel: string; applications: number; hired: number; clicks: number; links: number }[]
  by_owner: { owner: string | null; applications: number; hired: number }[]
}
