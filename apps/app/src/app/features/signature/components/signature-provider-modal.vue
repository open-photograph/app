<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { apiFetch } from '@/app/core/clients/api'
import type { SignatureCatalog, SignatureProvider } from '@/app/features/signature/types/provider'
import { apiErrorMessage } from '@/app/shared/utils/api-error'

const props = defineProps<{ open?: boolean; provider: SignatureProvider | null }>()
const emit = defineEmits<{ close: []; 'update:open': [value: boolean]; 'after:leave': [] }>()
const queryClient = useQueryClient()
const state = reactive({
  provider: '',
  is_active: true,
})
const errorMessage = ref('')
const {
  data: catalog,
  isPending: loadingCatalog,
  isError: catalogError,
  refetch: refetchCatalog,
} = useQuery({
  queryKey: ['signature-catalog'],
  queryFn: () => apiFetch<SignatureCatalog>('/api/signature-providers/catalog/'),
})
watch(
  [() => props.open, () => props.provider],
  ([open]) => {
    if (open) {
      Object.assign(state, {
        provider: props.provider?.provider ?? catalog.value?.providers[0]?.value ?? '',
        is_active: props.provider?.is_active ?? true,
      })
      errorMessage.value = ''
    }
  },
  { immediate: true },
)
watch(catalog, (value) => {
  if (!state.provider && props.open)
    state.provider = props.provider?.provider ?? value?.providers[0]?.value ?? ''
})
const save = useMutation({
  mutationFn: () =>
    apiFetch(
      props.provider
        ? `/api/signature-providers/${props.provider.id}/`
        : '/api/signature-providers/',
      {
        method: props.provider ? 'PATCH' : 'POST',
        body: { ...state },
      },
    ),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ['signature-providers'] })
    emit('close')
  },
  onError: (error) => {
    errorMessage.value = apiErrorMessage(error)
  },
})
</script>

<template>
  <UModal
    :open="open"
    :title="provider ? 'Editar configuração' : 'Configurar assinatura'"
    :dismissible="!save.isPending.value"
    @update:open="emit('update:open', $event)"
    @after:leave="emit('after:leave')"
  >
    <template #body>
      <UForm
        id="signature-provider-form"
        :state="state"
        class="space-y-5"
        :disabled="save.isPending.value"
        @submit="save.mutate()"
      >
        <UAlert
          v-if="catalogError"
          title="Não foi possível carregar os serviços de assinatura."
          color="error"
          :actions="[{ label: 'Tentar novamente', onClick: () => refetchCatalog() }]"
        />
        <UAlert v-if="errorMessage" :title="errorMessage" color="error" />
        <UFormField label="Provider" required
          ><USelect
            v-model="state.provider"
            :items="catalog?.providers ?? []"
            :loading="loadingCatalog"
            class="w-full"
            :disabled="!!provider || loadingCatalog || catalogError"
        /></UFormField>
        <USwitch v-model="state.is_active" label="Disponível para novos contratos" />
      </UForm>
    </template>
    <template #footer
      ><div class="flex w-full justify-end gap-2">
        <UButton
          label="Cancelar"
          color="neutral"
          variant="ghost"
          :disabled="save.isPending.value"
          @click="emit('close')"
        />
        <UButton
          label="Salvar configuração"
          color="neutral"
          type="submit"
          form="signature-provider-form"
          :loading="save.isPending.value"
          :disabled="!state.provider || catalogError"
        /></div
    ></template>
  </UModal>
</template>
