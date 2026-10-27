export class ApiError extends Error {
  status: number
  code: string
  extra: Record<string, unknown>
  constructor(status: number, code: string, extra: Record<string, unknown> = {}) {
    super(code)
    this.status = status
    this.code = code
    this.extra = extra
  }
}

const AUTH_PATHS = ['/api/auth/login', '/api/auth/refresh']

function doFetch(path: string, init?: RequestInit) {
  return fetch(path, {
    credentials: 'same-origin',
    ...init,
    headers: {
      Accept: 'application/json',
      // Backend CSRF himoyasi: o'zgartiruvchi so'rovlarda shart
      'X-Requested-With': 'vaksina',
      // FormData da Content-Type ni brauzer o'zi qo'yadi (boundary bilan)
      ...(init?.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
  })
}

let refreshing: Promise<boolean> | null = null

/** Access token tugasa, refresh cookie orqali bir marta yangilaydi (parallel so'rovlar bitta refresh kutadi). */
function refreshSession(): Promise<boolean> {
  refreshing ??= doFetch('/api/auth/refresh', { method: 'POST' })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    const d = body.detail
    if (d && typeof d === 'object' && 'code' in d) {
      const { code, ...extra } = d as { code: string }
      return new ApiError(res.status, code, extra)
    }
    if (res.status === 422) return new ApiError(422, 'validation')
  } catch {
    /* JSON emas */
  }
  return new ApiError(res.status, 'unknown')
}

/** JSON so'rov. `okStatuses` — xato hisoblanmaydigan qo'shimcha kodlar (masalan 503 readiness). */
export async function api<T>(path: string, init?: RequestInit, okStatuses: number[] = []): Promise<T> {
  let res = await doFetch(path, init)
  if (res.status === 401 && !AUTH_PATHS.includes(path) && (await refreshSession())) {
    res = await doFetch(path, init)
  }
  if (!res.ok && !okStatuses.includes(res.status)) throw await toError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const send = <T = void>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body?: unknown) =>
  api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) })

/** Fayl yuklash (multipart). */
export const upload = <T = void>(method: 'POST' | 'PUT', path: string, form: FormData) =>
  api<T>(path, { method, body: form })
