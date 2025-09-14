from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import requests
from .logic import plan_trip


class PlanTripView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            data = request.data

            # Validate required fields
            if not all(k in data for k in ["current_location", "pickup_location", "dropoff_location", "cycle_used"]):
                return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

            # Ensure values are the right types
            current_location = data["current_location"]   # [lat, lon]
            pickup_location = data["pickup_location"]     # [lon, lat]
            dropoff_location = data["dropoff_location"]   # [lon, lat]
            cycle_used = int(data["cycle_used"])          # string → int

            result = plan_trip(
                current_location=current_location,
                pickup_location=pickup_location,
                dropoff_location=dropoff_location,
                cycle_used=cycle_used
            )

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error in PlanTripView:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchLocations(APIView):
    """Proxy endpoint for getting the locations as searched by the user"""
    def get(self, request, *args, **kwargs):
        query = request.query_params.get("text")
        if not query:
            return Response({"error": "Missing 'text' query parameter"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            url = "https://api.openrouteservice.org/geocode/autocomplete"
            params = {"api_key": settings.ORS_API_KEY, "text": query}
            resp = requests.get(url, params=params)

            return Response(resp.json(), status=resp.status_code)

        except Exception as e:
            print("Error in GeocodeView:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
