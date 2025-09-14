import polyline

def decode_geometry_safe(geometry):
    """
    Decode ORS geometry safely.
    Returns a list of (lat, lon) coordinates.
    """
    if not geometry:
        return []
    if isinstance(geometry, str):
        # Encoded polyline
        return polyline.decode(geometry)
    elif isinstance(geometry, list):
        # Already decoded coordinates: assume [[lon, lat], ...]
        return [(lat, lon) for lon, lat in geometry]
    return []

def interpolate_coord(geometry, progress):
    """
    Find coordinate at a given progress along the route.
    progress ∈ [0,1]
    """
    coords = decode_geometry_safe(geometry)
    if not coords:
        return (0, 0)

    idx = int(progress * (len(coords) - 1))
    return coords[idx]  # (lat, lon)
