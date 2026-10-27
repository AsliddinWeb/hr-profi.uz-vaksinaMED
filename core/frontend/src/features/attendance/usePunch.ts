import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import type { PunchResult } from './api'
import { getPosition } from './geo'

/** Geolokatsiya olib, keldi/ketdi so'rovini yuboradi. `token` berilsa QR, aks holda GPS. */
export function usePunch(token?: string) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [geoError, setGeoError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      setGeoError(null)
      let pos = null
      try {
        pos = await getPosition()
      } catch (e) {
        // QR rejimida filialda joylashuv bo'lmasa ham ishlashi mumkin: serverga qoldiramiz
        if (!token) throw new GeoError((e as Error).message)
        setGeoError((e as Error).message)
      }
      return send<PunchResult>('POST', '/api/v1/attendance/punch', {
        method: token ? 'qr' : 'gps',
        token: token ?? null,
        lat: pos?.lat ?? null,
        lng: pos?.lng ?? null,
        accuracy: pos?.accuracy ?? null,
      })
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['attendance'] }),
  })

  const err = mutation.error
  let message: string | null = null
  if (err instanceof GeoError) message = t(`attendance.geo.${err.message}`)
  else if (err instanceof ApiError) {
    message = errorText(t, err)
    if (err.code === 'outside_geofence') message = t('errors.outside_geofence', { distance: err.extra.distance, radius: err.extra.radius })
    if (err.code === 'accuracy_too_low') message = t('errors.accuracy_too_low', { accuracy: err.extra.accuracy, max: err.extra.max })
  } else if (err) message = errorText(t, err)

  return { ...mutation, message, geoError }
}

class GeoError extends Error {}
