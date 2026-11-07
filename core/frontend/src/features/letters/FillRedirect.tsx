import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { openAutoLetter, type AutoLetter } from './autoApi'

/**
 * /letters/:id/fill: bildirishnoma va Telegram havolasi. Xat imzolanmagan bo'lsa oynasi ochiladi
 * (bosh sahifa ustida), imzolangan yoki boshqaniki bo'lsa xat sahifasiga o'tadi.
 */
export function FillRedirect() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const q = useQuery({ queryKey: ['letters', 'auto', id], queryFn: () => api<AutoLetter>(`/api/v1/letters/${id}/auto`), retry: false })

  useEffect(() => {
    if (q.isError) navigate(`/letters/${id}`, { replace: true })
    if (!q.data) return
    if (q.data.status === 'requested' || q.data.status === 'returned') {
      navigate('/', { replace: true })
      openAutoLetter()
    } else navigate(`/letters/${id}`, { replace: true })
  }, [q.data, q.isError, id, navigate])

  return <Skeleton className="mx-auto h-96 max-w-3xl" />
}
