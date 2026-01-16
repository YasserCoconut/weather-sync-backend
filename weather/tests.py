from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch

from .models import Weather

# Create your tests here.

class WeatherAPITests(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_weather_list_empty(self):
        resp = self.client.get("/api/weather/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)
        self.assertEqual(resp.json(), [])
    
    def test_weather_detail_not_found(self):
        resp = self.client.get("/api/weather/999999/")
        self.assertEqual(resp.status_code, 404)
    
    @patch("weather.tasks.sync_weather_task.delay")
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