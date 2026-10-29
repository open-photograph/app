from rest_framework.routers import DefaultRouter

from .views import SetupViewSet

router = DefaultRouter()
router.register(r"setup", SetupViewSet, basename="setup")

urlpatterns = router.urls
