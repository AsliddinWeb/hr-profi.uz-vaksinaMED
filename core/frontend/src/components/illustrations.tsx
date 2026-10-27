/** Yengil SVG illyustratsiyalar (tashqi rasm yuklamasdan, brend ranglarida). */

/** Jamoa va ma'lumotlar: login va bosh sahifa uchun katta rasm. */
export function TeamArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 480 360" className={className} fill="none" aria-hidden>
      <defs>
        <linearGradient id="ta-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.22" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0.06" />
        </linearGradient>
      </defs>
      <circle cx="240" cy="190" r="150" fill="url(#ta-g)" />
      <circle cx="240" cy="190" r="104" fill="#ffffff" fillOpacity="0.1" />
      {/* karta */}
      <rect x="120" y="96" width="240" height="168" rx="18" fill="#fff" />
      <rect x="120" y="96" width="240" height="40" rx="18" fill="#0b5ed7" fillOpacity="0.12" />
      <circle cx="146" cy="116" r="6" fill="#0b5ed7" />
      <rect x="160" y="111" width="70" height="10" rx="5" fill="#0b5ed7" fillOpacity="0.45" />
      <g>
        <circle cx="156" cy="162" r="14" fill="#7a4fd6" fillOpacity="0.9" />
        <rect x="180" y="152" width="90" height="8" rx="4" fill="#101828" fillOpacity="0.8" />
        <rect x="180" y="168" width="60" height="7" rx="3.5" fill="#667085" fillOpacity="0.5" />
        <rect x="296" y="156" width="44" height="18" rx="9" fill="#1f9d61" fillOpacity="0.18" />
        <circle cx="310" cy="165" r="3.5" fill="#1f9d61" />
      </g>
      <g>
        <circle cx="156" cy="206" r="14" fill="#0f9aa8" fillOpacity="0.9" />
        <rect x="180" y="196" width="76" height="8" rx="4" fill="#101828" fillOpacity="0.8" />
        <rect x="180" y="212" width="52" height="7" rx="3.5" fill="#667085" fillOpacity="0.5" />
        <rect x="296" y="200" width="44" height="18" rx="9" fill="#d9820b" fillOpacity="0.2" />
        <circle cx="310" cy="209" r="3.5" fill="#d9820b" />
      </g>
      <rect x="140" y="236" width="200" height="6" rx="3" fill="#0b5ed7" fillOpacity="0.15" />
      <rect x="140" y="236" width="132" height="6" rx="3" fill="#0b5ed7" />
      {/* grafik */}
      <rect x="318" y="46" width="124" height="86" rx="14" fill="#fff" />
      <path d="M332 112 L352 92 L370 102 L392 72 L428 84" stroke="#1f9d61" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="392" cy="72" r="5" fill="#1f9d61" />
      {/* belgilar */}
      <rect x="40" y="70" width="104" height="52" rx="14" fill="#fff" />
      <circle cx="66" cy="96" r="12" fill="#d6407a" fillOpacity="0.15" />
      <path d="M60 96 l5 5 9 -10" stroke="#d6407a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="86" y="88" width="42" height="8" rx="4" fill="#101828" fillOpacity="0.75" />
      <rect x="86" y="102" width="28" height="6" rx="3" fill="#667085" fillOpacity="0.5" />
      <rect x="352" y="238" width="96" height="56" rx="14" fill="#fff" />
      <circle cx="378" cy="266" r="13" fill="#4a55d6" fillOpacity="0.15" />
      <path d="M378 258 v8 l6 4" stroke="#4a55d6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="398" y="258" width="38" height="8" rx="4" fill="#101828" fillOpacity="0.75" />
      <rect x="398" y="272" width="24" height="6" rx="3" fill="#667085" fillOpacity="0.5" />
    </svg>
  )
}

/** Bo'sh holat: papka va qidiruv, bo'lim rangida. */
export function EmptyArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" className={className} fill="none" aria-hidden>
      <ellipse cx="80" cy="104" rx="52" ry="8" fill="currentColor" fillOpacity="0.1" />
      <rect x="30" y="34" width="100" height="64" rx="10" fill="currentColor" fillOpacity="0.12" />
      <path d="M30 44a10 10 0 0 1 10-10h24l8 10h48a10 10 0 0 1 10 10v8H30z" fill="currentColor" fillOpacity="0.22" />
      <rect x="44" y="58" width="72" height="6" rx="3" fill="currentColor" fillOpacity="0.3" />
      <rect x="44" y="72" width="48" height="6" rx="3" fill="currentColor" fillOpacity="0.2" />
      <circle cx="116" cy="34" r="16" fill="var(--surface)" stroke="currentColor" strokeWidth="4" />
      <path d="M128 46l10 10" stroke="currentColor" strokeWidth="5" strokeLinecap="round" />
    </svg>
  )
}
