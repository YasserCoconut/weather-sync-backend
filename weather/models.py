from django.db import models

class Weather(models.Model):
    city_name = models.CharField(max_length=100, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    temperature = models.FloatField(null=True, blank=True)
    windspeed = models.FloatField(null=True, blank=True)
    winddirection = models.FloatField(null=True, blank=True)
    weathercode = models.IntegerField(null=True, blank=True)
    time = models.DateTimeField(null=True, blank=True)

    raw_payload = models.JSONField(null=True, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["synced_at"]),
            models.Index(fields=["city_name", "synced_at"]),
        ]


    def __str__(self):
        return self.city_name
