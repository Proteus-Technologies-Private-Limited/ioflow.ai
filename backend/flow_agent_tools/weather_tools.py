import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


def get_weather(city: str) -> dict:
    """
    Get the current weather for a specified city.

    This function retrieves weather information for the given city name.
    The LLM should call this function by passing just the city name as a string.

    Args:
        city: The name of the city to get weather for (e.g., "New York", "London").
              Pass only the city name, not a full query or sentence.

    Returns:
        dict: A dictionary containing:
            - "status": "success" or "error"
            - "report": Weather report string if successful (e.g., "Sunny, 25C in New York.")
            - "error_message": Error description if city not found

    Example:
        >>> get_weather("New York")
        {"status": "success", "report": "Sunny, 25C in New York."}

        >>> get_weather("London")
        {"status": "success", "report": "Cloudy, 18C in London."}

    Note: This is a demonstration implementation with hardcoded data.
    In production, this would call a real weather API service.
    """
    # Log tool invocation for debugging
    logger.info(f"get_weather called with city: {city}")

    # In a real case, this might call an external API.
    city_lower = city.lower()
    if city_lower == "new york":
        return {"status": "success", "report": "Sunny, 25C in New York."}
    elif city_lower == "london":
        return {"status": "success", "report": "Cloudy, 18C in London."}
    elif city_lower == "tokyo":
        return {"status": "success", "report": "Clear, 22C in Tokyo."}
    elif city_lower == "paris":
        return {"status": "success", "report": "Rainy, 15C in Paris."}
    elif city_lower == "mumbai":
        return {"status": "success", "report": "Rainy, 26C in Mumbai."}
    else:
        return {"status": "error", "error_message": f"No weather data for '{city}'."}


def get_current_time(city: str) -> dict:
    """
    Get the current local time for a specified city.

    This function retrieves the current time in the local timezone of the given city.
    The LLM should call this function by passing just the city name as a string.

    Args:
        city: The name of the city to get the time for (e.g., "Tokyo", "Paris").
              Pass only the city name, not a full query or sentence.

    Returns:
        dict: A dictionary containing:
            - "status": "success" or "error"
            - "report": Time report string if successful (e.g., "The local time in Tokyo is 2024-01-15 14:30:00.")
            - "error_message": Error description if city timezone not found

    Example:
        >>> get_current_time("Tokyo")
        {"status": "success", "report": "The local time in Tokyo is 2024-01-15 14:30:00."}

        >>> get_current_time("New York")
        {"status": "success", "report": "The local time in New York is 2024-01-15 01:30:00."}

    Supported cities:
        New York, London, Tokyo, Paris, Los Angeles, Chicago,
        Sydney, Dubai, Singapore, Beijing
    """
    # Log tool invocation for debugging
    logger.info(f"get_current_time called with city: {city}")

    city_timezones = {
        "new york": "America/New_York",
        "london": "Europe/London",
        "tokyo": "Asia/Tokyo",
        "paris": "Europe/Paris",
        "los angeles": "America/Los_Angeles",
        "chicago": "America/Chicago",
        "sydney": "Australia/Sydney",
        "dubai": "Asia/Dubai",
        "singapore": "Asia/Singapore",
        "beijing": "Asia/Shanghai"
    }

    tz_name = city_timezones.get(city.lower())
    if tz_name:
        now = datetime.datetime.now(ZoneInfo(tz_name))
        return {
            "status": "success",
            "report": f"The local time in {city} is {now.strftime('%Y-%m-%d %H:%M:%S')}."
        }
    else:
        return {
            "status": "error",
            "error_message": f"Time zone for '{city}' not found."
        }