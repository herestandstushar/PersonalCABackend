"""
Core middleware — audit logging for write operations.
"""

import json
import logging
import time

from core.utils import get_client_ip

logger = logging.getLogger("finsight.audit")


class AuditLogMiddleware:
    """
    Logs all write operations (POST, PUT, PATCH, DELETE) with user info.

    Captures:
    - Timestamp, method, path
    - User ID (if authenticated)
    - Client IP
    - Response status code
    - Duration
    """

    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in self.WRITE_METHODS:
            return self.get_response(request)

        start_time = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        user_id = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = str(request.user.id)

        log_data = {
            "method": request.method,
            "path": request.path,
            "user_id": user_id,
            "ip": get_client_ip(request),
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        # Log request body for non-file uploads (truncated)
        if request.content_type and "multipart" not in request.content_type:
            try:
                body = request.body.decode("utf-8")[:2000]
                # Avoid logging sensitive fields
                try:
                    parsed = json.loads(body)
                    for sensitive_key in ("password", "token", "secret", "account_number"):
                        if sensitive_key in parsed:
                            parsed[sensitive_key] = "***REDACTED***"
                    log_data["body"] = parsed
                except (json.JSONDecodeError, ValueError):
                    log_data["body"] = body
            except Exception:
                pass

        logger.info("AUDIT: %s", json.dumps(log_data, default=str))
        return response
