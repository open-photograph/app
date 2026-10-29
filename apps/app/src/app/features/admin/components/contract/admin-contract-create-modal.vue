<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { apiFetch } from '@/app/core/clients/api'
import type { iApiPaginationNumber } from '@/app/shared/types'
import type { Client } from '../../types/client'
import type { Contract } from '../../types/contract/contract'
import type { ContractTemplate } from '../../types/contract/template'
import { apiErrorMessage } from '@/app/shared/utils/api-error'

const props = defineProps<{ open?: boolean }>()
const emit = defineEmits<{ close: []; 'update:open': [value: boolean]; 'after:leave': [] }>()
const router = useRouter()
const queryClient = useQueryClient()
const state = reactive({
  title: '',
  client: '',
  template: '',
  variables: {} as Record<string, string>,
})
const errorMessage = ref('')
const clientSearch = ref('')
const templateSearch = ref('')
const debouncedClientSearch = refDebounced(clientSearch, 250)
const debouncedTemplateSearch = refDebounced(templateSearch, 250)
const {
  data: clients,
  isPending: loadingClients,
  isError: clientsError,
} = useQuery({
  queryKey: computed(() => ['contract-client-options', debouncedClientSearch.value]),
  queryFn: () =>
    apiFetch<iApiPaginationNumber<Client>>('/api/clients/', {
      query: { search: debouncedClientSearch.value },
    }),
})
const {
  data: templates,
  isPending: loadingTemplates,
  isError: templatesError,
} = useQuery({
  queryKey: computed(() => ['contract-template-options', debouncedTemplateSearch.value]),
  queryFn: () =>
    apiFetch<iApiPaginationNumber<ContractTemplate>>('/api/contract-templates/', {
      query: { search: debouncedTemplateSearch.value },
    }),
})
const {
  data: selectedTemplate,
  isPending: loadingSelectedTemplate,
  isError: selectedTemplateError,
  refetch: refetchSelectedTemplate,
} = useQuery({
  queryKey: computed(() => ['contract-template', state.template]),
  queryFn: () => apiFetch<ContractTemplate>(`/api/contract-templates/${state.template}/`),
  enabled: computed(() => !!state.template),
})
const templateOptions = computed(() => {
  const options = templates.value?.results ?? []
  const selected = selectedTemplate.value
  return selected && !options.some((template) => template.id === selected.id)
    ? [selected, ...options]
    : options
})
const inputVariables = computed(() => selectedTemplate.value?.input_variables ?? [])
const variablesFilled = computed(() =>
  inputVariables.value.every((name) => state.variables[name]?.trim()),
)
watch(
  () => state.template,
  () => {
    state.variables = {}
    errorMessage.value = ''
  },
)
watch(
  selectedTemplate,
  (template) => {
    if (!template || template.id !== state.template) return
    state.variables = Object.fromEntries(
      template.input_variables.map((name) => [
        name,
        Object.prototype.hasOwnProperty.call(state.variables, name)
          ? (state.variables[name] ?? '')
          : '',
      ]),
    )
  },
  { immediate: true },
)
watch(
  () => props.open,
  (open) => {
    if (open) {
      Object.assign(state, { title: '', client: '', template: '', variables: {} })
      errorMessage.value = ''
    }
  },
  { immediate: true },
)
const create = useMutation({
  mutationFn: () => apiFetch<Contract>('/api/contracts/', { method: 'POST', body: state }),
  onSuccess: async (contract) => {
    await queryClient.invalidateQueries({ queryKey: ['contracts'] })
    emit('close')
    await router.push(`/admin/contracts/${contract.id}`)
  },
  onError: (error) => {
    errorMessage.value = apiErrorMessage(error)
  },
})
</script>

<template>
  <UModal
    :open="open"
    title="Novo contrato"
    description="Escolha o cliente e um template. Você poderá revisar o texto antes de gerar o link."
    :dismissible="!create.isPending.value"
    @update:open="emit('update:open', $event)"
    @after:leave="emit('after:leave')"
  >
    <template #body>
      <UForm
        id="contract-create"
        :state="state"
        class="space-y-5"
        :disabled="create.isPending.value"
        @submit="create.mutate()"
      >
        <UAlert v-if="errorMessage" :title="errorMessage" color="error" />
        <UAlert
          v-if="clientsError || templatesError"
          title="Não foi possível carregar as opções. Feche e tente novamente."
          color="error"
        />
        <UFormField label="Título do contrato" required
          ><UInput v-model="state.title" required :maxlength="255" class="w-full"
        /></UFormField>
        <UFormField label="Cliente" required>
          <USelectMenu
            v-model="state.client"
            v-model:search-term="clientSearch"
            :items="clients?.results ?? []"
            label-key="name"
            value-key="id"
            :ignore-filter="true"
            :ui="{ content: 'z-[60]' }"
            :loading="loadingClients"
            placeholder="Buscar cliente"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Template" required>
          <USelectMenu
            v-model="state.template"
            v-model:search-term="templateSearch"
            :items="templateOptions"
            label-key="name"
            value-key="id"
            :ignore-filter="true"
            :ui="{ content: 'z-[60]' }"
            :loading="loadingTemplates"
            placeholder="Buscar template"
            class="w-full"
          />
          <UButton
            to="/admin/contracts/templates"
            label="Gerenciar templates"
            variant="link"
            color="neutral"
            @click="emit('close')"
          />
        </UFormField>
        <template v-if="state.template">
          <UAlert
            v-if="selectedTemplateError"
            title="Não foi possível carregar os campos do template."
            color="error"
            :actions="[{ label: 'Tentar novamente', onClick: () => refetchSelectedTemplate() }]"
          />
          <USkeleton v-else-if="loadingSelectedTemplate" class="h-20 w-full" />
          <div v-else-if="inputVariables.length" class="space-y-5">
            <USeparator label="Dados do contrato" />
            <UFormField
              v-for="variable in inputVariables"
              :key="variable"
              :label="variable"
              required
            >
              <UInput
                v-model="state.variables[variable]"
                required
                :maxlength="10000"
                class="w-full"
              />
            </UFormField>
          </div>
        </template>
      </UForm>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          label="Cancelar"
          color="neutral"
          variant="ghost"
          :disabled="create.isPending.value"
          @click="emit('close')"
        />
        <UButton
          label="Criar rascunho"
          type="submit"
          form="contract-create"
          color="neutral"
          :loading="create.isPending.value"
          :disabled="
            !state.title.trim() ||
            !state.client ||
            !state.template ||
            loadingSelectedTemplate ||
            selectedTemplateError ||
            !variablesFilled
          "
        />
      </div>
    </template>
  </UModal>
</template>
