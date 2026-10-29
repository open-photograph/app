import type { Ref } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import type { SessionResponse } from '@/app/shared/services/session'

export interface PhotoComment {
  id: string
  photo: string
  photo_name: string
  name: string
  text: string
  created_at: string
}

export interface GallerySelection {
  id: string
  name: string
  email: string
  message: string
  photos: { id: string; name: string }[]
  created_at: string
}

export interface GalleryFeedback {
  like_counts: Record<string, number>
  liked_photo_ids: string[]
  comments: PhotoComment[]
  selections: GallerySelection[]
}

export interface AdminGalleryFeedback {
  likes: { id: string; name: string; count: number }[]
  comments: PhotoComment[]
  selections: GallerySelection[]
}

type MutationState<Payload> = {
  mutate: (payload: Payload) => void
  mutateAsync: (payload: Payload) => Promise<unknown>
  isPending: Ref<boolean>
  isSuccess: Ref<boolean>
}

export interface GalleryFeedbackContext {
  likingPhotos: Set<string>
  user: Ref<SessionResponse['data']['user']>
  isAuthenticated: Ref<boolean>
  loadingSession: Ref<boolean>
  loginRoute: Ref<RouteLocationRaw>
  requireLogin: () => Promise<boolean>
  data: Ref<GalleryFeedback | undefined>
  isPending: Ref<boolean>
  isError: Ref<boolean>
  refetch: () => Promise<unknown>
  selecting: Ref<boolean>
  selectedIds: Ref<string[]>
  name: Ref<string>
  like: MutationState<{ photoId: string; liked: boolean }>
  comment: MutationState<{ photoId: string; text: string }>
  submit: MutationState<{ email: string; message: string }>
  toggleSelection: (photoId: string) => void
}
