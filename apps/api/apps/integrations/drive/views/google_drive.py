from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers.base.constants import AuthProcess
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.urls import reverse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..serializers import GoogleDriveFileSerializer, GoogleDriveFolderSerializer
from ..services import GoogleDriveService


class GoogleDriveViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def status(self, request):
        """Returns whether the current user has a connected Google account."""
        account = SocialAccount.objects.filter(
            user=request.user,
            provider="google",
        ).first()

        return Response(
            {
                "connected": account is not None,
                "email": account.extra_data.get("email") if account else None,
                "configured": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
                "client_id": settings.GOOGLE_CLIENT_ID or None,
                "callback_url": request.build_absolute_uri(reverse("google_callback")),
            }
        )

    @action(detail=False, methods=["post"])
    def connect(self, request):
        """
        Returns the OAuth URL the frontend must redirect the user to.

        allauth picks up SCOPE and AUTH_PARAMS (access_type=offline,
        prompt=consent) from SOCIALACCOUNT_PROVIDERS in settings, so the
        resulting token always includes a refresh_token suitable for Drive.
        """
        if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
            return Response({"detail": "Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no servidor."}, status=400)

        callback_url = request.data.get(
            "callback_url",
            f"{settings.FRONTEND_URL.rstrip('/')}/setup/drive",
        )

        if not isinstance(callback_url, str) or not get_account_adapter().is_safe_url(callback_url):
            raise serializers.ValidationError({"callback_url": "Endereço de retorno não permitido."})

        oauth_request = request._request
        try:
            provider = get_socialaccount_adapter(oauth_request).get_provider(oauth_request, "google")
        except (Socialapps.doesNotExist, MultipleObjectsReturned):
            return Response(
                data={"detail": "Configure uma única aplicação OAuth do Google antes de conectar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        redirect = provider.redirect(
            oauth_request,
            process=AuthProcess.CONNECT,
            next_url=callback_url,
            headless=True,
        )
        return Response({"url": redirect.url})

    @action(detail=False, methods=["delete"])
    def disconnect(self, request):
        """Removes the connected Google account and its stored tokens."""
        accounts = SocialAccount.objects.filter(
            user=request.user,
            provider="google",
        )

        if not accounts.exists():
            return Response(
                data={"detail": "Google não conectado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        accounts.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------------
    # Drive browsing
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="folders")
    def folders(self, request):
        """
        Lists folders inside a Drive directory.

        Query params:
          - parent_id  (optional) — Drive folder ID. Defaults to "root".
        """
        account = SocialAccount.objects.filter(user=request.user, provider="google").first()

        if account is None:
            return Response(
                {"detail": "Google Drive não conectado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        search = request.query_params.get("search", "").strip()
        parent_id = request.query_params.get("parent_id", None if search else "root")
        service = GoogleDriveService(request.user)

        try:
            folders = (
                service.list_folder_tree()
                if request.query_params.get("tree") == "true"
                else service.list_folders(parent_id, search=search)
            )
            if request.query_params.get("tree") == "true" and search:
                folders = [folder for folder in folders if search.casefold() in folder.path.casefold()]
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(GoogleDriveFolderSerializer(folders, many=True).data)

    @action(detail=False, methods=["get"], url_path="files")
    def files(self, request):
        """
        Lists files inside a Drive folder.

        Query params:
          - folder_id  (required) — Drive folder ID to list files from.
        """
        account = SocialAccount.objects.filter(
            user=request.user,
            provider="google",
        ).first()

        if account is None:
            return Response(
                {"detail": "Google Drive não conectado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        folder_id = request.query_params.get("folder_id")
        if not folder_id:
            return Response(
                {"detail": "O parâmetro 'folder_id' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = GoogleDriveService(request.user)

        try:
            files = service.list_files(folder_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if request.query_params.get("summary") == "1":
            counts = {}
            for file in files:
                counts[file.mime_type] = counts.get(file.mime_type, 0) + 1
            return Response({"count": len(files), "mime_counts": counts})
        return Response(GoogleDriveFileSerializer(files, many=True).data)
