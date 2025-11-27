import os
from datetime import datetime
from typing import Dict, Optional, Tuple, List

import requests


class WeatherService:
    """Service to fetch weather data from Google Maps Weather API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self._geocode_cache: Dict[str, Tuple[float, float]] = {}

        if not self.api_key:
            # Don't raise error - just log warning and allow service to exist but fail gracefully
            print("Warning: GOOGLE_MAPS_API_KEY not set - weather service will use fallback data")
            self.api_key = None

    def _geocode_location(self, location: str) -> Optional[Tuple[float, float]]:
        """Get latitude and longitude for a location name."""
        if not location:
            return None

        cached = self._geocode_cache.get(location.lower())
        if cached:
            return cached

        if not self.api_key:
            return None

        try:
            geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": location, "key": self.api_key}
            response = requests.get(geocode_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK" and data.get("results"):
                    location_data = data["results"][0]["geometry"]["location"]
                    coords = (location_data["lat"], location_data["lng"])
                    self._geocode_cache[location.lower()] = coords
                    return coords
            return None
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error geocoding location '{location}': {exc}")
            return None

    def get_weather_for_location(self, location: str, date: Optional[str] = None) -> Dict:
        """Get weather data for a location and optional date."""
        try:
            if not self.api_key:
                return self._get_fallback_weather(location, date)

            coords = self._geocode_location(location)
            if not coords:
                print(f"Could not geocode location: {location}")
                return self._get_fallback_weather(location, date)

            lat, lng = coords

            url = "https://weather.googleapis.com/v1/forecast/days:lookup"
            params = {
                "location.latitude": lat,
                "location.longitude": lng,
                "languageCode": "en-US",
                "key": self.api_key,
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if "forecastDays" in data:
                    formatted = self._format_weather_data(data, location, date, lat, lng)
                    return formatted

                print(f"Weather API response format unexpected: {list(data.keys())}")
                return self._get_fallback_weather(location, date)

            print(f"Weather API returned status code: {response.status_code}")
            return self._get_fallback_weather(location, date)

        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error fetching weather data: {exc}")
            return self._get_fallback_weather(location, date)

    def _format_weather_data(
        self, data: Dict, location: str, date: Optional[str], lat: Optional[float], lng: Optional[float]
    ) -> Dict:
        """Format weather data from API response."""
        try:
            forecast_days = data.get("forecastDays", [])
            if not forecast_days:
                return self._get_fallback_weather(location, date)

            forecast = self._select_forecast_for_date(forecast_days, date)
            if not forecast:
                return self._get_fallback_weather(location, date)

            display_date = forecast.get("displayDate", {})
            forecast_date = f"{display_date.get('year', 2025)}-{display_date.get('month', 1):02d}-{display_date.get('day', 1):02d}"

            max_temp_obj = forecast.get("maxTemperature", {})
            min_temp_obj = forecast.get("minTemperature", {})
            high_temp = max_temp_obj.get("degrees")
            low_temp = min_temp_obj.get("degrees")
            temp_unit = max_temp_obj.get("unit", "CELSIUS")
            temp_unit_simple = "C" if temp_unit == "CELSIUS" else "F"

            daytime = forecast.get("daytimeForecast", {})
            weather_condition = daytime.get("weatherCondition", {})
            condition_type = weather_condition.get("type", "UNKNOWN")
            condition_desc = weather_condition.get("description", {}).get("text", condition_type)

            precip = daytime.get("precipitation", {})
            precip_prob_obj = precip.get("probability", {})
            precip_prob = precip_prob_obj.get("percent")

            humidity = daytime.get("relativeHumidity")

            wind = daytime.get("wind", {})
            wind_speed_obj = wind.get("speed", {})
            wind_speed = wind_speed_obj.get("value")

            avg_temp = self._compute_average_temp(high_temp, low_temp)

            result = {
                "location": location,
                "date": forecast_date,
                "high_temperature": self._safe_int(high_temp),
                "low_temperature": self._safe_int(low_temp),
                "temperature": avg_temp,
                "temperature_unit": temp_unit_simple,
                "condition": condition_desc,
                "precipitation_probability": precip_prob if precip_prob is not None else 0,
                "description": condition_desc,
                "humidity": humidity if humidity is not None else 0,
                "wind_speed": wind_speed if wind_speed is not None else 0,
                "latitude": lat,
                "longitude": lng,
                "is_fallback": False,
            }

            result["icon"] = self.get_weather_icon(condition_desc or "")
            result["is_bad_weather"] = self.is_bad_weather(result)
            return result

        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error formatting weather data: {exc}")
            return self._get_fallback_weather(location, date)

    def _select_forecast_for_date(self, forecast_days: List[Dict], date: Optional[str]) -> Optional[Dict]:
        """Return the forecast dict matching provided date."""
        if not forecast_days:
            return None

        if not date:
            return forecast_days[0]

        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            print(f"Warning: Invalid date format '{date}', using first forecast")
            return forecast_days[0]

        # Try exact match first
        for forecast in forecast_days:
            display_date = forecast.get("displayDate", {})
            if (
                display_date.get("year") == target_date.year
                and display_date.get("month") == target_date.month
                and display_date.get("day") == target_date.day
            ):
                return forecast

        # If no exact match, find the closest forecast (within 1 day)
        closest_forecast = None
        min_diff = float('inf')
        for forecast in forecast_days:
            display_date = forecast.get("displayDate", {})
            try:
                forecast_date = datetime(
                    display_date.get("year", target_date.year),
                    display_date.get("month", target_date.month),
                    display_date.get("day", target_date.day)
                )
                diff = abs((forecast_date - target_date).days)
                if diff < min_diff:
                    min_diff = diff
                    closest_forecast = forecast
            except (ValueError, TypeError):
                continue

        # Return closest if within 1 day, otherwise return first forecast
        if closest_forecast and min_diff <= 1:
            return closest_forecast

        # Fallback to first forecast
        return forecast_days[0] if forecast_days else None

    @staticmethod
    def _compute_average_temp(high_temp: Optional[float], low_temp: Optional[float]) -> int:
        temps = [t for t in (high_temp, low_temp) if isinstance(t, (int, float))]
        if temps:
            return int(sum(temps) / len(temps))
        return 25

    @staticmethod
    def _safe_int(value: Optional[float]) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        return 0

    def _get_fallback_weather(self, location: str, target_date: Optional[str] = None) -> Dict:
        """Fallback weather data if API fails."""
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        fallback = {
            "location": location,
            "date": date_str,
            "temperature": 25,
            "temperature_unit": "C",
            "high_temperature": 26,
            "low_temperature": 22,
            "condition": "Unknown",
            "description": "Weather data unavailable",
            "precipitation_probability": 0,
            "humidity": 0,
            "wind_speed": 0,
            "icon": "🌤️",
            "is_fallback": True,
        }
        fallback["is_bad_weather"] = self.is_bad_weather(fallback)
        return fallback

    def is_bad_weather(self, weather_data: Dict) -> bool:
        """Determine if weather is bad (rain, storms, extreme conditions)."""
        condition = (weather_data.get("condition", "") or "").lower()
        description = (weather_data.get("description", "") or "").lower()
        precip_prob = weather_data.get("precipitation_probability", 0) or 0

        bad_weather_keywords = ["rain", "storm", "thunder", "snow", "hail", "fog", "extreme"]

        if precip_prob > 60:
            return True

        if any(keyword in condition or keyword in description for keyword in bad_weather_keywords):
            return True

        return False

    def get_weather_icon(self, condition: str) -> str:
        """Get emoji icon for weather condition."""
        condition_lower = (condition or "").lower()
        if "sun" in condition_lower or "clear" in condition_lower:
            return "☀️"
        if "cloud" in condition_lower:
            return "☁️"
        if "rain" in condition_lower or "shower" in condition_lower:
            return "🌧️"
        if "storm" in condition_lower or "thunder" in condition_lower:
            return "⛈️"
        if "snow" in condition_lower:
            return "❄️"
        if "fog" in condition_lower or "mist" in condition_lower:
            return "🌫️"
        return "🌤️"

