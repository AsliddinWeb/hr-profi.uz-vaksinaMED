import { animate, motion, useInView, useReducedMotion, type HTMLMotionProps } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'

/** Umumiy egri chiziq: tez boshlanib, yumshoq to'xtaydi. */
const EASE = [0.22, 0.8, 0.24, 1] as const

/** Sahifa almashganda: yengil paydo bo'lish va ko'tarilish (har yo'l uchun `key` bilan). */
export function PageTransition({ children, id }: { children: ReactNode; id: string }) {
  return (
    <motion.div key={id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.32, ease: EASE }}>
      {children}
    </motion.div>
  )
}

/** Bolalarini navbat bilan chiqaradi (gridlar, ro'yxatlar). Ichida `StaggerItem` ishlatiladi. */
export function Stagger({ children, className, delay = 0.05, ...rest }: HTMLMotionProps<'div'> & { delay?: number }) {
  return (
    <motion.div className={className} initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: delay } } }} {...rest}>
      {children}
    </motion.div>
  )
}

export function StaggerItem({ children, className, ...rest }: HTMLMotionProps<'div'>) {
  return (
    <motion.div
      className={className}
      variants={{ hidden: { opacity: 0, y: 12, scale: 0.98 }, show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: EASE } } }}
      {...rest}
    >
      {children}
    </motion.div>
  )
}

/** Raqamni 0 dan sanab chiqaradi (ko'rinishga kirganda bir marta). Raqam bo'lmasa matnni o'zgarishsiz ko'rsatadi. */
export function AnimatedNumber({ value, format = (n) => n.toLocaleString('ru-RU'), duration = 0.9 }: { value: number | null | undefined; format?: (n: number) => string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const seen = useInView(ref, { once: true })
  const reduce = useReducedMotion()
  const [shown, setShown] = useState<number | null>(null)
  useEffect(() => {
    if (value == null || !seen) return
    if (reduce) {
      setShown(value)
      return
    }
    const ctl = animate(shown ?? 0, value, { duration, ease: EASE, onUpdate: (v) => setShown(v) })
    return () => ctl.stop()
    // `shown` qasddan bog'liqlikda emas: oxirgi ko'rsatilgan qiymatdan davom etadi
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, seen, reduce, duration])
  if (value == null) return <span ref={ref}>—</span>
  const n = shown ?? 0
  return (
    <span ref={ref} className="tabular-nums">
      {format(Number.isInteger(value) ? Math.round(n) : Math.round(n * 10) / 10)}
    </span>
  )
}

/** Matn ichidagi birinchi raqamni sanab chiqaradi: «105 mln», «42%», «7 / 12». */
export function AnimatedText({ text }: { text: string }) {
  const m = /^(\D*?)(-?\d[\d\s ]*(?:[.,]\d+)?)(.*)$/.exec(text)
  if (!m) return <>{text}</>
  const raw = m[2].replace(/[\s ]/g, '').replace(',', '.')
  const num = Number(raw)
  if (!Number.isFinite(num)) return <>{text}</>
  const decimals = raw.includes('.') ? raw.split('.')[1].length : 0
  const grouped = /[\s ]/.test(m[2].trim())
  const fmt = (v: number) => (grouped ? v.toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : v.toFixed(decimals))
  return (
    <>
      {m[1]}
      <AnimatedNumber value={num} format={fmt} />
      {m[3]}
    </>
  )
}

/** Ko'tariladigan karta: ustiga borganda yengil ko'tarilish va soya. */
export function LiftCard({ className, children, ...rest }: HTMLMotionProps<'div'>) {
  return (
    <motion.div className={className} whileHover={{ y: -3, boxShadow: 'var(--shadow-hover)' }} transition={{ type: 'spring', stiffness: 380, damping: 28 }} {...rest}>
      {children}
    </motion.div>
  )
}
