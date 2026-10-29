from pathlib import Path

from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ..models import IncludedPhoto, PhotoStatus
from ..serialzers.photo import PublicPhotoSerializer
from ..services.included import claim_included_photo, original_is_included


class IncludedPhotoInput(serializers.Serializer):
    photo_id = serializers.UUIDField()


class GalleryIncludedMixin:
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path=r"public/(?P<slug>[-\w]+)/included-photos",
    )
    def included_photos(self, request, slug=None):
        gallery = self.get_public_gallery(request, slug)
        choices = set(
            IncludedPhoto.objects.filter(gallery=gallery, user=request.user).values_list("photo_id", flat=True)
        )
        available = Q(pk__in=choices)
        if gallery.included_photo_mode == "all":
            available = Q()
        if gallery.included_photo_mode == "photographer":
            available |= Q(is_included=True)
        photos = gallery.photos.filter(available, is_active=True, status=PhotoStatus.READY).select_related("gallery")
        context = {**self.get_serializer_context(), "included_ids": choices}
        return Response(
            PublicPhotoSerializer(photos, many=True, context=context).data,
            headers={"Cache-Control": "private, no-store"},
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path=r"public/(?P<slug>[-\w]+)/included",
    )
    def claim_included(self, request, slug=None):
        gallery = self.get_public_gallery(request, slug)
        serializer = IncludedPhotoInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = claim_included_photo(gallery, request.user, serializer.validated_data["photo_id"])
        return Response({"photo_id": str(photo.pk)})

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path=r"public/(?P<slug>[-\w]+)/photos/(?P<photo_id>[0-9a-f-]+)/original",
    )
    def included_original(self, request, slug=None, photo_id=None):
        from apps.domains.commerce.services.download import open_original

        gallery = self.get_public_gallery(request, slug)
        photo = get_object_or_404(
            gallery.photos.select_related("gallery"), pk=photo_id, is_active=True, status=PhotoStatus.READY
        )
        if not original_is_included(photo, request.user):
            raise PermissionDenied("O original desta foto não está incluído para sua conta.")
        response = FileResponse(
            open_original(photo), as_attachment=True, filename=Path(photo.name).stem + ".jpg", content_type="image/jpeg"
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
