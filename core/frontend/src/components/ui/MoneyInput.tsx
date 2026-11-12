import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { calcMoney, fmtMoney } from '../../lib/money'
import { Input } from './Input'

/** Pul maydoni: xonalarga bo'lingan ko'rinish, kalkulyator formulasi (5000000*2, 8 mln + 500 ming), brauzer takliflari o'chiq. */
export function MoneyInput({ id, value, onChange, placeholder }: { id?: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  const { t } = useTranslation()
  const [text, setText] = useState(value ? fmtMoney(Number(value)) : '')
  const [focus, setFocus] = useState(false)
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    setSeen(value)
    if (!focus && String(calcMoney(text) ?? '') !== value) setText(value ? fmtMoney(Number(value)) : '')
  }
  const result = calcMoney(text)
  const isFormula = /[+\-*/()a-zа-я]/i.test(text.replace(/^-/, ''))
  const commit = () => {
    setFocus(false)
    if (result != null && result >= 0) {
      setText(fmtMoney(result))
      onChange(String(result))
    } else if (!text.trim()) onChange('')
  }
  return (
    <div className="flex flex-col gap-1">
      <Input
        id={id}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        spellCheck={false}
        value={text}
        placeholder={placeholder ?? t('money.placeholder')}
        onFocus={() => setFocus(true)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), commit())}
        onChange={(e) => {
          const v = e.target.value
          // oddiy son yozilsa — darhol xonalarga bo'lib ko'rsatamiz
          if (/^[\d\s]*$/.test(v)) {
            const n = v.replace(/\s/g, '')
            setText(n ? fmtMoney(Number(n)) : '')
            onChange(n)
          } else setText(v)
        }}
      />
      {text.trim() && (isFormula || focus) && (
        <span className={`text-xs ${result == null || result < 0 ? 'text-danger' : 'text-muted'}`}>
          {result == null || result < 0 ? t('money.invalid') : `= ${fmtMoney(result)} ${t('money.currency')}`}
        </span>
      )}
    </div>
  )
}
