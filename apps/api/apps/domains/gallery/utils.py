from __future__ import annotations

import io
import math
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .models import Photo, PhotoStatus


def filename_stem(filename: str) -> str:
    """Returns the filename without its extension."""
    return filename.rsplit(".", 1)[0] if "." in filename else filename


def mark_photo_failed(photo: Photo) -> None:
    """Marks a Photo as failed and saves only the status fields."""
    photo.status = PhotoStatus.FAILED
    photo.save(update_fields=["status", "updated_at"])


def _hex_to_rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    """Converte cor hex (#RRGGBB ou #RGB) + alpha inteiro (0-255) para RGBA."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    return r, g, b, alpha


@lru_cache(maxsize=256)
def _load_font(font_size: int) -> ImageFont.FreeTypeFont:
    """Use the bundled font consistently on every deployment."""
    return ImageFont.truetype(
        font=str(Path(__file__).parent / "fonts" / "Arimo.ttf"),
        size=font_size,
        layout_engine=ImageFont.Layout.BASIC,
    )


def _apply_text_watermark(
    img: Image.Image,
    text: str,
    color: str,
    opacity: float,
    font_size_ratio: float,
    rotation_angle: int,
    tile_spacing: int,
    *,
    randomize: bool = True,
) -> Image.Image:
    """
    Sobrepõe um grid diagonal de texto sobre toda a imagem.

    Técnicas anti-IA aplicadas (baseadas em pesquisa 2024-2025):

    1. TILING COMPLETO — o texto cobre 100% da imagem, não só cantos.
       Inpainting de IA precisa reconstruir toda a área, aumentando artefatos.

    2. VARIAÇÃO ALEATÓRIA — cada instância tem tamanho e opacidade
       ligeiramente diferentes, impedindo que redes neurais reconheçam um
       padrão único para remover.

    3. OUTLINE + SOMBRA — adiciona contorno escuro ao redor do texto claro
       (e vice-versa). A borda torna o texto visível sobre qualquer fundo
       e aumenta a complexidade de segmentação para a IA.

    4. POSICIONAMENTO SOBRE DETALHES — o grid denso garante que o watermark
       sempre incide sobre áreas de textura complexa (onde inpaint é mais
       difícil), não apenas sobre fundos lisos.
    """
    width, height = img.size
    base_font_size = max(12, int(width * font_size_ratio))
    alpha = int(opacity * 255)
    r, g, b, _alpha = _hex_to_rgba(color, alpha)

    # Cria layer transparente para compositing
    watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))

    diagonal = int(math.sqrt(width**2 + height**2))

    # Pré-mede o tile base para calcular o step
    base_font = _load_font(base_font_size)
    base_bbox = base_font.getbbox(text)
    base_text_w = base_bbox[2] - base_bbox[0]
    base_text_h = base_bbox[3] - base_bbox[1]

    step_x = max(base_text_w + tile_spacing, tile_spacing + 10)
    step_y = max(base_text_h + tile_spacing, tile_spacing + 10)

    # Keep per-tile variation stable across previews and background processing.
    # reproducible so editing parameters does not move the whole watermark.
    random_state = (width ^ (height << 16)) & 0xFFFFFFFF

    def next_random():
        nonlocal random_state
        random_state = (1664525 * random_state + 1013904223) & 0xFFFFFFFF
        return random_state / 4294967296

    for y in range(-diagonal, diagonal + step_y, step_y):
        for x in range(-diagonal, diagonal + step_x, step_x):
            # Variação aleatória por instância (técnica 2)
            if randomize:
                size_var = 0.85 + next_random() * 0.3
                alpha_var = max(30, min(255, int(alpha * (0.75 + next_random() * 0.35))))
            else:
                size_var = 1.0
                alpha_var = alpha

            font_size = max(10, int(base_font_size * size_var))
            font = _load_font(font_size)
            bbox = font.getbbox(text)
            tw, th = bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 20

            tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            tile_draw = ImageDraw.Draw(tile)

            # Técnica 3: outline escuro para contraste sobre qualquer fundo
            outline_alpha = min(255, alpha_var + 80)
            outline_color = (0, 0, 0, outline_alpha)
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
                tile_draw.text((10 + dx, 10 + dy), text, font=font, fill=outline_color, anchor="lt")

            tile_draw.text((10, 10), text, font=font, fill=(r, g, b, alpha_var), anchor="lt")

            rotated = tile.rotate(rotation_angle, expand=True, resample=Image.BICUBIC)
            watermark_layer.paste(rotated, (x, y), rotated)

    # Compositing final
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    result = Image.alpha_composite(img, watermark_layer)
    return result.convert("RGB")


def _apply_logo_watermark(
    img: Image.Image,
    logo: Image.Image,
    opacity: float,
    size_ratio: float,
    position: str,
) -> Image.Image:
    """
    Sobrepõe um logo/PNG com opacidade controlada.

    O logo é borrado levemente com um filtro passa-alta para aumentar
    a complexidade de segmentação pela IA (bordas menos nítidas = harder to mask).
    """
    width, height = img.size
    logo_w = max(1, int(width * size_ratio))
    logo_h = max(1, int(logo.height * (logo_w / logo.width)))
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")

    # Aplica opacidade
    if opacity < 1.0:
        r_ch, g_ch, b_ch, a_ch = logo.split()
        a_ch = a_ch.point(lambda p: int(p * opacity))
        logo = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))

    # Leve blur nas bordas para dificultar segmentação por IA
    logo = logo.filter(ImageFilter.GaussianBlur(radius=0.5))

    margin = max(10, int(width * 0.015))
    positions = {
        "top_left": (margin, margin),
        "top_right": (width - logo_w - margin, margin),
        "bottom_left": (margin, height - logo_h - margin),
        "bottom_right": (width - logo_w - margin, height - logo_h - margin),
        "center": ((width - logo_w) // 2, (height - logo_h) // 2),
    }
    pos = positions.get(position, positions["bottom_right"])

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    img.paste(logo, pos, logo)
    return img.convert("RGB")


def _build_watermarked_image(img: Image.Image, asset) -> Image.Image:
    """
    Aplica todas as camadas de watermark de acordo com o WatermarkAsset.

    Ordem: texto diagonal primeiro (cobre toda a imagem), depois logo
    por cima (âncora visual de identidade de marca).
    """
    style = asset.style

    if style in ("text_diagonal", "combined") and asset.text:
        img = _apply_text_watermark(
            img=img,
            text=asset.text,
            color=asset.text_color,
            opacity=asset.text_opacity,
            font_size_ratio=asset.font_size_ratio,
            rotation_angle=asset.rotation_angle,
            tile_spacing=asset.tile_spacing,
            randomize=True,
        )

    if style in ("image_overlay", "combined") and asset.logo:
        with Image.open(asset.logo) as logo_img:
            logo_rgba = logo_img.convert("RGBA")
        img = _apply_logo_watermark(
            img=img,
            logo=logo_rgba,
            opacity=asset.logo_opacity,
            size_ratio=asset.logo_size_ratio,
            position=asset.logo_position,
        )

    return img


def convert_to_webp(img: Image.Image, size: tuple[int, int], quality: int = 85) -> bytes:
    """
    Returns WebP-encoded bytes of `img` resized to fit within `size`.

    Uses Image.reduce() for a fast integer downscale before the final
    LANCZOS pass, avoiding a full in-memory copy at the original resolution.
    """
    target_w, target_h = size
    src_w, src_h = img.size

    # Integer pre-scale: find the largest factor that keeps both dimensions
    # at or above the target before the LANCZOS pass.
    factor = max(1, min(src_w // target_w, src_h // target_h))
    img = img.reduce(factor) if factor > 1 else img.copy()

    img.thumbnail(size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()


def render_preview(source: bytes, settings: dict, logo: bytes | None = None) -> tuple[bytes, int, int]:
    """Run the production resize, encode, decode and watermark sequence."""
    quality = settings.get("quality", 85)
    max_size = settings.get("maxSize", 1920)

    if not isinstance(quality, int) or not 40 <= quality <= 100:
        raise ValueError("Invalid WebP quality")

    if not isinstance(max_size, int) or not 800 <= max_size <= 4096:
        raise ValueError("Invalid preview size")

    with Image.open(io.BytesIO(source)) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        encoded = convert_to_webp(image, (max_size, max_size), quality=quality)

    with Image.open(io.BytesIO(encoded)) as preview:
        width, height = preview.size
        watermark = settings.get("watermark")

        if watermark:
            asset = SimpleNamespace(**(watermark | {"logo": io.BytesIO(logo) if logo else None}))
            marked = _build_watermarked_image(preview.convert("RGB"), asset)
            output = io.BytesIO()
            marked.save(output, format="WEBP", quality=quality, method=6)
            encoded = output.getvalue()

    return encoded, width, height
