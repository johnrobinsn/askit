import aiohttp
import asyncio

async def fetch_stock_price(ticker_symbol:str):
    """
    Takes the ticket symbol for a given stock and returns the current stock price in USD.

    Returns:
        float: The current price of the stock
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    current_price = data['chart']['result'][0]['meta']['regularMarketPrice']
                    return current_price
                else:
                    return f"Failed to fetch data: {response.status}"
    except Exception as e:
        return f"An error occurred: {e}"


def register():
    return fetch_stock_price

if __name__ == "__main__":
    # Main function to call the async function
    async def main():
        ticker = "AAPL"  # Replace with your desired stock ticker symbol
        price = await fetch_stock_price(ticker)
        print(f"The current price of {ticker} is: ${price:.2f}")

    # Run the async main function
    asyncio.run(main())
