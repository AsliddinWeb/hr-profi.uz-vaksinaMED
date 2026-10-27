import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import ru from '../locales/ru.json'
import uz from '../locales/uz.json'

const KEY = 'vaksina.lang'

function initialLang(): 'uz' | 'ru' {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'uz' || v === 'ru') return v
  } catch {
    /* ignore */
  }
  return 'uz'
}

void i18n.use(initReactI18next).init({
  resources: { uz: { translation: uz }, ru: { translation: ru } },
  lng: initialLang(),
  fallbackLng: 'uz',
  interpolation: { escapeValue: false },
})

export function setLang(lang: 'uz' | 'ru') {
  try {
    localStorage.setItem(KEY, lang)
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lang
  void i18n.changeLanguage(lang)
}

document.documentElement.lang = i18n.language

export default i18n
