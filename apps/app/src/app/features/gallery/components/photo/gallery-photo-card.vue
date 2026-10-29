<script setup lang="ts">
import CPhotoFeedback from './gallery-photo-feedback.vue'
import { downloadPhoto } from '@/app/features/gallery/utils/photo.ts'
import { getSession } from '@/app/shared/services/session'
import { useMutation } from '@tanstack/vue-query'
import type { PublicPhoto, Gallery, CreateOrderPayload } from '@/app/features/gallery/types'
import { galleryFeedbackKey } from '@/app/features/gallery/constants/feedback'

// ---------------------------------------------------------------------------
// Contrato do componente
// ---------------------------------------------------------------------------
const props = defineProps<{
  photo: PublicPhoto
  gallery: Gallery
}>()
const emit = defineEmits<{
  click: [photo: PublicPhoto]
}>()

// ---------------------------------------------------------------------------
// Composables
// ---------------------------------------------------------------------------
const router = useRouter()
const route = useRoute()
const feedback = inject(galleryFeedbackKey)
const toast = useToast()

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const selected = computed(getSelected)
// Imagem exibida: watermarked se habilitado, senão preview, senão thumbnail
const displayUrl = computed(getDisplayUrl)
// Aspect ratio para reservar espaço antes da imagem carregar
const aspectRatio = computed(getAspectRatio)
const canDownload = computed(getCanDownload)
const canBuy = computed(getCanBuy)
const priceLabel = computed(getPriceLabel)

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------
const orderMutation = useMutation({
  mutationFn: submitOrderMutation,
})
const download = useMutation({
  mutationFn: submitDownload,
  onError: handleDownloadError,
})

// ---------------------------------------------------------------------------
// Funções: computed
// ---------------------------------------------------------------------------

function getSelected() {
  return feedback?.selectedIds.value.includes(props.photo.id) && feedback.selecting.value
}

function getDisplayUrl() {
  return props.photo.watermarked_preview ?? props.photo.preview ?? props.photo.thumbnail
}

function getAspectRatio() {
  if (props.photo.width && props.photo.height) {
    return `${props.photo.width} / ${props.photo.height}`
  }
  return '4 / 3'
}

function getCanDownload() {
  return props.photo?.can_download ?? false
}

function getCanBuy() {
  return (
    props.gallery.enable_sales && props.gallery.allow_individual_purchase && !!props.photo.price
  )
}

function getPriceLabel() {
  if (!props.photo.price) return null
  return `${props.photo.price_currency} ${parseFloat(props.photo.price).toFixed(2)}`
}

// ---------------------------------------------------------------------------
// Funções: mutations
// ---------------------------------------------------------------------------

function handleBuy(event: Event) {
  event.stopPropagation()
  orderMutation.mutate({
    photo_ids: [props.photo.id],
  })
}

async function submitOrderMutation(payload: CreateOrderPayload) {
  const target = {
    path: `/g/${String(route.params.slug)}/checkout`,
    query: payload.gallery_id ? { package: '1' } : { photo: payload.photo_ids?.join(',') },
  }
  const session = await getSession()
  if (!session?.meta.is_authenticated) {
    await router.push({
      name: 'gallery.login',
      query: { next: router.resolve(target).fullPath },
    })
  } else {
    await router.push(target)
  }
}

function submitDownload() {
  return downloadPhoto(props.gallery, props.photo)
}

function handleDownloadError() {
  return toast.add({
    title: 'Não foi possível baixar esta foto. Atualize a galeria e tente novamente.',
    color: 'error',
  })
}
</script>

<template>
  <div
    class="group relative cursor-pointer overflow-hidden rounded-2xl bg-elevated transition-shadow duration-300 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
    :class="{ 'ring-2 ring-primary ring-offset-2 ring-offset-default': selected }"
    :style="{ aspectRatio }"
    role="button"
    tabindex="0"
    :aria-label="`${feedback?.selecting.value ? 'Selecionar foto' : 'Ver foto'} ${photo.name}`"
    :aria-pressed="feedback?.selecting.value ? !!selected : undefined"
    @click="emit('click', photo)"
    @keydown.enter.self="emit('click', photo)"
    @keydown.space.prevent.self="emit('click', photo)"
  >
    <!-- Imagem -->
    <img
      v-if="displayUrl"
      :src="displayUrl"
      :alt="photo.name"
      class="h-full w-full object-cover transition-transform duration-700 motion-safe:group-hover:scale-[1.025]"
      loading="lazy"
      decoding="async"
    />

    <!-- Skeleton enquanto carrega -->
    <USkeleton v-else class="absolute inset-0 rounded-xl" />

    <!-- Overlay ao hover -->
    <div
      class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-4 gap-3"
    >
      <!-- Nome da foto -->
      <p class="text-[11px] font-medium text-white/90 truncate leading-none tracking-wide">
        {{ photo.name }}
      </p>

      <!-- Ações -->
      <div class="flex flex-wrap items-center gap-2" @click.stop>
        <CPhotoFeedback :photo="photo" :gallery="gallery" />
        <CGalleryIncludedPhotoAction :gallery="gallery" :photo="photo" />
        <UTooltip v-if="gallery.allow_comments && !feedback?.selecting.value" text="Comentar foto">
          <UButton
            icon="i-lucide-message-circle"
            aria-label="Comentar foto"
            size="xs"
            color="neutral"
            variant="soft"
            @click="emit('click', photo)"
          />
        </UTooltip>
        <!-- Download -->
        <UTooltip v-if="canDownload" :text="`Baixar prévia de ${photo.name}`">
          <UButton
            icon="i-lucide-download"
            size="xs"
            color="neutral"
            variant="ghost"
            class="rounded-full backdrop-blur-md bg-white/15 hover:bg-white/25 text-white ring-0"
            :aria-label="`Baixar prévia de ${photo.name}`"
            @click.stop="download.mutate()"
            :loading="download.isPending.value"
          />
        </UTooltip>

        <!-- Comprar foto -->
        <UButton
          v-if="canBuy"
          :label="priceLabel ?? 'Comprar'"
          size="xs"
          color="primary"
          :loading="orderMutation.isPending.value"
          @click="handleBuy"
        />
      </div>
    </div>
    <div
      v-if="feedback?.selecting.value"
      class="pointer-events-none absolute right-3 top-3 flex size-7 items-center justify-center rounded-full shadow-sm backdrop-blur-md"
      :class="selected ? 'bg-primary text-inverted' : 'bg-black/25 text-white'"
    >
      <UIcon :name="selected ? 'i-lucide-check' : 'i-lucide-circle'" class="size-4" />
    </div>
  </div>
</template>
