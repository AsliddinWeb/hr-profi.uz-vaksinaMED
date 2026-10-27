# __NAME__

Mijoz papkasi (HR-Profi). Hujjatlar: `docs/NEW-CLIENT.md`, `docs/EXTENSIONS.md`, `docs/BACKUP.md`, `docs/UPGRADE.md`.

- `client.yaml` — brend, modullar, sozlamalar (tekshirish: `make validate-client CLIENT=__NAME__`)
- `backend_ext/` — qo'shimcha router, hodisalar, worker vazifalari
- `frontend_ext/` — sahifa, menyu, slot
- `migrations/` — faqat shu mijozning jadvallari (`client_*`), alohida versiya jadvali `alembic_version_ext`
