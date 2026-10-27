/** WebSocket mijoz: avtomatik qayta ulanish, ping, 4401 da sessiyani yangilash. */

export type RealtimeMessage = { type: string; [key: string]: unknown }
type Handler = (msg: RealtimeMessage) => void

const PING_MS = 25_000

export class RealtimeClient {
  private ws: WebSocket | null = null
  private handlers = new Set<Handler>()
  private retry = 0
  private timer: ReturnType<typeof setTimeout> | null = null
  private pinger: ReturnType<typeof setInterval> | null = null
  private stopped = true

  private readonly path: string
  /** 4401 (sessiya yaroqsiz) da chaqiriladi; true qaytarsa qayta ulanadi */
  private readonly onUnauthorized: () => Promise<boolean>

  constructor(path: string, onUnauthorized: () => Promise<boolean>) {
    this.path = path
    this.onUnauthorized = onUnauthorized
  }

  subscribe(handler: Handler): () => void {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  start() {
    if (!this.stopped) return
    this.stopped = false
    this.connect()
  }

  stop() {
    this.stopped = true
    if (this.timer) clearTimeout(this.timer)
    if (this.pinger) clearInterval(this.pinger)
    this.timer = this.pinger = null
    this.ws?.close(1000)
    this.ws = null
  }

  private connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}${this.path}`)
    this.ws = ws

    ws.onopen = () => {
      this.retry = 0
      this.pinger = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send('{"type":"ping"}'), PING_MS)
    }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string) as RealtimeMessage
        this.handlers.forEach((h) => h(msg))
      } catch {
        /* noto'g'ri xabar e'tiborsiz */
      }
    }
    ws.onclose = async (e) => {
      if (this.pinger) clearInterval(this.pinger)
      this.pinger = null
      if (this.stopped || this.ws !== ws) return
      if (e.code === 4401 && !(await this.onUnauthorized())) return
      // Eksponensial kutish (1s, 2s, 4s ... 30s) + biroz tasodifiylik
      const delay = Math.min(30_000, 1000 * 2 ** this.retry++) * (0.8 + Math.random() * 0.4)
      this.timer = setTimeout(() => !this.stopped && this.connect(), delay)
    }
  }
}
