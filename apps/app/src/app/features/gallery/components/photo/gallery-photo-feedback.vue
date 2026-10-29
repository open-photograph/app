<script setup lang="ts">
import { galleryFeedbackKey } from '@/app/features/gallery/constants/feedback'
import type { Gallery, PublicPhoto } from '@/app/features/gallery/types'

// ---------------------------------------------------------------------------
// Contrato do componente
// ---------------------------------------------------------------------------
const props = defineProps<{ photo: PublicPhoto; gallery: Gallery; expanded?: boolean }>()

// ---------------------------------------------------------------------------
// Composables
// ---------------------------------------------------------------------------
const feedback = inject(galleryFeedbackKey)

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
const text = ref('')
const commentError = ref('')

// ---------------------------------------------------------------------------
// Watchers e ciclo de vida
// ---------------------------------------------------------------------------
watch(
  () => props.photo.id,
  () => {
    text.value = ''
    commentError.value = ''
  },
)

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
const dateFormatter = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' })

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const liked = computed(getLiked)
const selected = computed(getSelected)
const comments = computed(getComments)

// ---------------------------------------------------------------------------
// Funções
// ---------------------------------------------------------------------------

async function toggleLike() {
  if (!feedback || !(await feedback.requireLogin())) return
  feedback.like.mutate({ photoId: props.photo.id, liked: !liked.value })
}

async function sendComment() {
  if (!feedback || !text.value.trim() || feedback.comment.isPending.value) return
  if (!(await feedback.requireLogin())) return
  commentError.value = ''
  try {
    await feedback.comment.mutateAsync({ photoId: props.photo.id, text: text.value.trim() })
    text.value = ''
  } catch {
    commentError.value =
      'Não foi possível enviar. Seu comentário foi mantido para tentar novamente.'
  }
}

// ---------------------------------------------------------------------------
// Funções: computed
// ---------------------------------------------------------------------------

function getLiked() {
  return feedback?.data.value?.liked_photo_ids.includes(props.photo.id) ?? false
}

function getSelected() {
  return feedback?.selectedIds.value.includes(props.photo.id) ?? false
}

function getComments() {
  return feedback?.data.value?.comments.filter((comment) => comment.photo === props.photo.id) ?? []
}
</script>

<template>
  <div
    v-if="feedback"
    :class="expanded ? 'flex min-h-0 flex-1 flex-col' : ''"
    @click.stop
    @keydown.stop
  >
    <div
      v-if="gallery.allow_likes || (gallery.allow_selection && feedback.selecting.value)"
      class="flex flex-wrap items-center gap-2"
      :class="expanded ? 'shrink-0 border-b border-default/60 p-5' : ''"
    >
      <UButton
        v-if="gallery.allow_likes"
        icon="i-lucide-heart"
        :ui="{ leadingIcon: liked ? 'fill-current' : '' }"
        :label="
          expanded
            ? liked
              ? 'Curtida'
              : 'Curtir foto'
            : String(feedback.data.value?.like_counts[photo.id] ?? 0)
        "
        :aria-label="liked ? 'Descurtir foto' : 'Curtir foto'"
        :aria-pressed="liked"
        :color="liked ? 'error' : 'neutral'"
        :variant="liked ? 'soft' : 'ghost'"
        size="sm"
        class="min-h-9 rounded-full"
        :loading="feedback.likingPhotos.has(photo.id)"
        :disabled="
          feedback.loadingSession.value || feedback.isPending.value || feedback.isError.value
        "
        @click="toggleLike"
      />
      <span v-if="expanded && gallery.allow_likes" class="text-xs text-muted tabular-nums"
        >{{ feedback.data.value?.like_counts[photo.id] ?? 0 }} curtidas</span
      >
      <UButton
        v-if="gallery.allow_selection && feedback.selecting.value"
        :icon="selected ? 'i-lucide-circle-check' : 'i-lucide-circle'"
        :label="expanded ? (selected ? 'Selecionada' : 'Selecionar') : undefined"
        :aria-label="selected ? 'Remover da seleção' : 'Selecionar foto'"
        :aria-pressed="selected"
        :color="selected ? 'primary' : 'neutral'"
        variant="soft"
        size="sm"
        class="min-h-9 rounded-full"
        :disabled="feedback.submit.isPending.value"
        @click="feedback.toggleSelection(photo.id)"
      />
    </div>
    <template v-if="expanded && gallery.allow_comments">
      <div
        class="min-h-0 flex-1 space-y-5 overflow-y-auto p-5 max-md:max-h-80"
        role="region"
        aria-label="Comentários da foto"
        tabindex="0"
      >
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-sm font-medium text-highlighted">Comentários</h3>
          <UBadge :label="String(comments.length)" color="neutral" variant="subtle" />
        </div>
        <div
          v-if="feedback.isPending.value"
          class="space-y-4"
          role="status"
          aria-label="Carregando comentários"
        >
          <USkeleton v-for="item in 3" :key="item" class="h-16 rounded-xl" />
        </div>
        <UAlert
          v-else-if="feedback.isError.value"
          title="Não foi possível carregar a conversa."
          color="error"
          variant="subtle"
          :actions="[{ label: 'Tentar novamente', onClick: () => feedback?.refetch() }]"
        />
        <div v-else-if="!comments.length" class="flex flex-col items-center gap-3 py-8 text-center">
          <UIcon name="i-lucide-messages-square" class="size-7 text-dimmed" />
          <p class="text-sm font-medium text-highlighted">O que chamou sua atenção?</p>
          <p class="max-w-64 text-xs leading-relaxed text-muted">
            Compartilhe o que gostou ou deixe uma sugestão para esta foto.
          </p>
        </div>
        <ol v-else class="space-y-6">
          <li v-for="comment in comments" :key="comment.id" class="flex gap-3">
            <UAvatar :alt="comment.name" size="sm" class="mt-0.5 shrink-0" />
            <div class="min-w-0 flex-1 space-y-2">
              <div class="space-y-0.5">
                <p class="break-words text-sm font-medium text-highlighted">{{ comment.name }}</p>
                <time :datetime="comment.created_at" class="block text-[11px] text-dimmed">{{
                  dateFormatter.format(new Date(comment.created_at))
                }}</time>
              </div>
              <p class="whitespace-pre-wrap break-words text-sm leading-relaxed text-muted">
                {{ comment.text }}
              </p>
            </div>
          </li>
        </ol>
      </div>
      <div class="shrink-0 border-t border-default/60 bg-default p-5">
        <USkeleton v-if="feedback.loadingSession.value" class="h-24 rounded-xl" />
        <div v-else-if="!feedback.isAuthenticated.value" class="space-y-3">
          <p class="text-xs leading-relaxed text-muted">
            Entre na sua conta para curtir e participar da conversa.
          </p>
          <UButton
            :to="feedback.loginRoute.value"
            label="Entrar para comentar"
            icon="i-lucide-log-in"
            color="neutral"
            variant="outline"
            class="rounded-full"
            block
          />
        </div>
        <form v-else class="space-y-3" @submit.prevent="sendComment">
          <div class="flex items-center gap-2 text-xs text-muted">
            <UAvatar :alt="feedback.user.value?.display || 'Sua conta'" size="xs" />
            <span class="truncate">{{ feedback.user.value?.display || 'Sua conta' }}</span>
          </div>
          <UFormField label="Seu comentário" name="comment">
            <UTextarea
              v-model="text"
              required
              maxlength="2000"
              :rows="3"
              autoresize
              :maxrows="6"
              class="w-full"
              size="md"
              placeholder="Escreva sobre esta foto…"
              :disabled="feedback.comment.isPending.value"
            />
          </UFormField>
          <UAlert v-if="commentError" :title="commentError" color="error" variant="subtle" />
          <div class="flex items-center justify-between gap-3">
            <span class="text-[11px] text-dimmed tabular-nums">{{ text.length }} / 2000</span>
            <UButton
              type="submit"
              label="Comentar"
              trailing-icon="i-lucide-send"
              color="neutral"
              size="sm"
              class="rounded-full px-4"
              :disabled="!text.trim() || feedback.isError.value || feedback.isPending.value"
              :loading="feedback.comment.isPending.value"
            />
          </div>
        </form>
      </div>
    </template>
  </div>
</template>
