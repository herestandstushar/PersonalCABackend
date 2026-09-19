"""
Categories serializers.
"""

from rest_framework import serializers

from categories.models import Category


class CategorySerializer(serializers.ModelSerializer):
    """Full category (detail / admin). Avoid nesting on list responses."""

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "icon",
            "color",
            "category_type",
            "parent",
            "is_system",
            "keywords",
            "sort_order",
            "created_at",
        ]
        read_only_fields = ["id", "is_system", "created_at"]


class CategoryListSerializer(serializers.ModelSerializer):
    """Lean list for filters / pickers — no keywords, no recursive children."""

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "icon",
            "color",
            "category_type",
            "parent",
            "is_system",
            "sort_order",
        ]


class CategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "icon", "color", "category_type", "parent", "keywords"]
