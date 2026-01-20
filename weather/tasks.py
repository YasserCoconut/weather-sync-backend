import logging
from celery import shared_task, group
from requests.exceptions import RequestException, HTTPError
from .services import sync_single_city
from .constants import CITIES

logger = logging.getLogger(__name__)

def should_retry_http_error(exc):
    """Check if HTTPError should be retried (5xx yes, 4xx no)."""
    if isinstance(exc, HTTPError):
        status = getattr(exc.response, "status_code", None)
        if status is not None and 400 <= status < 500:
            return False
    return True

@shared_task(bind=True, retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 5})
def sync_city_task(self, city_data):
    """
    Sync weather for a single city with automatic retry on network errors and 5xx.
    Does NOT retry on 4xx client errors.
    """
    city_name = city_data["city_name"]
    logger.info("City sync task started: %s", city_name)
    
    try:
        result = sync_single_city(city_data)
        if result:
            logger.info("City sync task completed: %s", city_name)
            return {"city": city_name, "status": "success"}
        else:
            logger.warning("City sync task failed (4xx): %s", city_name)
            return {"city": city_name, "status": "failed_4xx"}
    except HTTPError as e:
        if not should_retry_http_error(e):
            logger.warning("City sync task failed (4xx, no retry): %s", city_name)
            return {"city": city_name, "status": "failed_4xx"}
        logger.exception("City sync task failed (5xx, retrying): %s", city_name)
        raise self.retry(exc=e)
    except RequestException as e:
        logger.exception("City sync task failed (network, retrying): %s", city_name)
        raise self.retry(exc=e)

@shared_task
def sync_all_cities_task():
    """
    Coordinator task that spawns concurrent per-city sync tasks using Celery group().
    Returns the group result for tracking.
    """
    logger.info("Starting concurrent city sync for %d cities", len(CITIES))
    
    job = group(sync_city_task.s(city) for city in CITIES)
    group_result = job.apply_async()
    
    logger.info("Dispatched %d concurrent city sync tasks (group_id = %s)", len(CITIES), group_result.id)
    return {"task_type": "group", "group_id": group_result.id, "subtasks": len(CITIES)}

