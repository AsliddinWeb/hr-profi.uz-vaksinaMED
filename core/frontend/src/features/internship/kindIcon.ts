import { FileText, ListChecks, Play, Type } from 'lucide-react'

import type { Kind } from './api'

export const KIND_ICON: Record<Kind, typeof Play> = { video: Play, document: FileText, text: Type, test: ListChecks }
