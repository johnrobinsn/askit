# Non-streaming variant for reference.

``` python
    async def prompt(self,messages):
        msgs = messages.copy()
        tool_schemas = [schema(tool) for tool in self.tools]      

        max_tool_calls = 1
        for i in range(max_tool_calls+1):
            allow_tool_calls = i < max_tool_calls
            response = await self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=msgs,
                tools=tool_schemas if allow_tool_calls else None,
                stream=False,
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            if not tool_calls:
                return response_message.content

            # Thar be tool calls
            # Step 3: call the function
            # Note: the JSON response may not always be valid; be sure to handle errors
            available_functions = plugin_dict

            print('toolcall?:',response_message)
            msgs.append({
                "role": "assistant",
                "tool_calls": [{
                    "id": tool_call.id, 
                    "function": {
                        "name": tool_call.function.name, 
                        "arguments": tool_call.function.arguments
                    },
                    "type": "function"
                } for tool_call in tool_calls]
            })
            print('msgs:', msgs)

            # msgs.append(response_message)
            # Step 4: send the info for each function call and function response to the model
            for tool_call in tool_calls:
                # print("Calling tools")
                # function_id = tool_call.function.id
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
```

## Original

``` python
    # async def prompt(self,messages):
    #     msgs = messages.copy()
    #     tool_schemas = [schema(tool) for tool in self.tools]      

    #     start = datetime.now()
    #     response = await self.client.chat.completions.create(
    #         model="gpt-4-1106-preview",
    #         messages=msgs,
    #         tools=tool_schemas,
    #     )
    #     log.debug('Time for LLM Response: %d', (datetime.now()-start).total_seconds())

    #     response_message = response.choices[0].message
    #     tool_calls = response_message.tool_calls
    #     if tool_calls:
    #         # Step 3: call the function
    #         # Note: the JSON response may not always be valid; be sure to handle errors
    #         available_functions = plugin_dict

    #         # available_functions = {
    #         #     "get_current_weather": get_current_weather,
    #         #     "get_current_time": get_current_time,
    #         # }  # only one function in this example, but you can have multiple
    #         #messages.append(response_message)  # extend conversation with assistant's reply
    #         # print('xx:', response_message)
    #         # print('yy:', response_message.__dict__)
    #         #await appendMessage(response_message)
    #         print('toolcall?:',response_message)
    #         msgs.append(response_message)
    #         # Step 4: send the info for each function call and function response to the model
    #         for tool_call in tool_calls:
    #             # print("Calling tools")
    #             function_name = tool_call.function.name
    #             function_to_call = available_functions[function_name]
    #             # print('function to call:', function_to_call)
    #             function_args = json.loads(tool_call.function.arguments)
    #             function_response = await function_to_call(
    #                 # location=function_args.get("location"),
    #                 # unit=function_args.get("unit"),
    #                 **function_args
    #             )
    #             # if function_response:
    #             msgs.append(
    #                 {
    #                     "tool_call_id": tool_call.id,
    #                     "role": "tool",
    #                     "name": function_name,
    #                     "content": f'{function_response}',
    #                     "text": f"Calling {function_name}"
    #                 }                
    #             )
    #         start = datetime.now()
    #         # TODO better model?
    #         response = await self.client.chat.completions.create(
    #             model="gpt-4-1106-preview",
    #             messages=msgs,
    #         )  # get a new response from the model where it can see the function response
    #         # print('second call response:', response)
    #         log.debug('Time for llm tool processing: %d', (datetime.now()-start).total_seconds())
    #         response_message = response.choices[0].message
    #     # await self.appendMessage({
    #     #     "role": "assistant",
    #     #     "content": [
    #     #         {
    #     #             "type": "text",
    #     #             "text": response_message.content
    #     #         },
    #     #     ],
    #     # })
    #     return response_message.content
```


```
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

    # async def test(prompt):
    #     print(prompt)
    #     print(await askit.prompt1(prompt))

    # async def test(prompt):
    #     # print(prompt)
    #     print(await askit.prompt2(prompt))

```


## Links
https://platform.openai.com/docs/guides/function-calling
https://community.openai.com/t/help-for-function-calls-with-streaming/627170/2