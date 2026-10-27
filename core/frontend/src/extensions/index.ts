import register from '@client'

import { extensionApi } from './registry'

let loaded = false

/** Ilova ishga tushganda bir marta chaqiriladi. */
export function loadClientExtension() {
  if (loaded) return
  loaded = true
  register(extensionApi)
}
