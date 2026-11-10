import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CityResult:
    id: int
    name: str
    latitude: float
    longitude: float
    country: str
    admin1: str | None
    timezone: str

    @property
    def display_name(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1 != self.name:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


class GeocodingService:
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    REVERSE_GEO_URL = (
        "https://api.bigdatacloud.net/data/reverse-geocode-client"
    )
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    @classmethod
    async def search_cities(
        cls, query: str, limit: int = 5
    ) -> list[CityResult]:
        """Search cities by name using Open-Meteo Geocoding API."""
        params = {
            "name": query.strip(),
            "count": limit,
            "language": "ru",
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(cls.GEOCODING_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except Exception:
            logger.exception(
                "Error searching city '%s' in geocoding API", query
            )
            return []

        results = []
        for item in data.get("results", []):
            results.append(
                CityResult(
                    id=item.get("id", 0),
                    name=item.get("name", query),
                    latitude=float(item.get("latitude", 0.0)),
                    longitude=float(item.get("longitude", 0.0)),
                    country=item.get("country", ""),
                    admin1=item.get("admin1"),
                    timezone=item.get("timezone", "Europe/Moscow"),
                )
            )
        return results

    @classmethod
    async def reverse_geocode(
        cls, latitude: float, longitude: float
    ) -> CityResult | None:
        """Resolve city name and timezone from GPS coordinates."""
        city_name = "Неизвестный город"
        country = ""
        admin1 = None
        timezone = "Europe/Moscow"

        # 1. Reverse geocode via BigDataCloud
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "localityLanguage": "ru",
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(cls.REVERSE_GEO_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    city_name = (
                        data.get("city")
                        or data.get("locality")
                        or data.get("principalSubdivision")
                        or city_name
                    )
                    country = data.get("countryName", "")
                    admin1 = data.get("principalSubdivision")
        except Exception:
            logger.exception(
                "Error reverse geocoding coordinates (%f, %f)",
                latitude,
                longitude,
            )

        # 2. Get accurate timezone from Open-Meteo
        try:
            tz_params = {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "auto",
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                tz_resp = await client.get(cls.FORECAST_URL, params=tz_params)
                if tz_resp.status_code == 200:
                    timezone = tz_resp.json().get("timezone", timezone)
        except Exception:
            logger.exception(
                "Error resolving timezone for (%f, %f)",
                latitude,
                longitude,
            )

        return CityResult(
            id=int(latitude * 1000 + longitude),
            name=city_name,
            latitude=latitude,
            longitude=longitude,
            country=country,
            admin1=admin1,
            timezone=timezone,
        )
