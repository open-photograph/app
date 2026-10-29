# AGENTS.md — Frontend (`app/`)

## O que é este app

SPA Vue 3 para uma plataforma open-source de galeria de fotos para fotógrafos. Tem três grandes áreas:

1. **Setup** (`/setup`) — fluxo de onboarding do fotógrafo: conectar drive (Google Drive/OneDrive) e configurar payment provider (Stripe/MercadoPago).
2. **Admin** (`/admin`) — dashboard do fotógrafo: gerenciar galerias, sincronizar com o drive, configurar preços e marcas d'água.
3. **Gallery pública** (`/g/:slug`) — vitrine pública das fotos para os clientes; suporta acesso com código (unlisted), compra de fotos/galerias.

## Stack

- Vue 3 + Vue Router 5 (rotas escritas à mão, sem file-based routing — ver "Roteamento")
- Pinia (state) + TanStack Query (`@tanstack/vue-query`) para cache de dados da API
- Nuxt UI 4 (via `@nuxt/ui/vite` — sem Nuxt, apenas o design system)
- Vite
- Zod, VueUse, TypeScript
- Linting: oxlint + ESLint
- Formatting: oxfmt
- Package manager: pnpm
- Porta: 8080 (produção via Nginx)

## Estrutura: `app/core` / `app/features` / `app/shared`

`src/app/` é organizado por **feature** (vertical slice), não por tipo de arquivo.

```
src/
├── main.ts                     # Entry point — monta App.vue + router
├── styles/                     # CSS global (main.css, themes/)
└── app/
    ├── App.vue
    ├── core/
    │   ├── routes.ts           # Monta o router: importa routes de cada feature
    │   ├── clients/
    │   │   └── api.ts          # apiFetch (ofetch + CSRF automático) + API_*_URLS
    │   └── layouts/
    │       ├── account-layout.vue    # Setup / auth
    │       ├── dashboard-layout.vue  # (disponível, não usado ainda)
    │       └── public-layout.vue     # Gallery pública
    ├── features/
    │   ├── setup/              # Wizard de onboarding (welcome → drive → payment → done)
    │   ├── admin/              # Dashboard do fotógrafo (galerias, configurações)
    │   └── gallery/            # Vitrine pública (/g/:slug)
    └── shared/                 # Cross-feature — usado por 2+ features
        ├── components/
        ├── composables/
        ├── types/
        └── utils/
```

**Critério features vs. shared**: se corresponde a uma area autônoma do produto → `features/`. Se é
usado por 2+ features e não pertence a nenhuma (primitivos de UI, helpers, types genéricos) → `shared/`.

## Roteamento

```
/setup                        → setup.welcome (AccountLayout)
/setup/drive                  → setup.drive
/setup/payment                → setup.payment
/setup/done                   → setup.done

/admin                        → admin.galleries (AdminLayout, redirect)
/admin/galleries              → admin.galleries
/admin/settings/drive         → admin.settings.drive
/admin/settings/payment       → admin.settings.payment

/g/:slug                      → gallery (PublicLayout)
```

Cada feature declara seu array `RouteRecordRaw[]` em `features/<nome>/routes.ts`.
`app/core/routes.ts` importa todos e monta a árvore final — **não criar rotas direto em routes.ts**.

## Features

### `setup/`

Wizard multi-etapa de onboarding do fotógrafo:

| Página               | Rota            | O que faz                                          |
|----------------------|-----------------|----------------------------------------------------|
| `welcome.vue`        | `/setup`        | Criação do primeiro superusuário fotógrafo         |
| `drive.vue`          | `/setup/drive`  | Escolha de storage dinâmico (Google, Local, etc.)  |
| `payment.vue`        | `/setup/payment`| Escolha de gateway dinâmico (Mercado Pago, Stripe) |
| `done.vue`           | `/setup/done`   | Confirmação de setup e atalho para o painel        |

- **Providers Pluggable Open-Source**: O frontend consome `GET /api/setup/providers/?category=storage|payment` e renderiza cards, guias e inputs dinamicamente com base nas definições vindas do backend — permitindo adicionar novos storages ou meios de pagamento sem alterar os componentes do frontend.

### `admin/`

Dashboard do fotógrafo (requer `is_staff=True`):

| Página                             | Rota                       | O que faz                                              |
|------------------------------------|----------------------------|--------------------------------------------------------|
| `pages/galleries/index.vue`        | `/admin/galleries`         | Lista galerias, cria/edita, dispara sync, publica      |
| `pages/settings/drive.vue`         | `/admin/settings/drive`    | Ver/reconectar conta de Drive                          |
| `pages/settings/payment.vue`       | `/admin/settings/payment`  | Ver/trocar provider de payment                         |

Usa `AdminLayout` que fica em `features/admin/layouts/admin-layout.vue`.

**Ações de galeria** (chamam a API REST):
- `POST /api/galleries/` — criar galeria
- `PATCH /api/galleries/{id}/` — editar (nome, acesso, preços, watermark, etc.)
- `POST /api/galleries/{id}/sync/` — sincronizar com Drive (202 Accepted → background task)
- `POST /api/galleries/{id}/publish/` / `/unpublish/`
- `POST /api/galleries/{id}/reapply-watermark/` — regenerar watermarks

### `gallery/`

Vitrine pública das fotos:

| Arquivo              | O que faz                                                                     |
|----------------------|-------------------------------------------------------------------------------|
| `pages/slug.vue`     | Carrega galeria por slug, exibe fotos em grid, gerencia acesso com código     |
| `components/`        | PhotoGrid, PhotoDetail, PhotoBuyButton, GalleryHeader, etc.                   |
| `constants/`         | Chaves de provide/inject para tema e feedback                                |
| `types/`             | Tipos organizados por contexto, incluindo contratos de feedback              |

**Acesso à galeria** (lógica de visibilidade):
- `public` → acessível sem login
- `unlisted` → precisa do slug (não aparece em listagens)
- `private` → requer `access_code_hash` (código enviado para o cliente)

**Fluxo de compra:**
1. Cliente adiciona fotos/galeria ao carrinho (estado local).
2. `POST /api/orders/checkout/` com `client_id` + `gallery_id` e/ou `photo_ids`.
3. API retorna `checkout_url` → redirecionar para a gateway.
4. Após pagamento, o cliente recebe o link de download (`download_url` no Order).

## HTTP Client (`core/clients/api.ts`)

Todas as chamadas usam `apiFetch` — **nunca `fetch` ou `axios` direto**.

```ts
import { apiFetch } from '@/app/core/clients'

const gallery = await apiFetch<iGallery>('/api/galleries/my-slug/')
```

`apiFetch` (baseado em `ofetch`):
- Inclui credenciais (cookie de sessão) em toda request.
- Garante o cookie CSRF (`csrftoken`) automaticamente antes de cada mutação.
- Em 401: redireciona para `/account/login` (exceto logout).
- Em 5xx: exibe toast de erro automaticamente.

## ⚠️ Antes de escrever UI custom: olhe o mapa de componentes do Nuxt UI

**Regra dura**: antes de criar um `<button>`/`<div>`/`<select>` cru, um dropdown, um popover, uma
árvore, tabs, etc. — **procure primeiro se o Nuxt UI já tem o componente** na tabela abaixo.

**Por quê importa**: o usuário consegue re-temear a UI **globalmente** editando o tema do Nuxt UI
(`app.config.ts` / `appConfig.ui`) — isso só funciona se os componentes reais do Nuxt UI forem usados.

Versão instalada: ver `@nuxt/ui` em `package.json`. Fonte de verdade:
`node_modules/.pnpm/@nuxt+ui@*/node_modules/@nuxt/ui/dist/runtime/components/*.vue`.

### Mapa de componentes (relevantes para este SPA)

| Preciso de...                             | Use                           | Não escreva na mão                       |
|-------------------------------------------|-------------------------------|------------------------------------------|
| Botão                                     | `UButton`                     | `<button>` cru                           |
| Card / painel com cantos arredondados     | `UCard`                       | `<div class="border rounded-lg">`        |
| Painéis lado a lado/redimensionáveis      | `USplitter`                   | flex com drag handler manual             |
| Árvore de pastas/itens                    | `UTree`                       | lista recursiva de `<div>`               |
| Busca com fuzzy match + atalho            | `UCommandPalette`             | `<input>` + filtro manual                |
| Abas                                      | `UTabs`                       | linha de `<button>` com `:class`         |
| Menu dropdown (clique)                    | `UDropdownMenu`               | `UPopover` + lista de botões             |
| Popover simples (conteúdo livre)          | `UPopover`                    | —                                        |
| Modal                                     | `UModal`                      | overlay + div fixo na mão               |
| Slideover (painel lateral deslizante)     | `USlideover`                  | —                                        |
| Select simples                            | `USelect`                     | `<select>` cru                           |
| Select com busca/multi/async              | `USelectMenu`                 | —                                        |
| Input de texto                            | `UInput`                      | `<input>` cru                            |
| Textarea                                  | `UTextarea`                   | `<textarea>` cru                         |
| Checkbox / grupo                          | `UCheckbox` / `UCheckboxGroup`| —                                        |
| Switch (toggle)                           | `USwitch`                     | —                                        |
| Tabela                                    | `UTable`                      | `<table>` cru                            |
| Paginação                                 | `UPagination`                 | —                                        |
| Badge/tag                                 | `UBadge`                      | `<span class="rounded-full px-2">`       |
| Avatar                                    | `UAvatar` / `UAvatarGroup`    | —                                        |
| Tooltip                                   | `UTooltip`                    | `title="..."` cru                        |
| Ícone                                     | `UIcon`                       | —                                        |
| Toast/notificação                         | `useToast()` + `UToaster`     | —                                        |
| Estado vazio                              | `UEmpty`                      | —                                        |
| Skeleton de loading                       | `USkeleton`                   | —                                        |
| Progress bar                              | `UProgress`                   | —                                        |
| Upload de arquivo                         | `UFileUpload`                 | —                                        |
| Stepper (wizard multi-etapa)             | `UStepper`                    | —                                        |
| Accordion                                 | `UAccordion`                  | —                                        |

### Componentes que **não** se aplicam aqui

`Page*`, `Blog*`, `Pricing*`, `ChangelogVersion*`, `Footer*`, `Header`, `Hero`, `Marquee`, `Chat*` —
são para sites de marketing (Nuxt UI Pro templates). Este projeto é um SPA com área pública de fotos
e dashboard admin; esses componentes não se encaixam.

## Auto-imports (via `@nuxt/ui/vite`)

O plugin `ui()` configura auto-import para:
- **Módulos**: `vue`, `vue-router`, `@vueuse/core` — nunca precisam de import explícito.
- **Componentes**: todo `src/app/features/**` e `src/app/shared/components/**`, com prefixo `C`
  (ex: `photo-card.vue` → `<CPhotoCard>`) — nome vem só do filename, a pasta não importa.

**Composables, types, utils NÃO são auto-importados** — usar import explícito:
```ts
import { useSetupStepper } from '@/app/features/setup/composables/useSetupStepper'
import type { iGallery } from '@/app/features/gallery/types'
```

## Estilo de código

- Variáveis sempre descritivas — nunca nomes de uma letra (`p`, `e`, `v`)
- Foco em código legível: preferir clareza sobre brevidade
- Componentes Nuxt UI sempre com prefixo `C` (`<CButton>` → usa `UButton` internamente)
- Modais/Slideovers: abrir via `useOverlay()` — nunca `v-model:open` direto na página

## Convenções

- Alias `@` → `src/` (código do app fica sob `@/app/...`; `@/styles/...` é o CSS global)
- Rotas: um `routes.ts` por feature, montado em `app/core/routes.ts`
- Proxy dev: `/api` → backend (via `VITE_API_URL` no `vite.config.ts`)
- Paginação: usar o tipo de paginação padronizado do `shared/types/`

## Padrão de componentes

| Pasta                              | Critério                                                   |
|------------------------------------|------------------------------------------------------------|
| `app/shared/components/*.vue`      | Primitivo reutilizável sem lógica de negócio               |
| `app/shared/components/<algo>/`    | Usado por 2+ features, não pertence a nenhuma              |
| `app/features/<nome>/components/`  | Específico da feature — pode ter subpastas                 |

## Padrão de composables

- Usar `useQuery`, `useMutation` e os demais recursos das bibliotecas diretamente no componente que precisa deles.
- Não criar composables apenas para encapsular chamadas de API, configurar queries/mutations ou repassar estados de loading, erro e cache: TanStack Query já resolve essas responsabilidades.
- Antes de criar um composable, verificar se Vue, VueUse, TanStack Query ou outra biblioteca instalada já oferece o comportamento necessário. Usar a biblioteca diretamente quando oferecer.
- Reservar composables para comportamento reativo próprio da aplicação que não esteja coberto pelas bibliotecas. O tamanho do componente, por si só, não justifica essa camada.
- Compartilhar tipos, schemas e funções puras nos arquivos apropriados, sem transformá-los em composables.

| Local                                 | Critério                                                   |
|---------------------------------------|------------------------------------------------------------|
| `app/shared/composables/*.ts`         | Genérico, sem vínculo de domínio                           |
| `app/shared/composables/<algo>/`      | Usado por 2+ features ou integração externa                |
| `app/features/<nome>/composables/`    | Específico da feature                                      |

## Dados da API (TanStack Query)

Usar `useQuery`/`useMutation` do `@tanstack/vue-query` diretamente no `<script setup>` do componente
para chamadas à API. Eles gerenciam cache, loading states e refetch automático; não adicionar um
composable intermediário para isso. Usar `apiFetch` como `queryFn`/`mutationFn`.

```ts
import { useQuery, useMutation } from '@tanstack/vue-query'
import { apiFetch } from '@/app/core/clients'

const { data: gallery } = useQuery({
  queryKey: ['gallery', slug],
  queryFn: () => apiFetch<iGallery>(`/api/galleries/${slug}/`),
})
```

## Comandos

```bash
pnpm install        # Instalar dependências
pnpm dev            # Servidor de desenvolvimento
pnpm build          # Build de produção (type-check + vite build)
pnpm lint           # Lint (oxlint + eslint com --fix)
pnpm format         # Formatar com oxfmt
pnpm test:unit      # Testes via Vitest
```

## Contratos no admin

- `/admin/contracts`: lista, busca e criação de contratos por cliente/template; o backend seleciona o serviço de assinatura ativo.
- `/admin/contracts/templates`: templates com `UEditor` + `UEditorToolbar`, conteúdo Markdown.
- `/admin/contracts/:contractId`: revisão do rascunho, geração/cópia do link, consulta de status e download assinado.
- `/admin/settings/signatures`: configurações dos providers de assinatura, implementadas em `features/signature/`, com catálogo dinâmico do backend.
- Tipos organizados em `features/admin/types/contract/` (contrato e template); tipos dos serviços em `features/signature/types/`.
- Contratos gerados são imutáveis; alterações de templates não modificam contratos existentes.

O frontend não mantém listas, credenciais ou documentação específicas de fornecedores de assinatura.
As variáveis são descobertas no conteúdo de cada template e retornadas em `variables`/`input_variables`.
O formulário carrega os campos do template selecionado e envia seus valores em `variables` na criação do contrato.
