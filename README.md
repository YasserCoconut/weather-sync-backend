# Weather Sync Backend (Django + Celery + Redis)

A small backend service that synchronizes **current weather data** for a predefined list of cities using the **Open-Meteo API**, stores the latest snapshot per city in a database, and exposes simple REST-style API endpoints to retrieve the data.

Weather synchronization runs **asynchronously** using **Celery + Redis** with **concurrent per-city tasks**, includes **structured logging**, and implements **retry logic with backoff** for resilience against transient failures. Each city is synced in its own Celery task for maximum concurrency and per-city retry control.

---
## Quick Start Summary

> **Note:** This project uses PostgreSQL and Redis by default.

> **Prerequisites:** Docker must be running, and the required environment variables must be set in your shell (see "Environment Variables" section). For detailed setup instructions, refer to the "Local Setup" section below.


### Linux / macOS

```bash
docker compose up -d
python manage.py migrate
python manage.py runserver
```

In a separate terminal:

```bash
celery -A config worker -l info
```

Trigger a sync:

```bash
curl -X POST http://127.0.0.1:8000/api/sync/
```

---

### Windows (PowerShell)

```powershell
docker compose up -d
python manage.py migrate
python manage.py runserver
```

In a separate terminal:

```powershell
celery -A config worker -l info --pool=solo --concurrency=1
```

Trigger a sync:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/sync/
```

---

Retrieve synced data:

```
GET http://127.0.0.1:8000/api/weather/
```
---

## Environment Variables

This project reads configuration **only from OS environment variables** (no `.env` file).

Required variables:

```
DJANGO_SECRET_KEY=replace_me
DJANGO_DEBUG=1
ALLOWED_HOSTS=127.0.0.1,localhost

POSTGRES_DB=weatherdb
POSTGRES_USER=weatheruser
POSTGRES_PASSWORD=weatherpass
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433

REDIS_URL=redis://127.0.0.1:6379/0

CORS_ALLOWED_ORIGINS=https://example.com,https://app.example.com
CSRF_TRUSTED_ORIGINS=https://example.com,https://app.example.com
```

**Note:** Environment variables must be set in each terminal session (Django and Celery).

---

## Local Setup (Python environment)

### 1) Create virtual environment

```bash
python -m venv .venv
```
Activate:

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

### 2) Configure environment

### Linux / macOS (bash/zsh)

```bash
export DJANGO_SECRET_KEY="replace_me"
export DJANGO_DEBUG="1"
export ALLOWED_HOSTS="127.0.0.1,localhost"

export POSTGRES_DB="weatherdb"
export POSTGRES_USER="weatheruser"
export POSTGRES_PASSWORD="weatherpass"
export POSTGRES_HOST="127.0.0.1"
export POSTGRES_PORT="5433"

export REDIS_URL="redis://127.0.0.1:6379/0"

# Optional: Configure CORS and CSRF for browser clients on other origins
export CORS_ALLOWED_ORIGINS="https://example.com,https://app.example.com"
export CSRF_TRUSTED_ORIGINS="https://example.com,https://app.example.com"
```

### Windows (PowerShell)

```powershell
$env:DJANGO_SECRET_KEY = "replace_me"
$env:DJANGO_DEBUG = "1"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost"

$env:POSTGRES_DB = "weatherdb"
$env:POSTGRES_USER = "weatheruser"
$env:POSTGRES_PASSWORD = "weatherpass"
$env:POSTGRES_HOST = "127.0.0.1"
$env:POSTGRES_PORT = "5433"

$env:REDIS_URL = "redis://127.0.0.1:6379/0"

# Optional: Configure CORS and CSRF for browser clients on other origins
$env:CORS_ALLOWED_ORIGINS = "https://example.com,https://app.example.com"
$env:CSRF_TRUSTED_ORIGINS = "https://example.com,https://app.example.com"
```

> **Note:** These environment variables must be set in the terminal session where you run Django/Celery.

---

> Ensure PostgreSQL is running (via Docker or externally) before running migrations.

### 3) Run migrations

```bash
python manage.py migrate
```

---

### 4) Start Django server

```bash
python manage.py runserver
```

Access:

* `http://127.0.0.1:8000/api/weather/`

---

## Docker Setup

This is the recommended setup for running the project locally.

Docker Compose runs **PostgreSQL + Redis**.

### Start services

```bash
docker compose up -d
```

Apply migrations:

```bash
python manage.py migrate
```

Verify containers:

```bash
docker ps
```

Reset containers if needed:

```bash
docker compose down -v
docker compose up -d
```

---

## Celery Worker

Run Celery in a **separate terminal** (venv activated).

**Windows**

```bash
celery -A config worker -l info --pool=solo --concurrency=1
```

**macOS / Linux**

```bash
celery -A config worker -l info
```

Why `--pool=solo` on Windows?

* Windows has limitations with Celery’s prefork pool
* Solo pool is the recommended stable option for local development

---

## API Endpoints

### List weather for all cities
**GET** `/api/weather/`

Supports **limit/offset pagination** via query parameters.

**Query Parameters:**
- `limit` (optional, default: 10) - Number of records to return. Max: 1000.
- `offset` (optional, default: 0) - Number of records to skip.

Response structure:
```json
{
  "count": 10,
  "results": [...]
}
```

**Response example:**
```json
{
  "count": 4,
  "results": [
    {
      "id": 1,
      "city_name": "Paris",
      "latitude": 48.8566,
      "longitude": 2.3522,
      "temperature": 3.1,
      "windspeed": 10.4,
      "winddirection": 240,
      "weathercode": 3,
      "time": "2026-01-16T05:00",
      "synced_at": "2026-01-16T09:11:41.123Z"
    }
  ]
}
```

**Example requests:**

Default (limit=10, offset=0):
```bash
curl http://127.0.0.1:8000/api/weather/
```

Custom limit:
```bash
curl http://127.0.0.1:8000/api/weather/?limit=5
```

With offset:
```bash
curl http://127.0.0.1:8000/api/weather/?limit=5&offset=10
```

**Validation:**
- `limit` must be a positive integer (> 0)
- `offset` must be a non-negative integer (>= 0)
- `limit` is capped at 1000 to prevent abuse
- Invalid inputs return `400 Bad Request` with error details

---

### Get weather for a single city

**GET** `/api/weather/<id>/`

* `<id>` refers to the database primary key of the weather record
* Returns `404` if not found

---

### Trigger asynchronous synchronization

**POST** `/api/sync/`

Response example:

```json
{
  "task_id": "82ad4d62-f3fa-4ca1-981a-0fa30c2ddb38",
  "status": "started"
}
```

> Note: This endpoint **does not wait** for the sync to finish.  
> The actual work is performed asynchronously by Celery.
> This endpoint is safe to call multiple times and is idempotent.

#### Example (curl)

```bash
curl -X POST http://127.0.0.1:8000/api/sync/
```

#### CSRF and CORS for `/api/sync/`
- CSRF remains enabled. To call this endpoint from a browser client on another origin, first fetch `GET /api/csrf/` to obtain the CSRF cookie, then send the POST with the `X-CSRFToken` header set to that cookie value.
- Allowed CORS origins are configured via `CORS_ALLOWED_ORIGINS` (comma-separated). Credentials are allowed.
- Add cross-origin hosts that need to submit the POST to both `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` environment variables.

> Note (Windows PowerShell): `curl` is an alias for `Invoke-WebRequest`.  
> If needed, use `curl.exe` instead.

---

## Data Model

The `Weather` model stores the **latest weather snapshot** per city:

- `city_name` (unique)
- `latitude`, `longitude` (float)
- `temperature`, `windspeed`, `winddirection` (float)
- `weathercode` (integer - WMO code)
- `time` (datetime - ISO format from API)
- `raw_payload` (full JSON response for traceability)
- `synced_at` (timestamp of last successful sync)

Re-running the sync **updates existing rows** and never creates duplicates.

---

## Project Structure (High Level)

```
config/
weather/
├─ models.py
├─ constants.py
├─ services.py
├─ tasks.py
├─ views.py
├─ tests.py
docker-compose.yml
.gitignore
```


**Design choice**

- `views.py` handles HTTP concerns only
- `services.py` contains business logic and database writes
  - `sync_single_city()` for per-city sync
- `tasks.py` manages asynchronous execution and retry policy
  - `sync_city_task()` for individual city with retry logic
  - `sync_all_cities_task()` coordinator using Celery group()

This separation mirrors common production Django architectures and keeps the codebase easy to reason about and extend.

---

## Features

- Django REST-style JSON APIs
- Asynchronous background synchronization with Celery
- **Concurrent per-city task execution** using Celery group()
  - Each city syncs in its own independent task
  - Parallel processing for maximum throughput
  - Per-city retry logic (failures don't block other cities)
- Redis used as Celery broker/result backend
- Persistent storage via Django ORM
  - PostgreSQL is used (via Docker). A SQLite database file is present for local development, but current settings default to PostgreSQL.
- Idempotent sync behavior using `update_or_create` (one record per city)
- Structured logging (visible in Django & Celery processes)
- Robust retry policy:
  - Retries on network errors and 5xx responses
  - Skips retries for non-recoverable 4xx client errors
- Unit tests with mocked external API calls
- Docker Compose for Redis + PostgreSQL infrastructure

---

## Retry Behavior

Celery tasks use **automatic retries with exponential backoff and jitter**.

**Per-city retry policy**

Each city sync task has independent retry logic:

*  Retry on:
    * Network failures
    * Timeouts
    * 5xx HTTP responses (server errors)
*  Do not retry on:
    * 4xx client errors (invalid request, bad endpoint, etc.)

This avoids pointless retries and ensures that a failure for one city doesn't block or retry other cities.

---

## Logging

Structured logging is configured in `config/settings.py`.

Logs are visible in:

* Django server terminal
* Celery worker terminal

Examples:

* Task lifecycle logs (`Weather sync task started/completed`)
* Per-city sync logs
* Error logs with stack traces for retryable failures

---

## Unit Tests

Tests use Django’s test framework with **mocked Open-Meteo API calls**.

Run tests:

```bash
python manage.py test
```
>Note: The goal of these tests is to validate application behavior and error handling rather than the availability of the external API.

---

## Notes / Assumptions

* The service stores the **latest snapshot** of current weather per city.
* `raw_payload` is stored for traceability and future extensibility.
* The city list is predefined and small by design (easily extendable).
* Authentication was not added as it was not required by the test scope.

---

## Scaling Considerations (Required Question)

The current architecture already uses **concurrent per-city tasks** with Celery group() for parallel execution.

If this service needed to synchronize **thousands of cities every hour**, I would consider:

* Chunking city lists into batches to control memory usage and API rate limits
* Adding explicit rate limiting and request throttling (respecting API quotas)
* Implementing Celery task result expiration to avoid result backend bloat
* Using bulk database operations where applicable
* Introducing caching for unchanged weather data (TTL-based)
* Adding monitoring and alerting (task duration, retries, failure rates, throughput)
* Horizontal scaling of Celery workers across multiple machines
* Separating ingestion (sync workers) and read APIs into independent services
* Using task priority queues to prioritize critical cities

---


## Tech Stack

- Python 3.11
- Django 5.x
- Celery 5.x
- Redis
- PostgreSQL 16 (Docker)
- requests (HTTP client)

---