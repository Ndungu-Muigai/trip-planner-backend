import requests
from django.conf import settings
from rest_framework import viewsets, permissions
from .models import Trip, TripLeg
from .serializers import TripSerializer
from rest_framework import viewsets, permissions
from .models import Trip, TripLeg
from .serializers import TripSerializer
import polyline

# Constants
MAX_DRIVING_HOURS = 11  # max driving per day
REST_AFTER_HOURS = 8    # mandatory break
NON_DRIVING_HOURS = 3   # pickup, dropoff, fueling, inspections
FUEL_INTERVAL_MILES = 1000  # fuel stop every 1000 miles

class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Trip.objects.filter(user=self.request.user)



# Constants
MAX_DRIVING_HOURS = 11       # max driving per day
REST_AFTER_HOURS = 8         # mandatory break
NON_DRIVING_HOURS = 3        # pickup, dropoff, fueling, inspections
FUEL_INTERVAL_MILES = 1000   # fuel stop every 1000 miles

class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Trip.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        trip = serializer.save()

        # Ensure user has current location
        current_location = trip.current_location
        if not current_location:
            raise ValueError("Current location is not set for this user.")

        url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
        headers = {"Authorization": settings.ORS_API_KEY, "Content-Type": "application/json"}

        # Define legs: current → pickup → dropoff
        legs_data = [
            {"from": current_location, "to": trip.pickup_location},
            {"from": trip.pickup_location, "to": trip.dropoff_location}
        ]

        total_distance = 0
        total_driving_hours = 0
        total_rests = []
        total_fuel_stops = 0
        full_geometry = []

        for leg_info in legs_data:
            body = {
                "coordinates": [
                    leg_info["from"][::-1],  # ORS expects [lng, lat]
                    leg_info["to"][::-1]
                ]
            }

            response = requests.post(url, json=body, headers=headers)
            data = response.json()

            if "routes" not in data:
                raise ValueError("No routes returned from ORS API.")

            route = data["routes"][0]
            summary = route["summary"]
            leg_distance = summary["distance"] / 1609.34  # meters → miles
            leg_duration = summary["duration"] / 3600     # seconds → hours

            # Calculate rests
            rests = []
            remaining_hours = leg_duration
            while remaining_hours > REST_AFTER_HOURS:
                rests.append(REST_AFTER_HOURS)
                remaining_hours -= REST_AFTER_HOURS

            # Fuel stops
            fuel_stops = int(leg_distance // FUEL_INTERVAL_MILES)

            # Decode polyline geometry
            encoded_geometry = route.get("geometry", "")
            coordinates = polyline.decode(encoded_geometry)  # list of (lat, lng)
            coordinates = [[lng, lat] for lat, lng in coordinates]  # GeoJSON format

            # Save leg
            leg = TripLeg.objects.create(
                trip=trip,
                start_location=leg_info["from"],
                end_location=leg_info["to"],
                distance=round(leg_distance, 2),
                duration=round(leg_duration + len(rests)*0.5, 2),  # include rests
                driving_hours=round(leg_duration, 2),
                rests=rests,
                fuel_stops=fuel_stops,
                geometry={"type": "LineString", "coordinates": coordinates},
                steps=route["segments"][0]["steps"] if route.get("segments") else []
            )

            # Accumulate totals
            total_distance += leg_distance
            total_driving_hours += leg_duration
            total_rests.extend(rests)
            total_fuel_stops += fuel_stops
            full_geometry.extend(coordinates)

        # Update trip totals
        total_duration_hours = total_driving_hours + len(total_rests)*0.5 + NON_DRIVING_HOURS

        trip.distance = round(total_distance, 2)
        trip.driving_hours = round(total_driving_hours, 2)
        trip.rests = total_rests
        trip.fuel_stops = total_fuel_stops
        trip.duration = round(total_duration_hours, 2)
        trip.geometry = {"type": "LineString", "coordinates": full_geometry}
        trip.save()

