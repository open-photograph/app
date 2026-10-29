<script setup lang="ts">
import { galleryFeedbackKey } from '../constants/feedback'
import type { PublicPhoto } from '../types'

// ---------------------------------------------------------------------------
// Contrato do componente
// ---------------------------------------------------------------------------
const props = defineProps<{ photos: PublicPhoto[] }>()

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
const feedback = inject(galleryFeedbackKey)!

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
const email = ref('')
const message = ref('')
const reviewing = ref(false)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const selectedPhotos = computed(getSelectedPhotos)

// ---------------------------------------------------------------------------
// Watchers e ciclo de vida
// ---------------------------------------------------------------------------
watch(
  () => feedback.submit.isSuccess.value,
  (success) => {
    if (success) reviewing.value = false
  },
)

// ---------------------------------------------------------------------------
// Funções: computed
// ---------------------------------------------------------------------------

function getSelectedPhotos() {
  return props.photos.filter((photo) => feedback.selectedIds.value.includes(photo.id))
}
</script>

<template>
  <UCard
    v-if="feedback.selecting.value"
    :ui="{ body: 'space-y-4 p-4 sm:p-4' }"
    class="sticky top-20 z-10"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="text-sm font-medium">{{ selectedPhotos.length }} fotos selecionadas</p>
        <p class="text-xs text-muted">Marque suas favoritas e envie ao fotógrafo.</p>
      </div>
      <div class="flex gap-2">
        <UButton
          label="Sair da seleção"
          color="neutral"
          variant="ghost"
          size="sm"
          :disabled="feedback.submit.isPending.value"
          @click="feedback.selecting.value = false"
        />
        <UButton
          :label="reviewing ? 'Ocultar revisão' : 'Revisar e enviar'"
          icon="i-lucide-send"
          color="neutral"
          size="sm"
          :disabled="!selectedPhotos.length"
          @click="reviewing = !reviewing"
        />
      </div>
    </div>
    <template v-if="reviewing">
      <div class="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
        <UButton
          v-for="photo in selectedPhotos"
          :key="photo.id"
          :label="photo.name"
          icon="i-lucide-x"
          color="neutral"
          variant="soft"
          size="xs"
          :disabled="feedback.submit.isPending.value"
          @click="feedback.toggleSelection(photo.id)"
        />
      </div>
      <form
        class="grid gap-3 sm:grid-cols-2"
        @submit.prevent="feedback.submit.mutate({ email, message })"
      >
        <UFormField label="Seu nome"
          ><UInput v-model="feedback.name.value" required maxlength="120" class="w-full"
        /></UFormField>
        <UFormField label="Seu e-mail"
          ><UInput v-model="email" type="email" required maxlength="254" class="w-full"
        /></UFormField>
        <UFormField label="Mensagem (opcional)" class="sm:col-span-2"
          ><UTextarea v-model="message" maxlength="2000" class="w-full"
        /></UFormField>
        <UButton
          type="submit"
          label="Enviar seleção"
          icon="i-lucide-send"
          color="neutral"
          class="justify-center sm:col-span-2"
          :loading="feedback.submit.isPending.value"
          :disabled="!selectedPhotos.length || !feedback.name.value.trim() || !email"
        />
      </form>
    </template>
  </UCard>
  <p v-else-if="feedback.data.value?.selections.length" class="text-sm text-muted">
    Sua última seleção foi enviada com {{ feedback.data.value.selections[0]?.photos.length }} fotos.
  </p>
</template>
