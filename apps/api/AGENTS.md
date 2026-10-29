# AGENTS.md — Backend (`api/`)

## O que é este serviço

API REST para uma plataforma open-source de galeria de fotos para fotógrafos. O fotógrafo conecta seu
drive (Google Drive, OneDrive) ou usa armazenamento local/S3, sincroniza pastas de fotos para criar
galerias e compartilha-as com clientes — com marca d'água anti-IA opcional e possibilidade de vender
fotos/galerias via Stripe ou Mercado Pago.

## Stack

| Camada      | Tecnologia                                                                                        |
|-------------|---------------------------------------------------------------------------------------------------|
| Framework   | Django 6 + Django REST Framework (DRF)                                                            |
| Auth        | django-allauth headless (Google OAuth para login + Drive scope)                                   |
| Banco       | PostgreSQL                                                                                         |
| Background  | django-tasks + django-tasks-rq (Redis) — **não usar Celery diretamente**                          |
| Storage     | django-storages[s3] em produção / filesystem em dev                                               |
| Imagens     | Pillow — geração de thumbnail/preview/watermark                                                   |
| Pagamentos  | django-payments (abstração multi-provider)                                                         |
| Moeda       | django-money (MoneyField)                                                                         |
| Admin       | django-unfold                                                                                      |
| Schema      | drf-spectacular (OpenAPI 3) — `/docs` e `/redoc`                                                  |
| Observ.     | logfire[django,psycopg,redis]                                                                     |
| Runtime     | Python 3.12+ / uv                                                                                  |

## Estrutura de diretórios

```
api/
├── app/
│   ├── common/              # Utilitários de infraestrutura (sem domínio de negócio)
│   │   ├── streaming/       # Endpoints de streaming de mídia
│   │   └── websocket/       # Consumers WebSocket (Channels)
│   ├── domains/             # Apps de domínio — toda a lógica de negócio
│   │   ├── client/          # Cliente (comprador) de fotos
│   │   ├── commerce/        # Pedidos, watermark assets
│   │   ├── gallery/         # Galeria + Foto + EXIF + tags + tasks de sync/watermark
│   │   └── setup/           # Configuração do fotógrafo (drive + payment provider)
│   └── integrations/        # Integrações externas (sem models de domínio)
│       ├── drive/           # Google Drive / OneDrive — providers, services, views, serializers
│       └── payment/         # Stripe / Mercado Pago — providers, services (WIP)
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
└── shared/                  # Utilitários transversais importados por qualquer app
    ├── providers/
    │   └── storage.py       # ABC StorageProvider + dataclass StorageFile
    ├── models/              # Mixins de model (ex: TimestampMixin)
    ├── serializers/         # Mixins de serializer
    ├── paginations/
    └── enums/
```

## Domínios (`app/domains/`)

### `client`
Representa o comprador de fotos — não o fotógrafo (que é o Django User admin).

| Model  | Campos relevantes                                                      |
|--------|------------------------------------------------------------------------|
| Client | `user` (OneToOne nullable), `name`, `email` (unique), `phone`, `notes` |

- `Client.user` é opcional: o cliente pode existir sem conta no sistema.
- Quando existe, `user.client_profile` dá acesso direto ao Client.

### `gallery`

| Model        | Campos relevantes                                                                                     |
|--------------|-------------------------------------------------------------------------------------------------------|
| Gallery      | `name`, `slug` (unique), `clients` (M2M), `tags` (M2M), `access_type` (public/unlisted/private)      |
|              | `access_code_hash`, `is_published`, `allow_downloads`                                                 |
|              | `enable_sales`, `allow_individual_purchase`, `gallery_price` (MoneyField)                             |
|              | `watermark_enabled`, `watermark_asset` (FK→WatermarkAsset, nullable)                                  |
|              | `source_folder_id` (ID da pasta no drive), `last_synced_at`                                           |
| Photo        | `gallery` (FK), `name`, `source_file_id`, `thumbnail`, `preview`, `watermarked_preview`               |
|              | `width`, `height`, `size`, `mime_type`, `status` (processing/ready/failed), `position`               |
|              | `price` (MoneyField, para venda individual), `taken_at`                                               |
| PhotoExif    | OneToOne→Photo: `camera_make`, `camera_model`, `lens_model`, `iso`, `aperture`, `shutter_speed`      |
|              | `focal_length`, `exposure_compensation`, `flash_fired`, `software`, `captured_at`                    |
| GalleryTag   | `title`, `slug`                                                                                       |

**Fluxo de sync Drive → Galeria:**
1. `POST /api/galleries/{id}/sync/` → enfileira `sync_gallery_drive(gallery_id, user_id)`.
2. `sync_gallery_drive` lista JPEGs na pasta do Drive, cria `Photo` (status=processing) para cada novo arquivo e enfileira `process_photo(photo_id, user_id)`.
3. `process_photo` baixa o arquivo do Drive, converte para WebP e salva `thumbnail` + `preview`. Se `gallery.watermark_enabled`, enfileira `apply_watermark(photo_id)`.
4. `apply_watermark` usa `WatermarkAsset` da galeria (ou o padrão global) para gerar `watermarked_preview`.

### `commerce`

| Model          | Campos relevantes                                                                               |
|----------------|-------------------------------------------------------------------------------------------------|
| Order          | `client` (FK), `payment_provider` (snapshot), `payment_reference`, `status`, `total` (Money)  |
|                | `checkout_url`, `download_url`, `paid_at`, `expires_at`                                        |
| OrderItem      | `order` (FK), `item_type` (gallery/photo), `gallery` (FK nullable), `photo` (FK nullable)      |
|                | `unit_price` (snapshot do preço no momento da compra)                                          |
| WatermarkAsset | `name`, `style` (text_diagonal / image_overlay / combined)                                      |
|                | `text`, `text_color`, `text_opacity`, `font_size_ratio`, `rotation_angle`, `tile_spacing`      |
|                | `logo` (ImageField), `logo_opacity`, `logo_size_ratio`, `logo_position`                        |
|                | `is_default` (marca d'água padrão global)                                                       |

**Regras de negócio (Order):**
- `payment_provider` é snapshot do `Setup.provider` ativo — não muda mesmo que o Setup seja alterado depois.
- `unit_price` é snapshot do preço no momento da compra.
- Para comprar galeria inteira: `gallery.enable_sales=True` + `gallery.gallery_price` definido.
- Para comprar foto avulsa: `gallery.allow_individual_purchase=True` + `photo.price` definido.

**Fluxo de checkout:**
`POST /api/orders/checkout/` → valida itens → lê Setup de payment ativo → cria Order + OrderItems →
retorna `checkout_url` (integração real com gateway WIP em `integrations/payment/`).

### `setup`

Organizado sob **crescimento horizontal (1 classe por arquivo)**:
- `models/`: `setup.py` (`Setup`), `setup_type.py` (`SetupType`), `setup_drive.py` (`SetupDrive`), `setup_payment.py` (`SetupPayment`).
- `views/`: `setup_status_view.py`, `admin_account_create_view.py`, `setup_viewset.py`, `provider_list_view.py`.
- `serializers/`: `setup_serializer.py`, `admin_account_create_serializer.py`, `provider_form_field_serializer.py`, `provider_manifest_serializer.py`.
- `providers/`: Arquitetura pluggable open-source (`registry.py`, `manifest.py`, `form_field.py`, `defaults.py`).

| Model | Campos relevantes                                               |
|-------|-----------------------------------------------------------------|
| Setup | `name`, `type` (payment/storage), `provider`, `is_active`      |

- `SetupDrive`: `google_drive` | `one_drive` | `local` | `s3`
- `SetupPayment`: `mercado_pago` | `stripe`
- Apenas um Setup por tipo deve estar `is_active=True`.
- **Arquitetura Pluggable Open-Source**: Novos providers de storage (ex: Dropbox, Backblaze B2, MinIO) ou pagamento (ex: Asaas, PayPal, Lemonsqueezy) são registrados no `provider_registry` no backend via `ProviderManifest`. O frontend consome `GET /api/setup/providers/?category=` e renderiza cards, guias e formulários dinamicamente sem necessidade de alterar o código do frontend!

## Integrações (`app/integrations/`)

### `drive/` — StorageProvider pattern

```python
# shared/providers/storage.py
class StorageProvider(ABC):
    def list_files(self, folder_id: str) -> Iterable[StorageFile]: ...
    def list_folders(self, parent_id: str) -> Iterable[StorageFile]: ...
    def open_file(self, file_id: str) -> BinaryIO: ...
    def get_file(self, file_id: str) -> StorageFile: ...

@dataclass(frozen=True)
class StorageFile:
    id: str
    name: str
    mime_type: str
    size: int | None = None
```

- `GoogleDriveProvider` usa `SocialToken` do allauth (OAuth com `drive.readonly` scope).
- `OneDriveProvider` — arquivo existe, implementação pendente.
- **Novo provider**: criar em `integrations/drive/providers/`, implementar `StorageProvider`, registrar no `registry.py` (ainda vazio — o padrão de registro precisa ser definido).

### `payment/` — WIP

Providers em `integrations/payment/providers/` — ainda vazios. O `OrderViewSet.checkout` já lê o
`Setup.provider` mas não chama nenhuma gateway real ainda. Quando implementar:
1. Criar provider em `integrations/payment/providers/<nome>.py`.
2. Registrar no `registry.py`.
3. Chamar no `OrderViewSet.checkout` para gerar a `checkout_url` real.

## URLs (`config/urls.py`)

```
/admin/                     Django admin (django-unfold)
/allauth/                   Allauth classic (OAuth redirects)
/payments/                  django-payments webhooks
/schema                     OpenAPI schema
/docs                       Swagger UI
/redoc                      ReDoc

/api/
  (allauth headless)        /api/browser/v1/...
  /api/galleries/           GalleryViewSet
  /api/galleries/tags/      GalleryTagViewSet
  /api/photos/              PhotoViewSet
  /api/clients/             ClientViewSet
  /api/setups/              SetupViewSet
  /api/orders/              OrderViewSet
  /api/watermarks/          WatermarkAssetViewSet
  /api/drive/...            Drive integration (list folders, connect)
  /api/streaming/...        Media streaming
```

## Views e permissões

| ViewSet            | Permissão padrão | Ações especiais                                                        |
|--------------------|------------------|------------------------------------------------------------------------|
| GalleryViewSet     | IsAdminUser      | `POST /sync/` — enfileira sync do Drive                                |
|                    |                  | `POST /publish/` e `/unpublish/`                                       |
|                    |                  | `POST /reapply-watermark/` — reenfileira watermark para todas as fotos |
| PhotoViewSet       | IsAdminUser      | —                                                                      |
| GalleryTagViewSet  | IsAdminUser      | —                                                                      |
| ClientViewSet      | IsAdminUser      | —                                                                      |
| SetupViewSet       | IsAdminUser      | —                                                                      |
| WatermarkViewSet   | IsAdminUser      | —                                                                      |
| OrderViewSet       | IsAuthenticated  | Admin vê todos; cliente vê só os próprios                              |
|                    |                  | `POST /checkout/` — cria pedido (IsAuthenticated)                      |
|                    |                  | `POST /{id}/mark_paid/` — marca pago manualmente (IsAdminUser)         |

> **Nota**: "Admin" aqui é o fotógrafo/dono da instância (`is_staff=True`). Clients são compradores com contas normais.

## Tasks (background, django-tasks)

| Task                        | Trigger                                      | O que faz                                                             |
|-----------------------------|----------------------------------------------|-----------------------------------------------------------------------|
| `sync_gallery_drive`        | `POST /galleries/{id}/sync/`                 | Lista JPEGs na pasta do Drive, cria Photos, enfileira process_photo   |
| `process_photo`             | Enfileirada por sync_gallery_drive           | Baixa JPEG, converte para WebP, salva thumbnail+preview               |
| `apply_watermark`           | Enfileirada por process_photo (se habilitado)| Gera watermarked_preview com WatermarkAsset                           |
| `reapply_watermark_gallery` | `POST /galleries/{id}/reapply-watermark/`    | Reenfileira apply_watermark para todas as fotos prontas               |

**Enfileirar tasks**: sempre via `.enqueue()`, nunca chamar diretamente.

```python
sync_gallery_drive.enqueue(gallery.pk, user_id)
process_photo.enqueue(photo.pk, user_id)
apply_watermark.enqueue(photo.pk)
```

## Watermark anti-IA

Técnicas implementadas em `gallery/tasks.py`:
1. **Tiling completo** — grid diagonal cobre 100% da imagem (não só cantos).
2. **Variação aleatória** — rotação, tamanho e opacidade diferentes por instância.
3. **Outline + sombra** — borda escura em volta do texto para visibilidade em qualquer fundo.
4. Blur nas bordas do logo (dificulta detecção de máscara pela IA).

Precedência do asset: `gallery.watermark_asset` → `WatermarkAsset.objects.filter(is_default=True).first()`.

## Convenções de código

- **Package manager**: `uv` — instalar com `uv sync`, rodar com `uv run`.
- **Lint/format**: ruff — `uv run ruff check --fix` / `uv run ruff format`.
- Nomes de arquivo: snake_case; classes: PascalCase.
- Testes devem ficar sempre em `tests/` dentro da respectiva feature/dom?nio ou integra??o, com `__init__.py` e arquivos `test_*.py`; n?o criar `tests.py` nem `test_*.py` na raiz da feature.
- Imports de `app.*` são sempre absolutos — nunca relativos cruzando apps.
- Imports dentro do mesmo app podem ser relativos (`from ..models import Gallery`).
- `print()` é proibido em produção (ruff T20) — usar `logger = logging.getLogger(__name__)`.

## Comandos

```bash
uv sync                                              # Instalar dependências
uv run python manage.py migrate                      # Aplicar migrations
uv run python manage.py runserver                    # Dev server (porta 8000)
uv run python manage.py makemigrations <app>         # Criar migrations
uv run ruff check --fix && uv run ruff format        # Lint + format
uv run python manage.py rqworker default             # Worker de tasks (Redis)
```

## Adicionando um novo domínio

1. Criar `app/domains/<nome>/` com `apps.py`, `models.py`, `serializers.py`, `views.py`, `urls.py`.
2. Registrar em `config/settings.py` (`INSTALLED_APPS`).
3. Incluir `urls.py` em `config/urls.py`.
4. `uv run python manage.py makemigrations <nome>`.

## Adicionando um novo provider de Drive

1. Criar `app/integrations/drive/providers/<nome>.py` implementando `StorageProvider`.
2. Criar service em `app/integrations/drive/services/<nome>.py`.
3. Adicionar a opção em `app/domains/setup/models.py` (`SetupDrive`).
4. Registrar no `app/integrations/drive/registry.py`.
5. Usar nas tasks de gallery referenciando o provider correto pelo `Setup` ativo.

## Contratos (`app/domains/contract`)

Templates Markdown, rascunhos por cliente, geração de links de assinatura e consulta do documento assinado.
Integrações externas ficam em `app/integrations/signature/`, com interface comum, manifestos e registro de providers.
Cada fornecedor possui sua própria pasta em `signature/providers/`, incluindo sua factory de credenciais.
O catálogo e a validação são derivados do registro, sem listas duplicadas no domínio de contratos.
ZapSign é o primeiro provider, com credenciais exclusivamente no `.env` (`ZAPSIGN_API_TOKEN` e `ZAPSIGN_SANDBOX_API_TOKEN`) e ambientes separados.
Detalhes de schema, endpoints, configuração e testes em [`README.md`](app/domains/contract/README.md).
