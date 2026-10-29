<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { apiFetch } from '@/app/core/clients/api'
import type { SignatureCatalog, SignatureProvider } from '@/app/features/signature/types/provider'
import { apiErrorMessage } from '@/app/shared/utils/api-error'
import CSignatureProviderModal from '../components/signature-provider-modal.vue'

defineOptions({ name: 'AdminSignatureSettingsPage' })

const queryClient = useQueryClient()
const toast = useToast()
const providerModal = useOverlay().create(CSignatureProviderModal, {
  props: { provider: null },
})
const state = reactive({ provider: '' })
const errorMessage = ref('')
const accordionItems = [
  {
    label: 'Onde configuro as credenciais?',
    content:
      'As chaves são configuradas no ambiente do servidor, assim como no armazenamento e nos pagamentos. Este painel salva o serviço escolhido. O ambiente é definido automaticamente.',
  },
  {
    label: 'Qual a diferença entre teste e produção?',
    content:
      'O ambiente é definido automaticamente pelo servidor: teste quando DEBUG está ativado e produção quando está desativado. Cada ambiente usa sua própria credencial.',
  },
  {
    label: 'O que acontece ao desativar uma configuração?',
    content:
      'Ela deixa de estar disponível para novos contratos. Os documentos existentes continuam vinculados à configuração utilizada na criação.',
  },
]
const { data, isPending, isError, refetch } = useQuery({
  queryKey: ['signature-providers'],
  queryFn: () => apiFetch<SignatureProvider[]>('/api/signature-providers/'),
})
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
  catalog,
  (value) => {
    if (!state.provider) state.provider = value?.providers[0]?.value ?? ''
  },
  { immediate: true },
)
const selectedProvider = computed(() =>
  catalog.value?.providers.find((provider) => provider.value === state.provider),
)
const providerLabel = computed(() => selectedProvider.value?.label ?? 'Selecione um serviço')
const save = useMutation({
  mutationFn: () =>
    apiFetch<SignatureProvider>('/api/signature-providers/', {
      method: 'POST',
      body: { ...state, is_active: true },
    }),
  onSuccess: async () => {
    errorMessage.value = ''
    await queryClient.invalidateQueries({ queryKey: ['signature-providers'] })
    toast.add({ title: 'Configuração de assinatura salva', color: 'success' })
  },
  onError: (error) => {
    errorMessage.value = apiErrorMessage(error)
  },
})
</script>

<template>
  <CAdminPageFrame
    title="Assinaturas"
    eyebrow="Configurações"
    description="Prepare seus contratos e escolha como seus clientes vão assinar."
  >
    <template #actions>
      <UButton
        label="Ver contratos"
        icon="i-lucide-file-signature"
        to="/admin/contracts"
        color="neutral"
        variant="outline"
        class="rounded-full"
      />
    </template>
    <div class="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div class="min-w-0 space-y-5">
        <UCard :ui="{ root: 'rounded-2xl shadow-none ring-default/60', body: 'space-y-5' }">
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <h2 class="text-sm font-medium text-highlighted">Serviço de assinatura</h2>
              <UBadge :label="providerLabel" color="neutral" variant="subtle" />
            </div>
          </template>
          <UForm
            :state="state"
            :disabled="save.isPending.value"
            class="space-y-5"
            @submit="save.mutate()"
          >
            <UAlert
              v-if="catalogError"
              title="Não foi possível carregar os serviços de assinatura."
              color="error"
              variant="subtle"
              :actions="[{ label: 'Tentar novamente', onClick: () => refetchCatalog() }]"
            />
            <UAlert v-if="errorMessage" :title="errorMessage" color="error" variant="subtle" />
            <UFormField
              label="Serviço"
              name="provider"
              description="Escolha o serviço utilizado para gerar os links de assinatura."
            >
              <USelect
                v-model="state.provider"
                :items="catalog?.providers ?? []"
                :loading="loadingCatalog"
                :disabled="loadingCatalog || catalogError"
                placeholder="Selecione o serviço"
                class="w-full"
              />
            </UFormField>
            <UButton
              type="submit"
              label="Salvar configuração"
              icon="i-lucide-check"
              color="neutral"
              :loading="save.isPending.value"
              :disabled="!selectedProvider"
            />
          </UForm>
        </UCard>

        <UAlert
          v-if="isError"
          title="Não foi possível carregar as configurações."
          color="error"
          variant="subtle"
          :actions="[{ label: 'Tentar novamente', onClick: () => refetch() }]"
        />
        <USkeleton v-else-if="isPending" class="h-40 w-full rounded-2xl" />
        <UCard
          v-for="provider in data ?? []"
          v-else
          :key="provider.id"
          :ui="{ root: 'rounded-2xl shadow-none ring-default/60', body: 'space-y-5' }"
        >
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <h2 class="text-sm font-medium text-highlighted">{{ provider.name }}</h2>
              <UBadge
                :label="provider.is_active ? 'Em uso' : 'Desativado'"
                color="neutral"
                variant="subtle"
              />
            </div>
          </template>
          <div class="flex items-start gap-3">
            <UIcon name="i-lucide-file-signature" class="mt-0.5 size-5 shrink-0 text-muted" />
            <div class="space-y-2">
              <p class="text-sm text-highlighted">
                {{
                  catalog?.providers.find((item) => item.value === provider.provider)?.label ??
                  provider.provider
                }}
              </p>
              <p class="text-xs text-muted">
                {{
                  provider.environment === 'sandbox'
                    ? 'Ambiente de teste (sandbox)'
                    : 'Ambiente de produção'
                }}
              </p>
            </div>
          </div>
          <template #footer>
            <UButton
              label="Editar configuração"
              icon="i-lucide-pencil"
              color="neutral"
              variant="outline"
              @click="providerModal.open({ provider })"
            />
          </template>
        </UCard>
      </div>

      <UCard :ui="{ root: 'rounded-2xl shadow-none ring-default/60', body: 'space-y-5' }">
        <template #header
          ><h2 class="text-sm font-medium text-highlighted">Do contrato à assinatura</h2></template
        >
        <div class="flex gap-3">
          <UIcon name="i-lucide-files" class="mt-0.5 size-5 shrink-0 text-muted" />
          <p class="text-sm leading-relaxed text-muted">
            Crie um template e prepare um contrato com os dados do cliente. Revise o texto antes de
            gerar o link.
          </p>
        </div>
        <div class="flex gap-3">
          <UIcon name="i-lucide-link" class="mt-0.5 size-5 shrink-0 text-muted" />
          <p class="text-sm leading-relaxed text-muted">
            O contrato usa automaticamente o serviço ativo. Gere o link e compartilhe com o cliente.
          </p>
        </div>
        <div class="flex gap-3">
          <UIcon name="i-lucide-file-check" class="mt-0.5 size-5 shrink-0 text-muted" />
          <p class="text-sm leading-relaxed text-muted">
            Acompanhe o status pelo contrato. Após a assinatura, baixe o documento assinado.
          </p>
        </div>
        <UButton
          v-if="selectedProvider?.docs_url"
          :to="selectedProvider.docs_url"
          target="_blank"
          :label="`Documentação de ${selectedProvider.label}`"
          color="neutral"
          variant="link"
          trailing-icon="i-lucide-arrow-up-right"
        />
      </UCard>
    </div>
    <UCard :ui="{ root: 'rounded-2xl shadow-none ring-default/60' }"
      ><UAccordion :items="accordionItems"
    /></UCard>
  </CAdminPageFrame>
</template>
