from __future__ import annotations

import io
import logging
import uuid

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from django_tasks import task
from PIL import Image, ImageOps

from apps.integrations.drive.services import GoogleDriveService

from .constants import JPEG_MIME_TYPES, THUMBNAIL_SIZE
from .utils import _build_watermarked_image
from .models import Gallery, Photo, PhotoStatus, PreviewSettings
from .utils import convert_to_webp, filename_stem, mark_photo_failed

logger = logging.getLogger(__name__)

User = get_user_model()


@task
def regenerate_previews() -> None:
    photos = Photo.objects.filter(status=PhotoStatus.READY, source_user__isnull=False).exclude(source_file_id="")
    for photo_id, user_id in photos.values_list("pk", "source_user_id").iterator():
        process_photo.enqueue(str(photo_id), user_id)


# ---------------------------------------------------------------------------
# Watermark helpers
# ---------------------------------------------------------------------------


def _resolve_watermark_asset(gallery: Gallery):
    """
    Retorna o WatermarkAsset a usar para a galeria, ou None se não configurado.

    Precedência: asset específico da galeria → asset padrão global.
    """
    asset = gallery.watermark_asset
    if asset is None:
        # Import local para evitar circular import no nível de módulo
        from apps.domains.commerce.models import WatermarkAsset

        asset = WatermarkAsset.objects.filter(is_default=True).first()
    return asset


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@task()
def process_photo(photo_id: str, user_id: int) -> None:
    """
    Baixa o JPEG do Google Drive, converte para WebP e salva thumbnail + preview.

    Se a galeria tiver watermark_enabled=True, enfileira apply_watermark
    automaticamente após a conversão.
    """
    try:
        photo = Photo.objects.select_related("gallery").get(pk=photo_id)
    except Photo.DoesNotExist:
        logger.error("process_photo: Photo %s not found, skipping.", photo_id)
        return

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("process_photo: User %s not found, skipping.", user_id)
        return

    try:
        service = GoogleDriveService(user)
        with service.open_file(photo.source_file_id) as raw, Image.open(raw) as img:
            img_rgb = ImageOps.exif_transpose(img).convert("RGB")
            original_width, original_height = img_rgb.size
            preview_settings = PreviewSettings.current()
            thumbnail_bytes = convert_to_webp(img_rgb, THUMBNAIL_SIZE, quality=preview_settings.quality)
            preview_bytes = convert_to_webp(
                img_rgb, (preview_settings.max_size, preview_settings.max_size), quality=preview_settings.quality
            )

        base_name = f"{filename_stem(photo.name)}_{uuid.uuid4().hex}"

        photo.thumbnail.save(f"{base_name}_thumb.webp", ContentFile(thumbnail_bytes), save=False)
        photo.preview.save(f"{base_name}_preview.webp", ContentFile(preview_bytes), save=False)
        photo.watermarked_preview = None
        photo.width = original_width
        photo.height = original_height
        photo.mime_type = "image/webp"
        photo.status = PhotoStatus.READY
        photo.source_user = user
        photo.save(
            update_fields=[
                "thumbnail",
                "preview",
                "watermarked_preview",
                "width",
                "height",
                "mime_type",
                "status",
                "source_user",
                "updated_at",
            ]
        )

        logger.info("process_photo: Photo %s processed successfully.", photo_id)

        # Encadeia a geração do watermark se a galeria tiver watermark ativo
        if photo.gallery.watermark_enabled:
            apply_watermark.enqueue(str(photo.pk))

    except Exception:
        logger.exception("process_photo: failed for Photo %s.", photo_id)
        mark_photo_failed(photo)


@task()
def sync_gallery_drive(gallery_id: str, user_id: int) -> None:
    """
    Lista todos os JPEGs na pasta do Drive e enfileira process_photo para cada
    arquivo, incluindo fotos existentes.

    O watermark é controlado pela flag watermark_enabled da Gallery — nenhum
    parâmetro extra precisa ser passado aqui. Basta habilitar watermark_enabled
    na galeria antes de sincronizar.
    """
    try:
        gallery = Gallery.objects.get(pk=gallery_id)
    except Gallery.DoesNotExist:
        logger.error("sync_gallery_drive: Gallery %s not found.", gallery_id)
        return

    if not gallery.source_folder_id:
        logger.warning("sync_gallery_drive: Gallery %s has no source_folder_id, skipping.", gallery_id)
        return

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("sync_gallery_drive: User %s not found.", user_id)
        return

    service = GoogleDriveService(user)

    try:
        drive_files = service.list_files(gallery.source_folder_id)
    except ValueError as exc:
        logger.error("sync_gallery_drive: Drive error for Gallery %s — %s", gallery_id, exc)
        return

    jpeg_files = [f for f in drive_files if f.mime_type in JPEG_MIME_TYPES]

    enqueued = 0
    for drive_file in jpeg_files:
        photo, _created = Photo.objects.update_or_create(
            gallery=gallery,
            source_file_id=drive_file.id,
            defaults={
                "name": drive_file.name,
                "size": drive_file.size,
                "status": PhotoStatus.PROCESSING,
            },
        )

        process_photo.enqueue(str(photo.pk), user_id)
        enqueued += 1

    gallery.last_synced_at = timezone.now()
    gallery.save(update_fields=["last_synced_at", "updated_at"])

    logger.info(
        "sync_gallery_drive: Gallery %s — %d new photos enqueued (%d skipped). watermark_enabled=%s",
        gallery_id,
        enqueued,
        len(jpeg_files) - enqueued,
        gallery.watermark_enabled,
    )


@task()
def apply_watermark(photo_id: str) -> None:
    """
    Gera o preview com marca d'água anti-IA e salva em Photo.watermarked_preview.

    Técnicas de resistência implementadas (ver _apply_text_watermark):
    - Grid diagonal cobrindo 100% da imagem (tiling completo)
    - Variação aleatória de tamanho, rotação e opacidade por instância
    - Outline de contraste em cada texto (dificulta segmentação por IA)
    - Blur nas bordas do logo (dificulta detecção de máscara)

    Por que não watermark invisível (steganográfico)?
    Pesquisas de 2024 (NeurIPS) mostram que watermarks invisíveis podem ser
    removidos adicionando ruído e reconstruindo via diffusion model. O watermark
    visível denso é mais difícil de remover sem destruir o conteúdo da imagem.
    """
    try:
        photo = Photo.objects.select_related("gallery__watermark_asset").get(pk=photo_id)
    except Photo.DoesNotExist:
        logger.error("apply_watermark: Photo %s not found, skipping.", photo_id)
        return

    gallery = photo.gallery

    if not gallery.watermark_enabled:
        logger.info("apply_watermark: Gallery %s has watermark disabled, skipping.", gallery.pk)
        return

    asset = _resolve_watermark_asset(gallery)
    if asset is None:
        logger.warning(
            "apply_watermark: Photo %s — watermark habilitado mas nenhum WatermarkAsset configurado.",
            photo_id,
        )
        return

    if not photo.preview:
        logger.warning("apply_watermark: Photo %s sem preview gerado, skipping.", photo_id)
        return

    source_preview = photo.preview.name
    try:
        with photo.preview.open("rb") as preview_file, Image.open(preview_file) as img:
            img_rgb = img.convert("RGB")

        img_wm = _build_watermarked_image(img_rgb, asset)

        buf = io.BytesIO()
        img_wm.save(buf, format="WEBP", quality=PreviewSettings.current().quality, method=6)
        watermarked_bytes = buf.getvalue()

        base_name = f"{filename_stem(photo.name)}_{uuid.uuid4().hex}"
        photo.watermarked_preview.save(
            f"{base_name}_wm.webp",
            ContentFile(watermarked_bytes),
            save=False,
        )
        updated = Photo.objects.filter(
            pk=photo.pk,
            preview=source_preview,
            gallery__watermark_enabled=True,
        ).update(watermarked_preview=photo.watermarked_preview.name, updated_at=timezone.now())
        if not updated:
            logger.info("apply_watermark: discarded outdated rendition for photo %s", photo.pk)
            return

        logger.info("apply_watermark: Photo %s watermarked successfully.", photo_id)

    except Exception:
        logger.exception("apply_watermark: failed for Photo %s.", photo_id)


@task()
def reapply_watermark_gallery(gallery_id: str) -> None:
    """
    Reenfileira apply_watermark para todas as fotos prontas de uma galeria.

    Útil quando:
    - O WatermarkAsset é atualizado (novo logo, novo texto)
    - watermark_enabled é ativado numa galeria que já tinha fotos processadas
    - A gallery é associada a um novo WatermarkAsset
    """
    try:
        gallery = Gallery.objects.get(pk=gallery_id)
    except Gallery.DoesNotExist:
        logger.error("reapply_watermark_gallery: Gallery %s not found.", gallery_id)
        return

    if not gallery.watermark_enabled:
        logger.warning(
            "reapply_watermark_gallery: Gallery %s tem watermark desabilitado. "
            "Habilite watermark_enabled antes de chamar esta task.",
            gallery_id,
        )
        return

    photos = Photo.objects.filter(gallery=gallery, status=PhotoStatus.READY)
    count = 0
    for photo in photos:
        apply_watermark.enqueue(str(photo.pk))
        count += 1

    logger.info(
        "reapply_watermark_gallery: Gallery %s — %d fotos enfileiradas para remarcar.",
        gallery_id,
        count,
    )
