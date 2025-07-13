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

# Here is a very simple example of using the askit library to query an llm.

from dotenv import load_dotenv
from pathlib import Path

import asyncio

from askit import AskIt

async def main():
    load_dotenv(override=True,dotenv_path=Path.cwd() / ".env")

    async with AskIt() as askit:
        print(f'askit using model: {askit.model}')

        prompt = "What is 2 + 2?"
        print(f'Asking: {prompt}')
        # Send the prompt to the AskIt instance and get the response
        response = await askit.prompt(prompt)
        print(f'Response: {response}')

if __name__ == '__main__':
    asyncio.run(main())