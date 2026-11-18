export type Embed = { mode: 'iframe' | 'video' | 'link'; src: string }

export function embedOf(url: string): Embed {
  try {
    const u = new URL(url)
    const host = u.hostname.replace(/^www\./, '')
    if (host === 'youtube.com' || host === 'm.youtube.com') {
      const v = u.searchParams.get('v')
      if (v) return { mode: 'iframe', src: `https://www.youtube.com/embed/${encodeURIComponent(v)}` }
      if (u.pathname.startsWith('/embed/')) return { mode: 'iframe', src: url }
    }
    if (host === 'youtu.be' && u.pathname.length > 1) return { mode: 'iframe', src: `https://www.youtube.com/embed/${encodeURIComponent(u.pathname.slice(1))}` }
    const slides = host === 'docs.google.com' ? /\/presentation\/d\/(e\/)?([^/]+)/.exec(u.pathname) : null
    if (slides) return { mode: 'iframe', src: `https://docs.google.com/presentation/d/${slides[1] ?? ''}${slides[2]}/embed` }
    if (/\.(mp4|webm|ogg)$/i.test(u.pathname)) return { mode: 'video', src: url }
    if (/\.pdf$/i.test(u.pathname)) return { mode: 'iframe', src: url }
  } catch {
    return { mode: 'link', src: url }
  }
  return { mode: 'link', src: url }
}
