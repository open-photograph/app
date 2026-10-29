import logging

from rest_framework.exceptions import APIException

from apps.integrations.drive.services import GoogleDriveService

logger = logging.getLogger(__name__)


class OriginalUnavailable(APIException):
    status_code = 503


def open_original(photo):
    if not photo.source_user_id or not photo.source_file_id:
        raise OriginalUnavailable("Original indisponivel. Contate o fotografo.")

    stream = None
    try:
        stream = GoogleDriveService(photo.source_user).open_file(photo.source_file_id)
        signature = stream.read(3)
        stream.seek(0)
    except Exception:
        if stream is not None:
            stream.close()
        logger.exception("Original download failed for photo %s", photo.pk)
        raise OriginalUnavailable("Nao foi possivel acessar o original. Tente novamente.") from None

    if signature != b"\xff\xd8\xff":
        stream.close()
        raise OriginalUnavailable("O arquivo de origem nao e um JPEG.")

    return stream
