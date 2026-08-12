"""
Tiny public health endpoint for Render / load-balancer probes.
Must stay unauthenticated and free of DB/Redis dependency.
"""

from django.http import JsonResponse


def healthz(_request):
    return JsonResponse({"status": "ok"})
