from datetime import datetime

async def get_current_time():
    """
    Get the current date and time

    Returns:
        str: The current time in HH:MM:SS format

    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def register():
    return get_current_time