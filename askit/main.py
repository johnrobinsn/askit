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

import asyncio
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

from datetime import datetime
# import json
import os
# import copy

from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.getLogger("httpx").setLevel(logging.CRITICAL)

from pydantic import create_model
import inspect, json
from inspect import Parameter

import importlib


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

# print('schema:', json.dumps(schema(get_current_weather), indent=4))
# def main():

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

print('plugins: ', plugins)

plugin_dict = {plugin.__name__: plugin for plugin in plugins}

class AskIt():
    def __init__(self,prompt=None):
        # super().__init__()
        openai_api_key = os.getenv('OPENAI_API_KEY')
        # print('openai_api_key:', openai_api_key)        
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
        if prompt:
            self.initial_prompt = prompt

        self.tools = plugins

    async def prompt1(self,text):
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
        return await self.prompt(messages)

    async def prompt(self,messages):
        msgs = messages.copy()
        tool_schemas = [schema(tool) for tool in self.tools]      

        start = datetime.now()
        response = await self.client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=msgs,
            tools=tool_schemas,
        )
        log.debug('Time for LLM Response: %d', (datetime.now()-start).total_seconds())

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        if tool_calls:
            # Step 3: call the function
            # Note: the JSON response may not always be valid; be sure to handle errors
            available_functions = plugin_dict

            # available_functions = {
            #     "get_current_weather": get_current_weather,
            #     "get_current_time": get_current_time,
            # }  # only one function in this example, but you can have multiple
            #messages.append(response_message)  # extend conversation with assistant's reply
            # print('xx:', response_message)
            # print('yy:', response_message.__dict__)
            #await appendMessage(response_message)
            msgs.append(response_message)
            # Step 4: send the info for each function call and function response to the model
            for tool_call in tool_calls:
                # print("Calling tools")
                function_name = tool_call.function.name
                function_to_call = available_functions[function_name]
                # print('function to call:', function_to_call)
                function_args = json.loads(tool_call.function.arguments)
                function_response = await function_to_call(
                    # location=function_args.get("location"),
                    # unit=function_args.get("unit"),
                    **function_args
                )
                # if function_response:
                msgs.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": f'{function_response}',
                        "text": f"Calling {function_name}"
                    }                
                )
            start = datetime.now()
            # TODO better model?
            response = await self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=msgs,
            )  # get a new response from the model where it can see the function response
            # print('second call response:', response)
            log.debug('Time for llm tool processing: %d', (datetime.now()-start).total_seconds())
            response_message = response.choices[0].message
        # await self.appendMessage({
        #     "role": "assistant",
        #     "content": [
        #         {
        #             "type": "text",
        #             "text": response_message.content
        #         },
        #     ],
        # })
        return response_message.content

def main():
    load_dotenv(".env.local")

    # askit = AskIt([get_current_weather,get_current_time])
    askit = AskIt()

    # async def test(prompt):
    #     print(prompt)    
    #     print(await askit.prompt(prompt))

    # async def tests():
        # await test("What is the weather in Tokyo?")
        # await test("What is the weather in San Francisco?")
        # await test("What is the time?")
        # await test("Tesla stock price")
        # await test("$NVDA")
        # await test("Get the webpage at this URL: https://www.allrecipes.com/recipe/139183/scrumptious-sauerkraut-balls/")
        # await test("Search the web for Elon Musk.")
        # await test("How old is Elon Musk?")

    # asyncio.run(tests())

    import aiofiles

    # if __name__ == '__main__':
    #     load_dotenv(".env.local")

    #     askit = AskIt(plugins)

    async def test(prompt):
        print(prompt)
        print(await askit.prompt1(prompt))

    async def read_lines():
        async with aiofiles.open('/dev/stdin', mode='r') as f:
            async for line in f:
                await test(line.strip())

    asyncio.run(read_lines())

if __name__ == '__main__':
    main()