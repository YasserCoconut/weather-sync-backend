import requests
import logging
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from requests.exceptions import RequestException, HTTPError
from .models import Weather

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def sync_single_city(city_data):
    """
    Fetch current weather for a single city and update/insert into db.
    Raises HTTPError for 5xx responses and RequestException for network errors.
    Logs and returns False for 4xx responses (no retry).
    Returns True on success.
    """
    city_name = city_data["city_name"]
    params = {
        "latitude": city_data["latitude"],
        "longitude": city_data["longitude"],
        "current_weather": "true",
    }
    
    logger.info("Syncing city: %s", city_name)
    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        cw = data.get("current_weather") or {}
        
        # parse and make time timezone-aware
        time_str = cw.get("time")
        time_aware = None
        if time_str:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone=dt_timezone.utc)
            time_aware = dt

        
        Weather.objects.update_or_create(
            city_name=city_name,
            defaults={
                "latitude": city_data["latitude"],
                "longitude": city_data["longitude"],
                "temperature": cw.get("temperature"),
                "windspeed": cw.get("windspeed"),
                "winddirection": cw.get("winddirection"),
                "weathercode": cw.get("weathercode"),
                "time": time_aware,
                "raw_payload": data,
                "synced_at": timezone.now(),
            },
        )
        logger.info("Synced %s successfully", city_name)
        return True
    except HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status is not None and 400 <= status < 500:
            logger.warning("Client error (no retry) city=%s status=%s", city_name, status)
            return False
        else:
            logger.exception("Server/HTTP error (retry) city=%s", city_name)
            raise
    except RequestException:
        logger.exception("Network error (retry) city=%s", city_name)
        raise