<script setup lang="ts">
defineOptions({ name: 'AdminContractTemplateEditorPage' })
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { apiFetch } from '@/app/core/clients/api'
import type { ContractTemplate } from '../../types/contract/template'
import { apiErrorMessage } from '@/app/shared/utils/api-error'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const toast = useToast()
const templateId = computed(() => String(route.params.templateId ?? ''))
const isNew = computed(() => !templateId.value)
const state = reactive({ name: '', content: '' })
const errorMessage = ref('')
const dirty = ref(false)
const { data, isPending, isError, refetch } = useQuery({
  queryKey: computed(() => ['contract-template', templateId.value]),
  queryFn: () => apiFetch<ContractTemplate>(`/api/contract-templates/${templateId.value}/`),
  enabled: computed(() => !isNew.value),
})
watch(
  data,
  (template) => {
    if (template && !dirty.value)
      Object.assign(state, { name: template.name, content: template.content })
  },
  { immediate: true },
)
const save = useMutation({
  mutationFn: () =>
    apiFetch<ContractTemplate>(
      isNew.value ? '/api/contract-templates/' : `/api/contract-templates/${templateId.value}/`,
      {
        method: isNew.value ? 'POST' : 'PATCH',
        body: state,
      },
    ),
  onSuccess: async (template) => {
    dirty.value = false
    errorMessage.value = ''
    await queryClient.invalidateQueries({ queryKey: ['contract-templates'] })
    await queryClient.invalidateQueries({ queryKey: ['contract-template', template.id] })
    toast.add({ title: 'Template salvo', color: 'success' })
    if (isNew.value) await router.replace(`/admin/contracts/templates/${template.id}`)
  },
  onError: (error) => {
    errorMessage.value = apiErrorMessage(error)
  },
})
</script>

<template>
  <CAdminPageFrame
    :title="isNew ? 'Novo template' : 'Editar template'"
    eyebrow="Contratos"
    description="Use variáveis livres no texto. Os campos serão exibidos ao criar um contrato a partir deste template."
  >
    <template #actions>
      <UButton
        to="/admin/contracts/templates"
        label="Voltar"
        color="neutral"
        variant="ghost"
        class="rounded-full"
      />
      <UButton
        label="Salvar template"
        icon="i-lucide-check"
        color="neutral"
        class="rounded-full px-5"
        :disabled="!state.name.trim() || !state.content.trim() || (!isNew && !data)"
        :loading="save.isPending.value"
        @click="save.mutate()"
      />
    </template>
    <UAlert v-if="errorMessage" :title="errorMessage" color="error" />
    <UAlert
      v-if="isError"
      title="Não foi possível carregar o template."
      color="error"
      :actions="[{ label: 'Tentar novamente', onClick: () => refetch() }]"
    />
    <USkeleton v-else-if="!isNew && isPending" class="h-96 w-full" />
    <div v-else class="space-y-6" @input="dirty = true">
      <UFormField label="Nome do template" required>
        <UInput
          v-model="state.name"
          :maxlength="255"
          class="w-full"
          :disabled="save.isPending.value"
        />
      </UFormField>
      <p v-pre class="text-sm leading-relaxed text-muted">
        Escreva variáveis como {{ name }}, {{ valor }} ou {{ data_evento }} no texto. Cada variável
        gera um campo no formulário de criação do contrato.
      </p>
      <UCard :ui="{ body: 'p-0 sm:p-0' }">
        <CAdminContractEditor
          v-model="state.content"
          :readonly="save.isPending.value"
          @update:model-value="dirty = true"
        />
      </UCard>
    </div>
  </CAdminPageFrame>
</template>
