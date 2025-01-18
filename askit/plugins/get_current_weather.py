import json
import logging
import aiohttp

logger = logging.getLogger("get_current_weather")

async def get_current_weather(location: str):
    """
    Called when the user asks about the weather. This function will return the weather for the given location.
    If specifying a location with the state use the two letter abbrtivation for the state.

    Args:
        location (str): The location to get the weather for

    Returns:
        str: The weather in the given location.
    """
    logger.info(f"getting weather for {location}")
    import urllib.parse

    location = urllib.parse.quote(location)
    url = f"https://wttr.in/{location}?format=%C+%t"
    try:
        print('url:', url)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    # print('response:', response.text)
                    weather_data = await response.text()
                    # response from the function call is returned to the LLM
                    # as a tool response. The LLM's response will include this data
                    return f"The weather in {location} is {weather_data}."
                else:
                    print(response.status)
                    # raise f"Failed to get weather data, status code: {response.status}"
                    return f"Failed to get weather data, status code: {response.status}"
    except Exception as e:
        return f"An error occurred: {e}"
            
def register():
    return get_current_weather