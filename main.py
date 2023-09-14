import argparse
import asyncio
import sys
import openai
import json
import os
import logging
import shutil
from playwright import go_to_page, take_screenshot, params_to_pass
from test_specification.example import example_test

# Improve conversation managment.
# keep track of whole history. Done - we pass all messages to chatgpt
# Let GPT know about the result of function call. Done - we are testing with hardcoded status code and gpt reacts to it.
#                                                   We can add some if condition and gpt can try again or just print it.
# Start stop conversation
# adding context and system messages to conversation
# test how much we can send to the model (max 4k or 16k tokens for gpt 3.5)

# example taken from here https://platform.openai.com/docs/guides/gpt/function-calling

class GPT:

    def __init__(self):
        self.messages = []
        self.system_messages = ""
        self.functions = [
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
                        "path": {
                            "type": "string",
                            "description": "The path to save the screenshot"
                        },
                        "full_page": {
                            "type": "boolean",
                            "description": "Whether to take a screenshot of the full page or just the viewport"
                        }
                    },
                    "required": ["path"]
                }
            }
        ]

    async def run_conversation(self, step):
        self.messages.append({"role": "user", "content": step})
        print(f"user: {step}")
        # Step 1: send the conversation and available functions to GPT
        messages_gpt = self.get_messages_for_gpt()
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages_gpt,
            functions=self.functions,
            function_call="auto",  # auto is default, but we'll be explicit
        )
        response_message = response["choices"][0]["message"]

        tokens = response["usage"]
        logging.info(f"gpt context window: {messages_gpt}")
        logging.info(f"Tokens used so far (response): {tokens}\n")

        self.messages.append(response_message)
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
            # extend conversation with assistant's reply
            self.messages.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": function_response,
                }
            )
            messages_gpt = self.get_messages_for_gpt()
            second_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-0613",
                messages=messages_gpt,
            )  # get a new response from GPT where it can see the function response

            tokens = second_response["usage"]
            logging.info(f"gpt context window:  {messages_gpt}")
            logging.info(f"Tokens used so far (second response): {tokens}\n")

            self.messages.append(second_response["choices"][0]["message"])
            print(f"assistant: {second_response['choices'][0]['message']}")
            print(
                f"Generated playwright code: {json.loads(function_response)['cmd']}")
        else:
            print(f"assistant: {response_message}")
        

        # print("Messages:")
        # print(self.messages)
        # return self.messages

    async def generate_code(self, scenario, chat_mode=False):
        with open('tempfile', 'w') as f:
            f.write("import { test, expect } from '@playwright/test';\n\n")
            f.write(
                f"test('{'My example test name'}', async ({{ page }}) => {{\n")
        # append a system message to influence the AIs behaviour

        steps = scenario['steps'].splitlines()
        for step in steps:
            await self.run_conversation(step)
            if chat_mode is True:
                while True:
                    user_input = input("Press enter to continue with next step or press 'y' to add another prompt.")
                    if user_input.lower() not in ['y', '']:
                        print("Please enter 'y' or empty string")
                        continue
                    else:
                        if user_input == 'y':
                            new_step = input("Please enter new prompt: ")
                            await self.run_conversation(new_step)
                        elif user_input == '':
                            break

        with open('logfile', 'a') as f:
            f.write(json.dumps(self.messages, indent=4))
        # write footer
        with open('tempfile', 'a') as f:
            f.write("});\n\n")

        file_path = f"tests/{'example'}.spec.ts"
        shutil.move('tempfile', file_path)

        return file_path

    def get_messages_for_gpt(self):
        # add system and context messages to the conversation
        messages = [{"role": "system", "content": self.system_messages}, 
                    *self.messages]
                    # *self.messages[-5:]]
        return messages


if __name__ == "__main__":
    logging.basicConfig(filename='token_usage.log', encoding='utf-8', level=logging.INFO)
    open('token_usage.log', 'w').close()
    parser = argparse.ArgumentParser(description='Generate playwright typescript code from test specification')
    parser.add_argument(
        "-c", "--chat", help='Chat mode with agent. User can enter own real-time prompts', 
            dest='chat_mode', action="store_true")
    args = parser.parse_args()
    open('logfile', 'w').close()
    gpt = GPT()
    loop = asyncio.get_event_loop()
    test_file = loop.run_until_complete(gpt.generate_code(example_test, args.chat_mode))
    # print("Generated playwright typescript code: \n")
    # with open(test_file, 'r') as f:
    #     print(f.read())
