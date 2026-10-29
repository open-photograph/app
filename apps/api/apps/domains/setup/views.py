from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import Setup, SetupCategory
from .serializers import SetupSerializer

User = get_user_model()


class SetupViewSet(viewsets.ModelViewSet):
    queryset = Setup.objects.order_by("type")
    serializer_class = SetupSerializer
    permission_classes = [IsAdminUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        values = dict(serializer.validated_data)
        setup_type = values.pop("type")
        values.setdefault("is_active", True)
        values.setdefault("name", values["provider"])

        setup, _created = Setup.objects.update_or_create(
            type=setup_type,
            defaults=values,
        )

        return Response(
            self.get_serializer(setup).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="status",
        permission_classes=[AllowAny],
    )
    def status(self, request):
        has_admin = User.objects.filter(
            is_superuser=True,
            photographer__isnull=False,
        ).exists()

        has_drive = Setup.objects.filter(type=SetupCategory.STORAGE, is_active=True).exists()
        has_payment = Setup.objects.filter(type=SetupCategory.PAYMENT, is_active=True).exists()

        return Response(
            {
                "needs_setup": not has_admin,
                "has_admin": has_admin,
                "has_drive": has_drive,
                "has_payment": has_payment,
            }
        )
