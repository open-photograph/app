<script setup lang="ts">
defineOptions({ name: 'AdminContractsPage' })
import { useQuery } from '@tanstack/vue-query'
import type { TableColumn } from '@nuxt/ui'
import { adminTableUi } from '../../constants/table'
import { apiFetch } from '@/app/core/clients/api'
import type { iApiPaginationNumber } from '@/app/shared/types'
import type { Contract } from '../../types/contract/contract'
import { contractStatusLabels } from '../../constants/contract'
import CAdminContractCreateModal from '../../components/contract/admin-contract-create-modal.vue'

const createModal = useOverlay().create(CAdminContractCreateModal)
const page = ref(1)
const search = ref('')
const debouncedSearch = refDebounced(search, 300)
watch(debouncedSearch, () => {
  page.value = 1
})
const { data, isPending, isError, refetch } = useQuery({
  queryKey: computed(() => ['contracts', page.value, debouncedSearch.value]),
  queryFn: () =>
    apiFetch<iApiPaginationNumber<Contract>>('/api/contracts/', {
      query: { page: page.value, search: debouncedSearch.value },
    }),
})
const columns: TableColumn<Contract>[] = [
  { accessorKey: 'title', header: 'Contrato' },
  { accessorKey: 'signer_name', header: 'Cliente' },
  { accessorKey: 'status', header: 'Status' },
  { accessorKey: 'updated_at', header: 'Atualizado' },
  { id: 'actions', header: 'Ações' },
]
const dateFormatter = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' })
const total = computed(() => data.value?.count ?? 0)
const summary = computed(() => `${total.value} ${total.value === 1 ? 'contrato' : 'contratos'}`)
</script>

<template>
  <CAdminPageFrame
    title="Contratos"
    :eyebrow="`Documentos · ${summary}`"
    description="Do primeiro acordo à assinatura. Prepare, compartilhe e acompanhe seus contratos."
  >
    <template #actions>
      <UButton
        to="/admin/contracts/templates"
        label="Templates"
        icon="i-lucide-files"
        color="neutral"
        variant="outline"
        class="rounded-full px-5"
        size="md"
      />
      <UButton
        label="Novo contrato"
        icon="i-lucide-plus"
        color="neutral"
        class="rounded-full px-5"
        size="md"
        @click="createModal.open()"
      />
    </template>
    <CAdminListFrame
      v-model:page="page"
      title="Todos os contratos"
      :summary="summary"
      :total="total"
      :page-size="10"
    >
      <template #toolbar>
        <UInput
          v-model="search"
          icon="i-lucide-search"
          placeholder="Buscar contrato ou cliente"
          aria-label="Buscar contratos"
          class="w-full sm:w-64"
          color="neutral"
          variant="subtle"
        />
      </template>
      <UAlert
        v-if="isError"
        title="Não foi possível carregar os contratos."
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
        <template #title-cell="{ row }">
          <div class="flex items-center gap-3">
            <UAvatar icon="i-lucide-file-signature" color="neutral" size="sm" class="rounded-md" />
            <div class="min-w-0">
              <UButton
                :to="`/admin/contracts/${row.original.id}`"
                :label="row.original.title"
                color="neutral"
                variant="link"
                class="p-0 font-medium text-highlighted"
              />
              <p class="max-w-64 truncate text-xs text-muted">{{ row.original.provider_name }}</p>
            </div>
          </div>
        </template>
        <template #status-cell="{ row }">
          <UBadge
            :label="contractStatusLabels[row.original.status]"
            :color="row.original.status === 'signed' ? 'success' : 'neutral'"
            variant="subtle"
          />
        </template>
        <template #updated_at-cell="{ row }">
          <span class="text-xs text-muted">{{
            dateFormatter.format(new Date(row.original.updated_at))
          }}</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex justify-end gap-1">
            <UButton
              :to="`/admin/contracts/${row.original.id}`"
              label="Abrir"
              icon="i-lucide-arrow-up-right"
              color="neutral"
              variant="ghost"
              size="sm"
            />
          </div>
        </template>
        <template #empty>
          <UEmpty
            icon="i-lucide-file-signature"
            title="Nenhum contrato encontrado"
            :description="
              search
                ? 'Tente buscar por outro nome ou cliente.'
                : 'Crie um template e prepare seu primeiro contrato.'
            "
            class="py-16"
          />
        </template>
      </UTable>
    </CAdminListFrame>
  </CAdminPageFrame>
</template>
