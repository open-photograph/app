import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404
from rest_framework.exceptions import PermissionDenied


def download_photo_preview(photo):
    """Serve only the rendition that the public gallery is allowed to display."""
    if not photo.download_allowed:
        raise PermissionDenied("O fotógrafo não permite o download desta foto.")

    if not photo.can_download:
        raise Http404("A prévia desta foto ainda não está disponível.")

    preview = photo.public_preview
    filename = f"{Path(photo.name).stem}{Path(preview.name).suffix}"

    try:
        file = preview.open("rb")
    except FileNotFoundError as error:
        raise Http404("A prévia desta foto não está disponível.") from error

    response = FileResponse(
        file,
        as_attachment=True,
        filename=filename,
        content_type="image/webp"
        if Path(preview.name).suffix.lower() == ".webp"
        else mimetypes.guess_type(preview.name)[0] or "application/octet-stream",
    )

    response["Cache-Control"] = "private, no-store"
    return response
