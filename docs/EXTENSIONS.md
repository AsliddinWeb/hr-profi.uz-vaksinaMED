# Mijoz extension tizimi

Mijozga xos kod core'ga **tegmasdan** `clients/<nom>/` ichida yashaydi. Core yangilanganda extension o'zgarishsiz qoladi.

```
clients/acme/
  client.yaml          sozlamalar (CLIENT-YAML.md)
  backend_ext/         __init__.py: setup(ctx), setup_worker(registry)
  frontend_ext/        index.tsx: export default register(api)
  migrations/          faqat shu mijozning jadvallari (client_*)
```

Ishlaydigan namuna: `clients/example/` (router, hodisa, worker vazifa, slot, `client_note` jadvali). Yangi mijoz esa toza `clients/_template/` dan yaratiladi.

## Backend: `backend_ext/__init__.py`

```python
def setup(ctx):               # ilova ishga tushganda (ctx.app, ctx.config, ctx.events)
    router = APIRouter(prefix="/acme", tags=["client:acme"])

    @router.get("/hello")
    async def hello(): return {"client": ctx.config.name}

    ctx.app.include_router(router, prefix="/api")         # -> /api/acme/hello
    ctx.events.on("employee.created", on_employee_created)

def setup_worker(registry):   # worker ishga tushganda (ixtiyoriy)
    registry.functions.append(my_job)                      # arq vazifasi
    registry.cron_jobs.append(cron(my_job, hour={8}, minute={0}))
```

- Core modullarini import qilish mumkin (`from app.deps import get_auth`, `from app.db import SessionLocal`...), lekin ichki tuzilmasiga ortiqcha bog'lanmang: ommaviy API — quyidagi hodisalar va HTTP endpointlar.
- Himoyalangan endpoint uchun `Depends(get_auth)` va ruxsat tekshiruvi (`app.rbac.matches(auth.permissions, "x.y")`) ishlating; o'z ruxsatlaringizni `app.permissions.register_permission` bilan ro'yxatdan o'tkazing.
- Extension xatosi core'ni to'xtatmaydi: hodisa ishlovchisidagi istisno logga yoziladi, `setup` xatosi esa ishga tushishda ko'rinadi — uni `make logs` da kuzating.

### Hodisalar (`ctx.events.on(nom, handler)`)

Handler sinxron yoki `async` bo'lishi mumkin va faqat **kalit so'zli** argumentlar oladi (qolganini `**_` bilan yutib yuboring: kelajakda maydon qo'shilishi mumkin). Hodisa amal bazaga **saqlangandan keyin** chiqadi.

| Hodisa | Argumentlar |
|---|---|
| `employee.created` | `employee_id`, `employee_no`, `full_name` (qo'lda va nomzod → xodim orqali) |
| `employee.dismissed` | `employee_id`, `full_name`, `date`, `reason` |
| `ticket.created` | `ticket_id`, `number`, `priority`, `title` |

Yangi hodisa kerak bo'lsa, core'da `request.app.state.events.emit("nom", **payload)` qo'shiladi va shu jadvalga yoziladi.

## Frontend: `frontend_ext/index.tsx`

```tsx
import type { ExtensionApi } from '@core/extensions/registry'
export default function register(api: ExtensionApi) {
  api.addRoute({ path: 'acme/report', element: <AcmeReport /> })
  api.addNavItem({ id: 'acme-report', group: 'admin', label: { uz: 'Acme hisobot', ru: 'Отчёт Acme' }, to: '/acme/report', permission: 'reports.read' })
  api.slot('status.after', AcmeWidget)
}
```

- Faqat `@core/*` dan import qiling. Slot nomlari: `status.after` (tizim holati sahifasi oxiri).
- `addNavItem` dagi `module`/`permission`/`anyPermission` core menyusidagi kabi ishlaydi.
- CRUD qoidasi: yaratish/tahrirlash **alohida sahifa (route)** bo'lsin, modal emas.

## Migratsiyalar

Mijoz jadvallari core'dan **alohida alembic branch** va alohida versiya jadvalida (`alembic_version_ext`) yuradi, shuning uchun core migratsiyalari bilan to'qnashmaydi.

1. `clients/acme/migrations/versions/0001_xxx.py` yarating (namuna: `clients/example/migrations/versions/0001_example_note.py`).
2. `revision = "ext0001"` (har doim `ext` bilan), `down_revision = None` (birinchisi), keyingisi `ext0002` ← `ext0001`.
3. Jadval nomi **`client_` bilan boshlansin**; core jadvallarini o'zgartirmang (foreign key berish mumkin, lekin core jadvalini `ALTER` qilmang).
4. Qo'llash: `make migrate` (yoki `make up` — api har startda core, keyin mijoz migratsiyalarini qo'llaydi).

`make validate-client` revision nomi va jadval prefiksini tekshiradi.
