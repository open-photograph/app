import type { InjectionKey } from 'vue'
import type { GalleryFeedbackContext } from '../types/feedback'

export const galleryFeedbackKey: InjectionKey<GalleryFeedbackContext> = Symbol('gallery-feedback')
