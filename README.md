

# AskIt MCP
AskIt is a flexible asyncio Python library and CLI tool that allows various LLM models to extend their abilities by invoking services from [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) servers and call locally-defined Python functions.

## Features
* Simple and Lightweight
* Connect to multiple MCP servers simultaneously
* Support for Tool Use/Function Calling with MCP Servers Written in any Language
* Support for Tool Use/Function Calling with Locally-Defined Python Functions
* Supports Multiple LLM Providers
    * OpenAI and XAI (Grok) Currently Supported
    * Anthropic, Ollama, and LMStudio Support __coming soon__
* Optional Support for Streaming LLM Responses
* Securely Store API Keys in Environment Variables

## Installation
To get started with AskIt MCP, you need to have Python 3.11+ installed on your system. A python version manager is recommended. You can then install the package using pip:

```bash
pip install git+https://github.com/johnrobinsn/askit.git
```

## Getting Started with the AskIt CLI
The easiest way to get started with AskIt is to use its integrated command-line interface (CLI) tool. The CLI allows you to interact with MCP servers and LLMs using natural language queries, making it easy to access and manipulate data from various sources.

The following command will leverage the default OpenAI model (gpt-4o-mini) to enter into a "chat-eval" loop with the configured LLM. You can specify a different model or provider using command-line options.

You just need to provide your OpenAI API key as a command line argument.

eg.
``` bash
python -m askit --api_key="your_openai_api_key_here"
```

You can also provide the key as a provider specific environment variable.

```bash
OPENAI_API_KEY="your_openai_api_key_here" python -m askit
```

Here is an eample using the XAI provider (Grok) with a specific model. You will need to provide your XAI API key as an environment variable or command line argument.

```bash
python -m askit --model="grok-2-latest" --provider="XAI" --api_key="your_xai_api_key_here"
```

Find out more about [Provider Specific Environment Variables](#environment-variables).

## Connect MCP Servers to Askit
You can connect to multiple MCP servers by creating a `mcp_config.json` file in your current working directory. This file should contain the configuration for the MCP servers you want to connect to. The AskIt CLI will automatically load this configuration and connect to the specified MCP servers.

```json
{
    "mcpServers": {
      "example-stdio": {
        "command" : "node",
        "cwd" : "/mnt2/code/mcpcalc",
        "args": [
          "mcpcalc.mjs"
        ],
        "env": {
          "debug_log": "false"
        }
      },
      "example-streamable-http": {
        "transport" : "http",
        "url" : "http://127.0.0.1:8000/mcp",
        "disabled" : false
      }            
    }
}
```
You can add as many MCP servers as you need and the client will connect to all of them and make their tools available to the configured LLM. There are two primary types of MCP servers supported by AskIt STDIO and Streamable HTTP. The former is used for MCP servers that are located on your local machine, while the latter can be used to access MCP servers that are hosted remotely.

There are alot of third-party MCP servers available. You can find a good list of them in the [Model Context Protocol Servers](https://github.com/modelcontextprotocol/servers) repo or in the [Awesome MCP Servers](https://github.com/punkpeye/awesome-mcp-servers) repo.

Once you've setup some MCP servers and have them running, you can start the AskIt CLI and it will automatically connect to the configured MCP servers.  You can then launch the CLI as you did in the previous section but your LLM will now be able to interact with the configured MCP servers.

eg.
``` bash
python -m askit --api_key="your_openai_api_key_here"
```

## Configuration
Rather than passing command line arguments into the CLI you can configure environment variables to control the behavior of AskIt.  The AskIT CLI also looks for a standard .env file in the current working directory to set and overide these environment variables. The following environment variables are supported:
```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
# OPENAI_BASE_URL=https://api.openai.com/v1  # Uncomment and modify if using a custom base url
```

## Configuring MCP Servers
You can configure the MCP servers that AskIt will connect to by creating a `mcp_config.json` file in your current working directory. This file should contain a JSON object with the following structure:

```json
{
    "mcpServers": {
      "weather": {
        "url": "http://localhost:8088/sse"
      },
      "home-assistant": {
        "command" : "node",
        "cwd" : "/home/jr/code/mcpcalc",
        "args": [
          "home2.mjs"
        ],
        "env": {
          "debug_log": "false"
        }
      }      
    }
}
```

Once you have created this file, the AskIt CLI will automatically load the configuration and connect to the specified MCP servers. You can also specify a different configuration file using the `--config` command-line argument.

As a reference, a sample 'mcp_config.json.example' file is provided in the root of the repository. You can copy this file to 'mcp_config.json' and modify it to suit your needs.

## Getting started with the API
You can also use AskIt as a Python library in your own applications. Here is a simple example of how to use it programmatically:

```python
import asyncio
from askit import AskIt

async def main():
    # assume OPENAI_API_KEY is set in your environment variables
    # or you can pass it as an argument to the AskIt constructor

    async with AskIt() as askit:
        response = await askit.prompt("Who is Neil Armstrong?")
        print(f'Response: {response}')

asyncio.run(main())
```

## MCP Servers and the API
You can also connect to MCP servers using the AskIt API. Just add a call to `await askit.load_mcp_config()` as shown in the example below. This will load the MCP servers from the `mcp_config.json` file in your current working directory and make their tools available to the configured LLM.

```python
import asyncio
from askit import AskIt

async def main():
    # assume OPENAI_API_KEY is set in your environment variables
    # or you can pass it as an argument to the AskIt constructor

    async with AskIt() as askit:
        await askit.load_mcp_config("path/to/your/mcp_config.json")
        response = await askit.prompt("Who is Neil Armstrong?")
        print(f'Response: {response}')

asyncio.run(main())

```

## Function Calling with the API
With AskIt, It's easy to give your LLM access to custom functions that you write.  Just define your functions in python as shown below and pass them in using the tools argument to the prompt method.  The LLM will then be able to call your functions as needed.  In this quick example, we define a function that returns the current time and makes it available to the configured LLM.  The LLM can then call this function to get the current time.  You can pass in any number of functions, and the LLM will be able to call them as needed.

```python
from datetime import datetime
import asyncio
from askit import AskIt

async def main():
    async with AskIt() as askit:
        # Define a custom function
        async def get_current_time():
            """
            Get the current date and time

            Returns:
                str: The current time in YYYY-MM-DD HH:MM:SS format

            """
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Send the prompt to the AskIt instance, providing the 
        # get_current_time function as a tool.
        response = await askit.prompt("What time is it?", tools=[get_current_time])
        print(f'Response: {response}')

asyncio.run(main())
```

## Additional Examples
You can find additional API example in the root directory of this repository matching the pattern `example_*.py`. These examples demonstrate a variety of other use cases.

## Environment Variables
AskIt MCP uses environment variables to securely store API keys and configuration settings. You can use a standard `.env` file in your current working directory to set these environment variables. The AskIt CLI will automatically load the environment variables from this file.  As a reference a file called `.env.example` is provided in the root of the repository. You can copy this file to `.env` and modify it to suit your needs.

### Common Environment Variables
ASKIT_SYSTEM_PROMPT - Optionally configure a default system prompt for AskIt

ASKIT_PROVIDER - Optionally configure a default provider for AskIt ["OPENAI", "XAI"], defaults to "OPENAI"

### Provider Specific Environment Variables
OPENAI_API_KEY - Specify your_openai_api_key_here for the OpenAI provider

OPENAI_BASE_URL - Optionally configure a different base URL for the OpenAI provider

OPENAI_MODEL - Optionally configure a different model for the OpenAI provider, defaults to "gpt-4o-mini"

XAI_API_KEY - Specify your_xai_api_key_here for the XAI provider

XAI_BASE_URL - Optionally configure a different base URL for the XAI provider

XAI_MODEL - Optionally configure a different model for the XAI provider, defaults to "grok-3-latest"

## Requirements
- Python 3.11+
- OpenAI API key (or other supported provider API keys)

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
Apache License 2.0
