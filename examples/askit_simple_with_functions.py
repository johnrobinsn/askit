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

# Here is a very simple example of using the askit library to query an llm and allowing that llm to
# call locally-defined python functions as tools. 
#
# This example provides functions that will allow the llm to fetch stock prices, 
# get the current time, and retrieve a current fake hard-coded location.  
#
# These are just provided for reference showing you how you can make your own functions available to the llm.

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

import asyncio

from askit import AskIt

# simple stock price fetcher using Yahoo Finance API
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

# simple function to get the current time
async def get_current_time():
    """
    Get the current date and time

    Returns:
        str: The current time in HH:MM:SS format

    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# This function is just a placeholder to simulate getting a location.
# In a real application, you might use a geolocation service or API to get the actual location.
# Here we just return a hard-coded string for demonstration purposes.
async def get_current_location():
    """
    Get your current location

    Returns:
        str: Your current location.

    """
    return 'Chantilly, VA 20152'

async def main():
    load_dotenv(override=True,dotenv_path=Path.cwd() / ".env")

    async with AskIt() as askit:
        print(f'askit using model: {askit.model}')

        await askit.load_mcp_config()

        # Ask the llm what time is it without providing a tool to get the current time.
        # We expect the llm to respond that it can't provide the time or it might possibly
        # hallucinate a time.
        prompt = "What is the time?"
        print(f'Asking: {prompt}')

        # Send the prompt to the AskIt instance and get the response
        response = await askit.prompt(prompt)
        print(f'Response: {response}')

        # Now we will provide the llm with a tool to get the current time.
        prompt = "What is the time?"
        print(f'Asking: {prompt}')

        # Send the prompt to the AskIt instance and get the response providing the 
        # get_current_time function as a tool.
        response = await askit.prompt(prompt, tools=[get_current_time])        
        print(f'Response: {response}')

        # Now we will provide the llm with a number of tools.
        prompt = "Where am I?"
        print(f'Asking: {prompt}')

        # Send the prompt to the AskIt instance and get the response providing the 
        # get_current_time function as a tool.
        response = await askit.prompt(prompt, tools=[get_current_time, get_current_location, fetch_stock_price])        
        print(f'Response: {response}')    

        prompt = "What is the stock price of Tesla?"
        print(f'Asking: {prompt}')

        # Send the prompt to the AskIt instance and get the response providing the 
        # get_current_time function as a tool.
        response = await askit.prompt(prompt, tools=[get_current_time, get_current_location, fetch_stock_price])        
        print(f'Response: {response}')    

if __name__ == '__main__':
    asyncio.run(main())