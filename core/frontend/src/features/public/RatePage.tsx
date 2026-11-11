import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, ChevronLeft, Store, UserRound } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { api, send } from '../../lib/api'

type Info = { branch: string; staff: { id: number; name: string; position: string | null }[] }

const T = {
  uz: {
    kicker: 'FILIAL', title: 'XIZMATNI BAHOLANG', thanks: 'Dorixonamizga tashrifingiz uchun rahmat!', what: 'Nimani baholaysiz?', pick: 'Bitta yo‘nalishni tanlang',
    emp: 'Xodimlarni baholash', empHint: 'Hozir smenadagi xodimlar', noStaff: 'Hozir smenada xodim yo‘q — dorixonani baholashingiz mumkin.',
    ph: 'Dorixonani baholash', phHint: 'Filial, tozalik va mahsulotlar', back: 'Orqaga', q1: '1. Dorixonani umumiy baholang', qe: '1. Xodimni baholang',
    q2: '2. Tozalik va qulaylik qanday?', q3: '3. Dori va mahsulotlar tanlovi qanday?', levels: ["A'lo", 'Yaxshi', 'Qoniqarli', 'Yomon', 'Juda yomon'],
    comment: 'Izoh (ixtiyoriy)', commentPh: 'Fikringiz yoki taklifingiz…', name: 'Ismingiz', phone: 'Telefon raqamingiz', send: 'BAHONI YUBORISH',
    done: 'Rahmat! Bahoyingiz qabul qilindi.', invalid: 'QR kod eskirgan yoki bloklangan.', already: 'Siz yaqinda baho qoldirgansiz.', error: 'Xatolik. Qayta urinib ko‘ring.', choose: 'Xodimni tanlang',
  },
  ru: {
    kicker: 'ФИЛИАЛ', title: 'ОЦЕНИТЕ ОБСЛУЖИВАНИЕ', thanks: 'Спасибо, что посетили нашу аптеку!', what: 'Что вы хотите оценить?', pick: 'Выберите одно направление',
    emp: 'Оценить сотрудника', empHint: 'Сотрудники на смене', noStaff: 'Сейчас на смене никого нет — можно оценить аптеку.',
    ph: 'Оценить аптеку', phHint: 'Филиал, чистота и ассортимент', back: 'Назад', q1: '1. Общая оценка аптеки', qe: '1. Оцените сотрудника',
    q2: '2. Чистота и удобство?', q3: '3. Ассортимент лекарств и товаров?', levels: ['Отлично', 'Хорошо', 'Удовлетворительно', 'Плохо', 'Очень плохо'],
    comment: 'Комментарий (необязательно)', commentPh: 'Ваше мнение или предложение…', name: 'Ваше имя', phone: 'Номер телефона', send: 'ОТПРАВИТЬ ОЦЕНКУ',
    done: 'Спасибо! Ваша оценка принята.', invalid: 'QR-код устарел или заблокирован.', already: 'Вы недавно уже оставили оценку.', error: 'Ошибка. Попробуйте ещё раз.', choose: 'Выберите сотрудника',
  },
}

/** /baho/:token — mijoz filial QR kodini skanerlab, smenadagi xodimni yoki dorixonani baholaydi (login talab qilinmaydi). */
export function RatePage() {
  const { token = '' } = useParams()
  const [lang, setLang] = useState<'uz' | 'ru'>('uz')
  const L = T[lang]
  const info = useQuery({ queryKey: ['rate', token], queryFn: () => api<Info>(`/api/v1/public/rate/${token}`), retry: false })
  const [target, setTarget] = useState<'employee' | 'pharmacy' | null>(null)
  const [emp, setEmp] = useState<number | null>(null)
  const [stars, setStars] = useState(0)
  const [clean, setClean] = useState(0)
  const [assort, setAssort] = useState(0)
  const [comment, setComment] = useState('')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('+998')
  const submit = useMutation({
    mutationFn: () => send('POST', `/api/v1/public/rate/${token}`, { target, employee_id: emp, stars, cleanliness: clean || null, assortment: assort || null, comment: comment || null, name, phone: phone.replace(/[^\d+]/g, '') }),
  })
  const valid = stars > 0 && name.trim().length >= 2 && /^\+?998\d{9}$/.test(phone.replace(/[^\d+]/g, '')) && (target === 'employee' ? !!emp : clean > 0 && assort > 0)
  const err = submit.error as { status?: number } | null

  return (
    <main className="min-h-screen bg-[linear-gradient(160deg,#f5f3ff,#fefce8)] px-4 py-6 text-[#1e1b4b]">
      <div className="mx-auto flex max-w-md flex-col gap-4">
        <div className="flex justify-end">
          <button type="button" className="rounded-full bg-white px-3 py-1 text-xs font-semibold shadow" onClick={() => setLang(lang === 'uz' ? 'ru' : 'uz')}>{lang === 'uz' ? 'RU' : 'UZ'}</button>
        </div>
        {info.isError ? (
          <div className="rounded-2xl bg-white p-6 text-center shadow">{L.invalid}</div>
        ) : !info.data ? (
          <div className="h-60 animate-pulse rounded-2xl bg-white/70" />
        ) : submit.isSuccess ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl bg-white p-8 text-center shadow">
            <CheckCircle2 className="size-12 text-[#16a34a]" />
            <div className="text-lg font-semibold">{L.done}</div>
          </div>
        ) : (
          <div className="flex flex-col gap-4 rounded-2xl bg-white p-5 shadow">
            <div className="text-center">
              <div className="text-[11px] font-semibold tracking-wider text-[#7c3aed]">{L.kicker} · {info.data.branch}</div>
              <div className="mt-1 text-xl font-bold">{L.title}</div>
              <div className="text-sm text-gray-500">{L.thanks}</div>
            </div>
            {!target ? (
              <>
                <div><div className="font-semibold">{L.what}</div><div className="text-xs text-gray-500">{L.pick}</div></div>
                <button type="button" disabled={!info.data.staff.length} onClick={() => setTarget('employee')} className="flex items-center gap-3 rounded-xl border-2 border-[#ede9fe] p-4 text-left disabled:opacity-50">
                  <UserRound className="size-7 text-[#7c3aed]" />
                  <span><b>{L.emp}</b><span className="block text-xs text-gray-500">{info.data.staff.length ? L.empHint : L.noStaff}</span></span>
                </button>
                <button type="button" onClick={() => setTarget('pharmacy')} className="flex items-center gap-3 rounded-xl border-2 border-[#ede9fe] p-4 text-left">
                  <Store className="size-7 text-[#7c3aed]" />
                  <span><b>{L.ph}</b><span className="block text-xs text-gray-500">{L.phHint}</span></span>
                </button>
              </>
            ) : (
              <>
                <button type="button" onClick={() => setTarget(null)} className="flex items-center gap-1 self-start text-sm text-[#7c3aed]"><ChevronLeft className="size-4" />{L.back}</button>
                {target === 'employee' && (
                  <div className="flex flex-col gap-2">
                    <div className="font-semibold">{L.choose}*</div>
                    {info.data.staff.map((s) => (
                      <button key={s.id} type="button" onClick={() => setEmp(s.id)} className={`rounded-xl border-2 p-3 text-left ${emp === s.id ? 'border-[#7c3aed] bg-[#f5f3ff]' : 'border-[#ede9fe]'}`}>
                        <b>{s.name}</b><span className="block text-xs text-gray-500">{s.position ?? ''}</span>
                      </button>
                    ))}
                  </div>
                )}
                <div>
                  <div className="mb-2 font-semibold">{target === 'employee' ? L.qe : L.q1}*</div>
                  <div className="flex justify-between gap-2">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button key={n} type="button" onClick={() => setStars(n)} className={`flex-1 rounded-xl border-2 py-3 text-xl ${stars >= n ? 'border-[#facc15] bg-[#fefce8] text-[#ca8a04]' : 'border-[#ede9fe] text-gray-300'}`} aria-label={String(n)}>★</button>
                    ))}
                  </div>
                </div>
                {target === 'pharmacy' && (
                  <>
                    <Levels title={L.q2} levels={L.levels} value={clean} onChange={setClean} />
                    <Levels title={L.q3} levels={L.levels} value={assort} onChange={setAssort} />
                  </>
                )}
                <label className="flex flex-col gap-1 text-sm font-medium">{L.comment}
                  <textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder={L.commentPh} maxLength={1000} rows={3} className="rounded-xl border-2 border-[#ede9fe] p-2 font-normal" />
                </label>
                <label className="flex flex-col gap-1 text-sm font-medium">{L.name}*
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ism Familiya" className="rounded-xl border-2 border-[#ede9fe] p-2 font-normal" />
                </label>
                <label className="flex flex-col gap-1 text-sm font-medium">{L.phone}*
                  <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" placeholder="+998 9X XXX XX XX" className="rounded-xl border-2 border-[#ede9fe] p-2 font-normal" />
                </label>
                {submit.isError && <p role="alert" className="text-sm text-red-600">{err?.status === 429 ? L.already : L.error}</p>}
                <button type="button" disabled={!valid || submit.isPending} onClick={() => submit.mutate()} className="rounded-xl bg-[#6d28d9] py-3 font-bold text-white disabled:opacity-40">{L.send}</button>
              </>
            )}
          </div>
        )}
      </div>
    </main>
  )
}

function Levels({ title, levels, value, onChange }: { title: string; levels: string[]; value: number; onChange: (n: number) => void }) {
  return (
    <div>
      <div className="mb-2 font-semibold">{title}*</div>
      <div className="flex flex-wrap gap-2">
        {levels.map((l, i) => {
          const n = 5 - i
          return <button key={l} type="button" onClick={() => onChange(n)} className={`rounded-full border-2 px-3 py-1.5 text-sm ${value === n ? 'border-[#7c3aed] bg-[#7c3aed] text-white' : 'border-[#ede9fe]'}`}>{l}</button>
        })}
      </div>
    </div>
  )
}
