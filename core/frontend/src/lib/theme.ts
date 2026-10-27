export type ThemeMode = 'light' | 'dark' | 'system'
const KEY = 'vaksina.theme'

function read(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    /* storage mavjud emas */
  }
  return 'system'
}

export function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode !== 'system') return mode
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(mode: ThemeMode = read()) {
  document.documentElement.dataset.theme = resolveTheme(mode)
}

export function getTheme(): ThemeMode {
  return read()
}

export function setTheme(mode: ThemeMode) {
  try {
    localStorage.setItem(KEY, mode)
  } catch {
    /* ignore */
  }
  applyTheme(mode)
}

export function toggleTheme(): 'light' | 'dark' {
  const next = resolveTheme(read()) === 'dark' ? 'light' : 'dark'
  setTheme(next)
  return next
}
