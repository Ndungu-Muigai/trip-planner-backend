from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField  # if using Postgres
from django.utils import timezone

class Trip(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    current_location = models.JSONField(null=True, blank=True)
    pickup_location = models.JSONField()   # [lat, lng]
    dropoff_location = models.JSONField()  # [lat, lng]
    distance = models.FloatField(null=True, blank=True)  # miles
    duration = models.FloatField(null=True, blank=True)  # total hours including non-driving
    driving_hours = models.FloatField(null=True, blank=True)  # hours actually driving
    rests = models.JSONField(default=list, blank=True)  # hours at which rests occur, e.g. [8]
    fuel_stops = models.IntegerField(default=0)  # number of fuel stops
    geometry = models.JSONField(null=True, blank=True)  # ORS polyline
    summary = models.JSONField(null=True, blank=True)   # ORS summary
    steps = models.JSONField(null=True, blank=True)     # ORS turn-by-turn steps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Trip by {self.user.username} from {self.pickup_location} to {self.dropoff_location}"

class TripLeg(models.Model):
    trip = models.ForeignKey("Trip", related_name="legs", on_delete=models.CASCADE)
    start_location = models.JSONField()
    end_location = models.JSONField()
    distance = models.FloatField()         # miles
    duration = models.FloatField()         # hours
    driving_hours = models.FloatField()
    rests = models.JSONField(default=list)
    fuel_stops = models.IntegerField()
    geometry = models.JSONField(null=True, blank=True)
    steps = models.JSONField(default=list)

    def __str__(self):
        return f"Leg: {self.start_location} → {self.end_location}"