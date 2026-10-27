// __NAME__ mijoz frontend extension. Faqat `@core/*` dan import qiling.
import type { ExtensionApi } from '@core/extensions/registry'

export default function register(api: ExtensionApi) {
  // Misollar (docs/EXTENSIONS.md):
  //   api.addRoute({ path: 'my-page', element: <MyPage /> })
  //   api.addNavItem({ id: 'my-page', label: { uz: 'Mening sahifam', ru: 'Моя страница' }, to: '/my-page' })
  //   api.slot('status.after', MyWidget)
  void api
}
