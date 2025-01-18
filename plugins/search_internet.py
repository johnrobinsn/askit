# from duckduckgo_search import DDGS



# async def search_internet(query: str) -> str:
#     """
#     Searches the internet for the given query and returns the top search results.

#     Args:
#         query (str): The search query.

#     Returns:
#         str: The top search results.
#     """
#     results = DDGS().text(query, max_results=5)
#     # print('results:', results)
#     return results


# def register():
#     return search_internet


import asyncio
from concurrent.futures import ThreadPoolExecutor
from duckduckgo_search import DDGS

executor = ThreadPoolExecutor(1)

async def search_internet(query: str) -> str:
    """
    Searches the internet for the given query and returns the top search results.

    Args:
        query (str): The search query.

    Returns:
        str: The top search results.
    """
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(executor, DDGS().text, query, 5)
    return results

def register():
    return search_internet