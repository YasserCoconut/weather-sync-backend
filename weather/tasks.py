import logging
from celery import shared_task
from requests.exceptions import RequestException
from .services import sync_weather_for_cities

logger = logging.getLogger(__name__)

@shared_task(bind = True, autoretry_for=(RequestException,), retry_backoff = True, retry_jitter = True, retry_kwargs = {"max_retries": 5})
def sync_weather_task(self):
    logger.info("Weather sync task started")
    
    try:
        result = sync_weather_for_cities()
        logger.info("Weather sync task completed: %s", result)
        return result
    except Exception:
        logger.exception("Weather sync task failed")
        raise

