import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def get_coordinates(location: str) -> dict:
    """
    Convert a city/location name into latitude and longitude.
    """

    params = {
        "name": location,
        "count": 1,
        "language": "en",
        "format": "json",
    }

    response = requests.get(
        GEOCODING_URL,
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    results = data.get("results", [])

    if not results:
        raise ValueError(
            f"Location not found: {location}"
        )

    location_data = results[0]

    return {
        "name": location_data["name"],
        "latitude": location_data["latitude"],
        "longitude": location_data["longitude"],
        "country": location_data.get("country"),
    }


def get_weather(location: str) -> dict:
    """
    Get current weather for a location.
    """

    coordinates = get_coordinates(location)

    params = {
        "latitude": coordinates["latitude"],
        "longitude": coordinates["longitude"],
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "rain,"
            "weather_code,"
            "wind_speed_10m,"
            "wind_direction_10m"
        ),
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }

    response = requests.get(
        WEATHER_URL,
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    current = data.get("current")

    if not current:
        raise ValueError(
            "Weather data unavailable."
        )

    return {
        "location": coordinates["name"],
        "country": coordinates["country"],
        "latitude": coordinates["latitude"],
        "longitude": coordinates["longitude"],
        "temperature_c": current.get("temperature_2m"),
        "humidity_percent": current.get(
            "relative_humidity_2m"
        ),
        "apparent_temperature_c": current.get(
            "apparent_temperature"
        ),
        "precipitation_mm": current.get(
            "precipitation"
        ),
        "rain_mm": current.get("rain"),
        "weather_code": current.get("weather_code"),
        "wind_speed_kmh": current.get(
            "wind_speed_10m"
        ),
        "wind_direction": current.get(
            "wind_direction_10m"
        ),
        "time": current.get("time"),
    }