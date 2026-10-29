<script setup lang="ts">
import type {
  GalleryWithPhotos,
  LikeVariables,
  CommentVariables,
  SelectionVariables,
  StatusError,
} from '@/app/features/gallery/types/interaction'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { apiFetch } from '@/app/core/clients/api'
import { getSession } from '@/app/shared/services/session'
import { galleryThemeKey } from '../constants/theme'
import { galleryFeedbackKey } from '../constants/feedback'
import type { GalleryFeedback } from '../types/feedback.ts'
import type { PublicPhoto, CreateOrderPayload } from '../types/index.ts'
import GalleryThemeMasonry from '../components/themes/gallery-theme-masonry.vue'
import GalleryThemeInstagram from '../components/themes/gallery-theme-instagram.vue'
import GalleryThemeClassic from '../components/themes/gallery-theme-classic.vue'
import GalleryThemeFeatured from '../components/themes/gallery-theme-featured.vue'
import GalleryThemeCarousel from '../components/themes/gallery-theme-carousel.vue'

// ---------------------------------------------------------------------------
// Contrato do componente
// ---------------------------------------------------------------------------
defineOptions({ name: 'GalleryPublicPage' })

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
const ACCESS_CODE_HEADER = 'X-Gallery-Access-Code'
const FORBIDDEN_STATUS = 403
const DEFAULT_THEME = 'masonry'
const SKELETON_COUNT = 12
const themeComponents = {
  masonry: GalleryThemeMasonry,
  instagram: GalleryThemeInstagram,
  classic: GalleryThemeClassic,
  featured: GalleryThemeFeatured,
  carousel: GalleryThemeCarousel,
}

// ---------------------------------------------------------------------------
// Composables
// ---------------------------------------------------------------------------
const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const toast = useToast()
const layoutTheme = inject(galleryThemeKey)

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
const name = useLocalStorage('gallery-visitor-name', '')
const selecting = ref(false)
const activeTag = ref<string | null>(null)
const lightboxOpen = ref(false)
const activePhotoIndex = ref(0)
const likingPhotos = reactive(new Set<string>())

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------
const { data: session, isPending: loadingSession } = useQuery({
  queryKey: ['auth', 'session'],
  queryFn: getSession,
  retry: false,
})

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const slug = computed(getSlug)

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
const submittedCode = useSessionStorage<string>(computed(getAccessStorageKey), '')
const selectedIds = useSessionStorage<string[]>(computed(getSelectionStorageKey), [])

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const baseUrl = computed(getBaseUrl)
const headers = computed(getHeaders)
const user = computed(getUser)

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------
const {
  data: gallery,
  isPending: loadingGallery,
  isFetching,
  error,
  refetch: refetchGallery,
} = useQuery({
  queryKey: computed(getGalleryKey),
  queryFn: fetchGallery,
  enabled: computed(getGalleryEnabled),
  retry: false,
})

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const isAuthenticated = computed(getIsAuthenticated)
const loginRoute = computed(getLoginRoute)
const allPhotos = computed(getAllPhotos)
const photos = computed(getPhotos)
const activePhoto = computed<PublicPhoto | null>(getActivePhoto)
const theme = computed(getTheme)
const themeComponent = computed(getThemeComponent)

// ---------------------------------------------------------------------------
// Watchers e ciclo de vida
// ---------------------------------------------------------------------------
watchEffect(() => {
  if (layoutTheme) layoutTheme.value = theme.value
})
onBeforeUnmount(() => {
  if (layoutTheme) layoutTheme.value = DEFAULT_THEME
})

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const needsCode = computed(getNeedsCode)
const photosNoun = computed(getPhotosNoun)
const buyLabel = computed(getBuyLabel)
const includedDescription = computed(getIncludedDescription)
const feedbackKey = computed(getFeedbackKey)

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------
const { data, isPending, isError, refetch } = useQuery({
  queryKey: feedbackKey,
  queryFn: fetchFeedback,
  enabled: computed(getFeedbackEnabled),
  retry: false,
})

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------
const like = useMutation({
  mutationFn: postLike,
  onMutate: startLike,
  onSuccess: refreshFeedback,
  onError: notifySaveError,
  onSettled: finishLike,
})
const comment = useMutation({
  mutationFn: postComment,
  onSuccess: refreshFeedback,
  onError: notifySaveError,
})
const submit = useMutation({
  mutationFn: postSelection,
  onSuccess: handleSelectionSubmitted,
  onError: notifySaveError,
})

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
const feedback = {
  likingPhotos,
  user,
  isAuthenticated,
  loadingSession,
  loginRoute,
  requireLogin,
  data,
  isPending,
  isError,
  refetch,
  selecting,
  selectedIds,
  name,
  like,
  comment,
  submit,
  toggleSelection,
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------
const orderMutation = useMutation({
  mutationFn: startCheckout,
})

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------
provide(galleryFeedbackKey, feedback)

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
const feedbackErrorActions = [{ label: 'Tentar novamente', onClick: retryFeedback }]

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const selectionButtonLabel = computed(getSelectionButtonLabel)
const selectionButtonVariant = computed(getSelectionButtonVariant)

// ---------------------------------------------------------------------------
// Watchers e ciclo de vida
// ---------------------------------------------------------------------------
watch(getSlugAndSelectionFlag, exitSelectionMode)
watch(allPhotos, pruneSelection)

// ---------------------------------------------------------------------------
// Funções
// ---------------------------------------------------------------------------

async function requireLogin() {
  if (isAuthenticated.value) return true
  await router.push(loginRoute.value)
  return false
}

function unlockGallery(code: string) {
  if (submittedCode.value === code) {
    void refetchGallery()
    return
  }
  submittedCode.value = code
}

function notifySaveError() {
  toast.add({ title: 'Não foi possível salvar. Tente novamente.', color: 'error' })
}

function postLike({ photoId, liked }: LikeVariables) {
  return apiFetch(`${baseUrl.value}/like/`, {
    method: 'POST',
    headers: headers.value,
    body: { photo_id: photoId, liked },
  })
}

function startLike({ photoId }: LikeVariables) {
  likingPhotos.add(photoId)
}

function finishLike(_data: unknown, _error: unknown, { photoId }: LikeVariables) {
  likingPhotos.delete(photoId)
}

function postComment({ photoId, text }: CommentVariables) {
  return apiFetch(`${baseUrl.value}/comment/`, {
    method: 'POST',
    headers: headers.value,
    body: { photo_id: photoId, text },
  })
}

function postSelection({ email, message }: SelectionVariables) {
  return apiFetch(`${baseUrl.value}/selection/`, {
    method: 'POST',
    headers: headers.value,
    body: { name: name.value, email, message, photo_ids: selectedIds.value },
  })
}

function withoutId(ids: string[], target: string) {
  const result: string[] = []
  for (const id of ids) {
    if (id !== target) result.push(id)
  }
  return result
}

function toggleSelection(photoId: string) {
  if (submit.isPending.value) return
  selectedIds.value = selectedIds.value.includes(photoId)
    ? withoutId(selectedIds.value, photoId)
    : [...selectedIds.value, photoId]
}

function toggleSelecting() {
  selecting.value = !selecting.value
}

function exitSelectionMode() {
  selecting.value = false
}

function pruneSelection(availablePhotos: PublicPhoto[]) {
  if (!gallery.value) return

  const availableIds = new Set<string>()
  for (const photo of availablePhotos) availableIds.add(photo.id)

  const kept: string[] = []
  for (const id of selectedIds.value) {
    if (availableIds.has(id)) kept.push(id)
  }
  selectedIds.value = kept
}

function findPhotoIndex(photoId: string) {
  for (let index = 0; index < photos.value.length; index++) {
    if (photos.value[index]?.id === photoId) return index
  }
  return -1
}

function openPhoto(photo: PublicPhoto) {
  if (gallery.value?.allow_selection && selecting.value) {
    toggleSelection(photo.id)
    return
  }

  const index = findPhotoIndex(photo.id)
  if (index === -1) return

  activePhotoIndex.value = index
  lightboxOpen.value = true
}

function prevPhoto() {
  if (activePhotoIndex.value > 0) activePhotoIndex.value--
  else activePhotoIndex.value = photos.value.length - 1
}

function nextPhoto() {
  if (activePhotoIndex.value < photos.value.length - 1) activePhotoIndex.value++
  else activePhotoIndex.value = 0
}

async function startCheckout(payload: CreateOrderPayload) {
  const target = {
    path: `/g/${String(route.params.slug)}/checkout`,
    query: payload.gallery_id ? { package: '1' } : { photo: payload.photo_ids?.join(',') },
  }

  const currentSession = await getSession()
  if (!currentSession?.meta.is_authenticated) {
    await router.push({
      name: 'gallery.login',
      query: { next: router.resolve(target).fullPath },
    })
    return
  }

  await router.push(target)
}

// ---------------------------------------------------------------------------
// Funções: computed
// ---------------------------------------------------------------------------

function getSlug() {
  return route.params.slug as string
}

function getAccessStorageKey() {
  return `gallery-access:${slug.value}`
}

function getSelectionStorageKey() {
  return `gallery-selection:${slug.value}`
}

function getBaseUrl() {
  return `/api/galleries/public/${encodeURIComponent(slug.value)}`
}

function getHeaders() {
  return { [ACCESS_CODE_HEADER]: submittedCode.value }
}

function getUser() {
  return session.value?.data.user
}

function getIsAuthenticated() {
  return !!session.value?.meta.is_authenticated
}

function getLoginRoute() {
  return { path: '/gallery/login', query: { next: route.fullPath } }
}

function getGalleryKey() {
  return ['galleries', 'slug', slug.value, submittedCode.value, user.value?.id ?? 'anonymous']
}

function getGalleryEnabled() {
  return !!slug.value
}

function getAllPhotos() {
  return gallery.value?.photos ?? []
}

function getPhotos() {
  if (!allPhotos.value) return []
  if (!activeTag.value) return allPhotos.value
  // Filtragem client-side: tags estão na gallery; para filtrar por foto
  // usaríamos um campo na foto — por ora filtra pela tag da galeria
  return allPhotos.value
}

function getActivePhoto() {
  return photos.value[activePhotoIndex.value] ?? null
}

function getTheme() {
  return gallery.value?.theme ?? DEFAULT_THEME
}

function getNeedsCode() {
  return (error.value as StatusError | null)?.statusCode === FORBIDDEN_STATUS
}

function getPhotosNoun() {
  return allPhotos.value.length === 1 ? 'fotografia' : 'fotografias'
}

function getBuyLabel() {
  const current = gallery.value
  if (!current?.gallery_price) return ''
  const price = Number(current.package_remaining ?? current.gallery_price).toFixed(2)
  return `Comprar galeria · ${current.gallery_price_currency} ${price}`
}

function getFeedbackKey() {
  return ['gallery-feedback', slug.value, submittedCode.value, user.value?.id ?? 'anonymous']
}

function getFeedbackEnabled() {
  return !!gallery.value
}

function getSlugAndSelectionFlag() {
  return [slug.value, gallery.value?.allow_selection]
}

function getSelectionButtonLabel() {
  return selecting.value ? 'Selecionando fotos' : 'Selecionar fotos'
}

function getSelectionButtonVariant() {
  return selecting.value ? 'soft' : 'outline'
}

function getSkeletonStyle(index: number) {
  return { height: `${180 + (index % 4) * 60}px` }
}

function getThemeComponent() {
  return themeComponents[theme.value as keyof typeof themeComponents] ?? GalleryThemeMasonry
}

function getIncludedDescription() {
  const current = gallery.value
  if (!current) return ''
  if (!isAuthenticated.value)
    return `Seu trabalho inclui até ${current.included_photo_limit} fotos por cliente vinculado. Entre na sua conta para escolher.`
  if (!current.included_eligible)
    return 'As fotos incluídas estão disponíveis para os clientes vinculados a este trabalho. Se precisar de acesso, fale com o fotógrafo.'
  const used = current.included_used ?? 0
  const remaining = current.included_remaining ?? 0
  const progress =
    used > (current.included_photo_limit ?? 0)
      ? `Você já escolheu ${used} fotos incluídas.`
      : `Você já escolheu ${used} de ${current.included_photo_limit} fotos incluídas.`
  const nextStep =
    remaining > 0
      ? ` Ainda pode escolher ${remaining}. Abra uma foto para confirmar sua escolha.`
      : ' Todas as fotos incluídas já foram escolhidas.'
  const extras =
    current.enable_sales && current.default_photo_price
      ? ` Fotos extras custam ${new Intl.NumberFormat('pt-BR', { style: 'currency', currency: current.gallery_price_currency }).format(Number(current.default_photo_price))} cada, salvo fotos com preço próprio.`
      : ' A venda de fotos extras não está ativa.'
  return progress + nextStep + extras
}

// ---------------------------------------------------------------------------
// Funções: mutations
// ---------------------------------------------------------------------------

async function handleSelectionSubmitted() {
  selectedIds.value = []
  selecting.value = false
  toast.add({ title: 'Seleção enviada ao fotógrafo', color: 'success' })
  await refreshFeedback()
}

function handleBuyGallery() {
  if (!gallery.value) return
  orderMutation.mutate({ gallery_id: gallery.value.id })
}

// ---------------------------------------------------------------------------
// Funções: queries
// ---------------------------------------------------------------------------

function fetchGallery() {
  return apiFetch<GalleryWithPhotos>(`${baseUrl.value}/`, { headers: headers.value })
}

function fetchFeedback() {
  return apiFetch<GalleryFeedback>(`${baseUrl.value}/feedback/`, { headers: headers.value })
}

function refreshFeedback() {
  return queryClient.invalidateQueries({ queryKey: feedbackKey.value })
}

function retryFeedback() {
  refetch()
}
</script>

<template>
  <div class="gallery-page" :data-theme="theme">
    <CGalleryAccessForm
      v-if="needsCode"
      :loading="isFetching"
      :invalid="!!submittedCode"
      @submit="unlockGallery"
    />
    <div v-else-if="error" class="flex min-h-[50dvh] items-center justify-center">
      <UEmpty
        title="Galeria não encontrada"
        description="Esta galeria não existe ou não está disponível."
        icon="i-lucide-image-off"
      />
    </div>

    <component :is="themeComponent" v-else :photos="photos" :gallery="gallery" @select="openPhoto">
      <template #heading>
        <div class="min-w-0 max-w-2xl space-y-4">
          <p
            class="gallery-eyebrow flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.2em] text-muted"
          >
            <span>Coleção</span><span class="size-0.5 rounded-full bg-current" />
            <span>{{ allPhotos.length }} {{ photosNoun }}</span>
          </p>
          <USkeleton v-if="loadingGallery" class="h-12 w-56" />
          <h1
            v-else
            class="break-words font-serif text-4xl leading-tight tracking-tight text-highlighted sm:text-5xl lg:text-6xl"
          >
            {{ gallery?.name }}
          </h1>
          <p
            v-if="gallery?.description"
            class="max-w-xl whitespace-pre-line text-sm leading-relaxed text-muted sm:text-base"
          >
            {{ gallery.description }}
          </p>
        </div>
      </template>
      <template #actions>
        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <UButton
            v-if="gallery?.allow_selection"
            icon="i-lucide-circle-check"
            color="neutral"
            size="md"
            class="gallery-action rounded-full px-5"
            :label="selectionButtonLabel"
            :variant="selectionButtonVariant"
            :disabled="feedback.submit.isPending.value"
            @click="toggleSelecting"
          />
          <UButton
            v-if="gallery?.enable_sales && gallery?.gallery_price"
            icon="i-lucide-shopping-bag"
            color="neutral"
            size="md"
            class="gallery-action rounded-full px-5"
            :label="buyLabel"
            :loading="orderMutation.isPending.value"
            @click="handleBuyGallery"
          />
        </div>
      </template>
      <template #controls>
        <UAlert
          v-if="gallery?.included_photo_mode === 'all'"
          title="Todos os originais incluídos"
          description="Você pode baixar qualquer original desta galeria, sem pagamento. Abra uma foto e escolha Baixar original."
          icon="i-lucide-download"
          color="neutral"
          variant="subtle"
        />
        <UAlert
          v-if="gallery?.included_photo_mode === 'client'"
          icon="i-lucide-gift"
          title="Fotos incluídas no seu trabalho"
          color="neutral"
          variant="subtle"
          :description="includedDescription"
          :actions="!isAuthenticated ? [{ label: 'Entrar', to: loginRoute }] : []"
        />
        <UAlert
          v-if="feedback.isError.value"
          title="Não foi possível carregar suas interações."
          color="error"
          variant="subtle"
          :actions="feedbackErrorActions"
        />
        <CGallerySelectionBar v-if="gallery?.allow_selection" :photos="allPhotos" />

        <template v-if="gallery?.tags?.length">
          <CGalleryFilters v-model="activeTag" :tags="gallery.tags" />
        </template>
      </template>

      <template v-if="loadingGallery || !photos.length" #photos>
        <div v-if="loadingGallery" class="columns-1 sm:columns-2 lg:columns-3 xl:columns-4 gap-5">
          <div v-for="i in SKELETON_COUNT" :key="i" class="break-inside-avoid mb-5">
            <USkeleton class="w-full rounded-xl" :style="getSkeletonStyle(i)" />
          </div>
        </div>

        <div v-else class="flex items-center justify-center py-24">
          <UEmpty
            title="Nenhuma foto"
            description="Esta galeria ainda não possui fotos publicadas."
            icon="i-lucide-camera-off"
          />
        </div>
      </template>
    </component>

    <CGalleryPhotoLightbox
      v-if="gallery && activePhoto"
      v-model:open="lightboxOpen"
      :photo="activePhoto"
      :photo-index="activePhotoIndex"
      :total-photos="photos.length"
      :gallery="gallery"
      @prev="prevPhoto"
      @next="nextPhoto"
    />
  </div>
</template>
