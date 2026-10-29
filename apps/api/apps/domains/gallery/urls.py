from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import GalleryTagViewSet, GalleryViewSet, PhotoViewSet
from .views.image_preview import ImagePreviewView
from .views.preview_settings import PreviewSettingsView

router = DefaultRouter()
router.register(r"galleries", GalleryViewSet)
router.register(r"tags", GalleryTagViewSet)
router.register(r"photos", PhotoViewSet)

urlpatterns = [
    path("gallery-preview-settings/render/", ImagePreviewView.as_view()),
    path("gallery-preview-settings/", PreviewSettingsView.as_view()),
    *router.urls,
]
