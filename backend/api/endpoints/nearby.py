"""Nearby orthopedic care endpoint using OpenStreetMap Overpass API."""

from __future__ import annotations

import math
from typing import Optional

import httpx
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter(tags=["nearby"])

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Search radius in meters
DEFAULT_RADIUS = 15_000  # 15 km
MAX_RADIUS = 50_000  # 50 km

ORTHO_KEYWORDS = [
    "ortho",
    "orthop",
    "bone",
    "joint",
    "fracture",
    "musculoskeletal",
    "spine",
    "trauma",
    "skeleton",
    "sports medicine",
]


class NearbyCenter(BaseModel):
    id: str
    name: str
    specialty: str
    distanceKm: float
    address: str
    phone: str | None = None
    website: str | None = None
    latitude: float
    longitude: float
    openingHours: str | None = None
    rating: float | None = None


class NearbyResponse(BaseModel):
    centers: list[NearbyCenter]
    locationUsed: str  # "gps" | "ip" | "default"
    latitude: float
    longitude: float
    radiusKm: float


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _classify_specialty(tags: dict) -> str:
    """Determine specialty label from OSM tags."""
    name = (tags.get("name", "") + " " + tags.get("healthcare:speciality", "")).lower()
    specialty_tag = tags.get("healthcare:speciality", "").lower()

    if any(kw in specialty_tag for kw in ORTHO_KEYWORDS):
        return "Orthopedic Specialist"
    if any(kw in name for kw in ORTHO_KEYWORDS):
        return "Orthopedic Care"
    amenity = tags.get("amenity", "")
    healthcare = tags.get("healthcare", "")
    if amenity == "hospital":
        return "Hospital"
    if amenity == "clinic" or healthcare == "clinic":
        return "Clinic"
    if healthcare == "doctor":
        return "Doctor / Practice"
    if amenity == "doctors":
        return "Doctor / Practice"
    return "Medical Facility"


def _build_address(tags: dict) -> str:
    """Build address string from OSM tags."""
    parts = []
    for key in ["addr:housenumber", "addr:street", "addr:city", "addr:state", "addr:postcode"]:
        val = tags.get(key, "").strip()
        if val:
            parts.append(val)
    if parts:
        return ", ".join(parts)
    return tags.get("addr:full", tags.get("address", ""))


async def _geolocate_ip(client: httpx.AsyncClient, ip: str) -> tuple[float, float] | None:
    """Geolocate an IP address using free ip-api.com service."""
    if ip in ("127.0.0.1", "::1", "localhost"):
        return None
    try:
        resp = await client.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,lat,lon"},
            timeout=5,
        )
        data = resp.json()
        if data.get("status") == "success":
            return (data["lat"], data["lon"])
    except Exception:
        pass
    return None


async def _query_overpass(
    client: httpx.AsyncClient, lat: float, lon: float, radius: int
) -> list[dict]:
    """Query Overpass API for hospitals, clinics, and doctors nearby."""
    query = f"""
    [out:json][timeout:15];
    (
      nwr["amenity"="hospital"](around:{radius},{lat},{lon});
      nwr["amenity"="clinic"](around:{radius},{lat},{lon});
      nwr["amenity"="doctors"](around:{radius},{lat},{lon});
      nwr["healthcare"="clinic"](around:{radius},{lat},{lon});
      nwr["healthcare"="doctor"](around:{radius},{lat},{lon});
      nwr["healthcare"="hospital"](around:{radius},{lat},{lon});
      nwr["healthcare:speciality"~"orthopaedics|orthopedics|trauma"](around:{radius},{lat},{lon});
    );
    out center body;
    """
    try:
        resp = await client.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("elements", [])
    except Exception:
        return []


def _element_to_center(
    element: dict, user_lat: float, user_lon: float
) -> NearbyCenter | None:
    """Convert an OSM element to a NearbyCenter."""
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None

    # Get coordinates (center for ways/relations, direct for nodes)
    if element["type"] == "node":
        elat, elon = element["lat"], element["lon"]
    elif "center" in element:
        elat, elon = element["center"]["lat"], element["center"]["lon"]
    else:
        return None

    dist = _haversine(user_lat, user_lon, elat, elon)

    return NearbyCenter(
        id=f"osm-{element['type'][0]}{element['id']}",
        name=name,
        specialty=_classify_specialty(tags),
        distanceKm=round(dist, 1),
        address=_build_address(tags),
        phone=tags.get("phone") or tags.get("contact:phone"),
        website=tags.get("website") or tags.get("contact:website"),
        latitude=elat,
        longitude=elon,
        openingHours=tags.get("opening_hours"),
    )


@router.get("/nearby", response_model=NearbyResponse)
async def get_nearby_care(
    request: Request,
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    radius: int = Query(DEFAULT_RADIUS, le=MAX_RADIUS, description="Search radius in meters"),
):
    """Find nearby orthopedic care centers based on coordinates or IP geolocation."""
    location_used = "gps"

    async with httpx.AsyncClient() as client:
        # If no coordinates provided, try IP geolocation
        if lat is None or lon is None:
            # Get client IP
            client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if not client_ip:
                client_ip = request.client.host if request.client else ""

            coords = await _geolocate_ip(client, client_ip)
            if coords:
                lat, lon = coords
                location_used = "ip"
            else:
                # Default: Mumbai, India
                lat, lon = 19.076, 72.8777
                location_used = "default"

        # Query for nearby medical facilities
        elements = await _query_overpass(client, lat, lon, radius)

    # Convert to NearbyCenter objects
    centers: list[NearbyCenter] = []
    seen_names: set[str] = set()
    for elem in elements:
        center = _element_to_center(elem, lat, lon)
        if center and center.name.lower() not in seen_names:
            seen_names.add(center.name.lower())
            centers.append(center)

    # Sort: orthopedic-tagged first, then by distance
    def sort_key(c: NearbyCenter) -> tuple[int, float]:
        is_ortho = 0 if "ortho" in c.specialty.lower() else 1
        return (is_ortho, c.distanceKm)

    centers.sort(key=sort_key)

    return NearbyResponse(
        centers=centers[:30],  # Limit to 30 results
        locationUsed=location_used,
        latitude=lat,
        longitude=lon,
        radiusKm=round(radius / 1000, 1),
    )
