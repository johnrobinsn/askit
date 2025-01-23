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
import importlib

from datetime import datetime

import inspect, json
from collections import defaultdict
from inspect import Parameter
from pydantic import create_model

from dotenv import load_dotenv

import asyncio
from openai import AsyncOpenAI

import logging

logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, 'plugins')
PLUGIN_DIR = path

def load_plugins(plugin_dir):
    plugins = []
    for file in os.listdir(plugin_dir):
        if file.endswith(".py") and file != "__init__.py":
            module_name = f"askit.plugins.{file[:-3]}"
            print('module_name:', module_name)
            module = importlib.import_module(module_name)
            if hasattr(module, "register"):
                plugins.append(module)
    return plugins
  
def schema(f):
    kw = {n:(o.annotation, ... if o.default==Parameter.empty else o.default)
          for n,o in inspect.signature(f).parameters.items()}
    s = create_model(f'Input for `{f.__name__}`', **kw).model_json_schema()
    return dict(type='function',function=dict(name=f.__name__, description=f.__doc__, parameters=s))

plugin_modules = load_plugins(PLUGIN_DIR)
plugins = []
for plugin in plugin_modules:
    plugins = [plugin.register() for plugin in plugin_modules]

# flatten the list
flattened_plugins = []
for plugin in plugins:
    if isinstance(plugin, list):
        flattened_plugins.extend(plugin)
    else:
        flattened_plugins.append(plugin)
plugins = flattened_plugins

# print('plugins: ', plugins)
class AskIt():
    def __init__(self,system_prompt=None):
        openai_api_key = os.getenv('OPENAI_API_KEY')      
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.name = 'OpenAI'
        self.initial_prompt = {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are a helpful assistant to another assistent.  The other assistant does not have access to current information, but you do.  You can help the other assistant by providing information that it can't access.  You can provide information by calling a function that will get the information for you.  The function will return the information to the other assistant.  The other assistant will then use the information to help the user.  If you don't know how to obtain the requested information simply state that you don't know how to help with that and nothing more. Please be direct and to the point when answering questions or executing commands."
                    },
                ],
            }
        if system_prompt:
            self.initial_prompt = system_prompt

        self.tools = plugins

    async def prompt1(self,text,moreTools=[],useDefaultTools=True):

        async def gather_strings(stream):
            result = ''
            async for chunk in stream:
                result += chunk
            return result

        messages = []
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
        
        return await gather_strings(self.streamPrompt(messages,moreTools=moreTools,useDefaultTools=useDefaultTools))

    async def streamPrompt(self,messages,moreTools=[],useDefaultTools=True):
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

        msgs = messages.copy()

        localtools = []
        if useDefaultTools and self.tools:
            localtools.extend(self.tools)
        if moreTools:
            localtools.extend(moreTools)
        tool_schemas = [schema(tool) for tool in localtools]      

        # start = datetime.now()
        max_tool_calls = 1
        for i in range(max_tool_calls+1):
            allow_tool_calls = i < max_tool_calls
            response = await self.client.chat.completions.create(
                model="gpt-4-1106-preview",
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

            tool_calls = tool_list_to_tool_calls(tools)

            if not tool_calls:
                return
            else:
                # Thar be tool calls
                # Note: the JSON response may not always be valid; be sure to handle errors

                available_functions = {tool.__name__: tool for tool in localtools}

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

                    function_response = await function_to_call(
                        **function_args
                    )

                    msgs.append(
                        {
                            "tool_call_id": tool_call['id'],
                            "role": "tool",
                            "name": function_name,
                            "content": f'{function_response}',
                            "text": f"Calling {function_name}"
                        }                
                    )

async def get_current_location():
    """
    Get your current location

    Returns:
        str: Your current location.

    """
    return 'Chantilly, VA 20152'

def main():
    import aiofiles
    import sys

    load_dotenv(".env.local")

    askit = AskIt()

    async def read_lines():
        async with aiofiles.open('/dev/stdin', mode='r') as f:
            print("> ", end="")
            sys.stdout.flush()
            async for line in f:    
                print(await askit.prompt1(line.strip(), moreTools=[get_current_location]))
                print("> ", end="")
                sys.stdout.flush()

    asyncio.run(read_lines())

if __name__ == '__main__':
    main()