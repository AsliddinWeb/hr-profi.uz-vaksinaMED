import { CalendarClock, MessageSquare, Paperclip } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { dueText, PRIORITY_TONE, STATUSES, type TaskItem, type TStatus } from './api'

/** Kanban kartasi: sudrab ko'chiriladi; klaviatura/telefon uchun "ko'chirish" tanlovi ham bor. */
export function TaskCard({ task, onMove, dragging, onDragStart, onDragEnd, canMove }: { task: TaskItem; onMove: (s: TStatus) => void; dragging: boolean; onDragStart: () => void; onDragEnd: () => void; canMove: boolean }) {
  const { t } = useTranslation()
  return (
    <article
      draggable={canMove}
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', String(task.id))
        e.dataTransfer.effectAllowed = 'move'
        onDragStart()
      }}
      onDragEnd={onDragEnd}
      className={'rounded-control border border-border bg-surface p-3 shadow-sm ' + (dragging ? 'opacity-40' : 'hover:shadow-md') + (canMove ? ' cursor-grab active:cursor-grabbing' : '')}
      data-task-id={task.id}
    >
      <Link to={`/tasks/${task.id}`} className="line-clamp-3 text-sm font-medium hover:text-primary hover:underline" draggable={false}>
        {task.title}
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIORITY_TONE[task.priority]}`}>{t(`tasks.priority.${task.priority}`)}</span>
        {task.labels.map((l) => (
          <span key={l} className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-muted">
            {l}
          </span>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span className={'inline-flex items-center gap-1 ' + (task.overdue ? 'font-semibold text-danger' : '')}>
          {task.due_at && (
            <>
              <CalendarClock className="size-3.5" />
              {dueText(task.due_at)}
            </>
          )}
        </span>
        <span className="inline-flex items-center gap-2.5">
          {task.comments > 0 && (
            <span className="inline-flex items-center gap-1" title={t('tasks.comments')}>
              <MessageSquare className="size-3.5" />
              {task.comments}
            </span>
          )}
          {task.files > 0 && (
            <span className="inline-flex items-center gap-1" title={t('tasks.files')}>
              <Paperclip className="size-3.5" />
              {task.files}
            </span>
          )}
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="truncate text-xs text-muted">{task.assignee?.name ?? t('tasks.unassigned')}</span>
        {canMove && (
          <select value={task.status} onChange={(e) => onMove(e.target.value as TStatus)} aria-label={t('tasks.move')} className="h-7 max-w-[8.5rem] rounded-md border border-border bg-surface px-1 text-xs">
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`tasks.status.${s}`)}
              </option>
            ))}
          </select>
        )}
      </div>
    </article>
  )
}
