from django.db import models

# Create your models here.
class Weather(models.Model):
    city_name = models.CharField(max_length = 100, unique = True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    temperature = models.FloatField(null = True, blank = True)
    windspeed = models.FloatField(null = True, blank = True)
    winddirection = models.FloatField(null = True, blank = True)
    weathercode = models.FloatField(null = True, blank = True)
    time = models.CharField(max_length=50, null = True, blank = True)
    
    raw_payload = models.JSONField(null = True, blank = True)
    synced_at = models.DateTimeField(null = True, blank = True)
    
    def __str__(self):
        return self.city_name