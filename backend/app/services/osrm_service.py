"""OpenStreetMap & OSRM (Open Source Routing Machine) Service.

Calculates verified highway road distances and estimated transit durations
between geographic coordinates using the OSRM routing engine over OpenStreetMap road networks.
Respects OSM Foundation usage guidelines with proper User-Agent headers, timeout limits,
and in-memory caching.
Gracefully falls back to road-adjusted Haversine formula (1.25 winding factor) when offline.
"""

import math
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger("stockwise.osrm")

# In-memory LRU-like cache for coordinate pairs: (round(lat1, 4), round(lon1, 4), round(lat2, 4), round(lon2, 4)) -> result dict
_ROUTE_CACHE: Dict[Tuple[float, float, float, float], Dict[str, Any]] = {}


def haversine_road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float, winding_factor: float = 1.25) -> float:
    """
    Computes great-circle distance with standard road network winding factor (1.25 for Indian highways).
    """
    R = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(R * c * winding_factor, 2)


def get_route_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    allow_network_query: bool = True,
    timeout_seconds: float = 4.0,
) -> Dict[str, Any]:
    """
    Retrieves verified driving road distance between two coordinate pairs.

    Returns:
        dict with keys:
            - distance_km (float)
            - duration_hours (float)
            - routing_engine (str: 'osrm_open_street_map' or 'haversine_road_adjusted')
            - road_factor (float)
            - cached (bool)
            - retrieval_timestamp (str ISO)
            - notes (str)
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    cache_key = (round(lat1, 4), round(lon1, 4), round(lat2, 4), round(lon2, 4))

    if cache_key in _ROUTE_CACHE:
        cached_result = dict(_ROUTE_CACHE[cache_key])
        cached_result["cached"] = True
        return cached_result

    # If coordinates are identical
    if math.isclose(lat1, lat2, abs_tol=1e-5) and math.isclose(lon1, lon2, abs_tol=1e-5):
        zero_res = {
            "distance_km": 0.0,
            "duration_hours": 0.0,
            "routing_engine": "zero_distance_identical_node",
            "road_factor": 1.0,
            "cached": False,
            "retrieval_timestamp": now_iso,
            "notes": "Origin and destination coordinates are identical.",
        }
        _ROUTE_CACHE[cache_key] = zero_res
        return zero_res

    # Try live OSRM routing engine
    if allow_network_query:
        try:
            # OSRM expects {longitude},{latitude};{longitude},{latitude}
            url = f"http://router.project-osrm.org/route/v1/driving/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}?overview=false"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "StockWise-FMCG-Distribution-Platform/1.0 (https://stockwise.app; support@stockwise.internal)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("code") == "Ok" and data.get("routes"):
                        best_route = data["routes"][0]
                        dist_meters = float(best_route.get("distance", 0.0))
                        dur_seconds = float(best_route.get("duration", 0.0))
                        dist_km = round(dist_meters / 1000.0, 2)
                        dur_hours = round(dur_seconds / 3600.0, 2)

                        # Straight-line distance comparison to derive actual road winding ratio
                        great_circle = haversine_road_distance_km(lat1, lon1, lat2, lon2, winding_factor=1.0)
                        empirical_winding = round(dist_km / max(1.0, great_circle), 2)

                        result = {
                            "distance_km": dist_km,
                            "duration_hours": dur_hours,
                            "routing_engine": "osrm_open_street_map",
                            "road_factor": empirical_winding,
                            "cached": False,
                            "retrieval_timestamp": now_iso,
                            "notes": f"Calculated over OpenStreetMap road network via Project OSRM API (winding: {empirical_winding}x).",
                        }
                        _ROUTE_CACHE[cache_key] = result
                        return result
        except Exception as exc:
            logger.warning("OSRM routing API query failed (%s); falling back to road-adjusted Haversine.", exc)

    # Fallback to calibrated road-adjusted Haversine
    fallback_km = haversine_road_distance_km(lat1, lon1, lat2, lon2, winding_factor=1.25)
    # Estimate ~40 km/h average speed for Indian commercial FMCG freight trucks (includes standard stops)
    est_duration_hours = round(fallback_km / 40.0, 2)
    fallback_result = {
        "distance_km": fallback_km,
        "duration_hours": est_duration_hours,
        "routing_engine": "haversine_road_adjusted",
        "road_factor": 1.25,
        "cached": False,
        "retrieval_timestamp": now_iso,
        "notes": "Computed using road-adjusted Haversine model with calibrated 1.25 highway winding factor.",
    }
    _ROUTE_CACHE[cache_key] = fallback_result
    return fallback_result


class OSRMService:
    def __init__(self, timeout_seconds: float = 4.0):
        self.timeout_seconds = timeout_seconds

    def get_road_distance(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        allow_fallback: bool = True,
    ) -> Tuple[float, bool]:
        res = get_route_distance(origin_lat, origin_lon, dest_lat, dest_lon, allow_network_query=True, timeout_seconds=self.timeout_seconds)
        is_road = res.get("routing_engine") == "osrm_open_street_map"
        return float(res.get("distance_km", 0.0)), is_road

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        return haversine_road_distance_km(lat1, lon1, lat2, lon2, winding_factor=1.0)


osrm_service = OSRMService()
