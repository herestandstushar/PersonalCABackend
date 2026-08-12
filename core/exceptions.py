"""
Core exceptions — custom exception handler and business logic exceptions.
"""

import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("finsight")


def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler that returns a consistent error envelope.

    Response format:
    {
        "errors": [
            {
                "code": "validation_error",
                "message": "...",
                "field": "email"  // optional
            }
        ]
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        errors = []

        if isinstance(response.data, dict):
            for field, messages in response.data.items():
                if isinstance(messages, list):
                    for message in messages:
                        error = {"code": _get_error_code(exc), "message": str(message)}
                        if field != "detail" and field != "non_field_errors":
                            error["field"] = field
                        errors.append(error)
                else:
                    error = {"code": _get_error_code(exc), "message": str(messages)}
                    if field != "detail" and field != "non_field_errors":
                        error["field"] = field
                    errors.append(error)
        elif isinstance(response.data, list):
            for message in response.data:
                errors.append({"code": _get_error_code(exc), "message": str(message)})
        else:
            errors.append(
                {"code": _get_error_code(exc), "message": str(response.data)}
            )

        response.data = {"errors": errors}
    else:
        # Unhandled exception — log and return 500
        logger.exception("Unhandled exception in %s", context.get("view", "unknown"))
        return Response(
            {
                "errors": [
                    {
                        "code": "internal_error",
                        "message": "An unexpected error occurred. Please try again.",
                    }
                ]
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


def _get_error_code(exc):
    """Extract a machine-readable error code from the exception."""
    if hasattr(exc, "default_code"):
        return exc.default_code
    return "error"


class ServiceError(APIException):
    """Base exception for business logic errors in services."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A service error occurred."
    default_code = "service_error"


class NotFoundError(ServiceError):
    """Raised when a requested resource is not found."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The requested resource was not found."
    default_code = "not_found"


class DuplicateError(ServiceError):
    """Raised when a duplicate record is detected."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "A duplicate record was detected."
    default_code = "duplicate"


class ValidationError(ServiceError):
    """Raised for business validation failures."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Validation failed."
    default_code = "validation_error"


class PermissionDeniedError(ServiceError):
    """Raised when a user lacks permission for an action."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"
