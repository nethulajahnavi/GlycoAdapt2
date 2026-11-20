"""Nearby healthcare lookup using OpenStreetMap Overpass with mirror fallback."""
import math
import httpx

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "GlucoRAG-Academic-Prototype/2.1 (OpenStreetMap nearby healthcare lookup)"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a1, a2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1, a)))


async def find_nearby_hospitals(latitude: float, longitude: float, radius_m: int = 10000) -> dict:
    radius_m = max(1000, min(int(radius_m), 30000))
    query = f"""[out:json][timeout:18];
    (node[\"amenity\"~\"^(hospital|clinic|doctors)$\"](around:{radius_m},{latitude},{longitude});
     way[\"amenity\"~\"^(hospital|clinic)$\"](around:{radius_m},{latitude},{longitude});
     relation[\"amenity\"~\"^(hospital|clinic)$\"](around:{radius_m},{latitude},{longitude});
     node[\"healthcare\"~\"^(hospital|clinic|doctor)$\"](around:{radius_m},{latitude},{longitude});
     way[\"healthcare\"~\"^(hospital|clinic)$\"](around:{radius_m},{latitude},{longitude}););
    out center tags;"""
    payload = None
    errors = []
    timeout = httpx.Timeout(22.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        for endpoint in OVERPASS_URLS:
            try:
                response = await client.post(endpoint, data={"data": query})
                response.raise_for_status()
                payload = response.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{endpoint}: {str(exc)[:180]}")
    if payload is None:
        return {"status": "unavailable", "message": "OpenStreetMap's public search servers did not respond. Check your internet connection and retry in a minute. You can still open the map or use Google Maps.", "hospitals": [], "count": 0, "source": "OpenStreetMap contributors", "errors": errors}

    results, seen = [], set()
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        center = element.get("center", {})
        lat = element.get("lat", center.get("lat"))
        lon = element.get("lon", center.get("lon"))
        if lat is None or lon is None:
            continue
        identity = f"{element.get('type')}-{element.get('id')}"
        if identity in seen:
            continue
        seen.add(identity)
        name = tags.get("name") or tags.get("name:en") or "Unnamed healthcare facility"
        address = ", ".join(filter(None, [tags.get("addr:street"), tags.get("addr:suburb"), tags.get("addr:city"), tags.get("addr:state")]))
        results.append({
            "id": identity, "name": name,
            "facility_type": tags.get("amenity") or tags.get("healthcare") or "healthcare facility",
            "latitude": float(lat), "longitude": float(lon), "address": address,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "website": tags.get("website") or tags.get("contact:website"),
            "maps_url": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}",
            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}",
        })
    for item in results:
        item["distance_km"] = round(_distance_km(latitude, longitude, item["latitude"], item["longitude"]), 2)
    results.sort(key=lambda item: item["distance_km"])
    notice = (f"Found {len(results)} mapped healthcare facilities within approximately {radius_m/1000:g} km. Sorted by straight-line distance, not road travel time. OSM data may be incomplete; call to confirm services and hours." if results else "No facilities were returned for this radius. OpenStreetMap coverage may be incomplete; try a larger radius or open a map app.")
    return {"status": "success", "count": len(results), "hospitals": results[:60], "source": "OpenStreetMap contributors", "radius_m": radius_m, "notice": notice}
