import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { getExtensionRoutes } from './extensions/registry'
import { DashboardPage } from './features/attendance/DashboardPage'
import { DailyPage } from './features/attendance/DailyPage'
import { EmployeeAttendancePage } from './features/attendance/EmployeeAttendancePage'
import { MyAttendancePage } from './features/attendance/MyAttendancePage'
import { QrDisplayPage } from './features/attendance/QrDisplayPage'
import { QrPunchPage } from './features/attendance/QrPunchPage'
import { RecordFormPage } from './features/attendance/RecordFormPage'
import { TimesheetPage } from './features/attendance/TimesheetPage'
import { CoordReportPage } from './features/attendance/coord/CoordReportPage'
import { IssueDetailPage } from './features/attendance/issues/IssueDetailPage'
import { IssueFormPage as AttendanceIssueFormPage } from './features/attendance/issues/IssueFormPage'
import { IssuesPage } from './features/attendance/issues/IssuesPage'
import { AdminDetailPage } from './features/face/AdminDetailPage'
import { AdminPage } from './features/face/AdminPage'
import { ConsentPage } from './features/face/ConsentPage'
import { EnrollPage } from './features/face/EnrollPage'
import { EvaluationPage } from './features/face/EvaluationPage'
import { FacePunchPage } from './features/face/FacePunchPage'
import { MyFacePage } from './features/face/MyFacePage'
import { CalendarPage } from './features/answers/CalendarPage'
import { InboxPage } from './features/answers/InboxPage'
import { AnswersStatusPage } from './features/answers/StatusPage'
import { MyRequestsPage } from './features/answers/MyRequestsPage'
import { RequestDetailPage } from './features/answers/RequestDetailPage'
import { RequestFormPage } from './features/answers/RequestFormPage'
import { IssueFormPage } from './features/letters/IssueFormPage'
import { LetterDetailPage } from './features/letters/LetterDetailPage'
import { LettersPage } from './features/letters/LettersPage'
import { ScanPage } from './features/letters/ScanPage'
import { TemplateFormPage } from './features/letters/TemplateFormPage'
import { TemplatesPage } from './features/letters/TemplatesPage'
import { VerifyPage } from './features/letters/VerifyPage'
import { WritePage } from './features/letters/WritePage'
import { ManualFormPage } from './features/penalties/ManualFormPage'
import { PenaltiesPage } from './features/penalties/PenaltiesPage'
import { PenaltyDetailPage } from './features/penalties/PenaltyDetailPage'
import { ReportPage } from './features/penalties/ReportPage'
import { RuleVersionPage, RulesFormPage } from './features/penalties/RulesFormPage'
import { RulesPage } from './features/penalties/RulesPage'
import { ScanPage as PenaltyScanPage } from './features/penalties/ScanPage'
import { AnalyticsPage } from './features/tasks/AnalyticsPage'
import { BoardPage } from './features/tasks/BoardPage'
import { CalendarPage as TaskCalendarPage } from './features/tasks/CalendarPage'
import { DetailPage as TaskDetailPage } from './features/tasks/DetailPage'
import { FormPage as TaskFormPage } from './features/tasks/FormPage'
import { ListPage as TaskListPage } from './features/tasks/ListPage'
import { TemplateFormPage as TaskTemplateFormPage, TemplatesPage as TaskTemplatesPage } from './features/tasks/TemplatesPage'
import { EventsPage as MobileEventsPage } from './features/mobile/EventsPage'
import { LivePage as MobileLivePage } from './features/mobile/LivePage'
import { MyPage as MobileMyPage } from './features/mobile/MyPage'
import { PermitFormPage } from './features/mobile/PermitFormPage'
import { PermitsPage } from './features/mobile/PermitsPage'
import { SessionDetailPage } from './features/mobile/SessionDetailPage'
import { SessionsPage as MobileSessionsPage } from './features/mobile/SessionsPage'
import { ControlPage } from './features/warehouse/ControlPage'
import { DetailPage as WarehouseDetailPage } from './features/warehouse/DetailPage'
import { StaffAddPage } from './features/warehouse/StaffAddPage'
import { StatusPage as WarehouseStatusPage } from './features/warehouse/StatusPage'
import { WarehouseFormPage } from './features/warehouse/WarehouseFormPage'
import { WarehousesPage } from './features/warehouse/WarehousesPage'
import { DocumentFormPage as VehicleDocFormPage } from './features/logistics/DocumentFormPage'
import { DriverFormPage } from './features/logistics/DriverFormPage'
import { DriversPage } from './features/logistics/DriversPage'
import { FuelFormPage } from './features/logistics/FuelFormPage'
import { FuelPage } from './features/logistics/FuelPage'
import { LivePage } from './features/logistics/LivePage'
import { MyPage } from './features/logistics/MyPage'
import { ReportsPage as LogisticsReportsPage } from './features/logistics/ReportsPage'
import { TripDetailPage } from './features/logistics/TripDetailPage'
import { TripFormPage } from './features/logistics/TripFormPage'
import { TripsPage } from './features/logistics/TripsPage'
import { VehicleDetailPage } from './features/logistics/VehicleDetailPage'
import { VehicleFormPage } from './features/logistics/VehicleFormPage'
import { VehiclesPage } from './features/logistics/VehiclesPage'
import { AnalyticsPage as CanteenAnalyticsPage } from './features/canteen/AnalyticsPage'
import { CommentsPage } from './features/canteen/CommentsPage'
import { MenuFormPage } from './features/canteen/MenuFormPage'
import { MenuPage } from './features/canteen/MenuPage'
import { MenusPage } from './features/canteen/MenusPage'
import { QrPage } from './features/canteen/QrPage'
import { SettingsPage as CanteenSettingsPage } from './features/canteen/SettingsPage'
import { ItemFormPage } from './features/payroll/ItemFormPage'
import { ItemsImportPage } from './features/payroll/ItemsImportPage'
import { ItemsPage } from './features/payroll/ItemsPage'
import { LinePage } from './features/payroll/LinePage'
import { MyPayslipPage, MyPayslipsPage } from './features/payroll/MyPayslipsPage'
import { RunDetailPage } from './features/payroll/RunDetailPage'
import { RunFormPage } from './features/payroll/RunFormPage'
import { RunsPage } from './features/payroll/RunsPage'
import { SchemeFormPage } from './features/payroll/SchemeFormPage'
import { SchemesPage } from './features/payroll/SchemesPage'
import { ClassDetailPage, ClassFormPage, ClassesPage } from './features/internship/ClassesPage'
import { KadrPage } from './features/internship/KadrPage'
import { EnrollmentPage } from './features/internship/EnrollmentPage'
import { EnrollmentsPage } from './features/internship/EnrollmentsPage'
import { EnrollPage as InternEnrollPage } from './features/internship/EnrollPage'
import { LearnPage } from './features/internship/LearnPage'
import { ProgramDetailPage } from './features/internship/ProgramDetailPage'
import { ProgramFormPage } from './features/internship/ProgramFormPage'
import { ProgramsPage } from './features/internship/ProgramsPage'
import { StepFormPage } from './features/internship/StepFormPage'
import { ApplicationDetailPage } from './features/recruit/ApplicationDetailPage'
import { ApplicationNewPage } from './features/recruit/ApplicationNewPage'
import { ApplicationsPage } from './features/recruit/ApplicationsPage'
import { CandidateDetailPage } from './features/recruit/CandidateDetailPage'
import { CandidateFormPage } from './features/recruit/CandidateFormPage'
import { CandidatesPage } from './features/recruit/CandidatesPage'
import { HirePage } from './features/recruit/HirePage'
import { SummaryPage as RecruitSummaryPage } from './features/recruit/SummaryPage'
import { VacanciesPage } from './features/recruit/VacanciesPage'
import { VacancyDetailPage } from './features/recruit/VacancyDetailPage'
import { VacancyFormPage } from './features/recruit/VacancyFormPage'
import { DetailPage as CheckDetailPage } from './features/checklists/DetailPage'
import { FillPage as CheckFillPage } from './features/checklists/FillPage'
import { ListPage as CheckListPage } from './features/checklists/ListPage'
import { NewPage as CheckNewPage } from './features/checklists/NewPage'
import { ReportPage as CheckReportPage } from './features/checklists/ReportPage'
import { TemplateFormPage as CheckTemplateFormPage } from './features/checklists/TemplateFormPage'
import { TemplatesPage as CheckTemplatesPage } from './features/checklists/TemplatesPage'
import { SearchPage } from './features/ai/SearchPage'
import { SettingsPage as AiSettingsPage } from './features/ai/SettingsPage'
import { UsagePage as AiUsagePage } from './features/ai/UsagePage'
import { BatchesPage as MigBatchesPage } from './features/migration/BatchesPage'
import { BatchPage as MigBatchPage } from './features/migration/BatchPage'
import { CheckFormPage as MigCheckFormPage } from './features/migration/CheckFormPage'
import { NewImportPage as MigNewImportPage } from './features/migration/NewImportPage'
import { ReconcilePage as MigReconcilePage } from './features/migration/ReconcilePage'
import { TemplateFormPage as MigTemplateFormPage } from './features/migration/TemplateFormPage'
import { TemplatesPage as MigTemplatesPage } from './features/migration/TemplatesPage'
import { HistoryPage as ReportHistoryPage } from './features/reports/HistoryPage'
import { ReportsPage } from './features/reports/ReportsPage'
import { ScheduleFormPage } from './features/reports/ScheduleFormPage'
import { SchedulesPage } from './features/reports/SchedulesPage'
import { FormPage as CallFormPage } from './features/calls/FormPage'
import { ListPage as CallListPage } from './features/calls/ListPage'
import { RoomPage as CallRoomPage } from './features/calls/RoomPage'
import { AnalyticsPage as HelpAnalyticsPage } from './features/helpdesk/AnalyticsPage'
import { CategoriesPage as HelpCategoriesPage } from './features/helpdesk/CategoriesPage'
import { CategoryFormPage as HelpCategoryFormPage } from './features/helpdesk/CategoryFormPage'
import { DetailPage as HelpDetailPage } from './features/helpdesk/DetailPage'
import { FormPage as HelpFormPage } from './features/helpdesk/FormPage'
import { ListPage as HelpListPage } from './features/helpdesk/ListPage'
import { DetailPage as VisitDetailPage } from './features/reception/DetailPage'
import { FormPage as VisitFormPage } from './features/reception/FormPage'
import { ListPage as VisitListPage } from './features/reception/ListPage'
import { ReportPage as VisitReportPage } from './features/reception/ReportPage'
import { AnalyticsPage as ReqAnalyticsPage } from './features/needs/AnalyticsPage'
import { CategoriesPage as ReqCategoriesPage } from './features/needs/CategoriesPage'
import { CategoryFormPage as ReqCategoryFormPage } from './features/needs/CategoryFormPage'
import { DetailPage as ReqDetailPage } from './features/needs/DetailPage'
import { FormPage as ReqFormPage } from './features/needs/FormPage'
import { ListPage as ReqListPage } from './features/needs/ListPage'
import { DetailPage as ReminderDetailPage } from './features/reminders/DetailPage'
import { FormPage as ReminderFormPage } from './features/reminders/FormPage'
import { ListPage as ReminderListPage } from './features/reminders/ListPage'
import { BranchCardPage } from './features/pharmacy/BranchCardPage'
import { MapPage as PharmacyMapPage } from './features/pharmacy/MapPage'
import { NeedFormPage } from './features/pharmacy/NeedFormPage'
import { NeedsPage } from './features/pharmacy/NeedsPage'
import { NormsBulkPage } from './features/pharmacy/NormsBulkPage'
import { OverviewPage as PharmacyOverviewPage } from './features/pharmacy/OverviewPage'
import { ProfileFormPage } from './features/pharmacy/ProfileFormPage'
import { QualityPage } from './features/pharmacy/QualityPage'
import { AuditPage } from './features/audit/AuditPage'
import { ChangePasswordPage } from './features/auth/ChangePasswordPage'
import { LoginPage } from './features/auth/LoginPage'
import { RequireAuth } from './features/auth/RequireAuth'
import { RequirePerm } from './features/auth/RequirePerm'
import { BranchesPage } from './features/branches/BranchesPage'
import { BranchFormPage } from './features/branches/BranchFormPage'
import { BranchImportPage } from './features/branches/BranchImportPage'
import { AccountPage } from './features/employees/AccountPage'
import { BulkPage } from './features/employees/BulkPage'
import { BulkResultPage } from './features/employees/BulkResultPage'
import { DocumentFormPage } from './features/employees/DocumentFormPage'
import { DuplicatesPage } from './features/employees/DuplicatesPage'
import { EmployeeCardPage } from './features/employees/EmployeeCardPage'
import { EmployeeFormPage } from './features/employees/EmployeeFormPage'
import { EmployeesPage } from './features/employees/EmployeesPage'
import { ImportPage } from './features/employees/ImportPage'
import { MergePage } from './features/employees/MergePage'
import { DismissPage, ReinstatePage } from './features/employees/StatusChangePages'
import { TransferPage } from './features/employees/TransferPage'
import { DepartmentFormPage } from './features/org/DepartmentFormPage'
import { DepartmentsPage } from './features/org/DepartmentsPage'
import { OrgChartPage } from './features/org/OrgChartPage'
import { RotationDetailPage, RotationFormPage, RotationsPage } from './features/rotations/RotationPages'
import { BroadcastPage } from './features/notifications/BroadcastPage'
import { NotificationsPage } from './features/notifications/NotificationsPage'
import { ProfilePage } from './features/profile/ProfilePage'
import { RolesPage } from './features/roles/RolesPage'
import { UserCredentialsPage } from './features/users/UserCredentialsPage'
import { UserFormPage } from './features/users/UserFormPage'
import { UsersPage } from './features/users/UsersPage'
import { ApplyPage } from './features/schedule/ApplyPage'
import { EmployeeSchedulePage } from './features/schedule/EmployeeSchedulePage'
import { GroupFormPage } from './features/schedule/GroupFormPage'
import { GroupsPage } from './features/schedule/GroupsPage'
import { HolidayFormPage } from './features/schedule/HolidayFormPage'
import { HolidaySeedPage } from './features/schedule/HolidaySeedPage'
import { HolidaysPage } from './features/schedule/HolidaysPage'
import { PatternFormPage } from './features/schedule/PatternFormPage'
import { PatternsPage } from './features/schedule/PatternsPage'
import { SchedulePage } from './features/schedule/SchedulePage'
import { ShiftFormPage } from './features/schedule/ShiftFormPage'
import { ShiftsPage } from './features/schedule/ShiftsPage'
import { ApplyPage as PublicApplyPage } from './features/public/ApplyPage'
import { RecruiterPage } from './features/recruit/RecruiterPage'
import { PromoPage } from './features/recruit/sources/PromoPage'
import { RequirementFormPage, RequirementsPage } from './features/recruit/sources/RequirementsPage'
import { SourcesPage } from './features/recruit/sources/SourcesPage'
import { AttestationDetailPage, AttestationPage } from './features/growth/AttestationPages'
import { CareerPage, GrowthSettingsPage, LevelsFormPage, PromotionFormPage } from './features/growth/CareerPages'
import { PerformancePage } from './features/growth/PerformancePage'
import { ControlPage as HrControlPage } from './features/retention/ControlPage'
import { OffboardingDetailPage, OffboardingFormPage, OffboardingPage } from './features/retention/OffboardingPages'
import { MeetingFormPage, RetentionDetailPage, RetentionFormPage, RetentionPage } from './features/retention/RetentionPages'
import { ComplaintDetailPage, ComplaintFormPage, ComplaintsPage } from './features/complaints/ComplaintPages'
import { IntegrationsPage, KeyFormPage, ReconcilePage } from './features/integrations/IntegrationsPages'
import { HomePage } from './features/home/HomePage'
import { PlanPage } from './features/system/PlanPage'
import { StatusPage } from './features/system/StatusPage'
import { NotFound } from './pages/NotFound'

export function createRouter() {
  return createBrowserRouter([
    { path: '/login', element: <LoginPage /> },
    // Ochiq: QR orqali hujjatni tekshirish (kirish shart emas)
    { path: '/verify', element: <VerifyPage /> },
    { path: '/verify/:code', element: <VerifyPage /> },
    { path: '/apply/:code', element: <PublicApplyPage /> },
    {
      element: <RequireAuth />,
      children: [
        { path: '/change-password', element: <ChangePasswordPage /> },
        {
          element: <AppShell />,
          children: [
            { index: true, element: <HomePage /> },
            { path: 'system', element: <StatusPage /> },
            { path: 'system/plan', element: <RequirePerm perm="roles.read"><PlanPage /></RequirePerm> },
            { path: 'profile', element: <ProfilePage /> },
            { path: 'notifications', element: <NotificationsPage /> },
            { path: 'notifications/send', element: <RequirePerm perm="notifications.send"><BroadcastPage /></RequirePerm> },
            { path: 'employees', element: <RequirePerm perm="employees.read"><EmployeesPage /></RequirePerm> },
            { path: 'employees/new', element: <RequirePerm perm="employees.create"><EmployeeFormPage /></RequirePerm> },
            { path: 'employees/duplicates', element: <RequirePerm perm="employees.merge"><DuplicatesPage /></RequirePerm> },
            { path: 'employees/merge', element: <RequirePerm perm="employees.merge"><MergePage /></RequirePerm> },
            { path: 'employees/import', element: <RequirePerm perm="employees.import"><ImportPage /></RequirePerm> },
            { path: 'employees/bulk/:action', element: <RequirePerm perm="employees.read"><BulkPage /></RequirePerm> },
            { path: 'employees/bulk-result', element: <RequirePerm perm="employees.read"><BulkResultPage /></RequirePerm> },
            { path: 'employees/:id', element: <RequirePerm perm="employees.read"><EmployeeCardPage /></RequirePerm> },
            { path: 'employees/:id/edit', element: <RequirePerm perm="employees.update"><EmployeeFormPage /></RequirePerm> },
            { path: 'employees/:id/transfer', element: <RequirePerm perm="employees.transfer"><TransferPage /></RequirePerm> },
            { path: 'employees/:id/dismiss', element: <RequirePerm perm="employees.dismiss"><DismissPage /></RequirePerm> },
            { path: 'employees/:id/reinstate', element: <RequirePerm perm="employees.dismiss"><ReinstatePage /></RequirePerm> },
            { path: 'employees/:id/account', element: <RequirePerm perm="employees.accounts"><AccountPage /></RequirePerm> },
            { path: 'employees/:id/documents/new', element: <RequirePerm perm="employees.documents"><DocumentFormPage /></RequirePerm> },
            { path: 'employees/:id/documents/:docId/edit', element: <RequirePerm perm="employees.documents"><DocumentFormPage /></RequirePerm> },
            { path: 'schedule', element: <RequirePerm perm="schedule.read"><SchedulePage /></RequirePerm> },
            { path: 'schedule/apply', element: <RequirePerm perm="schedule.edit"><ApplyPage /></RequirePerm> },
            { path: 'schedule/employee/:id', element: <RequirePerm perm="schedule.read"><EmployeeSchedulePage /></RequirePerm> },
            { path: 'schedule/shifts', element: <RequirePerm perm="schedule.read"><ShiftsPage /></RequirePerm> },
            { path: 'schedule/shifts/new', element: <RequirePerm perm="schedule.manage"><ShiftFormPage /></RequirePerm> },
            { path: 'schedule/shifts/:id/edit', element: <RequirePerm perm="schedule.read"><ShiftFormPage /></RequirePerm> },
            { path: 'schedule/groups', element: <RequirePerm perm="schedule.read"><GroupsPage /></RequirePerm> },
            { path: 'schedule/groups/new', element: <RequirePerm perm="schedule.manage"><GroupFormPage /></RequirePerm> },
            { path: 'schedule/groups/:id/edit', element: <RequirePerm perm="schedule.read"><GroupFormPage /></RequirePerm> },
            { path: 'schedule/patterns', element: <RequirePerm perm="schedule.read"><PatternsPage /></RequirePerm> },
            { path: 'schedule/patterns/new', element: <RequirePerm perm="schedule.manage"><PatternFormPage /></RequirePerm> },
            { path: 'schedule/patterns/:id/edit', element: <RequirePerm perm="schedule.read"><PatternFormPage /></RequirePerm> },
            { path: 'schedule/holidays', element: <RequirePerm perm="schedule.read"><HolidaysPage /></RequirePerm> },
            { path: 'schedule/holidays/new', element: <RequirePerm perm="schedule.manage"><HolidayFormPage /></RequirePerm> },
            { path: 'schedule/holidays/seed', element: <RequirePerm perm="schedule.manage"><HolidaySeedPage /></RequirePerm> },
            { path: 'schedule/holidays/:id/edit', element: <RequirePerm perm="schedule.read"><HolidayFormPage /></RequirePerm> },
            { path: 'attendance', element: <RequirePerm perm="attendance.punch"><MyAttendancePage /></RequirePerm> },
            { path: 'attendance/punch', element: <RequirePerm perm="attendance.punch"><QrPunchPage /></RequirePerm> },
            { path: 'attendance/coordinator-report', element: <RequirePerm any={['attendance.edit', 'attendance.read', 'answers.decide']}><CoordReportPage /></RequirePerm> },
            { path: 'attendance/issues', element: <RequirePerm any={['attendance.punch', 'attendance.edit', 'attendance.read', 'answers.decide']}><IssuesPage /></RequirePerm> },
            { path: 'attendance/issues/new', element: <RequirePerm perm="attendance.punch"><AttendanceIssueFormPage /></RequirePerm> },
            { path: 'attendance/issues/:id', element: <RequirePerm any={['attendance.punch', 'attendance.edit', 'attendance.read', 'answers.decide']}><IssueDetailPage /></RequirePerm> },
            { path: 'attendance/qr', element: <RequirePerm perm="attendance.qr"><QrDisplayPage /></RequirePerm> },
            { path: 'attendance/dashboard', element: <RequirePerm perm="attendance.read"><DashboardPage /></RequirePerm> },
            { path: 'attendance/daily', element: <RequirePerm perm="attendance.read"><DailyPage /></RequirePerm> },
            { path: 'attendance/timesheet', element: <RequirePerm perm="attendance.read"><TimesheetPage /></RequirePerm> },
            { path: 'attendance/employee/:id', element: <RequirePerm perm="attendance.read"><EmployeeAttendancePage /></RequirePerm> },
            { path: 'attendance/records/new', element: <RequirePerm perm="attendance.edit"><RecordFormPage /></RequirePerm> },
            { path: 'attendance/records/:id/edit', element: <RequirePerm perm="attendance.edit"><RecordFormPage /></RequirePerm> },
            { path: 'face', element: <RequirePerm perm="face.enroll"><MyFacePage /></RequirePerm> },
            { path: 'face/consent', element: <RequirePerm perm="face.enroll"><ConsentPage /></RequirePerm> },
            { path: 'face/enroll', element: <RequirePerm perm="face.enroll"><EnrollPage /></RequirePerm> },
            { path: 'face/punch', element: <RequirePerm perm="face.enroll"><FacePunchPage /></RequirePerm> },
            { path: 'face/admin', element: <RequirePerm perm="face.read"><AdminPage /></RequirePerm> },
            { path: 'face/admin/:id', element: <RequirePerm perm="face.read"><AdminDetailPage /></RequirePerm> },
            { path: 'face/evaluation', element: <RequirePerm perm="face.evaluate"><EvaluationPage /></RequirePerm> },
            { path: 'answers', element: <RequirePerm perm="answers.request"><MyRequestsPage /></RequirePerm> },
            { path: 'answers/new', element: <RequirePerm perm="answers.request"><RequestFormPage /></RequirePerm> },
            { path: 'answers/inbox', element: <RequirePerm any={['answers.decide', 'answers.read']}><InboxPage /></RequirePerm> },
            { path: 'answers/calendar', element: <RequirePerm any={['answers.request', 'answers.read']}><CalendarPage /></RequirePerm> },
            { path: 'answers/holat', element: <RequirePerm any={['answers.read', 'answers.decide']}><AnswersStatusPage /></RequirePerm> },
            { path: 'answers/:id', element: <RequirePerm any={['answers.request', 'answers.decide', 'answers.read']}><RequestDetailPage /></RequirePerm> },
            { path: 'letters', element: <RequirePerm any={['letters.own', 'letters.issue', 'letters.read', 'letters.manage']}><LettersPage /></RequirePerm> },
            { path: 'letters/new', element: <RequirePerm any={['letters.issue', 'letters.manage']}><IssueFormPage /></RequirePerm> },
            { path: 'letters/templates', element: <RequirePerm any={['letters.manage', 'letters.issue']}><TemplatesPage /></RequirePerm> },
            { path: 'letters/templates/new', element: <RequirePerm perm="letters.manage"><TemplateFormPage /></RequirePerm> },
            { path: 'letters/templates/:id/edit', element: <RequirePerm any={['letters.manage', 'letters.issue']}><TemplateFormPage /></RequirePerm> },
            { path: 'letters/:id', element: <RequirePerm any={['letters.own', 'letters.issue', 'letters.read', 'letters.manage']}><LetterDetailPage /></RequirePerm> },
            { path: 'letters/:id/write', element: <RequirePerm perm="letters.own"><WritePage /></RequirePerm> },
            { path: 'letters/:id/scan', element: <RequirePerm any={['letters.own', 'letters.issue', 'letters.read', 'letters.manage']}><ScanPage /></RequirePerm> },
            { path: 'penalties', element: <RequirePerm any={['penalties.own', 'penalties.read', 'penalties.approve', 'penalties.manage']}><PenaltiesPage /></RequirePerm> },
            { path: 'penalties/new', element: <RequirePerm perm="penalties.manage"><ManualFormPage /></RequirePerm> },
            { path: 'penalties/scan', element: <RequirePerm perm="penalties.manage"><PenaltyScanPage /></RequirePerm> },
            { path: 'penalties/rules', element: <RequirePerm any={['penalties.read', 'penalties.approve', 'penalties.manage']}><RulesPage /></RequirePerm> },
            { path: 'penalties/rules/new', element: <RequirePerm perm="penalties.manage"><RulesFormPage /></RequirePerm> },
            { path: 'penalties/rules/:id', element: <RequirePerm any={['penalties.read', 'penalties.approve', 'penalties.manage']}><RuleVersionPage /></RequirePerm> },
            { path: 'penalties/report', element: <RequirePerm any={['penalties.read', 'penalties.approve', 'penalties.manage']}><ReportPage /></RequirePerm> },
            { path: 'penalties/:id', element: <RequirePerm any={['penalties.own', 'penalties.read', 'penalties.approve', 'penalties.manage']}><PenaltyDetailPage /></RequirePerm> },
            { path: 'tasks', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><TaskListPage /></RequirePerm> },
            { path: 'tasks/board', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><BoardPage /></RequirePerm> },
            { path: 'tasks/calendar', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><TaskCalendarPage /></RequirePerm> },
            { path: 'tasks/analytics', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><AnalyticsPage /></RequirePerm> },
            { path: 'tasks/new', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><TaskFormPage /></RequirePerm> },
            { path: 'tasks/templates', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><TaskTemplatesPage /></RequirePerm> },
            { path: 'tasks/templates/new', element: <RequirePerm perm="tasks.manage"><TaskTemplateFormPage /></RequirePerm> },
            { path: 'tasks/templates/:id/edit', element: <RequirePerm perm="tasks.manage"><TaskTemplateFormPage /></RequirePerm> },
            { path: 'tasks/:id', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><TaskDetailPage /></RequirePerm> },
            { path: 'tasks/:id/edit', element: <RequirePerm any={['tasks.own', 'tasks.read', 'tasks.manage']}><TaskFormPage /></RequirePerm> },
            { path: 'mobile', element: <RequirePerm any={['mobile.read', 'mobile.manage']}><MobileLivePage /></RequirePerm> },
            { path: 'mobile/my', element: <RequirePerm perm="mobile.own"><MobileMyPage /></RequirePerm> },
            { path: 'mobile/permits', element: <RequirePerm any={['mobile.read', 'mobile.manage']}><PermitsPage /></RequirePerm> },
            { path: 'mobile/permits/new', element: <RequirePerm perm="mobile.manage"><PermitFormPage /></RequirePerm> },
            { path: 'mobile/permits/:eid/edit', element: <RequirePerm perm="mobile.manage"><PermitFormPage /></RequirePerm> },
            { path: 'mobile/sessions', element: <RequirePerm any={['mobile.read', 'mobile.manage']}><MobileSessionsPage /></RequirePerm> },
            { path: 'mobile/sessions/:id', element: <RequirePerm any={['mobile.read', 'mobile.manage']}><SessionDetailPage /></RequirePerm> },
            { path: 'mobile/events', element: <RequirePerm any={['mobile.read', 'mobile.manage']}><MobileEventsPage /></RequirePerm> },
            { path: 'warehouse', element: <RequirePerm any={['warehouse.read', 'warehouse.manage']}><WarehouseStatusPage /></RequirePerm> },
            { path: 'warehouse/list', element: <RequirePerm any={['warehouse.read', 'warehouse.manage']}><WarehousesPage /></RequirePerm> },
            { path: 'warehouse/new', element: <RequirePerm perm="warehouse.manage"><WarehouseFormPage /></RequirePerm> },
            { path: 'warehouse/:id', element: <RequirePerm any={['warehouse.read', 'warehouse.manage']}><WarehouseDetailPage /></RequirePerm> },
            { path: 'warehouse/:id/edit', element: <RequirePerm perm="warehouse.manage"><WarehouseFormPage /></RequirePerm> },
            { path: 'warehouse/:id/staff/new', element: <RequirePerm perm="warehouse.manage"><StaffAddPage /></RequirePerm> },
            { path: 'warehouse/:id/control', element: <RequirePerm any={['warehouse.read', 'warehouse.manage']}><ControlPage /></RequirePerm> },
            { path: 'logistics', element: <RequirePerm any={['logistics.read', 'logistics.manage']}><LivePage /></RequirePerm> },
            { path: 'logistics/vehicles', element: <RequirePerm any={['logistics.read', 'logistics.manage']}><VehiclesPage /></RequirePerm> },
            { path: 'logistics/vehicles/new', element: <RequirePerm perm="logistics.manage"><VehicleFormPage /></RequirePerm> },
            { path: 'logistics/vehicles/:id', element: <RequirePerm any={['logistics.read', 'logistics.manage']}><VehicleDetailPage /></RequirePerm> },
            { path: 'logistics/vehicles/:id/edit', element: <RequirePerm perm="logistics.manage"><VehicleFormPage /></RequirePerm> },
            { path: 'logistics/vehicles/:vid/documents/new', element: <RequirePerm perm="logistics.manage"><VehicleDocFormPage /></RequirePerm> },
            { path: 'logistics/documents/:did/edit', element: <RequirePerm perm="logistics.manage"><VehicleDocFormPage /></RequirePerm> },
            { path: 'logistics/drivers', element: <RequirePerm any={['logistics.read', 'logistics.manage']}><DriversPage /></RequirePerm> },
            { path: 'logistics/drivers/new', element: <RequirePerm perm="logistics.manage"><DriverFormPage /></RequirePerm> },
            { path: 'logistics/drivers/:eid/edit', element: <RequirePerm perm="logistics.manage"><DriverFormPage /></RequirePerm> },
            { path: 'logistics/trips', element: <RequirePerm any={['logistics.read', 'logistics.manage']}><TripsPage /></RequirePerm> },
            { path: 'logistics/trips/new', element: <RequirePerm perm="logistics.manage"><TripFormPage /></RequirePerm> },
            { path: 'logistics/trips/:id', element: <RequirePerm any={['logistics.own', 'logistics.read', 'logistics.manage']}><TripDetailPage /></RequirePerm> },
            { path: 'logistics/trips/:id/edit', element: <RequirePerm perm="logistics.manage"><TripFormPage /></RequirePerm> },
            { path: 'logistics/my', element: <RequirePerm perm="logistics.own"><MyPage /></RequirePerm> },
            { path: 'logistics/fuel', element: <RequirePerm any={['logistics.read', 'logistics.manage']}><FuelPage /></RequirePerm> },
            { path: 'logistics/fuel/new', element: <RequirePerm any={['logistics.own', 'logistics.read', 'logistics.manage']}><FuelFormPage /></RequirePerm> },
            { path: 'logistics/fuel/:id/edit', element: <RequirePerm perm="logistics.manage"><FuelFormPage /></RequirePerm> },
            { path: 'logistics/reports', element: <RequirePerm any={['logistics.read', 'logistics.manage']}><LogisticsReportsPage /></RequirePerm> },
            { path: 'canteen', element: <RequirePerm any={['canteen.own', 'canteen.read', 'canteen.manage']}><MenuPage mode="today" /></RequirePerm> },
            { path: 'canteen/rate', element: <RequirePerm any={['canteen.own', 'canteen.read', 'canteen.manage']}><MenuPage mode="qr" /></RequirePerm> },
            { path: 'canteen/menus', element: <RequirePerm any={['canteen.own', 'canteen.read', 'canteen.manage']}><MenusPage /></RequirePerm> },
            { path: 'canteen/menus/new', element: <RequirePerm perm="canteen.manage"><MenuFormPage /></RequirePerm> },
            { path: 'canteen/menus/:id', element: <RequirePerm any={['canteen.own', 'canteen.read', 'canteen.manage']}><MenuPage mode="id" /></RequirePerm> },
            { path: 'canteen/menus/:id/edit', element: <RequirePerm perm="canteen.manage"><MenuFormPage /></RequirePerm> },
            { path: 'canteen/comments', element: <RequirePerm any={['canteen.read', 'canteen.manage']}><CommentsPage /></RequirePerm> },
            { path: 'canteen/analytics', element: <RequirePerm any={['canteen.read', 'canteen.manage']}><CanteenAnalyticsPage /></RequirePerm> },
            { path: 'canteen/qr', element: <RequirePerm perm="canteen.manage"><QrPage /></RequirePerm> },
            { path: 'canteen/settings', element: <RequirePerm perm="canteen.manage"><CanteenSettingsPage /></RequirePerm> },
            { path: 'payroll', element: <RequirePerm perm="payroll.read"><RunsPage /></RequirePerm> },
            { path: 'payroll/runs/new', element: <RequirePerm perm="payroll.manage"><RunFormPage /></RequirePerm> },
            { path: 'payroll/runs/:id', element: <RequirePerm perm="payroll.read"><RunDetailPage /></RequirePerm> },
            { path: 'payroll/runs/:id/lines/:lid', element: <RequirePerm perm="payroll.read"><LinePage /></RequirePerm> },
            { path: 'payroll/schemes', element: <RequirePerm perm="payroll.read"><SchemesPage /></RequirePerm> },
            { path: 'payroll/schemes/new', element: <RequirePerm perm="payroll.manage"><SchemeFormPage /></RequirePerm> },
            { path: 'payroll/schemes/:id/edit', element: <RequirePerm perm="payroll.manage"><SchemeFormPage /></RequirePerm> },
            { path: 'payroll/items', element: <RequirePerm perm="payroll.read"><ItemsPage /></RequirePerm> },
            { path: 'payroll/items/new', element: <RequirePerm perm="payroll.input"><ItemFormPage /></RequirePerm> },
            { path: 'payroll/items/import', element: <RequirePerm perm="payroll.input"><ItemsImportPage /></RequirePerm> },
            { path: 'payroll/items/:id/edit', element: <RequirePerm perm="payroll.input"><ItemFormPage /></RequirePerm> },
            { path: 'payroll/my', element: <RequirePerm perm="payroll.own"><MyPayslipsPage /></RequirePerm> },
            { path: 'payroll/my/:id', element: <RequirePerm perm="payroll.own"><MyPayslipPage /></RequirePerm> },
            { path: 'internship', element: <RequirePerm any={['internship.own', 'internship.read', 'internship.manage']}><EnrollmentsPage /></RequirePerm> },
            { path: 'internship/classes', element: <RequirePerm any={['internship.own', 'internship.read', 'internship.manage']}><ClassesPage /></RequirePerm> },
            { path: 'internship/classes/new', element: <RequirePerm perm="internship.manage"><ClassFormPage /></RequirePerm> },
            { path: 'internship/classes/:id', element: <RequirePerm any={['internship.own', 'internship.read', 'internship.manage']}><ClassDetailPage /></RequirePerm> },
            { path: 'attestation', element: <RequirePerm any={['attestation.own', 'attestation.read', 'attestation.manage']}><AttestationPage /></RequirePerm> },
            { path: 'attestation/:id', element: <RequirePerm any={['attestation.own', 'attestation.read', 'attestation.manage']}><AttestationDetailPage /></RequirePerm> },
            { path: 'career', element: <RequirePerm any={['career.read', 'career.propose', 'career.manage']}><CareerPage /></RequirePerm> },
            { path: 'career/new', element: <RequirePerm any={['career.propose', 'career.manage']}><PromotionFormPage /></RequirePerm> },
            { path: 'career/levels', element: <RequirePerm perm="career.manage"><LevelsFormPage /></RequirePerm> },
            { path: 'career/settings', element: <RequirePerm perm="career.manage"><GrowthSettingsPage /></RequirePerm> },
            { path: 'performance', element: <RequirePerm any={['performance.read', 'performance.own']}><PerformancePage /></RequirePerm> },
            { path: 'retention', element: <RequirePerm any={['retention.report', 'retention.manage', 'retention.read', 'retention.audit']}><RetentionPage /></RequirePerm> },
            { path: 'retention/new', element: <RequirePerm any={['retention.report', 'retention.manage']}><RetentionFormPage /></RequirePerm> },
            { path: 'retention/meetings/new', element: <RequirePerm perm="retention.manage"><MeetingFormPage /></RequirePerm> },
            { path: 'retention/:id', element: <RequirePerm any={['retention.report', 'retention.manage', 'retention.read', 'retention.audit']}><RetentionDetailPage /></RequirePerm> },
            { path: 'offboarding', element: <RequirePerm any={['retention.manage', 'retention.read', 'retention.audit']}><OffboardingPage /></RequirePerm> },
            { path: 'offboarding/new', element: <RequirePerm perm="retention.manage"><OffboardingFormPage /></RequirePerm> },
            { path: 'offboarding/:id', element: <RequirePerm any={['retention.manage', 'retention.read', 'retention.audit']}><OffboardingDetailPage /></RequirePerm> },
            { path: 'control', element: <RequirePerm perm="control.read"><HrControlPage /></RequirePerm> },
            { path: 'integrations', element: <RequirePerm any={['integrations.read', 'integrations.manage']}><IntegrationsPage /></RequirePerm> },
            { path: 'integrations/keys/new', element: <RequirePerm perm="integrations.manage"><KeyFormPage /></RequirePerm> },
            { path: 'integrations/reconcile', element: <RequirePerm any={['integrations.read', 'integrations.manage']}><ReconcilePage /></RequirePerm> },
            { path: 'complaints', element: <RequirePerm any={['complaints.own', 'complaints.manage']}><ComplaintsPage /></RequirePerm> },
            { path: 'complaints/new', element: <RequirePerm perm="complaints.own"><ComplaintFormPage /></RequirePerm> },
            { path: 'complaints/:id', element: <RequirePerm any={['complaints.own', 'complaints.manage']}><ComplaintDetailPage /></RequirePerm> },
            { path: 'kadr', element: <RequirePerm perm="employees.documents"><KadrPage /></RequirePerm> },
            { path: 'internship/enrollments/new', element: <RequirePerm perm="internship.manage"><InternEnrollPage /></RequirePerm> },
            { path: 'internship/enrollments/:id', element: <RequirePerm any={['internship.own', 'internship.read', 'internship.manage']}><EnrollmentPage /></RequirePerm> },
            { path: 'internship/enrollments/:id/steps/:sid', element: <RequirePerm any={['internship.own', 'internship.read', 'internship.manage']}><LearnPage /></RequirePerm> },
            { path: 'internship/programs', element: <RequirePerm any={['internship.own', 'internship.read', 'internship.manage']}><ProgramsPage /></RequirePerm> },
            { path: 'internship/programs/new', element: <RequirePerm perm="internship.manage"><ProgramFormPage /></RequirePerm> },
            { path: 'internship/programs/:id', element: <RequirePerm any={['internship.own', 'internship.read', 'internship.manage']}><ProgramDetailPage /></RequirePerm> },
            { path: 'internship/programs/:id/edit', element: <RequirePerm perm="internship.manage"><ProgramFormPage /></RequirePerm> },
            { path: 'internship/programs/:pid/steps/new', element: <RequirePerm perm="internship.manage"><StepFormPage /></RequirePerm> },
            { path: 'internship/steps/:sid/edit', element: <RequirePerm perm="internship.manage"><StepFormPage /></RequirePerm> },
            { path: 'recruit', element: <RequirePerm perm="recruit.read"><VacanciesPage /></RequirePerm> },
            { path: 'recruit/vacancies', element: <RequirePerm perm="recruit.read"><VacanciesPage /></RequirePerm> },
            { path: 'recruit/vacancies/new', element: <RequirePerm perm="recruit.manage"><VacancyFormPage /></RequirePerm> },
            { path: 'recruit/vacancies/:id/promo', element: <RequirePerm any={['recruit.read', 'recruit.manage']}><PromoPage /></RequirePerm> },
            { path: 'recruit/recruiter', element: <RequirePerm any={['recruit.read', 'recruit.manage']}><RecruiterPage /></RequirePerm> },
            { path: 'recruit/sources', element: <RequirePerm any={['recruit.read', 'recruit.manage']}><SourcesPage /></RequirePerm> },
            { path: 'recruit/requirements', element: <RequirePerm any={['recruit.read', 'recruit.manage']}><RequirementsPage /></RequirePerm> },
            { path: 'recruit/requirements/:positionId/edit', element: <RequirePerm perm="recruit.manage"><RequirementFormPage /></RequirePerm> },
            { path: 'recruit/vacancies/:id', element: <RequirePerm perm="recruit.read"><VacancyDetailPage /></RequirePerm> },
            { path: 'recruit/vacancies/:id/edit', element: <RequirePerm perm="recruit.manage"><VacancyFormPage /></RequirePerm> },
            { path: 'recruit/candidates', element: <RequirePerm perm="recruit.read"><CandidatesPage /></RequirePerm> },
            { path: 'recruit/candidates/new', element: <RequirePerm perm="recruit.manage"><CandidateFormPage /></RequirePerm> },
            { path: 'recruit/candidates/:id', element: <RequirePerm perm="recruit.read"><CandidateDetailPage /></RequirePerm> },
            { path: 'recruit/candidates/:id/edit', element: <RequirePerm perm="recruit.manage"><CandidateFormPage /></RequirePerm> },
            { path: 'recruit/applications', element: <RequirePerm perm="recruit.read"><ApplicationsPage /></RequirePerm> },
            { path: 'recruit/applications/new', element: <RequirePerm perm="recruit.manage"><ApplicationNewPage /></RequirePerm> },
            { path: 'recruit/applications/:id', element: <RequirePerm perm="recruit.read"><ApplicationDetailPage /></RequirePerm> },
            { path: 'recruit/applications/:id/hire', element: <RequirePerm perm="recruit.manage"><HirePage /></RequirePerm> },
            { path: 'recruit/summary', element: <RequirePerm perm="recruit.read"><RecruitSummaryPage /></RequirePerm> },
            { path: 'checklists', element: <RequirePerm any={['checklists.own', 'checklists.read', 'checklists.manage']}><CheckListPage /></RequirePerm> },
            { path: 'checklists/new', element: <RequirePerm any={['checklists.own', 'checklists.manage']}><CheckNewPage /></RequirePerm> },
            { path: 'checklists/report', element: <RequirePerm any={['checklists.own', 'checklists.read', 'checklists.manage']}><CheckReportPage /></RequirePerm> },
            { path: 'checklists/templates', element: <RequirePerm any={['checklists.own', 'checklists.read', 'checklists.manage']}><CheckTemplatesPage /></RequirePerm> },
            { path: 'checklists/templates/new', element: <RequirePerm perm="checklists.manage"><CheckTemplateFormPage /></RequirePerm> },
            { path: 'checklists/templates/:id/edit', element: <RequirePerm perm="checklists.manage"><CheckTemplateFormPage /></RequirePerm> },
            { path: 'checklists/:id', element: <RequirePerm any={['checklists.own', 'checklists.read', 'checklists.manage']}><CheckDetailPage /></RequirePerm> },
            { path: 'checklists/:id/fill', element: <RequirePerm any={['checklists.own', 'checklists.manage']}><CheckFillPage /></RequirePerm> },
            { path: 'migration', element: <RequirePerm perm="migration.manage"><MigBatchesPage /></RequirePerm> },
            { path: 'migration/new', element: <RequirePerm perm="migration.manage"><MigNewImportPage /></RequirePerm> },
            { path: 'migration/batches/:id', element: <RequirePerm perm="migration.manage"><MigBatchPage /></RequirePerm> },
            { path: 'migration/reconcile', element: <RequirePerm perm="migration.manage"><MigReconcilePage /></RequirePerm> },
            { path: 'migration/checks/new', element: <RequirePerm perm="migration.manage"><MigCheckFormPage /></RequirePerm> },
            { path: 'migration/checks/:id/edit', element: <RequirePerm perm="migration.manage"><MigCheckFormPage /></RequirePerm> },
            { path: 'migration/templates', element: <RequirePerm perm="migration.manage"><MigTemplatesPage /></RequirePerm> },
            { path: 'migration/templates/new', element: <RequirePerm perm="migration.manage"><MigTemplateFormPage /></RequirePerm> },
            { path: 'migration/templates/:id/edit', element: <RequirePerm perm="migration.manage"><MigTemplateFormPage /></RequirePerm> },
            { path: 'reports', element: <RequirePerm any={['reports.read', 'reports.manage']}><ReportsPage /></RequirePerm> },
            { path: 'reports/history', element: <RequirePerm any={['reports.read', 'reports.manage']}><ReportHistoryPage /></RequirePerm> },
            { path: 'reports/schedules', element: <RequirePerm perm="reports.manage"><SchedulesPage /></RequirePerm> },
            { path: 'reports/schedules/new', element: <RequirePerm perm="reports.manage"><ScheduleFormPage /></RequirePerm> },
            { path: 'reports/schedules/:id/edit', element: <RequirePerm perm="reports.manage"><ScheduleFormPage /></RequirePerm> },
            { path: 'search', element: <SearchPage /> },
            { path: 'ai/usage', element: <RequirePerm perm="ai.manage"><AiUsagePage /></RequirePerm> },
            { path: 'ai/settings', element: <RequirePerm perm="ai.manage"><AiSettingsPage /></RequirePerm> },
            { path: 'calls', element: <RequirePerm any={['calls.own', 'calls.read', 'calls.manage']}><CallListPage /></RequirePerm> },
            { path: 'calls/new', element: <RequirePerm perm="calls.own"><CallFormPage /></RequirePerm> },
            { path: 'calls/:id', element: <RequirePerm any={['calls.own', 'calls.read', 'calls.manage']}><CallRoomPage /></RequirePerm> },
            { path: 'calls/:id/edit', element: <RequirePerm perm="calls.own"><CallFormPage /></RequirePerm> },
            { path: 'reception', element: <RequirePerm any={['reception.own', 'reception.desk', 'reception.read']}><VisitListPage /></RequirePerm> },
            { path: 'reception/new', element: <RequirePerm any={['reception.own', 'reception.desk', 'reception.read']}><VisitFormPage /></RequirePerm> },
            { path: 'reception/report', element: <RequirePerm any={['reception.desk', 'reception.read']}><VisitReportPage /></RequirePerm> },
            { path: 'reception/:id', element: <RequirePerm any={['reception.own', 'reception.desk', 'reception.read']}><VisitDetailPage /></RequirePerm> },
            { path: 'reception/:id/edit', element: <RequirePerm any={['reception.own', 'reception.desk', 'reception.read']}><VisitFormPage /></RequirePerm> },
            { path: 'helpdesk', element: <RequirePerm any={['helpdesk.own', 'helpdesk.work', 'helpdesk.read', 'helpdesk.manage']}><HelpListPage /></RequirePerm> },
            { path: 'helpdesk/new', element: <RequirePerm any={['helpdesk.own', 'helpdesk.work', 'helpdesk.read', 'helpdesk.manage']}><HelpFormPage /></RequirePerm> },
            { path: 'helpdesk/analytics', element: <RequirePerm any={['helpdesk.work', 'helpdesk.read', 'helpdesk.manage']}><HelpAnalyticsPage /></RequirePerm> },
            { path: 'helpdesk/categories', element: <RequirePerm perm="helpdesk.manage"><HelpCategoriesPage /></RequirePerm> },
            { path: 'helpdesk/categories/new', element: <RequirePerm perm="helpdesk.manage"><HelpCategoryFormPage /></RequirePerm> },
            { path: 'helpdesk/categories/:id/edit', element: <RequirePerm perm="helpdesk.manage"><HelpCategoryFormPage /></RequirePerm> },
            { path: 'helpdesk/:id', element: <RequirePerm any={['helpdesk.own', 'helpdesk.work', 'helpdesk.read', 'helpdesk.manage']}><HelpDetailPage /></RequirePerm> },
            { path: 'helpdesk/:id/edit', element: <RequirePerm any={['helpdesk.own', 'helpdesk.work', 'helpdesk.read', 'helpdesk.manage']}><HelpFormPage /></RequirePerm> },
            { path: 'needs', element: <RequirePerm any={['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage']}><ReqListPage /></RequirePerm> },
            { path: 'needs/new', element: <RequirePerm any={['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage']}><ReqFormPage /></RequirePerm> },
            { path: 'needs/analytics', element: <RequirePerm any={['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage']}><ReqAnalyticsPage /></RequirePerm> },
            { path: 'needs/categories', element: <RequirePerm any={['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage']}><ReqCategoriesPage /></RequirePerm> },
            { path: 'needs/categories/new', element: <RequirePerm perm="needs.manage"><ReqCategoryFormPage /></RequirePerm> },
            { path: 'needs/categories/:id/edit', element: <RequirePerm perm="needs.manage"><ReqCategoryFormPage /></RequirePerm> },
            { path: 'needs/:id', element: <RequirePerm any={['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage']}><ReqDetailPage /></RequirePerm> },
            { path: 'needs/:id/edit', element: <RequirePerm any={['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage']}><ReqFormPage /></RequirePerm> },
            { path: 'reminders', element: <RequirePerm any={['reminders.own', 'reminders.assign']}><ReminderListPage /></RequirePerm> },
            { path: 'reminders/new', element: <RequirePerm any={['reminders.own', 'reminders.assign']}><ReminderFormPage /></RequirePerm> },
            { path: 'reminders/:id', element: <RequirePerm any={['reminders.own', 'reminders.assign']}><ReminderDetailPage /></RequirePerm> },
            { path: 'reminders/:id/edit', element: <RequirePerm any={['reminders.own', 'reminders.assign']}><ReminderFormPage /></RequirePerm> },
            { path: 'pharmacy', element: <RequirePerm any={['pharmacy.read', 'pharmacy.own', 'pharmacy.manage']}><PharmacyOverviewPage /></RequirePerm> },
            { path: 'pharmacy/map', element: <RequirePerm any={['pharmacy.read', 'pharmacy.own', 'pharmacy.manage']}><PharmacyMapPage /></RequirePerm> },
            { path: 'pharmacy/quality', element: <RequirePerm any={['pharmacy.read', 'pharmacy.manage']}><QualityPage /></RequirePerm> },
            { path: 'pharmacy/norms', element: <RequirePerm perm="pharmacy.manage"><NormsBulkPage /></RequirePerm> },
            { path: 'pharmacy/needs', element: <RequirePerm any={['pharmacy.read', 'pharmacy.own', 'pharmacy.manage']}><NeedsPage /></RequirePerm> },
            { path: 'pharmacy/needs/new', element: <RequirePerm any={['pharmacy.request', 'pharmacy.manage']}><NeedFormPage /></RequirePerm> },
            { path: 'pharmacy/needs/:id', element: <RequirePerm any={['pharmacy.read', 'pharmacy.own', 'pharmacy.manage']}><NeedFormPage /></RequirePerm> },
            { path: 'pharmacy/needs/:id/edit', element: <RequirePerm any={['pharmacy.read', 'pharmacy.own', 'pharmacy.manage']}><NeedFormPage /></RequirePerm> },
            { path: 'pharmacy/:id/edit', element: <RequirePerm perm="pharmacy.manage"><ProfileFormPage /></RequirePerm> },
            { path: 'pharmacy/:id', element: <RequirePerm any={['pharmacy.read', 'pharmacy.own', 'pharmacy.manage']}><BranchCardPage /></RequirePerm> },
            { path: 'org', element: <RequirePerm perm="org.read"><OrgChartPage /></RequirePerm> },
            { path: 'org/departments', element: <RequirePerm perm="org.read"><DepartmentsPage /></RequirePerm> },
            { path: 'org/departments/new', element: <RequirePerm perm="org.manage"><DepartmentFormPage /></RequirePerm> },
            { path: 'org/departments/:id/edit', element: <RequirePerm perm="org.read"><DepartmentFormPage /></RequirePerm> },
            { path: 'org/rotations', element: <RequirePerm any={['rotations.read', 'rotations.request', 'rotations.manage']}><RotationsPage /></RequirePerm> },
            { path: 'org/rotations/new', element: <RequirePerm any={['rotations.request', 'rotations.manage']}><RotationFormPage /></RequirePerm> },
            { path: 'org/rotations/:id', element: <RequirePerm any={['rotations.read', 'rotations.request', 'rotations.manage']}><RotationDetailPage /></RequirePerm> },
            { path: 'branches', element: <RequirePerm perm="branches.read"><BranchesPage /></RequirePerm> },
            { path: 'branches/new', element: <RequirePerm perm="branches.manage"><BranchFormPage /></RequirePerm> },
            { path: 'branches/import', element: <RequirePerm perm="branches.manage"><BranchImportPage /></RequirePerm> },
            { path: 'branches/:id/edit', element: <RequirePerm perm="branches.read"><BranchFormPage /></RequirePerm> },
            { path: 'users', element: <RequirePerm perm="users.read"><UsersPage /></RequirePerm> },
            { path: 'users/new', element: <RequirePerm perm="users.create"><UserFormPage /></RequirePerm> },
            { path: 'users/credentials', element: <RequirePerm perm="users.read"><UserCredentialsPage /></RequirePerm> },
            { path: 'users/:id/edit', element: <RequirePerm perm="users.update"><UserFormPage /></RequirePerm> },
            { path: 'roles', element: <RequirePerm perm="roles.read"><RolesPage /></RequirePerm> },
            { path: 'audit', element: <RequirePerm perm="audit.read"><AuditPage /></RequirePerm> },
            ...getExtensionRoutes(),
            { path: '*', element: <NotFound /> },
          ],
        },
      ],
    },
  ])
}
