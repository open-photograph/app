from django.contrib.auth.hashers import check_password
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from ..models import Gallery, GalleryTag, PhotoStatus
from ..serialzers import GallerySerializer, GalleryTagSerializer
from ..serialzers.photo import PublicPhotoSerializer
from ..services.downloads import download_photo_preview
from ..services.included import included_summary
from ..tasks import reapply_watermark_gallery, sync_gallery_drive
from .feedback import GalleryFeedbackMixin
from .included import GalleryIncludedMixin


class GalleryTagViewSet(viewsets.ModelViewSet):
    queryset = GalleryTag.objects.annotate(gallery_count=Count("galleries", distinct=True)).order_by("title", "id")
    serializer_class = GalleryTagSerializer
    permission_classes = [IsAdminUser]


class GalleryViewSet(GalleryIncludedMixin, GalleryFeedbackMixin, viewsets.ModelViewSet):
    queryset = Gallery.objects.prefetch_related("tags", "clients").all()
    serializer_class = GallerySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["access_type", "is_published"]
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_public_gallery(self, request, slug):
        gallery = get_object_or_404(self.queryset, slug=slug, is_published=True)
        if gallery.is_private and not check_password(
            request.headers.get("X-Gallery-Access-Code", ""), gallery.access_code_hash
        ):
            raise PermissionDenied("Informe o codigo de acesso.")
        return gallery

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path=r"public/(?P<slug>[-\w]+)")
    def public(self, request, slug=None):
        gallery = self.get_public_gallery(request, slug)
        serialized = self.get_serializer(gallery).data
        public_fields = [
            "id",
            "name",
            "slug",
            "description",
            "theme",
            "access_type",
            "is_published",
            "allow_downloads",
            "allow_likes",
            "allow_comments",
            "allow_selection",
            "enable_sales",
            "included_photo_mode",
            "included_photo_limit",
            "allow_individual_purchase",
            "gallery_price",
            "gallery_price_currency",
            "default_photo_price",
            "watermark_enabled",
            "tags",
        ]
        data = {key: serialized[key] for key in public_fields}
        data["allow_individual_purchase"] = gallery.individual_sales_enabled
        from apps.domains.commerce.services.pricing import package_balance

        balance = package_balance(gallery, request.user)
        data["package_discount"] = str(balance["discount"])
        data["package_remaining"] = str(balance["remaining"])
        photos = gallery.photos.filter(status=PhotoStatus.READY, is_active=True).select_related("gallery")
        summary = included_summary(gallery, request.user)
        data["included_remaining"] = summary["remaining"]
        data["included_used"] = summary["used"]
        data["included_eligible"] = summary["eligible"]
        context = {**self.get_serializer_context(), "included_ids": summary["ids"]}
        data["photos"] = PublicPhotoSerializer(photos, many=True, context=context).data
        response = Response(data)
        response["Cache-Control"] = "private, no-store"
        return response

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path=r"public/(?P<slug>[-\w]+)/photos/(?P<photo_id>[0-9a-f-]+)/download",
    )
    def download(self, request, slug=None, photo_id=None):
        gallery = self.get_public_gallery(request, slug)
        photo = get_object_or_404(
            gallery.photos.select_related("gallery"),
            pk=photo_id,
            status=PhotoStatus.READY,
            is_active=True,
        )
        return download_photo_preview(photo)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        gallery = self.get_object()
        gallery.publish()
        return Response(self.get_serializer(gallery).data)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        gallery = self.get_object()
        gallery.unpublish()
        return Response(self.get_serializer(gallery).data)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """
        Enqueues a Drive sync for this gallery.

        Requires the gallery to have a source_folder_id set and the current
        user to have a connected Google Drive account.
        """
        gallery = self.get_object()

        if not gallery.source_folder_id:
            return Response(
                {"detail": "A gallery não tem uma pasta do Drive vinculada (source_folder_id)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sync_gallery_drive.enqueue(str(gallery.pk), request.user.pk)

        return Response(
            {"detail": "Sincronização iniciada."},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="reapply-watermark")
    def reapply_watermark(self, request, pk=None):
        """
        Reenfileira a geração de marca d'água para todas as fotos prontas desta galeria.

        Use quando:
        - O WatermarkAsset foi atualizado (novo logo, novo texto).
        - watermark_enabled foi ativado numa galeria que já tinha fotos processadas.
        - A galeria foi associada a um novo WatermarkAsset.
        """
        gallery = self.get_object()

        if not gallery.watermark_enabled:
            return Response(
                {"detail": "watermark_enabled está desativado nesta galeria. Ative-o primeiro."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reapply_watermark_gallery.enqueue(str(gallery.pk))

        return Response(
            {"detail": "Reaplicação de marca d'água iniciada para todas as fotos desta galeria."},
            status=status.HTTP_202_ACCEPTED,
        )
