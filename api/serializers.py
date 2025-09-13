from rest_framework import serializers

class TripRequestSerializer(serializers.Serializer):
    current_location = serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2)  
    pickup_location = serializers.CharField()
    dropoff_location = serializers.CharField()
    cycle_used = serializers.CharField() 

    def validate(self, data):
        # Convert cycle_used to int
        data["cycle_used"] = int(data["cycle_used"])
        return data
