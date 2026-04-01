"""API views for user preferences."""

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RecentAccess


class RecentAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecentAccess
        fields = ["resource_type", "resource_id", "resource_title", "resource_status", "accessed_at"]


class RecentAccessView(APIView):
    """GET /v1/profile/recent/ — list recently accessed resources."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Reject agent users (no usable password)
        if not request.user.has_usable_password():
            return Response(
                {"detail": "Agent tokens cannot access user profile endpoints."},
                status=status.HTTP_403_FORBIDDEN,
            )

        accesses = RecentAccess.objects.filter(user=request.user)[:20]
        serializer = RecentAccessSerializer(accesses, many=True)
        return Response({"results": serializer.data})
