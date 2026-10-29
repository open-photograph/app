<script setup lang="ts">
defineOptions({ name: 'AdminContractDetailPage' })
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { apiFetch } from '@/app/core/clients/api'
import type { Contract } from '../../types/contract/contract'
import { contractStatusLabels } from '../../constants/contract'
import { apiErrorMessage } from '@/app/shared/utils/api-error'

const route = useRoute()
const contractId = computed(() => String(route.params.contractId))
const queryClient = useQueryClient()
const toast = useToast()
const state = reactive({ title: '', content: '' })
const dirty = ref(false)
const errorMessage = ref('')
const recoveryDocumentId = ref('')
const {
  data: contract,
  isPending,
  isError,
  refetch,
} = useQuery({
  queryKey: computed(() => ['contract', contractId.value]),
  queryFn: () => apiFetch<Contract>(`/api/contracts/${contractId.value}/`),
})
watch(
  contract,
  (value) => {
    if (value && !dirty.value) Object.assign(state, { title: value.title, content: value.content })
  },
  { immediate: true },
)
const isDraft = computed(() => contract.value?.status === 'draft')
const isBusy = computed(() => action.isPending.value || save.isPending.value)
async function refresh(value: Contract) {
  dirty.value = false
  Object.assign(state, { title: value.title, content: value.content })
  queryClient.setQueryData(['contract', value.id], value)
  await queryClient.invalidateQueries({ queryKey: ['contracts'] })
  errorMessage.value = ''
}
const save = useMutation({
  mutationFn: () =>
    apiFetch<Contract>(`/api/contracts/${contractId.value}/`, { method: 'PATCH', body: state }),
  onSuccess: refresh,
  onError: (error) => {
    errorMessage.value = apiErrorMessage(error)
  },
})
const action = useMutation({
  mutationFn: async (operation: 'generate-link' | 'sync' | 'recover') => {
    if (operation === 'generate-link' && dirty.value) {
      await apiFetch<Contract>(`/api/contracts/${contractId.value}/`, {
        method: 'PATCH',
        body: state,
      })
      dirty.value = false
    }
    return apiFetch<Contract>(`/api/contracts/${contractId.value}/${operation}/`, {
      method: 'POST',
      retry: 0,
      body: operation === 'recover' ? { document_id: recoveryDocumentId.value.trim() } : undefined,
    })
  },
  onSuccess: async (value) => {
    await refresh(value)
    toast.add({
      title: value.signing_url ? 'Contrato atualizado' : 'Rascunho salvo',
      color: 'success',
    })
  },
  onError: async (error) => {
    errorMessage.value = apiErrorMessage(error, 'Não foi possível atualizar o contrato.')
    await refetch()
  },
})
async function copyLink() {
  if (!contract.value?.signing_url) return
  try {
    await navigator.clipboard.writeText(contract.value.signing_url)
    toast.add({ title: 'Link de assinatura copiado', color: 'success' })
  } catch {
    toast.add({ title: 'Copie o link no campo abaixo.', color: 'error' })
  }
}
const download = useMutation({
  mutationFn: () => apiFetch<{ url: string }>(`/api/contracts/${contractId.value}/signed-file/`),
  onSuccess: (result) => {
    window.location.assign(result.url)
  },
  onError: (error) => {
    errorMessage.value = apiErrorMessage(error, 'Não foi possível obter o documento assinado.')
  },
})
</script>

<template>
  <CAdminPageFrame
    :title="contract?.title ?? 'Contrato'"
    eyebrow="Contratos"
    description="Revise o documento antes de gerar o link para o seu cliente."
  >
    <template #actions>
      <UButton
        to="/admin/contracts"
        label="Voltar"
        color="neutral"
        variant="ghost"
        class="rounded-full"
      />
      <template v-if="contract">
        <UButton
          v-if="isDraft"
          label="Salvar rascunho"
          color="neutral"
          variant="outline"
          class="rounded-full"
          :disabled="isBusy || !state.title.trim() || !state.content.trim()"
          :loading="save.isPending.value"
          @click="save.mutate()"
        />
        <UButton
          v-if="isDraft"
          label="Gerar link de assinatura"
          icon="i-lucide-link"
          color="neutral"
          class="rounded-full"
          :disabled="isBusy || !state.title.trim() || !state.content.trim()"
          :loading="action.isPending.value"
          @click="action.mutate('generate-link')"
        />
        <UButton
          v-if="contract.provider_document_id"
          label="Atualizar status"
          icon="i-lucide-refresh-cw"
          color="neutral"
          variant="outline"
          class="rounded-full"
          :loading="action.isPending.value"
          @click="action.mutate('sync')"
        />
        <UButton
          v-if="contract.status === 'signed'"
          label="Baixar assinado"
          icon="i-lucide-download"
          color="neutral"
          class="rounded-full"
          :loading="download.isPending.value"
          @click="download.mutate()"
        />
      </template>
    </template>
    <UAlert v-if="errorMessage" :title="errorMessage" color="error" />
    <UAlert
      v-if="isError"
      title="Não foi possível carregar o contrato."
      color="error"
      :actions="[{ label: 'Tentar novamente', onClick: () => refetch() }]"
    />
    <USkeleton v-else-if="isPending" class="h-96 w-full" />
    <template v-else-if="contract">
      <UCard>
        <div class="flex flex-wrap items-start justify-between gap-5">
          <div class="space-y-2">
            <p class="font-medium text-highlighted">{{ contract.signer_name }}</p>
            <p class="text-sm text-muted">{{ contract.signer_email }}</p>
            <p class="text-xs text-muted">
              {{ contract.provider_name }} ·
              {{ contract.provider_environment === 'sandbox' ? 'Ambiente de teste' : 'Produção' }}
            </p>
            <p v-if="contract.last_synced_at" class="text-xs text-muted">
              Atualizado em {{ new Date(contract.last_synced_at).toLocaleString('pt-BR') }}
            </p>
          </div>
          <UBadge
            :label="contractStatusLabels[contract.status]"
            :color="contract.status === 'signed' ? 'success' : 'neutral'"
            variant="subtle"
          />
        </div>
        <UAlert
          v-if="contract.provider_environment === 'sandbox'"
          title="Contrato de teste"
          description="Assinaturas neste ambiente não têm validade jurídica. Para contratos reais, use uma configuração de produção."
          color="warning"
          variant="subtle"
          class="mt-5"
        />
        <UAlert
          v-if="contract.status === 'uncertain' || contract.status === 'generating'"
          title="Verifique a criação no serviço de assinatura"
          :description="`Busque o documento pelo identificador externo ${contract.id}. Uma nova geração está bloqueada para evitar duplicidade.`"
          color="warning"
          class="mt-5"
        />
        <div
          v-if="contract.status === 'uncertain' || contract.status === 'generating'"
          class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <UFormField label="Identificador do documento no serviço de assinatura" class="flex-1">
            <UInput v-model="recoveryDocumentId" placeholder="Token do documento" class="w-full" />
          </UFormField>
          <UButton
            label="Recuperar documento"
            color="neutral"
            variant="outline"
            :disabled="!recoveryDocumentId.trim()"
            :loading="action.isPending.value"
            @click="action.mutate('recover')"
          />
        </div>
        <p v-if="contract.last_error" class="mt-4 text-sm text-error">{{ contract.last_error }}</p>
        <div v-if="contract.signing_url" class="mt-6 space-y-3">
          <UFormField label="Link para o cliente assinar"
            ><UInput :model-value="contract.signing_url" readonly class="w-full"
          /></UFormField>
          <UButton
            label="Copiar link"
            icon="i-lucide-copy"
            color="neutral"
            variant="outline"
            @click="copyLink"
          />
        </div>
      </UCard>
      <UFormField v-if="isDraft" label="Título" required
        ><UInput
          v-model="state.title"
          :maxlength="255"
          :disabled="isBusy"
          class="w-full"
          @update:model-value="dirty = true"
      /></UFormField>
      <UCard :ui="{ body: 'p-0 sm:p-0' }">
        <CAdminContractEditor
          :key="`${contract.id}-${isDraft}-${isBusy}`"
          v-model="state.content"
          :readonly="!isDraft || isBusy"
          @update:model-value="dirty = true"
        />
      </UCard>
    </template>
  </CAdminPageFrame>
</template>
