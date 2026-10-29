from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, WatermarkAssetViewSet

router = DefaultRouter()
router.register(r"commerce/orders", OrderViewSet, basename="order")
router.register(r"commerce/watermarks", WatermarkAssetViewSet, basename="watermark")

urlpatterns = router.urls
