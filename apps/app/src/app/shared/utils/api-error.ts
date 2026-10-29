import type { iApiErrorResponse } from '@/app/shared/types'

export function apiErrorMessage(
  error: unknown,
  fallback = 'Não foi possível salvar as alterações.',
) {
  return (
    (error as iApiErrorResponse)?.data?.errors?.map((item) => item.detail).join(' ') || fallback
  )
}
