import asyncio
import sys
import openai
import json
import os
import shutil
from playwright import go_to_page, take_screenshot, params_to_pass
from test_specification.example import example_test


async def run_conversation(content):
    # Step 1: send the conversation and available functions to GPT
    messages = [
        {"role": "user", "content": content}]

    functions = [
        {
            "name": "go_to_page",
            "description": "Go to a page in the browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to navigate to"}
                }
            },
            "required": ["url"],
        },
        {
            "name": "take_screenshot",
            "description": "Take screenshot of the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to save the screenshot"},
                    "full_page": {"type": "boolean", "description": "Whether to take a screenshot of the full page or just the viewport"}
                }
            },
            "required": ["path"],
        },
    ]
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0613",
        messages=messages,
        functions=functions,
        function_call="auto",  # auto is default, but we'll be explicit
    )
    response_message = response["choices"][0]["message"]
    messages.append(response_message)
    # Step 2: check if GPT wanted to call a function
    if response_message.get("function_call"):
        # Step 3: call the function
        # Note: the JSON response may not always be valid; be sure to handle errors
        available_functions = {
            "go_to_page": go_to_page,
            "take_screenshot": take_screenshot,
        }
        function_name = response_message["function_call"]["name"]
        fuction_to_call = available_functions[function_name]
        function_args = json.loads(
            response_message["function_call"]["arguments"])
        function_response = fuction_to_call(
            **{key: function_args.get(key) for key in params_to_pass[function_name]})

        # Step 4: send the info on the function call and function response to GPT
        # extend conversation with assistant's reply, optional for us
        messages.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        )
    print(messages)
    return messages


async def generate_code(scenario):
    with open('tempfile', 'w') as f:
        f.write("import { test, expect } from '@playwright/test';\n\n")
        f.write(f"test('{'My example test name'}', async ({{ page }}) => {{\n")

    steps = str(scenario['steps']).split("\\n")
    for step in steps:
        await run_conversation(step)

    # write footer
    with open('tempfile', 'a') as f:
        f.write("});\n\n")

    file_path = f"tests/{'example'}.spec.ts"
    shutil.move('tempfile', file_path)

    return file_path


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    test_file = loop.run_until_complete(generate_code(example_test))
    print("Generated playwright typescript code: \n")
    with open(test_file, 'r') as f:
        print(f.read())
