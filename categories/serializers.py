"""
Categories serializers.
"""

from rest_framework import serializers

from categories.models import Category


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

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
            "subcategories",
            "created_at",
        ]
        read_only_fields = ["id", "is_system", "created_at"]

    def get_subcategories(self, obj):
        children = obj.subcategories.all()
        if children.exists():
            return CategorySerializer(children, many=True).data
        return []


class CategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "icon", "color", "category_type", "parent", "keywords"]
