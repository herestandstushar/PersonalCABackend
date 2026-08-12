"""
Core models — BaseModel providing UUID primary key, timestamps, and soft-delete.

All application models should extend BaseModel for consistent behavior.
"""

import uuid

from django.db import models


class BaseManager(models.Manager):
    """Manager that filters out soft-deleted records by default."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_with_deleted(self):
        """Return all records including soft-deleted ones."""
        return super().get_queryset()

    def deleted_only(self):
        """Return only soft-deleted records."""
        return super().get_queryset().filter(is_deleted=True)


class BaseModel(models.Model):
    """
    Abstract base model for all FinSight models.

    Provides:
    - UUID primary key
    - created_at / updated_at timestamps
    - Soft-delete via is_deleted flag
    - Custom manager that excludes deleted records
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = BaseManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        """Mark the record as deleted without removing from the database."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.save(update_fields=["is_deleted", "updated_at"])
