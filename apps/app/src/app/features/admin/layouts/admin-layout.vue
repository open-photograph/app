<script setup lang="ts">
import type { NavigationMenuItem } from "@nuxt/ui";

const open = ref(false);

const navItems = computed<NavigationMenuItem[][]>(() => [
  [
    {
      label: "Vendas",
      icon: "i-lucide-chart-no-axes-combined",
      to: "/admin/sales",
    },
    {
      label: "Clientes",
      icon: "i-lucide-users",
      to: "/admin/clients",
    },
    {
      label: "Galerias",
      icon: "i-lucide-images",
      to: "/admin/galleries",
    },
    {
      label: "Contratos",
      icon: "i-lucide-file-signature",
      to: "/admin/contracts",
    },
    {
      label: "Tags",
      icon: "i-lucide-tags",
      to: "/admin/tags",
    },
    {
      label: "Marcas d'água",
      icon: "i-lucide-stamp",
      to: "/admin/settings/watermark",
    },
  ],
  [
    {
      label: "Configurações",
      type: "label",
    },
    {
      label: "Drive",
      icon: "i-lucide-hard-drive",
      to: "/admin/settings/drive",
    },
    {
      label: "Prévias",
      icon: "i-lucide-image",
      to: "/admin/settings/previews",
    },

    {
      label: "Assinaturas",
      icon: "i-lucide-pen-line",
      to: "/admin/settings/signatures",
    },
    {
      label: "Pagamento",
      icon: "i-lucide-credit-card",
      to: "/admin/settings/payment",
    },
  ],
]);
</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      v-model:open="open"
      id="default"
      mode="drawer"
      :default-size="16"
      :min-size="14"
      :max-size="20"
      :ui="{
        root: 'bg-muted/15',
        header: 'h-16 px-5 border-b border-default/60',
        body: 'px-3 py-6',
        footer: 'border-t border-default/60 p-3',
      }"
      toggle-side="right"
      collapsible
      resizable
    >
      <template #header="{ collapsed }">
        <RouterLink
          to="/admin/galleries"
          aria-label="Open Photograph — Galerias"
          class="flex items-center gap-2.5 text-highlighted"
        >
          <UIcon name="i-lucide-aperture" class="size-5 shrink-0" />
          <span v-if="!collapsed" class="text-sm font-medium tracking-wide">Open Photograph</span>
        </RouterLink>
      </template>
      <template #default="{ collapsed }">
        <UNavigationMenu
          :collapsed="collapsed"
          :items="navItems"
          color="neutral"
          variant="pill"
          :ui="{
            link: 'rounded-lg py-2.5 text-sm',
            label: 'text-[10px] uppercase tracking-[0.15em] text-muted',
          }"
          orientation="vertical"
        />
      </template>
      <template #footer="{ collapsed }"><CAdminAccountMenu :collapsed="collapsed" /></template>
    </UDashboardSidebar>

    <RouterView />
  </UDashboardGroup>
</template>
