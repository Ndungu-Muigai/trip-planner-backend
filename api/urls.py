from django.urls import path
from .views import PlanTripView, SearchLocations

urlpatterns = [
    path("plan-trip/", PlanTripView.as_view(), name="plan-trip"),
    path("search-locations/", SearchLocations.as_view(), name="geocode"),
]
