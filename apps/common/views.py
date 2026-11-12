from django.http import JsonResponse
from drf_spectacular.utils import extend_schema


@extend_schema(tags=["Common"])
def health(request):
    return JsonResponse({"status": "ok"})
