import requests
import logging
from django.utils import timezone
from requests.exceptions import RequestException, HTTPError
from .models import Weather
from .constants import CITIES

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def sync_weather_for_cities():
    """
    fetch current weather for predefined cities and update/insert into db
    returns a small summary dict (for logs/debugging)
    """
    
    ok, failed = 0, 0
    
    for c in CITIES:
        params = {
            "latitude": c["latitude"],
            "longitude": c["longitude"],
            "current_weather": "true",
        }
        
        logger.info("Syncing city: %s (lat = %s, lon = %s)", c["city_name"], c["latitude"], c["longitude"])
        try:
            resp = requests.get(OPEN_METEO_URL, params = params, timeout = 10)
            resp.raise_for_status()
            data = resp.json()
            
            cw = data.get("current_weather") or {}
            Weather.objects.update_or_create(
                city_name = c["city_name"],
                defaults={
                    "latitude": c["latitude"],
                    "longitude": c["longitude"],
                    "temperature": cw.get("temperature"),
                    "windspeed": cw.get("windspeed"),
                    "winddirection": cw.get("winddirection"),
                    "weathercode": cw.get("weathercode"),
                    "time": cw.get("time"),
                    "raw_payload": data,
                    "synced_at": timezone.now(),
                },
            )
            ok += 1
            logger.info("Synced %s successfully", c["city_name"])
        except HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status is not None and 400 <= status < 500:
                logger.warning("Client error (no retry) city=%s status=%s", c["city_name"], status)
                failed += 1
            else:
                logger.exception("Server/HTTP error (retry) city=%s", c["city_name"])
                failed += 1
                raise
        except RequestException:
            logger.exception("Network error (retry) syncing city=%s", c["city_name"])
            failed += 1
            raise
    
    logger.info("Sync summary: synced = %s failed = %s", ok, failed)
    return {"synced": ok, "failed": failed}