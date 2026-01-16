from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Weather
from .tasks import sync_weather_task

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
        "time": w.time,
        "synced_at": w.synced_at.isoformat() if w.synced_at else None,
    }

@require_http_methods(["GET"])
def weather_list(request):
    qs = Weather.objects.all().order_by("id")
    return JsonResponse([serialize_weather(w) for w in qs], safe = False)

@require_http_methods(["GET"])
def weather_detail(request, id):
    try:
        w = Weather.objects.get(id=id)
    except Weather.DoesNotExist:
        return JsonResponse({"detail": "Not Found"}, status = 404)
    return JsonResponse(serialize_weather(w))

@csrf_exempt
@require_http_methods(["POST"])
def sync_weather(request):
    task = sync_weather_task.delay()
    return JsonResponse({"task_id": task.id, "status": "started"})