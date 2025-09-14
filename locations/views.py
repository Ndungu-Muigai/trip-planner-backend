from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import requests

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
