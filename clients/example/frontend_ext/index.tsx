// Namuna mijoz frontend extension. Faqat `@core/*` dan import qiling.
import type { ExtensionApi } from '@core/extensions/registry'

export default function register(api: ExtensionApi) {
  // Core sahifadagi "slot" ga komponent qo'shish
  api.slot('status.after', () => (
    <div className="rounded-card border border-dashed border-border p-4 text-sm text-muted">
      Mijoz extension slot: bu blok <code>clients/example/frontend_ext</code> dan keldi.
    </div>
  ))
}
