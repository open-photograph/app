import uuid

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ..models import GallerySelection, Photo, PhotoComment, PhotoLike, PhotoStatus
from ..serialzers.feedback import (
    CommentInputSerializer,
    GallerySelectionSerializer,
    LikeInputSerializer,
    PhotoCommentSerializer,
    SelectionInputSerializer,
)


class GalleryFeedbackMixin:
    def _visitor(self, request):
        if "gallery_visitor" not in request.session:
            request.session["gallery_visitor"] = str(uuid.uuid4())
        return request.session["gallery_visitor"]

    def _require_feature(self, request, gallery, feature):
        SessionAuthentication().enforce_csrf(request)
        if not getattr(gallery, feature):
            raise PermissionDenied("Esta interação está desativada para esta galeria.")

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path=r"public/(?P<slug>[-\w]+)/feedback")
    def public_feedback(self, request, slug=None):
        gallery = self.get_public_gallery(request, slug)
        visitor = self._visitor(request)
        photos = gallery.photos.filter(status=PhotoStatus.READY, is_active=True)
        response = Response(
            {
                "liked_photo_ids": list(
                    PhotoLike.objects.filter(photo__in=photos, user=request.user).values_list("photo_id", flat=True)
                    if request.user.is_authenticated
                    else []
                ),
                "like_counts": {
                    str(photo["id"]): photo["count"]
                    for photo in photos.annotate(count=Count("likes")).values("id", "count")
                },
                "comments": PhotoCommentSerializer(
                    PhotoComment.objects.filter(
                        Q(user__isnull=False) | Q(visitor=visitor), photo__in=photos
                    ).select_related("photo"),
                    many=True,
                ).data,
                "selections": GallerySelectionSerializer(
                    gallery.selections.filter(visitor=visitor).prefetch_related(
                        Prefetch("photos", queryset=Photo.objects.filter(is_active=True))
                    ),
                    many=True,
                ).data,
            }
        )
        response["Cache-Control"] = "private, no-store"
        return response

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path=r"public/(?P<slug>[-\w]+)/like",
    )
    def like(self, request, slug=None):
        gallery = self.get_public_gallery(request, slug)
        self._require_feature(request, gallery, "allow_likes")

        serializer = LikeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        photo = get_object_or_404(
            gallery.photos,
            pk=serializer.validated_data["photo_id"],
            status=PhotoStatus.READY,
            is_active=True,
        )

        lookup = {
            "photo": photo,
            "user": request.user,
        }

        if serializer.validated_data["liked"]:
            PhotoLike.objects.get_or_create(**lookup)
        else:
            PhotoLike.objects.filter(**lookup).delete()

        return Response({"liked": serializer.validated_data["liked"]})

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path=r"public/(?P<slug>[-\w]+)/comment",
    )
    def comment(self, request, slug=None):
        gallery = self.get_public_gallery(request, slug)
        self._require_feature(request, gallery, "allow_comments")
        serializer = CommentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        values = serializer.validated_data.copy()
        photo = get_object_or_404(
            gallery.photos,
            pk=values.pop("photo_id"),
            status=PhotoStatus.READY,
            is_active=True,
        )

        name = (request.user.get_full_name() or request.user.get_username())[:120]

        comment = PhotoComment.objects.create(
            photo=photo,
            user=request.user,
            name=name,
            **values,
        )

        return Response(PhotoCommentSerializer(comment).data, status=201)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        url_path=r"public/(?P<slug>[-\w]+)/selection",
    )
    def selection(self, request, slug=None):
        gallery = self.get_public_gallery(request, slug)
        self._require_feature(request, gallery, "allow_selection")
        serializer = SelectionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data.copy()

        photo_ids = set(values.pop("photo_ids"))
        photos = list(
            gallery.photos.filter(
                pk__in=photo_ids,
                status=PhotoStatus.READY,
                is_active=True,
            )
        )

        if len(photos) != len(photo_ids):
            raise ValidationError({"photo_ids": "Selecione apenas fotos disponíveis nesta galeria."})

        with transaction.atomic():
            selection = GallerySelection.objects.create(
                gallery=gallery,
                visitor=self._visitor(request),
                **values,
            )
            selection.photos.set(photos)

        return Response(GallerySelectionSerializer(selection).data, status=201)

    @action(detail=True, methods=["get"])
    def feedback(self, request, pk=None):
        gallery = self.get_object()
        return Response(
            {
                "likes": list(
                    gallery.photos.annotate(count=Count("likes")).filter(count__gt=0).values("id", "name", "count")
                ),
                "comments": PhotoCommentSerializer(
                    PhotoComment.objects.filter(photo__gallery=gallery).select_related("photo"), many=True
                ).data,
                "selections": GallerySelectionSerializer(gallery.selections.prefetch_related("photos"), many=True).data,
            }
        )
