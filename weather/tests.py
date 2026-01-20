from django.test import TestCase, Client
from unittest.mock import patch
from django.utils import timezone
from .models import Weather

# Create your tests here.

class WeatherAPITests(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_weather_list_empty(self):
        resp = self.client.get("/api/weather/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 0)
        self.assertIsInstance(data["results"], list)
        self.assertEqual(data["results"], [])
    
    def test_weather_list_pagination_default(self):
        # Create 15 cities
        for i in range(15):
            Weather.objects.create(
                city_name=f"City {i}",
                latitude=float(i),
                longitude=float(i),
            )
        
        resp = self.client.get("/api/weather/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 15)
        self.assertEqual(len(data["results"]), 10)  # default limit
        self.assertEqual(data["results"][0]["city_name"], "City 0")
    
    def test_weather_list_pagination_custom_limit(self):
        for i in range(15):
            Weather.objects.create(
                city_name=f"City {i}",
                latitude=float(i),
                longitude=float(i),
            )
        
        resp = self.client.get("/api/weather/?limit=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 15)
        self.assertEqual(len(data["results"]), 5)
    
    def test_weather_list_pagination_offset(self):
        for i in range(15):
            Weather.objects.create(
                city_name=f"City {i}",
                latitude=float(i),
                longitude=float(i),
            )
        
        resp = self.client.get("/api/weather/?limit=5&offset=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 15)
        self.assertEqual(len(data["results"]), 5)
        self.assertEqual(data["results"][0]["city_name"], "City 10")
    
    def test_weather_list_pagination_offset_beyond_count(self):
        for i in range(5):
            Weather.objects.create(
                city_name=f"City {i}",
                latitude=float(i),
                longitude=float(i),
            )
        
        resp = self.client.get("/api/weather/?limit=10&offset=20")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 5)
        self.assertEqual(len(data["results"]), 0)
    
    def test_weather_list_pagination_invalid_limit(self):
        resp = self.client.get("/api/weather/?limit=invalid")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)
    
    def test_weather_list_pagination_invalid_offset(self):
        resp = self.client.get("/api/weather/?offset=invalid")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)
    
    def test_weather_list_pagination_negative_limit(self):
        resp = self.client.get("/api/weather/?limit=-5")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)
    
    def test_weather_list_pagination_negative_offset(self):
        resp = self.client.get("/api/weather/?offset=-5")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)
    
    def test_weather_list_pagination_zero_limit(self):
        resp = self.client.get("/api/weather/?limit=0")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "limit must be greater than 0")

    
    def test_weather_list_pagination_limit_capped(self):
        for i in range(1100):
            Weather.objects.create(
                city_name=f"City {i}",
                latitude=float(i % 180),
                longitude=float(i % 360),
            )
        
        resp = self.client.get("/api/weather/?limit=2000")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1100)
        self.assertEqual(len(data["results"]), 1000)  # capped at 1000
    
    def test_weather_detail_not_found(self):
        resp = self.client.get("/api/weather/999999/")
        self.assertEqual(resp.status_code, 404)
    
    @patch("weather.tasks.sync_all_cities_task.delay")
    def test_sync_endpoint_returns_task_id(self, mock_delay):
        # fake celery AsyncResult-like object
        class DummyTask:
            id = "test-task-id"
        
        mock_delay.return_value = DummyTask()
        
        resp = self.client.post("/api/sync/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "started")
        self.assertEqual(data["task_id"], "test-task-id")
    
    def test_sync_endpoint_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        resp = csrf_client.post("/api/sync/")
        self.assertEqual(resp.status_code, 403)

    
    def test_weather_detail_ok(self):
        w = Weather.objects.create(
            city_name = "Test City",
            latitude = 1.0,
            longitude = 2.0,
        )
        resp = self.client.get(f"/api/weather/{w.id}/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["id"], w.id)
        self.assertEqual(body["city_name"], "Test City")
    
    @patch("weather.services.requests.get")
    def test_sync_single_city_mocked_api(self, mock_get):
        from weather.services import sync_single_city, OPEN_METEO_URL

        mock_response = mock_get.return_value
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "current_weather": {
                "temperature": 15.5,
                "windspeed": 10.2,
                "winddirection": 180,
                "weathercode": 1,
                "time": "2026-01-20T12:00:00Z",
            }
        }

        city_data = {"city_name": "London", "latitude": 51.5074, "longitude": -0.1278}

        result = sync_single_city(city_data)
        self.assertTrue(result)

        mock_get.assert_called_once_with(
            OPEN_METEO_URL,
            params={"latitude": 51.5074, "longitude": -0.1278, "current_weather": "true"},
            timeout=10,
        )

        weather = Weather.objects.get(city_name="London")
        self.assertEqual(weather.temperature, 15.5)
        self.assertEqual(weather.windspeed, 10.2)
        self.assertEqual(weather.winddirection, 180)
        self.assertEqual(weather.weathercode, 1)

        # time parsed + timezone-aware
        self.assertIsNotNone(weather.time)
        self.assertTrue(timezone.is_aware(weather.time))
        self.assertEqual(weather.time.isoformat(), "2026-01-20T12:00:00+00:00")