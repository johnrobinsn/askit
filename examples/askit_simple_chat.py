# Copyright 2025 John Robinson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Here is an example of how to use the AskIt library in a simple chat client.
#
# Askit also supports local function calling python functions as tools in addtion to its support for calling MCP servers.
# This example shows how to use the AskIt library to fetch stock prices, current time, and location using local functions as tools.
#
# As a simple chat client this example provides a historical context in the form of a "messages" array that is passed into the prompt call.
# this array is used to maintain the chat history and is updated with each response from the LLM.

from datetime import datetime
import argparse
import asyncio

from dotenv import load_dotenv

import logging

from askit import AskIt

logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("mcp").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

import aiohttp
async def fetch_stock_price(ticker_symbol:str):
    """
    Takes the ticket symbol for a given stock and returns the current stock price in USD.

    Returns:
        float: The current price of the stock
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; AskIt/1.0)'}) as response:
                if response.status == 200:
                    data = await response.json()
                    current_price = data['chart']['result'][0]['meta']['regularMarketPrice']
                    return current_price
                else:
                    return f"Failed to fetch data: {response.status}"
    except Exception as e:
        return f"An error occurred: {e}"

async def get_current_time():
    """
    Get the current date and time

    Returns:
        str: The current time in HH:MM:SS format

    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def get_current_location():
    """
    Get your current location

    Returns:
        str: Your current location.

    """
    return 'Chantilly, VA 20152'


async def main():
    from termcolor import colored
    from pathlib import Path

    load_dotenv(override=True,dotenv_path=Path.cwd() / ".env")

    parser = argparse.ArgumentParser(description='AskIt command line interface')
    parser.add_argument('--api_key', type=str, help='API key')
    parser.add_argument('--base_url', type=str, help='Base URL')
    parser.add_argument('--model', type=str, help='Model to use')
    parser.add_argument('--provider', type=str, default='OPENAI', help='LLM provider (default: OPENAI)')
    args = parser.parse_args()

    api_key = args.api_key if args.api_key is not None else None
    base_url = args.base_url if args.base_url is not None else None
    model = args.model if args.model is not None else None
    provider = args.provider

    from prompt_toolkit import PromptSession
    
    async def read_lines():

        async with AskIt(api_key=api_key, base_url=base_url, model=model, provider=provider) as askit:

            print(colored(f'askit using model: {askit.model}', 'cyan'))

            await askit.load_mcp_config()
            print(colored(f'askit using mcp tools: {askit.get_mcp_tool_names()}', 'cyan'))

            session = PromptSession("> ")
            messages = []

            # In-memory history is maintained by prompt_toolkit automatically
            while True:
                try:
                    line = await session.prompt_async("> ")
                except (EOFError, KeyboardInterrupt):
                    break

                # We pass in the functions as tools to AskIt
                # This allows the LLM to call these functions as tools
                response = await askit.prompt(line.strip(), 
                                            tools=[fetch_stock_price, get_current_time, get_current_location], 
                                            messages=messages)
                if response: print(colored(response, "green"))

            print("shutting down")

    await read_lines()

if __name__ == '__main__':
    asyncio.run(main())