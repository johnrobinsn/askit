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

import os
import argparse
from dotenv import load_dotenv

import asyncio

import logging

from functools import partial

import inspect,json
import json5 # used for config file only
from collections import defaultdict
from inspect import Parameter
from pydantic import create_model

from openai import AsyncOpenAI

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

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

# This class helps manage the nested async context managers for the MCP client.
# It handles the streams context and the session context, allowing for clean startup and shutdown of the
# MCP client connection.
# The unfortunate design choice of the MCP client library forces us to manually shut down the streams and 
# session contexts via the stop() method prior to exiting the asyncio loop.
class MCPClient():
    def __init__(self):
        self._streams_context = None
        self._session_context = None
        self._session = None

    async def start(self,server_name,**kwargs):
        try:
            self.server_name = server_name
            transport = kwargs.get('transport', 'http' if 'url' in kwargs else 'stdio')
            kwargs_no_transport = {k: v for k, v in kwargs.items() if k not in ['transport','disabled']}

            if transport == 'stdio':
                log.debug('setting up stdio client %s', kwargs)
                server_params = StdioServerParameters(**kwargs_no_transport)                
                self._streams_context = stdio_client(server_params)
            elif transport == 'sse':
                log.debug('setting up sse client %s', kwargs)
                self._streams_context = sse_client(**kwargs_no_transport)
            elif transport == 'http':                
                log.debug('setting up http client %s', kwargs)
                # Note: MCP client library does not support HTTP transport yet.
                self._streams_context = streamablehttp_client(**kwargs_no_transport)

            streams = await self._streams_context.__aenter__()

            # streams is a tuple of (read_stream, write_stream, *)
            self._session_context = ClientSession(streams[0],streams[1])
            self._session = await self._session_context.__aenter__()
            await self._session.initialize()
        except Exception as e:
            raise Exception(f"Error connecting to server.  Confirm config and availability. {e}")

    def get_session(self):
        return self._session          

    async def stop(self):
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)
        self._session = None

class AskIt():
    provider_defaults = {
        'OPENAI': {
            'base_url': None,  # for OPENAI just tunnel this through to the openai api impl
            'model': "gpt-4o-mini"
        },
        'XAI': {
            'base_url': "https://api.x.ai/v1",
            'model': "grok-4-latest"
        }
    }

    def __init__(self,system_prompt=None,model=None,api_key=None,base_url=None,provider=None):
        if not provider:
            provider = os.getenv('ASKIT_PROVIDER', 'OPENAI').upper()

        if provider not in ['OPENAI', 'XAI']:
            log.warning(f"Unsupported provider: {provider}. Defaulting to OPENAI.")
            provider = 'OPENAI'

        if not api_key:
            api_key = os.getenv(f'{provider}_API_KEY')
        if not base_url:
            base_url = os.getenv(f'{provider}_BASE_URL', AskIt.provider_defaults[provider]['base_url'])
        if not model:
            model = os.getenv(f'{provider}_MODEL', AskIt.provider_defaults[provider]['model'])
        if not system_prompt:
            system_prompt = os.getenv('ASKIT_SYSTEM_PROMPT', None)

        if not api_key:
            raise ValueError(f"API key for {provider} is required. Please set the {provider}_API_KEY environment variable or pass in api_key as an argument.")
        
        self.client = AsyncOpenAI(api_key=api_key,base_url=base_url)
        
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        
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

    async def __aenter__(self):
        """
        Asynchronous context manager entry point.
        """
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """
        Asynchronous context manager exit point.
        """
        await self.stop()        

    def get_mcp_tool_names(self):
        return [client.server_name for client in self.mcp_clients]

    async def load_mcp_config(self, mcp_config_file='mcp_config.json'):
        # await self.stop()
        try:
            with open(mcp_config_file, "r") as f:
                try:
                    mcp_config = json5.load(f)
                except json.JSONDecodeError as e:
                    log.error(f"Error decoding mcp_config.json: {e}")
                    return False
                
                for server_name, server_config in mcp_config['mcpServers'].items():
                    if 'disabled' in server_config and server_config['disabled']:
                        log.warning(f"Skipping disabled MCP server: {server_name}")
                        continue
                    try:
                        log.debug(f"Configure mcpServer; key: {server_name}, value: {server_config}")
                        client = MCPClient()
                        await client.start(server_name,**server_config)
                        self.mcp_clients.append(client)
                        session = client.get_session()      

                        tools = await session.list_tools()
                        for t in tools.tools:
                            input_schema = getattr(t,'inputSchema',{"type": "object", "properties": {}})
                            
                            # Clean up schema to remove None values that OpenAI doesn't accept
                            def clean_schema(schema):
                                if isinstance(schema, dict):
                                    cleaned = {}
                                    for key, value in schema.items():
                                        if value is not None:
                                            cleaned[key] = clean_schema(value)
                                    return cleaned
                                elif isinstance(schema, list):
                                    return [clean_schema(item) for item in schema]
                                else:
                                    return schema
                            
                            cleaned_input_schema = clean_schema(input_schema)
                            
                            fn_def = {
                            "name": f"{server_name}_{t.name}",
                            "description": getattr(t,'description', '') or '',
                            "parameters": cleaned_input_schema
                            }
                            self.mcp_schemas.append({'type': 'function', 'function': fn_def})
                            def mk_func(call_tool, name):
                                # closure capturing 'session' and 'name'
                                async def async_wrapper(**kwargs):
                                    if inspect.iscoroutinefunction(call_tool):
                                        return await call_tool(name, kwargs)
                                    else:
                                        return call_tool(name, kwargs)
                                return async_wrapper
                            self.mcp_funcs[f"{server_name}_{t.name}"] = mk_func(session.call_tool, t.name)
                    except Exception as e:
                        log.error(f"mcp server: {server_name}; {e}")
        except FileNotFoundError:
            log.warning(f"{mcp_config_file} not found.  Please create a config file.")
            return False
        except Exception as e:
            log.error(f"Error loading {mcp_config_file}: {e}")
            return False
        return True

    async def prompt(self,text,tools=[],messages=[],max_tool_calls=3,stream=False):
        """
        Prompt the model with the given text and return the response as a string or a generator that streams the response.
        If stream is True, the response will be streamed.
        If stream is False, the response will be returned as a string.
        """
        if stream:
            return self._streamResponse(text,tools=tools,messages=messages,max_tool_calls=max_tool_calls)
        else:
            return await self._getResponse(text,tools=tools,messages=messages,max_tool_calls=max_tool_calls)

    async def _getResponse(self,text,tools=[],messages=[],max_tool_calls=3):
        """
        Prompt the model with the given text and return the response as a string.
        """

        async def gather_strings(stream):
            result = ''
            async for chunk in stream:
                result += chunk
            return result

        return await gather_strings(self._streamResponse(text,tools=tools,messages=messages,max_tool_calls=max_tool_calls))

    async def _streamResponse(self,text,tools=[],messages=[],max_tool_calls=3):
        """
        Prompt the model with the given text and return a generator 
        that streams the response.
        """
        
        # async def gather_strings(stream):
        #     result = ''
        #     async for chunk in stream:
        #         result += chunk
        #     return result

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

        if len(messages) == 0 and self.system_prompt:
            messages.append({
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": self.system_prompt.strip()
                        },
                    ],
                })

        if text:
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
        tool_schemas.extend([schema(tool) for tool in tools])

        for i in range(max_tool_calls+1):
            allow_tool_calls = i < max_tool_calls

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                tools=tool_schemas if allow_tool_calls else None,
                stream=True,
            )

            reply=""
            _tools=[]
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    reply += chunk.choices[0].delta.content        # gather for chat history
                    yield chunk.choices[0].delta.content           # your output method
                if chunk.choices[0].delta.tool_calls:
                    _tools += chunk.choices[0].delta.tool_calls     # gather ChoiceDeltaToolCall list chunks

            messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": reply
                        },
                    ],
                })

            tool_calls = tool_list_to_tool_calls(_tools)

            if not tool_calls:
                return
            else:
                # Thar be tool calls
                # Note: the JSON response may not always be valid; be sure to handle errors

                available_functions = self.mcp_funcs.copy()
                more_functions = {tool.__name__: tool for tool in tools}
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
                        if inspect.iscoroutinefunction(function_to_call):
                            function_response = await function_to_call(**function_args)
                        else:
                            function_response = function_to_call(**function_args)
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

    from prompt_toolkit import PromptSession
    
    async def read_lines():
        messages = []

        # askit = AskIt(api_key=api_key,base_url=base_url, model=model)
        async with AskIt(api_key=args.api_key, base_url=args.base_url, model=args.model, provider=args.provider) as askit:
            print(colored(f'askit using model: {askit.model}', 'cyan'))
            await askit.load_mcp_config()
            print(colored(f'askit using mcp tools: {askit.get_mcp_tool_names()}', 'cyan'))

            session = PromptSession("> ")
            # In-memory history is maintained by prompt_toolkit automatically
            while True:
                try:
                    line = await session.prompt_async("> ")
                except (EOFError, KeyboardInterrupt):
                    break
                response = await askit.prompt(line.strip(), messages=messages)
                if response: print(colored(response, "green"))

        print("shutting down")
        # await askit.stop()

    await read_lines()


if __name__ == '__main__':
    asyncio.run(main())