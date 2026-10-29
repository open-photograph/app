from rest_framework.routers import DefaultRouter

from .views import ContractTemplateViewSet, ContractViewSet, SignatureProviderViewSet

router = DefaultRouter()
router.register("contract-templates", ContractTemplateViewSet)
router.register("signature-providers", SignatureProviderViewSet)
router.register("contracts", ContractViewSet)
urlpatterns = router.urls
