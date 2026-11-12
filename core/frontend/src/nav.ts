import { Coffee, Video, Eye, FileWarning, MonitorPlay, PlayCircle, Activity, DatabaseZap, FileBarChart, Sparkles, PhoneCall, DoorOpen, LifeBuoy, BookUser, MonitorSmartphone, Radar, Smartphone, Warehouse as WarehouseIcon, Truck, Navigation, QrCode as QrIcon, MessageSquareQuote, Salad, UtensilsCrossed, Banknote, ReceiptText, GraduationCap, BookOpen, Briefcase, Users2, FileCheck2, LineChart, MapPinCheck, ClipboardList, PackagePlus, Tags, HeartPulse, MapPinned, UserPlus, ShieldCheck as QualityShield, AlarmClock, BarChart2, KanbanSquare, ListChecks, ListTodo, Gavel, Receipt, Scale, FileSignature, FileStack, ShieldQuestion, CalendarRange, Inbox, MessageSquareText, LayoutDashboard, BarChart3, ScanFace, ShieldAlert, ClipboardCheck, QrCode, Table2, UserCheck, Bell, CalendarDays, CalendarOff, Building2, Clock, Contact, Layers, Network, Repeat, ScrollText, ShieldCheck, Store, Users } from 'lucide-react'

import type { NavItem } from './extensions/registry'

/**
 * Core navigatsiyasi. Yangi faza tayyor bo'lganda shu yerga qo'shiladi (rolga qarab filtr F1 da).
 * `module` — backend modules ro'yxatidagi kalit (client.yaml orqali o'chirilishi mumkin).
 */
const baseNav: NavItem[] = [
  { id: 'checklist-status', group: 'checklists', label: { uz: 'Cheklist holati', ru: 'Статус чек-листов' }, to: '/checklists/status', icon: ClipboardCheck, anyPermission: ['checklists.own', 'checklists.read', 'checklists.manage'], module: 'checklists' },
  { id: 'company-settings', group: 'system', label: { uz: 'Kompaniya sozlamalari', ru: 'Настройки компании' }, to: '/settings/company', icon: Building2, anyPermission: ['org.manage'] },
  { id: 'devices', group: 'system', label: { uz: 'Qurilmalar', ru: 'Устройства' }, to: '/devices', icon: MonitorSmartphone, anyPermission: ['devices.read', 'devices.manage'] },
  { id: 'payroll-sheet', group: 'payroll', label: { uz: 'Oylik hisob', ru: 'Расчёт зарплаты' }, to: '/payroll/sheet', icon: Table2, permission: 'payroll.read', module: 'payroll' },
  { id: 'revisions', group: 'revision', label: { uz: 'Reviziya', ru: 'Ревизия' }, to: '/revisions', icon: ClipboardCheck, anyPermission: ['revision.own', 'revision.read', 'revision.manage'], module: 'pharmacy' },
  { id: 'ratings', group: 'pharmacy', label: { uz: 'Mijozlar baholashi', ru: 'Оценки клиентов' }, to: '/ratings', icon: MessageSquareQuote, anyPermission: ['ratings.own', 'ratings.read', 'ratings.manage'], module: 'pharmacy' },
  { id: 'home', group: 'main', label: { uz: 'Bosh sahifa', ru: 'Главная' }, to: '/', icon: LayoutDashboard },
  { id: 'help', group: 'main', label: { uz: 'Jarayonlar qo\'llanmasi', ru: 'Справочник процессов' }, to: '/help', icon: BookOpen },
  { id: 'my-documents', group: 'people', label: { uz: 'Mening hujjatlarim', ru: 'Мои документы' }, to: '/my-documents', icon: FileSignature },
  { id: 'employees', group: 'people', label: { uz: 'Xodimlar', ru: 'Сотрудники' }, to: '/employees', icon: Contact, permission: 'employees.read', module: 'employees' },
  { id: 'org', group: 'hr', sub: 'structure', label: { uz: 'Tashkiliy tuzilma', ru: 'Оргструктура' }, to: '/org', icon: Network, permission: 'org.read', module: 'org' },
  { id: 'departments', group: 'hr', sub: 'structure', label: { uz: "Bo'limlar va lavozimlar", ru: 'Отделы и должности' }, to: '/org/departments', icon: Building2, permission: 'org.read', module: 'org' },
  { id: 'positions', group: 'hr', sub: 'structure', label: { uz: 'Lavozimlar', ru: 'Должности' }, to: '/org/positions', icon: Briefcase, permission: 'org.read', module: 'org' },
  { id: 'position-duties', group: 'hr', sub: 'structure', label: { uz: 'Lavozim vazifalari', ru: 'Обязанности должностей' }, to: '/org/duties', icon: ClipboardList, permission: 'org.read', module: 'org' },
  { id: 'org-structures', group: 'hr', sub: 'structure', label: { uz: 'Shajara turlari', ru: 'Варианты оргструктуры' }, to: '/org/structures', icon: Network, permission: 'org.manage', module: 'org' },
  { id: 'branches', group: 'hr', sub: 'structure', label: { uz: 'Filiallar', ru: 'Филиалы' }, to: '/branches', icon: Store, permission: 'branches.read', module: 'pharmacy' },
  { id: 'hr-library', group: 'hr', sub: 'kadrdocs', label: { uz: 'Hujjatlar kutubxonasi', ru: 'Библиотека документов' }, to: '/hr/library', icon: BookOpen, permission: 'hrdocs.read', module: 'employees' },
  { id: 'hr-documents', group: 'hr', sub: 'kadrdocs', label: { uz: 'Ariza va buyruqlar', ru: 'Заявления и приказы' }, to: '/hr/documents', icon: FileStack, anyPermission: ['staffdocs.apply', 'staffdocs.read', 'staffdocs.manage'], module: 'employees' },
  { id: 'hr-references', group: 'hr', sub: 'kadrdocs', label: { uz: "Ma'lumotnomalar", ru: 'Справки' }, to: '/hr/references', icon: FileCheck2, permission: 'staffdocs.manage', module: 'employees' },
  { id: 'kadr', group: 'hr', sub: 'kadrdocs', label: { uz: 'Kadrovik', ru: 'Кадровик' }, to: '/kadr', icon: FileCheck2, permission: 'employees.documents', module: 'employees' },
  { id: 'recruit-dashboard', group: 'hr', sub: 'recruit', label: { uz: 'Rekruting dashboardi', ru: 'Дашборд подбора' }, to: '/recruit/dashboard', icon: LayoutDashboard, anyPermission: ['recruit.read', 'recruit.manage', 'recruit.approve', 'org.read', 'org.manage'], module: 'recruit' },
  { id: 'competencies', group: 'hr', sub: 'recruit', label: { uz: 'Kompetensiyalar bazasi', ru: 'База компетенций' }, to: '/recruit/competencies', icon: ListChecks, anyPermission: ['recruit.read', 'recruit.manage', 'recruit.approve', 'org.read', 'org.manage'], module: 'recruit' },
  { id: 'position-profiles', group: 'hr', sub: 'recruit', label: { uz: 'Lavozim profillari', ru: 'Профили должностей' }, to: '/recruit/profiles', icon: FileCheck2, anyPermission: ['recruit.read', 'recruit.manage', 'recruit.approve', 'org.read', 'org.manage'], module: 'recruit' },
  { id: 'recruit-approvals', group: 'hr', sub: 'recruit', label: { uz: 'Tasdiqlash markazi', ru: 'Центр согласования' }, to: '/recruit/approvals', icon: ShieldCheck, anyPermission: ['recruit.read', 'recruit.manage', 'recruit.approve', 'org.read', 'org.manage'], module: 'recruit' },
  { id: 'recruit-requests', group: 'hr', sub: 'recruit', label: { uz: 'Zayafkalar', ru: 'Заявки' }, to: '/recruit/requests', icon: ClipboardList, anyPermission: ['recruit.read', 'recruit.manage', 'recruit.approve', 'org.read'], module: 'recruit' },
  { id: 'recruit-vacancies', group: 'hr', sub: 'recruit', label: { uz: 'Vakansiyalar', ru: 'Вакансии' }, to: '/recruit/vacancies', icon: Briefcase, permission: 'recruit.read', module: 'recruit' },
  { id: 'recruit-candidates', group: 'hr', sub: 'recruit', label: { uz: 'Nomzodlar bazasi', ru: 'База кандидатов' }, to: '/recruit/candidates', icon: Users2, permission: 'recruit.read', module: 'recruit' },
  { id: 'recruit-requirements', group: 'hr', sub: 'recruit', label: { uz: 'Kompetensiyalar', ru: 'Компетенции' }, to: '/recruit/requirements', icon: ListChecks, anyPermission: ['recruit.read', 'recruit.manage'], module: 'recruit' },
  { id: 'recruit-recruiter', group: 'hr', sub: 'recruit', label: { uz: 'Rekruter paneli', ru: 'Панель рекрутера' }, to: '/recruit/recruiter', icon: PhoneCall, anyPermission: ['recruit.read', 'recruit.manage'], module: 'recruit' },
  { id: 'recruit-funnel', group: 'hr', sub: 'recruit', label: { uz: 'Voronka hisoboti', ru: 'Отчёт воронки' }, to: '/recruit/funnel', icon: BarChart2, anyPermission: ['recruit.read', 'recruit.manage'], module: 'recruit' },
  { id: 'recruit-compare', group: 'hr', sub: 'recruit', label: { uz: 'Rezyume solishtirish', ru: 'Сравнение резюме' }, to: '/recruit/compare', icon: KanbanSquare, anyPermission: ['recruit.read', 'recruit.manage'], module: 'recruit' },
  { id: 'preboarding', group: 'hr', sub: 'preboarding', label: { uz: 'Prebording darslari', ru: 'Уроки пребординга' }, to: '/preboarding', icon: MonitorPlay, anyPermission: ['internship.read', 'internship.manage'], module: 'internship' },
  { id: 'preboarding-my', group: 'hr', sub: 'preboarding', label: { uz: 'Mening prebordingim', ru: 'Мой пребординг' }, to: '/preboarding/my', icon: PlayCircle, permission: 'internship.own', module: 'internship' },
  { id: 'internship', group: 'hr', sub: 'preboarding', label: { uz: 'Stajirovka', ru: 'Стажировка' }, to: '/internship', icon: GraduationCap, anyPermission: ['internship.own', 'internship.read', 'internship.manage'], module: 'internship' },
  { id: 'conferences', group: 'hr', sub: 'preboarding', label: { uz: 'Onlayn darslar', ru: 'Онлайн-занятия' }, to: '/conferences', icon: Video, anyPermission: ['conference.own', 'conference.read', 'conference.manage'], module: 'internship' },
  { id: 'internship-classes', group: 'hr', sub: 'preboarding', label: { uz: 'Oflayn darslar', ru: 'Офлайн-занятия' }, to: '/internship/classes', icon: CalendarRange, anyPermission: ['internship.own', 'internship.read', 'internship.manage'], module: 'internship' },
  { id: 'attestation', group: 'hr', sub: 'preboarding', label: { uz: 'Attestatsiya', ru: 'Аттестация' }, to: '/attestation', icon: ClipboardCheck, anyPermission: ['attestation.own', 'attestation.read', 'attestation.manage'], module: 'internship' },
  { id: 'internship-programs', group: 'hr', sub: 'preboarding', label: { uz: 'Stajirovka dasturlari', ru: 'Программы стажировки' }, to: '/internship/programs', icon: BookOpen, anyPermission: ['internship.own', 'internship.read', 'internship.manage'], module: 'internship' },
  { id: 'career', group: 'hr', sub: 'growth', label: { uz: "O'sish", ru: 'Рост' }, to: '/career', icon: LineChart, anyPermission: ['career.read', 'career.propose', 'career.manage'], module: 'internship' },
  { id: 'performance', group: 'hr', sub: 'growth', label: { uz: "Yig'ma baho", ru: 'Сводная оценка' }, to: '/performance', icon: BarChart3, anyPermission: ['performance.read', 'performance.own'], module: 'internship' },
  { id: 'retention', group: 'hr', sub: 'preboarding', label: { uz: 'Ushlab qolish', ru: 'Удержание' }, to: '/retention', icon: HeartPulse, anyPermission: ['retention.report', 'retention.manage', 'retention.read', 'retention.audit'], module: 'internship' },
  { id: 'offboarding', group: 'hr', sub: 'preboarding', label: { uz: 'Offboarding', ru: 'Оффбординг' }, to: '/offboarding', icon: DoorOpen, anyPermission: ['retention.manage', 'retention.read', 'retention.audit'], module: 'internship' },
  { id: 'control', group: 'hr', sub: 'growth', label: { uz: 'Nazorat', ru: 'Контроль' }, to: '/control', icon: ShieldAlert, permission: 'control.read', module: 'internship' },
  { id: 'schedule', group: 'schedule', label: { uz: 'Ish grafigi', ru: 'График работы' }, to: '/schedule', icon: CalendarDays, permission: 'schedule.read', module: 'attendance' },
  { id: 'shifts', group: 'schedule', label: { uz: 'Smena turlari', ru: 'Виды смен' }, to: '/schedule/shifts', icon: Clock, permission: 'schedule.read', module: 'attendance' },
  { id: 'work-groups', group: 'schedule', label: { uz: 'Ish guruhlari', ru: 'Рабочие группы' }, to: '/schedule/groups', icon: Layers, permission: 'schedule.read', module: 'attendance' },
  { id: 'patterns', group: 'schedule', label: { uz: 'Grafik shablonlari', ru: 'Шаблоны графика' }, to: '/schedule/patterns', icon: Repeat, permission: 'schedule.read', module: 'attendance' },
  { id: 'holidays', group: 'schedule', label: { uz: 'Bayramlar', ru: 'Праздники' }, to: '/schedule/holidays', icon: CalendarOff, permission: 'schedule.read', module: 'attendance' },
  { id: 'rotations', group: 'schedule', label: { uz: 'Rotatsiya', ru: 'Ротация' }, to: '/org/rotations', icon: Repeat, anyPermission: ['rotations.read', 'rotations.request', 'rotations.manage'], module: 'org' },
  { id: 'my-attendance', group: 'attendance', label: { uz: 'Mening davomatim', ru: 'Моя посещаемость' }, to: '/attendance', icon: UserCheck, permission: 'attendance.punch', module: 'attendance' },
  { id: 'attendance-dashboard', group: 'attendance', label: { uz: 'Davomat tahlili', ru: 'Аналитика посещаемости' }, to: '/attendance/dashboard', icon: LayoutDashboard, permission: 'attendance.read', module: 'attendance' },
  { id: 'attendance-daily', group: 'attendance', label: { uz: 'Kunlik davomat', ru: 'Посещаемость за день' }, to: '/attendance/daily', icon: ClipboardCheck, permission: 'attendance.read', module: 'attendance' },
  { id: 'timesheet', group: 'attendance', label: { uz: 'Tabel', ru: 'Табель' }, to: '/attendance/timesheet', icon: Table2, permission: 'attendance.read', module: 'attendance' },
  { id: 'coord-report', group: 'attendance', label: { uz: 'Koordinator hisoboti', ru: 'Отчёт координатора' }, to: '/attendance/coordinator-report', icon: ClipboardCheck, anyPermission: ['attendance.edit', 'attendance.read', 'answers.decide'], module: 'attendance' },
  { id: 'attendance-issues', group: 'attendance', label: { uz: 'Davomat muammolari', ru: 'Проблемы с отметками' }, to: '/attendance/issues', icon: FileWarning, anyPermission: ['attendance.punch', 'attendance.edit', 'attendance.read', 'answers.decide'], module: 'attendance' },
  { id: 'attendance-qr', group: 'attendance', label: { uz: 'Filial QR kodi', ru: 'QR-код филиала' }, to: '/attendance/qr', icon: QrCode, permission: 'attendance.qr', module: 'attendance' },
  { id: 'face-id', group: 'attendance', label: { uz: 'Face ID', ru: 'Face ID' }, to: '/face', icon: ScanFace, permission: 'face.enroll', module: 'face_id' },
  { id: 'face-admin', group: 'attendance', label: { uz: 'Face ID boshqaruvi', ru: 'Управление Face ID' }, to: '/face/admin', icon: ShieldAlert, permission: 'face.read', module: 'face_id' },
  { id: 'face-eval', group: 'attendance', label: { uz: 'Face ID sifati', ru: 'Качество Face ID' }, to: '/face/evaluation', icon: BarChart3, permission: 'face.evaluate', module: 'face_id' },
  { id: 'my-answers', group: 'requests', label: { uz: "Mening so'rovlarim", ru: 'Мои заявки' }, to: '/answers', icon: MessageSquareText, permission: 'answers.request', module: 'answers' },
  { id: 'answers-inbox', group: 'requests', label: { uz: "Qaror kutayotganlar", ru: 'Ожидают решения' }, to: '/answers/inbox', icon: Inbox, anyPermission: ['answers.decide', 'answers.read'], module: 'answers' },
  { id: 'answers-calendar', group: 'requests', label: { uz: "So'rovlar kalendari", ru: 'Календарь заявок' }, to: '/answers/calendar', icon: CalendarRange, anyPermission: ['answers.request', 'answers.read'], module: 'answers' },
  { id: 'answers-status', group: 'requests', label: { uz: 'Javob olish holati', ru: 'Статус заявок' }, to: '/answers/holat', icon: Eye, anyPermission: ['answers.read', 'answers.decide'], module: 'answers' },
  { id: 'complaints', group: 'requests', label: { uz: 'Shikoyat va murojaatlar', ru: 'Жалобы и обращения' }, to: '/complaints', icon: MessageSquareQuote, anyPermission: ['complaints.own', 'complaints.manage'], module: 'employees' },
  { id: 'letters', group: 'requests', label: { uz: 'Tushuntirish xatlari', ru: 'Объяснительные' }, to: '/letters', icon: FileSignature, anyPermission: ['letters.own', 'letters.issue', 'letters.read', 'letters.manage'], module: 'discipline' },
  { id: 'letter-templates', group: 'requests', label: { uz: 'Xat shablonlari', ru: 'Шаблоны писем' }, to: '/letters/templates', icon: FileStack, permission: 'letters.manage', module: 'discipline' },
  { id: 'verify', group: 'requests', label: { uz: 'Hujjatni tekshirish', ru: 'Проверка документа' }, to: '/verify', icon: ShieldQuestion, module: 'discipline' },
  { id: 'penalties', group: 'requests', label: { uz: 'Jarimalar', ru: 'Штрафы' }, to: '/penalties', icon: Gavel, anyPermission: ['penalties.own', 'penalties.read', 'penalties.approve', 'penalties.manage'], module: 'discipline' },
  { id: 'penalty-rules', group: 'requests', label: { uz: 'Jarima qoidalari', ru: 'Правила штрафов' }, to: '/penalties/rules', icon: Scale, anyPermission: ['penalties.read', 'penalties.approve', 'penalties.manage'], module: 'discipline' },
  { id: 'penalty-report', group: 'requests', label: { uz: 'Jarima hisoboti', ru: 'Отчёт по штрафам' }, to: '/penalties/report', icon: Receipt, anyPermission: ['penalties.read', 'penalties.approve', 'penalties.manage'], module: 'discipline' },
  { id: 'tasks-board', group: 'tasks', label: { uz: 'Kanban doska', ru: 'Канбан-доска' }, to: '/tasks/board', icon: KanbanSquare, anyPermission: ['tasks.own', 'tasks.read', 'tasks.manage'], module: 'tasks' },
  { id: 'tasks-list', group: 'tasks', label: { uz: "Topshiriqlar ro'yxati", ru: 'Список поручений' }, to: '/tasks', icon: ListTodo, anyPermission: ['tasks.own', 'tasks.read', 'tasks.manage'], module: 'tasks' },
  { id: 'tasks-analytics', group: 'tasks', label: { uz: 'Topshiriq tahlili', ru: 'Аналитика поручений' }, to: '/tasks/analytics', icon: BarChart2, anyPermission: ['tasks.own', 'tasks.read', 'tasks.manage'], module: 'tasks' },
  { id: 'tasks-templates', group: 'tasks', label: { uz: 'Topshiriq shablonlari', ru: 'Шаблоны поручений' }, to: '/tasks/templates', icon: ListChecks, anyPermission: ['tasks.own', 'tasks.read', 'tasks.manage'], module: 'tasks' },
  { id: 'reminders', group: 'tasks', label: { uz: 'Eslatmalar', ru: 'Напоминания' }, to: '/reminders', icon: AlarmClock, anyPermission: ['reminders.own', 'reminders.assign'], module: 'reminders' },
  { id: 'mobile', group: 'mobile', label: { uz: "Jonli kuzatuv", ru: 'Живое отслеживание' }, to: '/mobile', icon: Radar, anyPermission: ['mobile.read', 'mobile.manage'], module: 'mobile_tracking' },
  { id: 'mobile-my', group: 'mobile', label: { uz: 'Mening ish kunim', ru: 'Мой рабочий день' }, to: '/mobile/my', icon: Smartphone, permission: 'mobile.own', module: 'mobile_tracking' },
  { id: 'migration', group: 'migration', label: { uz: 'Eski tizimdan migratsiya', ru: 'Миграция из старой системы' }, to: '/migration', icon: DatabaseZap, permission: 'migration.manage', module: 'migration' },
  { id: 'reports', group: 'reports', label: { uz: 'Hisobotlar markazi', ru: 'Центр отчётов' }, to: '/reports', icon: FileBarChart, anyPermission: ['reports.read', 'reports.manage'], module: 'reports' },
  { id: 'ai-usage', group: 'ai', label: { uz: 'AI foydalanish', ru: 'Использование AI' }, to: '/ai/usage', icon: Sparkles, permission: 'ai.manage', module: 'ai' },
  { id: 'calls', group: 'calls', label: { uz: "Qo'ng'iroqlar", ru: 'Звонки' }, to: '/calls', icon: PhoneCall, anyPermission: ['calls.own', 'calls.read', 'calls.manage'], module: 'calls' },
  { id: 'reception-panel', group: 'reception', label: { uz: 'Resepshin', ru: 'Ресепшн' }, to: '/reception/panel', icon: LayoutDashboard },
  { id: 'coffee', group: 'reception', label: { uz: 'Kofe-ledi', ru: 'Кофе-леди' }, to: '/reception/coffee', icon: Coffee },
  { id: 'reception', group: 'reception', label: { uz: 'Mehmonlar', ru: 'Гости' }, to: '/reception', icon: DoorOpen, anyPermission: ['reception.own', 'reception.desk', 'reception.read'], module: 'reception' },
  { id: 'reception-new', group: 'reception', label: { uz: 'Mehmon qaydi', ru: 'Регистрация гостя' }, to: '/reception/new', icon: BookUser, anyPermission: ['reception.own', 'reception.desk', 'reception.read'], module: 'reception' },
  { id: 'reception-report', group: 'reception', label: { uz: 'Mehmonlar hisoboti', ru: 'Отчёт по гостям' }, to: '/reception/report', icon: BarChart2, anyPermission: ['reception.desk', 'reception.read'], module: 'reception' },
  { id: 'helpdesk', group: 'helpdesk', label: { uz: 'AyTi ticketlar', ru: 'ИТ-заявки' }, to: '/helpdesk', icon: LifeBuoy, anyPermission: ['helpdesk.own', 'helpdesk.work', 'helpdesk.read', 'helpdesk.manage'], module: 'it_desk' },
  { id: 'helpdesk-new', group: 'helpdesk', label: { uz: 'Yangi ticket', ru: 'Новая заявка' }, to: '/helpdesk/new', icon: MonitorSmartphone, anyPermission: ['helpdesk.own', 'helpdesk.work', 'helpdesk.read', 'helpdesk.manage'], module: 'it_desk' },
  { id: 'helpdesk-analytics', group: 'helpdesk', label: { uz: 'AyTi tahlili', ru: 'Аналитика ИТ' }, to: '/helpdesk/analytics', icon: BarChart2, anyPermission: ['helpdesk.work', 'helpdesk.read', 'helpdesk.manage'], module: 'it_desk' },
  { id: 'helpdesk-categories', group: 'helpdesk', label: { uz: 'Ticket kategoriyalari', ru: 'Категории заявок' }, to: '/helpdesk/categories', icon: Tags, permission: 'helpdesk.manage', module: 'it_desk' },
  { id: 'warehouse', group: 'warehouse', label: { uz: 'Ombor holati', ru: 'Состояние склада' }, to: '/warehouse', icon: WarehouseIcon, anyPermission: ['warehouse.read', 'warehouse.manage'], module: 'warehouse' },
  { id: 'logistics', group: 'logistics', label: { uz: 'Logistika', ru: 'Логистика' }, to: '/logistics', icon: Truck, anyPermission: ['logistics.read', 'logistics.manage'], module: 'logistics' },
  { id: 'logistics-my', group: 'logistics', label: { uz: 'Mening reysim', ru: 'Мой рейс' }, to: '/logistics/my', icon: Navigation, permission: 'logistics.own', module: 'logistics' },
  { id: 'canteen', group: 'canteen', label: { uz: 'Bugungi menyu', ru: 'Меню на сегодня' }, to: '/canteen', icon: UtensilsCrossed, anyPermission: ['canteen.own', 'canteen.read', 'canteen.manage'], module: 'canteen' },
  { id: 'canteen-menus', group: 'canteen', label: { uz: 'Menyular', ru: 'Меню' }, to: '/canteen/menus', icon: Salad, anyPermission: ['canteen.own', 'canteen.read', 'canteen.manage'], module: 'canteen' },
  { id: 'canteen-comments', group: 'canteen', label: { uz: 'Abet izohlari', ru: 'Отзывы о столовой' }, to: '/canteen/comments', icon: MessageSquareQuote, anyPermission: ['canteen.read', 'canteen.manage'], module: 'canteen' },
  { id: 'canteen-analytics', group: 'canteen', label: { uz: 'Abet tahlili', ru: 'Аналитика столовой' }, to: '/canteen/analytics', icon: BarChart2, anyPermission: ['canteen.read', 'canteen.manage'], module: 'canteen' },
  { id: 'canteen-qr', group: 'canteen', label: { uz: 'Abet QR kodi', ru: 'QR-код столовой' }, to: '/canteen/qr', icon: QrIcon, permission: 'canteen.manage', module: 'canteen' },
  { id: 'payroll', group: 'payroll', label: { uz: 'Ish haqi (oylik)', ru: 'Зарплата' }, to: '/payroll', icon: Banknote, permission: 'payroll.read', module: 'payroll' },
  { id: 'payroll-my', group: 'payroll', label: { uz: 'Mening varaqam', ru: 'Мой расчётный лист' }, to: '/payroll/my', icon: ReceiptText, permission: 'payroll.own', module: 'payroll' },
  { id: 'checklists', group: 'checklists', label: { uz: 'Filial tekshiruvlari', ru: 'Проверки филиалов' }, to: '/checklists', icon: MapPinCheck, anyPermission: ['checklists.own', 'checklists.read', 'checklists.manage'], module: 'checklists' },
  { id: 'checklists-report', group: 'checklists', label: { uz: 'Qamrov va reyting', ru: 'Охват и рейтинг' }, to: '/checklists/report', icon: LineChart, anyPermission: ['checklists.own', 'checklists.read', 'checklists.manage'], module: 'checklists' },
  { id: 'checklists-templates', group: 'checklists', label: { uz: 'Checklist shablonlari', ru: 'Шаблоны чек-листов' }, to: '/checklists/templates', icon: FileCheck2, anyPermission: ['checklists.own', 'checklists.read', 'checklists.manage'], module: 'checklists' },
  { id: 'duty-my', group: 'checklists', label: { uz: 'Mening chek-listim', ru: 'Мой чек-лист' }, to: '/checklists/my', icon: ListChecks, permission: 'duty.own', module: 'checklists' },
  { id: 'duty-control', group: 'checklists', label: { uz: 'Chek-list nazorati', ru: 'Контроль чек-листов' }, to: '/checklists/control', icon: ShieldCheck, anyPermission: ['duty.control', 'duty.read', 'duty.manage'], module: 'checklists' },
  { id: 'duty-templates', group: 'checklists', label: { uz: 'Lavozim chek-listlari', ru: 'Чек-листы должностей' }, to: '/checklists/duty', icon: ClipboardList, anyPermission: ['duty.read', 'duty.manage'], module: 'checklists' },
  { id: 'needs', group: 'needs', label: { uz: 'Ehtiyojlar', ru: 'Потребности' }, to: '/needs', icon: ClipboardList, anyPermission: ['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage'], module: 'needs' },
  { id: 'needs-new', group: 'needs', label: { uz: "Yangi so'rov", ru: 'Новая заявка' }, to: '/needs/new', icon: PackagePlus, anyPermission: ['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage'], module: 'needs' },
  { id: 'needs-analytics', group: 'needs', label: { uz: 'Ehtiyoj tahlili', ru: 'Аналитика потребностей' }, to: '/needs/analytics', icon: BarChart2, anyPermission: ['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage'], module: 'needs' },
  { id: 'needs-categories', group: 'needs', label: { uz: 'Ehtiyoj kategoriyalari', ru: 'Категории потребностей' }, to: '/needs/categories', icon: Tags, anyPermission: ['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage'], module: 'needs' },
  { id: 'pharmacy', group: 'pharmacy', label: { uz: "Tarmoq holati", ru: 'Состояние сети' }, to: '/pharmacy', icon: HeartPulse, anyPermission: ['pharmacy.read', 'pharmacy.own', 'pharmacy.manage'], module: 'pharmacy' },
  { id: 'pharmacy-map', group: 'pharmacy', label: { uz: 'Tarmoq xaritasi', ru: 'Карта сети' }, to: '/pharmacy/map', icon: MapPinned, anyPermission: ['pharmacy.read', 'pharmacy.own', 'pharmacy.manage'], module: 'pharmacy' },
  { id: 'pharmacy-needs', group: 'pharmacy', label: { uz: 'Xodim kerak', ru: 'Нужен сотрудник' }, to: '/pharmacy/needs', icon: UserPlus, anyPermission: ['pharmacy.read', 'pharmacy.own', 'pharmacy.manage'], module: 'pharmacy' },
  { id: 'pharmacy-quality', group: 'pharmacy', label: { uz: "Ma'lumot sifati", ru: 'Качество данных' }, to: '/pharmacy/quality', icon: QualityShield, anyPermission: ['pharmacy.read', 'pharmacy.manage'], module: 'pharmacy' },
  { id: 'users', group: 'admin', label: { uz: 'Foydalanuvchilar', ru: 'Пользователи' }, to: '/users', icon: Users, permission: 'users.read' },
  { id: 'roles', group: 'admin', label: { uz: 'Rollar va ruxsatlar', ru: 'Роли и права' }, to: '/roles', icon: ShieldCheck, permission: 'roles.read' },
  { id: 'audit', group: 'admin', label: { uz: 'Audit jurnali', ru: 'Журнал аудита' }, to: '/audit', icon: ScrollText, permission: 'audit.read' },
  { id: 'notifications', group: 'system', label: { uz: 'Bildirishnomalar', ru: 'Уведомления' }, to: '/notifications', icon: Bell },
  { id: 'integrations', group: 'system', label: { uz: 'Integratsiyalar', ru: 'Интеграции' }, to: '/integrations', icon: DatabaseZap, anyPermission: ['integrations.read', 'integrations.manage'], module: 'migration' },
  { id: 'plan', group: 'system', label: { uz: 'Tarif va litsenziya', ru: 'Тариф и лицензия' }, to: '/system/plan', icon: Tags, permission: 'roles.read' },
  { id: 'system', group: 'system', label: { uz: 'Tizim holati', ru: 'Состояние системы' }, to: '/system', icon: Activity },
]

/**
 * Bo'lim klasterlari: yon menyuda har klasterdan faqat birinchi ruxsatli band turadi,
 * qolganlari sahifa tepasida tab bo'lib chiqadi (ClusterTabs). tabs: false — sahifaning o'z tablari bor.
 */
export const NAV_CLUSTERS: { ids: string[]; tabs?: false }[] = [
  // Tuzilma: yon menyuda faqat Tashkiliy tuzilma, qolganlari uning o'ng panelida (ruxsati bo'lmasa — birinchi ruxsatli band ko'rinadi)
  { ids: ['org', 'departments', 'positions', 'position-duties', 'org-structures', 'branches'], tabs: false },
  { ids: ['reception-panel', 'reception', 'reception-new', 'reception-report', 'coffee', 'my-answers', 'answers-inbox'] },
]
export const clusterOf = new Map(NAV_CLUSTERS.flatMap((c) => c.ids.map((id) => [id, c] as const)))

/** Joriy yo'lga eng uzun mos keladigan band. */
export function matchNav<T extends { to: string }>(pathname: string, items: T[]): T | undefined {
  return items.filter((i) => pathname === i.to || pathname.startsWith(i.to === '/' ? '/__' : `${i.to}/`)).sort((a, b) => b.to.length - a.to.length)[0]
}

/** Klasterning ruxsatli birinchi bandi (yon menyuda shu turadi). */
export function clusterHead(id: string, allowed: Set<string>): string {
  return clusterOf.get(id)?.ids.find((x) => allowed.has(x)) ?? id
}

/** Yon menyu uchun: klasterdan faqat bosh band qoladi. */
export function collapseNav<T extends { id: string }>(items: T[]): T[] {
  const allowed = new Set(items.map((i) => i.id))
  return items.filter((i) => !clusterOf.has(i.id) || clusterHead(i.id, allowed) === i.id)
}

export const navById = new Map(baseNav.map((i) => [i.id, i]))
/** Keyin qo'shilgan bandlar (baseNav boshida): o'z guruhining oxiriga qo'yiladi, qolgan menyu asl tartibida. */
const ADDED = new Set(['checklist-status', 'company-settings', 'devices', 'payroll-sheet', 'revisions', 'ratings'])

/** Menyuda birinchi turadigan guruhlar: Bosh sahifa, HR, Resepshin; qolganlari keyin. */
const FIRST = ['main', 'people', 'hr', 'revision', 'reception']

/** Menyu asl holicha: guruhlar va bandlar baseNav tartibida, bir xil kichik bo'lim (sub) bandlari yonma-yon. */
function original(items: NavItem[]): NavItem[] {
  const g = (i: NavItem) => i.group ?? 'main'
  const groups = [...new Set([...FIRST, ...[...items.filter((i) => !ADDED.has(i.id)), ...items].map(g)])]
  return groups.flatMap((grp) => {
    const chunk = [...items.filter((i) => !ADDED.has(i.id) && g(i) === grp), ...items.filter((i) => ADDED.has(i.id) && g(i) === grp)]
    const subs = [...new Set(chunk.map((i) => i.sub ?? `#${i.id}`))]
    return subs.flatMap((k) => chunk.filter((i) => (i.sub ?? `#${i.id}`) === k))
  })
}

export const coreNav: NavItem[] = original(baseNav).filter((i) => i.id !== 'help')
