<script setup lang="ts">
import type { RecentSale, SalesSummary, SeriesPoint } from "@/app/features/admin/types/sales";
import { useQuery } from "@tanstack/vue-query";
import type { TableColumn } from "@nuxt/ui";
import { apiFetch } from "@/app/core/clients/api";

// ---------------------------------------------------------------------------
// Contrato do componente
// ---------------------------------------------------------------------------
defineOptions({ name: "AdminSalesPage" });

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
const LOCALE = "pt-BR";
const DEFAULT_CURRENCY = "BRL";
const DEFAULT_DAYS = 30;
const REFETCH_INTERVAL = 60_000;
const METRIC_SKELETON_COUNT = 3;
const ORDER_ID_PREVIEW_LENGTH = 8;
const periods = [
  { label: "Últimos 7 dias", value: 7 },
  { label: "Últimos 30 dias", value: 30 },
  { label: "Últimos 90 dias", value: 90 },
];
const providerLabels: Record<string, string> = { stripe: "Stripe", mercado_pago: "Mercado Pago" };
const columns: TableColumn<RecentSale>[] = [
  { accessorKey: "client_name", header: "Cliente" },
  { accessorKey: "id", header: "Pedido" },
  { accessorKey: "paid_at", header: "Pagamento" },
  { accessorKey: "payment_provider", header: "Provedor" },
  { accessorKey: "total", header: "Valor" },
];
const revenueCategories = [{ key: "revenue" as const, label: "Receita", color: "neutral" }];
const countCategories = [{ key: "count" as const, label: "Vendas", color: "neutral" }];
const dateFormatter = new Intl.DateTimeFormat(LOCALE, { day: "2-digit", month: "short" });
const paidDateFormatter = new Intl.DateTimeFormat(LOCALE, {
  dateStyle: "short",
  timeStyle: "short",
});
const countFormatter = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
const days = ref(DEFAULT_DAYS);
const currency = ref<string>();

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------
const { data, isPending, isError, isFetching, refetch } = useQuery({
  queryKey: ["admin-sales", days, currency],
  queryFn: fetchSales,
  refetchInterval: REFETCH_INTERVAL,
});

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
const retryActions = [{ label: "Tentar novamente", onClick: retry }];

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const chartData = computed(getChartData);
const metrics = computed(getMetrics);
const showCurrencySelect = computed(getShowCurrencySelect);

// ---------------------------------------------------------------------------
// Funções
// ---------------------------------------------------------------------------

function money(value: number | string) {
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: data.value?.currency ?? DEFAULT_CURRENCY,
  }).format(Number(value));
}

function countFormat(value: number) {
  return countFormatter.format(value);
}

function paidDate(value: string) {
  return paidDateFormatter.format(new Date(value));
}

function shortOrderId(id: string) {
  return id.slice(0, ORDER_ID_PREVIEW_LENGTH);
}

function providerLabel(provider: string) {
  return providerLabels[provider] ?? provider;
}

function toChartPoint(point: SeriesPoint) {
  return {
    date: dateFormatter.format(new Date(`${point.date}T12:00:00`)),
    count: point.count,
    revenue: Number(point.revenue),
  };
}

function selectCurrency(value: string) {
  currency.value = value;
}

// ---------------------------------------------------------------------------
// Funções: computed
// ---------------------------------------------------------------------------

function getChartData() {
  const series = data.value?.series ?? [];
  const points = [];
  for (const point of series) points.push(toChartPoint(point));
  return points;
}

function getMetrics() {
  return [
    { label: "Vendas pagas", value: String(data.value?.count ?? 0), icon: "i-lucide-shopping-bag" },
    { label: "Receita", value: money(data.value?.revenue ?? 0), icon: "i-lucide-wallet" },
    { label: "Ticket médio", value: money(data.value?.average ?? 0), icon: "i-lucide-receipt" },
  ];
}

function getShowCurrencySelect() {
  return !!data.value && data.value.currencies.length > 1;
}

// ---------------------------------------------------------------------------
// Funções: queries
// ---------------------------------------------------------------------------

function fetchSales() {
  return apiFetch<SalesSummary>("/api/commerce/orders/sales/", {
    query: { days: days.value, currency: currency.value },
  });
}

function retry() {
  refetch();
}

function refresh() {
  refetch();
}
</script>

<template>
  <CAdminPageFrame
    title="Vendas"
    eyebrow="Seu negócio"
    description="Acompanhe suas vendas e os pagamentos mais recentes."
  >
    <template #actions>
      <USelect
        v-model="days"
        :items="periods"
        aria-label="Período das vendas"
        size="md"
        class="w-44"
      />
      <USelect
        v-if="showCurrencySelect"
        :model-value="data?.currency"
        :items="data?.currencies"
        aria-label="Moeda das vendas"
        size="md"
        @update:model-value="selectCurrency"
      />
      <UButton
        icon="i-lucide-refresh-cw"
        aria-label="Atualizar vendas"
        color="neutral"
        variant="ghost"
        :loading="isFetching"
        class="rounded-full"
        @click="refresh"
      />
    </template>
    <UAlert
      v-if="isError"
      title="Não foi possível carregar as vendas."
      color="error"
      :actions="retryActions"
    />
    <div v-else-if="isPending" class="space-y-6" aria-label="Carregando vendas" role="status">
      <div class="grid gap-4 sm:grid-cols-3">
        <USkeleton v-for="metric in METRIC_SKELETON_COUNT" :key="metric" class="h-32 rounded-xl" />
      </div>
      <USkeleton class="h-80 rounded-xl" />
    </div>

    <div v-else-if="data" class="space-y-6">
      <div class="grid gap-4 sm:grid-cols-3">
        <UCard v-for="metric in metrics" :key="metric.label" variant="subtle">
          <div class="flex items-center justify-between gap-3 text-muted">
            <span class="text-xs">
              {{ metric.label }}
            </span>
            <UIcon :name="metric.icon" class="size-4" />
          </div>
          <p class="mt-4 text-3xl font-medium tracking-tight text-highlighted tabular-nums">
            {{ metric.value }}
          </p>
        </UCard>
      </div>

      <p class="text-xs text-muted">
        Somente pedidos pagos no período selecionado, em {{ data.currency }}. Reembolsos não entram
        nos totais.
      </p>

      <UEmpty
        v-if="!data.count"
        icon="i-lucide-shopping-bag"
        title="Nenhuma venda neste período"
        description="As vendas aparecerão aqui após a confirmação do pagamento. Experimente selecionar outro período."
      />

      <div v-else class="grid min-w-0 gap-6 xl:grid-cols-2">
        <UCard class="min-w-0">
          <template #header>
            <h2 class="text-sm font-medium text-highlighted">Receita por dia</h2>
          </template>

          <UChart
            type="area"
            :data="chartData"
            index="date"
            :categories="revenueCategories"
            :format="money"
            :height="280"
            aria-label="Receita diária das vendas pagas"
          />
        </UCard>
        <UCard class="min-w-0">
          <template #header>
            <h2 class="text-sm font-medium text-highlighted">Vendas por dia</h2>
          </template>

          <UChart
            type="bar"
            :data="chartData"
            index="date"
            :categories="countCategories"
            :format="countFormat"
            :height="280"
            aria-label="Quantidade diária de vendas pagas"
          />
        </UCard>
      </div>

      <UCard>
        <template #header>
          <div class="space-y-1">
            <h2 class="text-sm font-medium text-highlighted">Vendas recentes</h2>
            <p class="text-xs text-muted">
              Até 10 pagamentos mais recentes no período e na moeda selecionados.
            </p>
          </div>
        </template>

        <UTable :data="data.recent" :columns="columns" empty="Nenhuma venda neste período.">
          <template #client_name-cell="{ row }">
            <div>
              <p class="font-medium text-highlighted">{{ row.original.client_name }}</p>
              <p class="text-xs text-muted">{{ row.original.client_email }}</p>
            </div>
          </template>

          <template #id-cell="{ row }">
            <span class="font-mono text-xs" :title="row.original.id">
              {{ shortOrderId(row.original.id) }}
            </span>
          </template>

          <template #paid_at-cell="{ row }">
            {{ paidDate(row.original.paid_at) }}
          </template>

          <template #payment_provider-cell="{ row }">
            {{ providerLabel(row.original.payment_provider) }}
          </template>

          <template #total-cell="{ row }">
            <span class="font-medium tabular-nums">
              {{ money(row.original.total) }}
            </span>
          </template>
        </UTable>
      </UCard>
    </div>
  </CAdminPageFrame>
</template>
