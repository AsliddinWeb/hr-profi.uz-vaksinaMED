export function formatDateTime(iso: string | null | undefined, lang: string): string {
  if (!iso) return '—'
  // 'uz-UZ' Intl formati g'alati (2026 M10 22), ikkala tilda ham KK.OO.YYYY, SS:DD
  void lang
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Tashkent',
  }).format(new Date(iso))
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
}

export function relativeTime(iso: string, lang: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  const abs = Math.abs(diff)
  if (lang !== 'ru') {
    // Intl 'uz' qisqa ("-40 s") chiqaradi, shuning uchun o'zimiz
    if (abs < 60) return 'hozir'
    if (abs < 3600) return `${Math.round(abs / 60)} daqiqa oldin`
    if (abs < 86400) return `${Math.round(abs / 3600)} soat oldin`
    return `${Math.round(abs / 86400)} kun oldin`
  }
  const rtf = new Intl.RelativeTimeFormat('ru', { numeric: 'auto' })
  if (abs < 60) return 'только что'
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour')
  return rtf.format(Math.round(diff / 86400), 'day')
}

export function formatDate(iso: string | null | undefined, lang: string): string {
  if (!iso) return '—'
  void lang
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' }).format(new Date(iso))
}
