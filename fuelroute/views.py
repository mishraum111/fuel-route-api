import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from services.routing import RouteFuelService, RouteFuelError

service = RouteFuelService()

@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok", "service": "route-fuel-api"})

@require_http_methods(["GET", "POST"])
def route_fuel(request):
    try:
        if request.method == "POST":
            try:
                body = json.loads(request.body or "{}")
            except json.JSONDecodeError:
                raise RouteFuelError("Request body must be valid JSON")
            start, finish = body.get("start", ""), body.get("finish", "")
        else:
            start, finish = request.GET.get("start", ""), request.GET.get("finish", "")
        result = service.plan(start=start, finish=finish)
        return JsonResponse(result)
    except RouteFuelError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": "External service or server error", "detail": str(exc)}, status=502)
