from rest_framework.routers import DefaultRouter

from .views import GoogleDriveViewSet

router = DefaultRouter()
router.register(r"drive/google", GoogleDriveViewSet, basename="drive")

urlpatterns = router.urls
