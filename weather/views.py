from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect

from .models import Weather
from .tasks import sync_all_cities_task

# Create your views here.

def serialize_weather(w):
    return {
        "id": w.id,
        "city_name": w.city_name,
        "latitude": w.latitude,
        "longitude": w.longitude,
        "temperature": w.temperature,
        "windspeed": w.windspeed,
        "winddirection": w.winddirection,
        "weathercode": w.weathercode,
        "time": w.time.isoformat() if w.time else None,
        "synced_at": w.synced_at.isoformat() if w.synced_at else None,
    }

@require_http_methods(["GET"])
def weather_list(request):
    # get and validate pagination parameters
    try:
        limit = int(request.GET.get("limit", 10))
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        return JsonResponse({"error": "limit and offset must be integers"}, status=400)
    
    # validate non-negative values
    if limit < 0 or offset < 0:
        return JsonResponse({"error": "limit and offset must be non-negative"}, status=400)
    
    # apply limits to prevent abuse
    if limit == 0:
        return JsonResponse({"error": "limit must be greater than 0"}, status=400)
    if limit > 1000:
        limit = 1000
    
    qs = Weather.objects.all().order_by("id")
    total_count = qs.count()
    
    # apply pagination
    paginated_qs = qs[offset : offset + limit]
    
    return JsonResponse({
        "count": total_count,
        "results": [serialize_weather(w) for w in paginated_qs]
    })

@require_http_methods(["GET"])
def weather_detail(request, id):
    try:
        w = Weather.objects.get(id=id)
    except Weather.DoesNotExist:
        return JsonResponse({"detail": "Not Found"}, status = 404)
    return JsonResponse(serialize_weather(w))

@csrf_protect
@require_http_methods(["POST"])
def sync_weather(request):
    task = sync_all_cities_task.delay()
    return JsonResponse({"task_id": task.id, "status": "started"})


@ensure_csrf_cookie
@require_http_methods(["GET"])
def csrf_token(request):
    return JsonResponse({"detail": "CSRF cookie set"})