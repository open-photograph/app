from datetime import timedelta
from pathlib import Path

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ..models import Order
from ..serializers.order import OrderCreateSerializer, OrderSerializer
from ..services.download import open_original
from ..services.order import OrderService
from ..services.payment import PaymentError


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------

    def get_queryset(self):
        queryset = Order.objects.select_related("client").prefetch_related(
            "items__gallery",
            "items__photo",
            "order_photos__photo__gallery",
        )
        own_orders = queryset.filter(client__user=self.request.user)

        match self.action:
            case "mine" | "refresh" | "download":
                return own_orders
            case _ if self.request.user.is_staff:
                return queryset
            case _:
                return own_orders

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def mine(self, request):
        queryset = self.get_queryset()
        gallery_slug = request.query_params.get("gallery")

        if gallery_slug:
            queryset = queryset.filter(order_photos__photo__gallery__slug=gallery_slug).distinct()

        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=["post"])
    def checkout(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order = OrderService().checkout(request.user, data)

        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        order = self.get_object()

        try:
            OrderService().refresh_payment(order)
        except PaymentError as exc:
            return Response(
                data={"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["get"], url_path=r"download/(?P<photo_id>[0-9a-f-]+)")
    def download(self, request, pk=None, photo_id=None):
        order = self.get_object()

        if order.payment_reference:
            try:
                OrderService().refresh_payment(order)
            except PaymentError:
                return Response(
                    data={"detail": "Nao foi possivel verificar o pagamento."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        if not order.is_paid:
            return Response(
                data={"detail": "O download requer pagamento aprovado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        purchased = get_object_or_404(order.order_photos.select_related("photo"), photo_id=photo_id)
        stream = open_original(purchased.photo)
        return self._jpeg_response(stream, purchased.photo.name)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def mark_paid(self, request, pk=None):
        order = self.get_object()

        OrderService().mark_as_paid(order)

        return Response(self.get_serializer(order).data)

    @staticmethod
    def _jpeg_response(stream, photo_name):
        response = FileResponse(
            stream,
            as_attachment=True,
            filename=Path(photo_name).stem + ".jpg",
            content_type="image/jpeg",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"

        return response

    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
    def sales(self, request):
        from ..models.order import OrderStatus

        try:
            days = int(request.query_params.get("days", "30"))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"days": "Período inválido."}) from exc
        if days not in (7, 30, 90):
            raise ValidationError({"days": "Use 7, 30 ou 90 dias."})

        today = timezone.localdate()
        start = today - timedelta(days=days - 1)
        paid = Order.objects.filter(status=OrderStatus.PAID).annotate(
            sale_date=TruncDate(Coalesce("paid_at", "created_at"))
        )
        currencies = list(paid.order_by("total_currency").values_list("total_currency", flat=True).distinct())
        currency = request.query_params.get("currency") or (currencies[0] if currencies else "BRL")
        if currency not in currencies and currencies:
            raise ValidationError({"currency": "Moeda inválida."})
        orders = paid.filter(total_currency=currency, sale_date__gte=start, sale_date__lte=today)
        totals = orders.aggregate(count=Count("id"), revenue=Sum("total"))
        revenue = totals["revenue"] or 0
        daily = {
            row["sale_date"]: row
            for row in orders.order_by().values("sale_date").annotate(count=Count("id"), revenue=Sum("total"))
        }
        series = []
        for offset in range(days):
            date = start + timedelta(days=offset)
            row = daily.get(date, {})
            series.append(
                {"date": date.isoformat(), "count": row.get("count", 0), "revenue": str(row.get("revenue", 0))}
            )
        recent = orders.select_related("client").order_by("-paid_at", "-created_at", "-id")[:10]
        return Response(
            {
                "currency": currency,
                "currencies": currencies or [currency],
                "count": totals["count"],
                "revenue": str(revenue),
                "average": str(revenue / totals["count"] if totals["count"] else 0),
                "series": series,
                "recent": [
                    {
                        "id": str(order.pk),
                        "client_name": order.client.name,
                        "client_email": order.client.email,
                        "total": str(order.total.amount),
                        "paid_at": order.paid_at or order.created_at,
                        "payment_provider": order.payment_provider,
                    }
                    for order in recent
                ],
            }
        )
