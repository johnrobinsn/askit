# Copyright 2024 John Robinson
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

import os
import argparse
from functools import partial

from datetime import datetime

import inspect,json
import json5 # used for config file only
from collections import defaultdict
from inspect import Parameter
from pydantic import create_model

from dotenv import load_dotenv

import asyncio
from openai import AsyncOpenAI

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

import logging

logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("mcp").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
# log.setLevel(logging.DEBUG)
  
def schema(f):
    kw = {n:(o.annotation, ... if o.default==Parameter.empty else o.default)
          for n,o in inspect.signature(f).parameters.items()}
    s = create_model(f'Input for `{f.__name__}`', **kw).model_json_schema()
    return dict(type='function',function=dict(name=f.__name__, description=f.__doc__, parameters=s))

defaultSystemPrompt = '''
You are a helpful assistant to another assistent.  The other assistant does not have access to current information, but you do.  
You can help the other assistant by providing information that it can't access.  You can provide information by calling a function that will get the information for you.  
The function will return the information to the other assistant.  The other assistant will then use the information to help the user.  
If you don't know how to obtain the requested information simply state that you don't know how to help with that and nothing more. 
Please be direct and to the point when answering questions or executing commands.
'''

class MCPClient():
    def __init__(self):
        self._streams_context = None
        self._session_context = None
        self._session = None

    async def start(self,server_name,**kwargs):
        try:
            self.server_name = server_name
            if 'url' not in kwargs:
                log.debug('setting up stdio client %s', kwargs)
                server_params = StdioServerParameters(**kwargs)                
                self._streams_context = stdio_client(server_params)
            else:
                log.debug('setting up sse client %s', kwargs)
                self._streams_context = sse_client(**kwargs)

            streams = await self._streams_context.__aenter__()

            self._session_context = ClientSession(*streams)
            self._session = await self._session_context.__aenter__()
            await self._session.initialize()
        except Exception as e:
            raise Exception(f"Error connecting to server.  Confirm config and availability.")

    def get_session(self):
        return self._session          

    async def stop(self):
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)
        self._session = None
class AskIt():
    def __init__(self,system_prompt=None,model=None,api_key=None,base_url=None):
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')      
        self.client = AsyncOpenAI(api_key=api_key,base_url=base_url)
        self.name = 'OpenAI'
        self.initial_prompt = {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": defaultSystemPrompt.strip()
                    },
                ],
            }
        if system_prompt:
            self.initial_prompt = system_prompt

        self.model = model if model else "gpt-4o-mini"
        
        self.mcp_schemas = []
        self.mcp_funcs = {}

        self.mcp_clients = []

    async def stop(self):
        self.mcp_funcs = {}
        # Note that the order of stopping is important.  
        # The last client started should be stopped first.
        self.mcp_clients.reverse()
        for client in self.mcp_clients:
            await client.stop()
        self.mcp_clients = []

    def get_mcp_tool_names(self):
        return [client.server_name for client in self.mcp_clients]

    async def load_mcp_config(self, mcp_config_file='mcp_config.json'):
        await self.stop()
        try:
            with open(mcp_config_file, "r") as f:
                try:
                    mcp_config = json5.load(f)
                except json.JSONDecodeError as e:
                    log.error(f"Error decoding mcp_config.json: {e}")
                    return False
                
                for server_name, server_config in mcp_config['mcpServers'].items():
                    try:
                        log.debug(f"Configure mcpServer; key: {server_name}, value: {server_config}")
                        client = MCPClient()
                        await client.start(server_name,**server_config)
                        self.mcp_clients.append(client)
                        session = client.get_session()      

                        tools = await session.list_tools()
                        for t in tools.tools:
                            input_schema = getattr(t,'inputSchema',{"type": "object", "properties": {}})
                            fn_def = {
                            "name": f"{server_name}_{t.name}",
                            "description": getattr(t,'description', '') or '',
                            "parameters": input_schema
                            }
                            self.mcp_schemas.append({'type': 'function', 'function': fn_def})
                            def mk_func(call_tool, name):
                                # closure capturing 'session' and 'name'
                                return lambda **kwargs: partial(call_tool, name)(kwargs)
                            self.mcp_funcs[f"{server_name}_{t.name}"] = mk_func(session.call_tool, t.name)
                    except Exception as e:
                        log.error(f"mcp server: {server_name}; {e}")
        except FileNotFoundError:
            log.error(f"{mcp_config_file} not found.  Please create a config file.")
            return False
        except Exception as e:
            log.error(f"Error loading {mcp_config_file}: {e}")
            return False
        return True

    async def prompt(self,text,moreTools=[],messages=[],max_tool_calls=3):
        """
        Prompt the model with the given text and return the response as a string.
        """

        async def gather_strings(stream):
            result = ''
            async for chunk in stream:
                result += chunk
            return result
        
        return await gather_strings(self.promptStream(text,moreTools=moreTools,messages=messages,max_tool_calls=max_tool_calls))

    async def promptStream(self,text,moreTools=[],messages=[],max_tool_calls=3):
        """
        Prompt the model with the given text and return a generator 
        that streams the response.
        """
        
        # await self.load_mcp_tools()

        def tool_list_to_tool_calls(tools):
            # Initialize a dictionary with default values
            tool_calls_dict = defaultdict(lambda: {"id": None, "function": {"arguments": "", "name": None}, "type": None})

            # Iterate over the tool calls
            for tool_call in tools:
                # If the id is not None, set it
                if tool_call.id is not None:
                    tool_calls_dict[tool_call.index]["id"] = tool_call.id

                # If the function name is not None, set it
                if tool_call.function.name is not None:
                    tool_calls_dict[tool_call.index]["function"]["name"] = tool_call.function.name

                # Append the arguments
                tool_calls_dict[tool_call.index]["function"]["arguments"] += tool_call.function.arguments

                # If the type is not None, set it
                if tool_call.type is not None:
                    tool_calls_dict[tool_call.index]["type"] = tool_call.type

            # Convert the dictionary to a list
            tool_calls_list = list(tool_calls_dict.values())

            # Return the result
            return tool_calls_list

        if text == '':
            return

        if len(messages) == 0:
            messages.append(self.initial_prompt)

        messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text
                    },
                ],
            })

        msgs = messages

        tool_schemas = self.mcp_schemas.copy()
        tool_schemas.extend([schema(tool) for tool in moreTools])

        for i in range(max_tool_calls+1):
            allow_tool_calls = i < max_tool_calls

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                tools=tool_schemas if allow_tool_calls else None,
                stream=True,
            )

            reply=""
            tools=[]
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    reply += chunk.choices[0].delta.content        # gather for chat history
                    yield chunk.choices[0].delta.content           # your output method
                if chunk.choices[0].delta.tool_calls:
                    tools += chunk.choices[0].delta.tool_calls     # gather ChoiceDeltaToolCall list chunks

            messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": reply
                        },
                    ],
                })

            tool_calls = tool_list_to_tool_calls(tools)

            if not tool_calls:
                return
            else:
                # Thar be tool calls
                # Note: the JSON response may not always be valid; be sure to handle errors

                available_functions = self.mcp_funcs.copy()
                more_functions = {tool.__name__: tool for tool in moreTools}
                available_functions.update(more_functions)

                msgs.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tool_call['id'], 
                        "function": {
                            "name": tool_call['function']['name'], 
                            "arguments": tool_call['function']['arguments']
                        },
                        "type": "function"
                    } for tool_call in tool_calls]
                })

                for tool_call in tool_calls:
                    function_name = tool_call['function']['name']

                    function_to_call = available_functions[function_name]
                    function_args = tool_call['function']['arguments']
                    function_args = json.loads(function_args)

                    log.debug(f"Function call: {function_name} with args: {function_args}")

                    try:
                        function_response = await function_to_call(
                            **function_args
                        )
                    except Exception as e:
                        function_response = f"Error: {e}"

                    log.debug(f"Function result: {function_response}")

                    msgs.append(
                        {
                            "tool_call_id": tool_call['id'],
                            "role": "tool",
                            "name": function_name,
                            "content": f'{function_response}',
                            "text": f"Calling {function_name}"
                        }                
                    )

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

def main():
    from termcolor import colored

    load_dotenv(override=True)

    parser = argparse.ArgumentParser(description='AskIt command line interface')
    parser.add_argument('--api_key', type=str, help='API key')
    parser.add_argument('--base_url', type=str, help='Base URL')
    parser.add_argument('--model', type=str, help='Model to use')
    args = parser.parse_args()

    api_key = args.api_key
    base_url = args.base_url
    model = args.model

    askit = AskIt(api_key=api_key,base_url=base_url, model=args.model)
    print(colored(f'askit using model: {askit.model}', 'cyan'))

    from prompt_toolkit import PromptSession
    
    async def read_lines():
        messages = []
        tools = [fetch_stock_price, get_current_time, get_current_location]

        await askit.load_mcp_config()
        print(colored(f'askit using mcp tools: {askit.get_mcp_tool_names()}', 'cyan'))

        session = PromptSession("> ")
        # In-memory history is maintained by prompt_toolkit automatically
        while True:
            try:
                line = await session.prompt_async("> ")
            except (EOFError, KeyboardInterrupt):
                break
            response = await askit.prompt(line.strip(), moreTools=tools, messages=messages)
            if response: print(colored(response, "green"))

        print("shutting down")
        await askit.stop()

    asyncio.run(read_lines())


if __name__ == '__main__':
    main()