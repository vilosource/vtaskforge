from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Link
from .serializers import LinkSerializer


class LinkViewSet(ModelViewSet):
    queryset = Link.objects.all()
    serializer_class = LinkSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Link.objects.all()
        source_id = self.request.query_params.get("source_id")
        target_id = self.request.query_params.get("target_id")
        source_type = self.request.query_params.get("source_type")
        link_type = self.request.query_params.get("link_type")

        if source_id is not None:
            queryset = queryset.filter(source_id=source_id)
        if target_id is not None:
            queryset = queryset.filter(target_id=target_id)
        if source_type is not None:
            queryset = queryset.filter(source_type=source_type)
        if link_type is not None:
            queryset = queryset.filter(link_type=link_type)

        return queryset

    def retrieve(self, request, *args, **kwargs):
        return Response(
            {"detail": "Method not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Method not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Method not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
