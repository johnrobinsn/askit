
import aiohttp
import re
from markdownify import markdownify as md
    
async def visit_webpage(url: str) -> str:
    """Visits a webpage at the given URL and returns its content as a markdown string.

    Args:
        url (str): The URL of the webpage to visit.

    Returns:
        str: The content of the webpage converted to Markdown, or an error message if the request fails.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    # Convert the HTML content to Markdown
                    # print('before markdownify')
                    markdown_content = md(text).strip()
                    # Remove multiple line breaks
                    markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
                    # print('after markdownify')
                    return markdown_content
                else:
                    return f"Failed to fetch data: {response.status}"
    except Exception as e:
        return f"An error occurred: {e}"

def register():
    return visit_webpage