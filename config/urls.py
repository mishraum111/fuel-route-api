from django.urls import path
from fuelroute.views import health, route_fuel

urlpatterns = [
    path("health/", health, name="health"),
    path("api/v1/route-fuel/", route_fuel, name="route-fuel"),
]
