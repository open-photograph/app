from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from ..models import Gallery, IncludedPhoto, PhotoStatus


def included_summary(gallery, user):
    choices = set()
    eligible = False
    if user.is_authenticated:
        choices = set(IncludedPhoto.objects.filter(gallery=gallery, user=user).values_list("photo_id", flat=True))
        eligible = gallery.clients.filter(Q(user=user) | Q(user__isnull=True, email__iexact=user.email)).exists()
    return {
        "ids": choices,
        "eligible": eligible and gallery.included_photo_mode == "client",
        "remaining": max(0, gallery.included_photo_limit - len(choices)),
        "used": len(choices),
    }


def original_is_included(photo, user):
    if photo.gallery.included_photo_mode == "all":
        return True
    return (photo.gallery.included_photo_mode == "photographer" and photo.is_included) or (
        user.is_authenticated and IncludedPhoto.objects.filter(photo=photo, user=user).exists()
    )


@transaction.atomic
def claim_included_photo(gallery, user, photo_id):
    # Serialize claims (including concurrent requests from different tabs).
    gallery = Gallery.objects.select_for_update().get(pk=gallery.pk)
    photo = get_object_or_404(gallery.photos, pk=photo_id, is_active=True, status=PhotoStatus.READY)
    if IncludedPhoto.objects.filter(photo=photo, user=user).exists():
        return photo
    if gallery.included_photo_mode != "client":
        raise PermissionDenied("Esta galeria não oferece franquia de fotos.")
    from apps.domains.commerce.services.order import OrderService

    buyer = OrderService()._buyer_for(user)
    if not gallery.clients.filter(pk=buyer.pk).exists():
        raise PermissionDenied("A franquia está disponível apenas aos clientes vinculados a esta galeria.")
    if IncludedPhoto.objects.filter(gallery=gallery, user=user).count() >= gallery.included_photo_limit:
        raise ValidationError("Você já utilizou todas as fotos incluídas nesta galeria.")
    if not photo.source_file_id or not photo.source_user_id:
        raise ValidationError("O original desta foto ainda não está disponível.")
    # Paid photos should not consume an included choice.
    if photo.purchases.filter(order__client__user=user, order__status="paid").exists():
        raise ValidationError("Esta foto já está disponível em Minhas fotos.")
    IncludedPhoto.objects.create(gallery=gallery, photo=photo, user=user)
    return photo
