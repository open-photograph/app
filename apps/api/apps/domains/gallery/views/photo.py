from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..models import Photo, PhotoStatus
from ..serialzers import PhotoSerializer
from ..tasks import process_photo


class PhotoViewSet(viewsets.ModelViewSet):
    queryset = Photo.objects.select_related("gallery", "exif").all()
    serializer_class = PhotoSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        gallery_id = self.request.query_params.get("gallery")

        if gallery_id:
            queryset = queryset.filter(gallery_id=gallery_id)

        return queryset

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        photo = self.get_object()
        if not photo.source_file_id:
            return Response(
                {"detail": "Esta foto nao tem arquivo de origem vinculado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        photo.status = PhotoStatus.PROCESSING
        photo.save(update_fields=["status", "updated_at"])
        process_photo.enqueue(str(photo.pk), request.user.pk)
        return Response({"detail": "Sincronizacao da foto solicitada."}, status=status.HTTP_202_ACCEPTED)
