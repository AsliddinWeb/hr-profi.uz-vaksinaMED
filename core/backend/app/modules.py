"""Core modullar ro'yxati. Mijoz `client.yaml -> modules` orqali yoqadi/o'chiradi."""

CORE_MODULES: dict[str, bool] = {
    "dashboard": True,
    "answers": True,  # Javob olish
    "org": True,  # Tashkiliy tuzilma
    "attendance": True,
    "face_id": True,
    "discipline": True,  # Tushuntirish xatlari, jarimalar
    "tasks": True,
    "reminders": True,
    "employees": True,
    "recruitment": True,
    "internship": True,
    "payroll": True,
    "canteen": True,  # Abet
    "pharmacy": True,  # Apteka tarmog'i
    "recruit": True,  # Nomzodlar va ish o'rinlari
    "checklists": True,  # Koordinator checklist
    "needs": True,  # Ehtiyojlar (so'rov -> ijrochi -> bajarish -> tasdiq)
    "logistics": True,
    "warehouse": True,
    "mobile_tracking": True,
    "reception": True,
    "it_desk": True,
    "calls": True,
    "ai": True,
    "migration": True,  # Eski tizimdan migratsiya
    "reports": True,  # Hisobotlar markazi
}
