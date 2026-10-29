import type { RouteRecordRaw } from 'vue-router'

export const signatureAdminRoutes: RouteRecordRaw[] = [
  {
    path: 'settings/signatures',
    name: 'admin.settings.signatures',
    component: () => import('./pages/signature-settings.vue'),
  },
]
