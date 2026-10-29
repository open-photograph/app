<script setup lang="ts">
defineOptions({ name: 'AdminContractTemplatesPage' })
import { useQuery } from '@tanstack/vue-query'
import type { TableColumn } from '@nuxt/ui'
import { adminTableUi } from '../../constants/table'
import { apiFetch } from '@/app/core/clients/api'
import type { iApiPaginationNumber } from '@/app/shared/types'
import type { ContractTemplate } from '../../types/contract/template'

const page = ref(1)
const search = ref('')
const debouncedSearch = refDebounced(search, 300)
watch(debouncedSearch, () => {
  page.value = 1
})
const { data, isPending, isError, refetch } = useQuery({
  queryKey: computed(() => ['contract-templates', page.value, debouncedSearch.value]),
  queryFn: () =>
    apiFetch<iApiPaginationNumber<ContractTemplate>>('/api/contract-templates/', {
      query: { page: page.value, search: debouncedSearch.value },
    }),
})
const columns: TableColumn<ContractTemplate>[] = [
  { accessorKey: 'name', header: 'Template' },
  { accessorKey: 'updated_at', header: 'Atualizado' },
  { id: 'actions', header: 'Ações' },
]
const dateFormatter = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' })
const total = computed(() => data.value?.count ?? 0)
const summary = computed(() => `${total.value} ${total.value === 1 ? 'template' : 'templates'}`)
</script>

<template>
  <CAdminPageFrame
    title="Templates de contrato"
    :eyebrow="`Contratos · ${summary}`"
    description="Prepare seus modelos e personalize cada contrato antes de gerar o link de assinatura."
  >
    <template #actions>
      <UButton
        to="/admin/contracts"
        label="Contratos"
        color="neutral"
        variant="outline"
        class="rounded-full px-5"
        size="md"
      />
      <UButton
        to="/admin/contracts/templates/new"
        label="Novo template"
        icon="i-lucide-plus"
        color="neutral"
        class="rounded-full px-5"
        size="md"
      />
    </template>
    <CAdminListFrame
      v-model:page="page"
      title="Todos os templates"
      :summary="summary"
      :total="total"
      :page-size="10"
    >
      <template #toolbar>
        <UInput
          v-model="search"
          icon="i-lucide-search"
          placeholder="Buscar templates"
          aria-label="Buscar templates"
          class="w-full sm:w-64"
          color="neutral"
          variant="subtle"
        />
      </template>
      <UAlert
        v-if="isError"
        title="Não foi possível carregar os templates."
        color="error"
        variant="subtle"
        :actions="[{ label: 'Tentar novamente', onClick: () => refetch() }]"
      />
      <UTable
        v-else
        :data="data?.results ?? []"
        :columns="columns"
        :loading="isPending"
        class="w-full"
        :ui="adminTableUi"
      >
        <template #name-cell="{ row }">
          <div class="flex items-center gap-3">
            <UAvatar icon="i-lucide-files" color="neutral" size="sm" class="rounded-md" />
            <UButton
              :to="`/admin/contracts/templates/${row.original.id}`"
              :label="row.original.name"
              color="neutral"
              variant="link"
              class="p-0 font-medium text-highlighted"
            />
          </div>
        </template>
        <template #updated_at-cell="{ row }">
          <span class="text-xs text-muted">{{
            dateFormatter.format(new Date(row.original.updated_at))
          }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-1">
            <UButton
              :to="`/admin/contracts/templates/${row.original.id}`"
              label="Editar"
              icon="i-lucide-pencil"
              color="neutral"
              variant="ghost"
              size="sm"
            />
          </div>
        </template>
        <template #empty>
          <UEmpty
            icon="i-lucide-files"
            title="Nenhum template encontrado"
            :description="
              search
                ? 'Tente buscar por outro nome.'
                : 'Crie um modelo para começar seus contratos.'
            "
            class="py-16"
          />
        </template>
      </UTable>
    </CAdminListFrame>
  </CAdminPageFrame>
</template>
