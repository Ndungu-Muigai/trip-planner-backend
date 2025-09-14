from rest_framework import serializers
from .models import Trip, TripLeg

class TripLegSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripLeg
        fields = [
            "id",
            "start_location",
            "end_location",
            "distance",
            "duration",
            "driving_hours",
            "rests",
            "fuel_stops",
            "geometry",
            "steps",
        ]

class TripSerializer(serializers.ModelSerializer):
    # Include legs in the serialized output
    legs = TripLegSerializer(many=True, read_only=True)
    # Make sure duration is always serialized as 2 decimals
    duration = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = "__all__"

    def get_duration(self, obj):
        return round(obj.duration, 2) if obj.duration is not None else None
