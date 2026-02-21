"""
Weather API service using Open-Meteo (free, no API key required)
Uses synchronous requests for simplicity with GTK
"""
import urllib.request
import urllib.parse
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import logging

log = logging.getLogger(__name__)


@dataclass
class WeatherData:
    """Weather data for a location"""
    location_name: str
    country: str
    timezone: str
    temperature: float
    feels_like: float
    humidity: int
    wind_speed: float
    weather_code: int
    is_day: bool
    local_time: datetime
    latitude: float
    longitude: float
    temp_max: float = 0.0
    temp_min: float = 0.0
    display_name: str = ""  # Optional custom display name

    @property
    def weather_icon(self) -> str:
        """Get weather icon name based on WMO weather code"""
        return WEATHER_ICONS.get(self.weather_code, "weather-clear")

    @property
    def weather_description(self) -> str:
        """Get human-readable weather description"""
        return WEATHER_DESCRIPTIONS.get(self.weather_code, "Unknown")


# WMO Weather interpretation codes (WW)
# https://open-meteo.com/en/docs
WEATHER_ICONS = {
    0: "weather-clear",  # Clear sky
    1: "weather-clear",  # Mainly clear
    2: "weather-few-clouds",  # Partly cloudy
    3: "weather-overcast",  # Overcast
    45: "weather-fog",  # Foggy
    48: "weather-fog",  # Depositing rime fog
    51: "weather-showers-scattered",  # Light drizzle
    53: "weather-showers-scattered",  # Moderate drizzle
    55: "weather-showers-scattered",  # Dense drizzle
    56: "weather-freezing-rain",  # Light freezing drizzle
    57: "weather-freezing-rain",  # Dense freezing drizzle
    61: "weather-showers",  # Slight rain
    63: "weather-showers",  # Moderate rain
    65: "weather-showers",  # Heavy rain
    66: "weather-freezing-rain",  # Light freezing rain
    67: "weather-freezing-rain",  # Heavy freezing rain
    71: "weather-snow",  # Slight snow
    73: "weather-snow",  # Moderate snow
    75: "weather-snow",  # Heavy snow
    77: "weather-snow",  # Snow grains
    80: "weather-showers-scattered",  # Slight rain showers
    81: "weather-showers",  # Moderate rain showers
    82: "weather-storm",  # Violent rain showers
    85: "weather-snow",  # Slight snow showers
    86: "weather-snow",  # Heavy snow showers
    95: "weather-storm",  # Thunderstorm
    96: "weather-storm",  # Thunderstorm with slight hail
    99: "weather-storm",  # Thunderstorm with heavy hail
}

WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Light snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm",
}


class GeocodingError(Exception):
    """Raised when geocoding fails"""
    pass


class WeatherAPI:
    """Open-Meteo API client using synchronous requests"""

    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

    def _fetch_json(self, url: str, params: dict) -> dict:
        """Fetch JSON from URL with parameters"""
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"

        request = urllib.request.Request(
            full_url,
            headers={"User-Agent": "WeatherBuddy/1.0"}
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    async def search_location(self, query: str) -> list[dict]:
        """Search for a location by name"""
        params = {
            "name": query,
            "count": 5,
            "language": "en",
            "format": "json"
        }

        try:
            data = self._fetch_json(self.GEOCODING_URL, params)
            return data.get("results", [])
        except Exception as e:
            log.error(f"Geocoding error: {e}")
            raise GeocodingError(f"Network error: {e}")

    async def get_weather(self, latitude: float, longitude: float,
                          location_name: str, country: str, timezone: str) -> WeatherData:
        """Get current weather for coordinates"""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": timezone,
            "forecast_days": 1
        }

        try:
            data = self._fetch_json(self.WEATHER_URL, params)
            current = data.get("current", {})
            daily = data.get("daily", {})

            # Parse local time from the API
            time_str = current.get("time", "")
            local_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

            # Get daily high/low
            temp_max = daily.get("temperature_2m_max", [0.0])[0]
            temp_min = daily.get("temperature_2m_min", [0.0])[0]

            return WeatherData(
                location_name=location_name,
                country=country,
                timezone=timezone,
                temperature=current.get("temperature_2m", 0),
                feels_like=current.get("apparent_temperature", 0),
                humidity=current.get("relative_humidity_2m", 0),
                wind_speed=current.get("wind_speed_10m", 0),
                weather_code=current.get("weather_code", 0),
                is_day=bool(current.get("is_day", 1)),
                local_time=local_time,
                latitude=latitude,
                longitude=longitude,
                temp_max=temp_max,
                temp_min=temp_min
            )
        except Exception as e:
            log.error(f"Weather API error: {e}")
            raise Exception(f"Network error: {e}")

    async def get_weather_for_location(self, location_query: str) -> WeatherData:
        """Search for location and get weather in one call"""
        results = await self.search_location(location_query)
        if not results:
            raise GeocodingError(f"Location not found: {location_query}")

        location = results[0]  # Use first result
        return await self.get_weather(
            latitude=location["latitude"],
            longitude=location["longitude"],
            location_name=location["name"],
            country=location.get("country", ""),
            timezone=location["timezone"]
        )

    async def close(self):
        """No-op for synchronous client"""
        pass


# Global instance
weather_api = WeatherAPI()
