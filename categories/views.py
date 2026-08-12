"""
Categories views.
"""

from django.db import models
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from categories.models import Category
from categories.serializers import CategoryCreateSerializer, CategorySerializer
from categories.services import CategoryService


class CategoryViewSet(ModelViewSet):
    """
    CRUD for categories. System categories are read-only.
    Users can create/edit/delete their custom categories.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Categories are always a small set

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CategoryCreateSerializer
        return CategorySerializer

    def get_queryset(self):
        qs = Category.objects.filter(
            models.Q(is_system=True) | models.Q(user=self.request.user)
        ).select_related("parent").prefetch_related("subcategories")

        category_type = self.request.query_params.get("type")
        if category_type:
            qs = qs.filter(category_type=category_type)

        # Only return top-level categories (no parent)
        if self.request.query_params.get("top_level") == "true":
            qs = qs.filter(parent__isnull=True)

        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = CategoryService.create_custom_category(
            user=request.user,
            data=serializer.validated_data,
        )
        return Response(
            CategorySerializer(category).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        if instance.is_system:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("System categories cannot be deleted.")
        instance.soft_delete()
