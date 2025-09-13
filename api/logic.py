import requests
from django.conf import settings
from .utils import interpolate_coord, decode_geometry_safe

# --------------------------
# Constants
# --------------------------
CYCLE_LIMIT = 70         # hrs in 8 days
DAILY_DRIVING_LIMIT = 11 # max driving hrs per day
DAILY_ON_DUTY_LIMIT = 14 # max on-duty window per day
OFF_DUTY_RESET = 10      # hrs off duty required daily
BREAK_AFTER = 8          # hrs driving before 30-min break
RESET_34H = 34           # hrs restart
FUEL_INTERVAL = 1000     # miles before fueling

AVG_SPEED = 55  # mph fallback

# --------------------------
# Helpers
# --------------------------
def make_segment(status, duration_hours):
    return {"status": status, "duration_hours": duration_hours}

def hours_to_miles(hours, avg_speed=AVG_SPEED):
    return hours * avg_speed

def miles_to_hours(miles, avg_speed=AVG_SPEED):
    return miles / avg_speed

def decode_geometry(geom):
    """
    Decode geometry for ORS response.
    Accepts either encoded polyline (str) or list of coordinates.
    Returns list of [lat, lon] pairs for Leaflet.
    """
    if isinstance(geom, str):
        coords = decode_geometry_safe(geom)
        return [[lat, lon] for lon, lat in coords]
    elif isinstance(geom, list):
        return [[lat, lon] for lon, lat in geom]
    return []

# --------------------------
# Map API (OpenRouteService)
# --------------------------
def geocode_address(address):
    """Convert address into coordinates (lon, lat)."""
    url = "https://api.openrouteservice.org/geocode/search"
    params = {"api_key": settings.ORS_API_KEY, "text": address}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("features"):
        return {"error": f"Could not geocode address: {address}", "ors_response": data}

    coords = data["features"][0]["geometry"]["coordinates"]
    return coords[0], coords[1]  # (lon, lat)

def get_route(origin, destination):
    """Get distance (miles), duration (hours), and geometry using ORS API."""
    # Use coordinates directly if given as tuple/list
    if isinstance(origin, (list, tuple)):
        start_lon, start_lat = origin[1], origin[0]
    else:
        start = geocode_address(origin)
        if isinstance(start, dict) and "error" in start:
            return start
        start_lon, start_lat = start

    if isinstance(destination, (list, tuple)):
        end_lon, end_lat = destination[1], destination[0]
    else:
        end = geocode_address(destination)
        if isinstance(end, dict) and "error" in end:
            return end
        end_lon, end_lat = end

    url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
    headers = {
        "Authorization": settings.ORS_API_KEY,
        "Content-Type": "application/json"
    }
    body = {"coordinates": [[start_lon, start_lat], [end_lon, end_lat]]}

    resp = requests.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    if "routes" in data and data["routes"]:
        route = data["routes"][0]
        summary = route["summary"]
        geometry = route.get("geometry") or route.get("geometry_encoded") or route.get("geometry_raw")
        miles = summary["distance"] / 1609.34
        hours = summary["duration"] / 3600
        return {
            "distance_miles": round(miles, 1),
            "duration_hours": round(hours, 2),
            "geometry": geometry
        }

    return {
        "error": f"No route found between {origin} and {destination}",
        "ors_response": data
    }

# --------------------------
# HOS Planning Logic
# --------------------------
def plan_trip(current_location, pickup_location, dropoff_location, cycle_used):
    cycle_remaining = CYCLE_LIMIT - cycle_used
    if cycle_remaining <= 0:
        return {"error": "Driver has no available hours left in cycle."}

    # Fetch route legs
    leg1 = get_route(current_location, pickup_location)
    if "error" in leg1:
        return {"error": f"Leg 1 failed: {leg1['error']}", "ors_response": leg1.get("ors_response")}
    leg2 = get_route(pickup_location, dropoff_location)
    if "error" in leg2:
        return {"error": f"Leg 2 failed: {leg2['error']}", "ors_response": leg2.get("ors_response")}

    legs = [
        {"label": "Current → Pickup", **leg1},
        {"label": "Pickup → Dropoff", **leg2},
    ]

    logs, stops, features = [], [], []
    miles_since_fuel, day_hours_driving, day_hours_onduty = 0, 0, 0

    for leg in legs:
        hours = leg["duration_hours"]
        total_hours = hours
        geometry = decode_geometry(leg.get("geometry", []))  # <-- decode safely

        # Add the route line as GeoJSON
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in geometry]},
            "properties": {"type": "route", "label": leg["label"]}
        })

        while hours > 0:
            drive_time_left = min(
                DAILY_DRIVING_LIMIT - day_hours_driving,
                DAILY_ON_DUTY_LIMIT - day_hours_onduty,
                cycle_remaining,
                hours,
            )
            if drive_time_left <= 0:
                logs.append(make_segment("Off Duty (Daily Reset)", OFF_DUTY_RESET))
                coord = interpolate_coord(geometry, 0.5)
                stops.append({"type": "Daily Reset", "duration_hours": OFF_DUTY_RESET, "location": coord})
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coord[::-1]},
                    "properties": {"type": "daily_reset"}
                })
                day_hours_driving = day_hours_onduty = 0
                continue

            logs.append(make_segment("Driving", drive_time_left))
            progress = 1 - (hours - drive_time_left) / total_hours
            coord = interpolate_coord(geometry, progress)
            stops.append({"type": "Driving", "duration_hours": drive_time_left, "location": coord})

            day_hours_driving += drive_time_left
            day_hours_onduty += drive_time_left
            cycle_remaining -= drive_time_left
            hours -= drive_time_left
            miles_since_fuel += hours_to_miles(drive_time_left)

            # Break
            if day_hours_driving >= BREAK_AFTER and not any(s["status"].startswith("Break") for s in logs):
                logs.append(make_segment("Break (Off Duty)", 0.5))
                stops.append({"type": "Break", "duration_hours": 0.5, "location": coord})
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coord[::-1]},
                    "properties": {"type": "break"}
                })
                day_hours_onduty += 0.5

            # Fuel
            if miles_since_fuel >= FUEL_INTERVAL:
                logs.append(make_segment("On Duty (Fuel)", 0.5))
                stops.append({"type": "Fuel", "duration_hours": 0.5, "location": coord})
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coord[::-1]},
                    "properties": {"type": "fuel"}
                })
                day_hours_onduty += 0.5
                cycle_remaining -= 0.5
                miles_since_fuel = 0

        # Pickup or dropoff
        coord = interpolate_coord(geometry, 1)
        if "Pickup" in leg["label"]:
            logs.append(make_segment("On Duty (Pickup)", 1))
            stops.append({"type": "Pickup", "duration_hours": 1, "location": coord})
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coord[::-1]},
                "properties": {"type": "pickup"}
            })
        elif "Dropoff" in leg["label"]:
            logs.append(make_segment("On Duty (Dropoff)", 1))
            stops.append({"type": "Dropoff", "duration_hours": 1, "location": coord})
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coord[::-1]},
                "properties": {"type": "dropoff"}
            })

    return {
        "legs": legs,
        "logs": logs,
        "stops": stops,
        "geojson": {
            "type": "FeatureCollection",
            "features": features
        },
        "remaining_cycle_hours": round(cycle_remaining, 2),
    }
