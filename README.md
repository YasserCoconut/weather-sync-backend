# Weather Sync Backend (Django + Celery + Redis)

A small backend service that synchronizes **current weather data** for a predefined list of cities using the **Open-Meteo API**, stores the latest snapshot per city in a database, and exposes simple REST-style API endpoints to retrieve the data.

Weather synchronization runs **asynchronously** using **Celery + Redis**, includes **structured logging**, and implements **retry logic with backoff** for resilience against transient failures.

---

## Features

- Django REST-style JSON APIs
- Asynchronous background synchronization with Celery
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

## Tech Stack

- Python 3.11
- Django 5.x
- Celery 5.x
- Redis
- PostgreSQL 16 (Docker)
- requests (HTTP client)

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
.env.example
.gitignore
```


**Design choice**

- `views.py` handles HTTP concerns only
- `services.py` contains business logic and database writes
- `tasks.py` manages asynchronous execution and retry policy

This separation mirrors common production Django architectures and keeps the codebase easy to reason about and extend.

---

## Data Model

The `Weather` model stores the **latest weather snapshot** per city:

- `city_name` (unique)
- `latitude`, `longitude`
- `temperature`
- `windspeed`
- `winddirection`
- `weathercode`
- `time` (as provided by the API)
- `raw_payload` (full JSON response for traceability)
- `synced_at` (timestamp of last successful sync)

Re-running the sync **updates existing rows** and never creates duplicates.

---

## API Endpoints

### List weather for all cities
**GET** `/api/weather/`

Response example:
```json
[
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
```

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
  "status": "started",
  "task_id": "82ad4d62-f3fa-4ca1-981a-0fa30c2ddb38"
}
```

> Note: This endpoint **does not wait** for the sync to finish.  
> The actual work is performed asynchronously by Celery.
> This endpoint is safe to call multiple times and is idempotent.

#### Example (curl)

```bash
curl -X POST http://127.0.0.1:8000/api/sync/
```

> Note (Windows PowerShell): `curl` is an alias for `Invoke-WebRequest`.  
> If needed, use `curl.exe` instead.

---

## Environment Variables

Create a `.env` file (not committed) based on `.env.example`.

### `.env.example`

```env
DJANGO_SECRET_KEY=replace_me
DJANGO_DEBUG=1

# Database
POSTGRES_DB=weatherdb
POSTGRES_USER=weatheruser
POSTGRES_PASSWORD=weatherpass
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433

# Celery / Redis
REDIS_URL=redis://127.0.0.1:6379/0
```
---

## Local Setup (Windows / macOS / Linux)

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

```bash
copy .env.example .env   # Windows
```

Edit `.env` with appropriate values.

---

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

## Docker Setup (Recommended)

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

**Windows (recommended)**

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

## Retry Behavior

Celery tasks use **automatic retries with exponential backoff and jitter**.

**Retry policy**

*  Retry on:
    * Network failures
    * Timeouts
    * 5xx HTTP responses
*  Do not retry on:
    * 4xx client errors (invalid request, bad endpoint, etc.)

This avoids pointless retries and keeps behavior production-like.

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

If this service needed to synchronize **thousands of cities every hour**, I would consider:

* Splitting the sync into multiple Celery tasks using task groups or chunks
* Chunking city lists to control memory usage and API rate limits
* Adding explicit rate limiting and request throttling
* Using bulk database operations where applicable
* Introducing caching for unchanged weather data
* Adding monitoring and alerting (task duration, retries, failure rates)
* Separating ingestion (sync workers) and read APIs into independent services

---

## Quick Start Summary

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