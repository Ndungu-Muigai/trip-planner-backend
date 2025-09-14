from django.urls import path
from .views import SearchLocations

urlpatterns = [
    path("search/", SearchLocations.as_view(), name="locations"),
]
