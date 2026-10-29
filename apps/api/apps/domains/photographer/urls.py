from rest_framework.routers import DefaultRouter

from .views import PhotographerViewSet

router = DefaultRouter()

router.register(
    r"photographer",
    PhotographerViewSet,
    basename="photographer",
)

urlpatterns = router.urls
