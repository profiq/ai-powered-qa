import argparse
import asyncio
import sys
import openai
import json
import os
import logging
import shutil
# from playwright_mine import expect_text, go_to_page, take_screenshot, params_to_pass
from test_specification.example import example_test
from langchain.tools import format_tool_to_openai_function

# Improve conversation managment.
# keep track of whole history. Done - we pass all messages to chatgpt
# Let GPT know about the result of function call. Done - we are testing with hardcoded status code and gpt reacts to it.
#                                                   We can add some if condition and gpt can try again or just print it.
# Start stop conversation
# adding context and system messages to conversation
# test how much we can send to the model (max 4k or 16k tokens for gpt 3.5)
# write a login pattern and let gpt decide what to do. Test it.
# Add a context and see if gpt can find if there is a text Seznam on the page. Test it.

# example taken from here https://platform.openai.com/docs/guides/gpt/function-calling

# truncate messages, do nejakeho maximalniho limitu
# moznosti pro vylepseni: aby sam navrhl loginy, convertor html, pridat do kontextu, co je pageobject, zkusit do 16k dat stranku a at vymysli jak se prihlasit
# nahled stranky do kontextu
# now working on adding tools to our agent
# how to define a tool: https://python.langchain.com/docs/modules/agents/tools/custom_tools
# now find how to use the tools in out agent
# Using official langchain, but added some changes from our fork
# make more phases,

from langchain.tools.playwright.utils import create_async_playwright_browser
from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.tools.playwright.click import ClickTool
from langchain.tools.playwright.click_by_text import ClickByTextTool
from langchain.tools.playwright.iframe_click import IframeClickTool
from langchain.tools.playwright.iframe_click_by_text import IframeClickByTextTool
from langchain.tools.playwright.iframe_expect_hidden import IframeExpectHiddenTool
from langchain.tools.playwright.iframe_upload import IframeUploadTool
from langchain.tools.playwright.current_page import CurrentWebPageTool
from langchain.tools.playwright.expect_test_id import ExpectTestIdTool
from langchain.tools.playwright.expect_text import ExpectTextTool
from langchain.tools.playwright.expect_title import ExpectTitleTool
from langchain.tools.playwright.extract_hyperlinks import ExtractHyperlinksTool
from langchain.tools.playwright.extract_text import ExtractTextTool
from langchain.tools.playwright.fill import FillTool
from langchain.tools.playwright.get_elements import GetElementsTool
from langchain.tools.playwright.navigate import NavigateTool
from langchain.tools.playwright.navigate_back import NavigateBackTool
from langchain.tools.playwright.take_screenshot import TakeScreenshotTool

available_functions = {
    "click_element": ClickTool,
    "click_by_text": ClickByTextTool,
    "iframe_click": IframeClickTool,
    "iframe_click_by_text": IframeClickByTextTool,
    "iframe_expect_hidden": IframeExpectHiddenTool,
    "iframe_upload": IframeUploadTool,
    "current_page": CurrentWebPageTool,
    "expect_test_id": ExpectTestIdTool,
    "expect_text": ExpectTextTool,
    "expect_title": ExpectTitleTool,
    "extract_hyperlinks": ExtractHyperlinksTool,
    "extract_text": ExtractTextTool,
    "fill_element": FillTool,
    "get_elements": GetElementsTool,
    "navigate_browser": NavigateTool,
    "navigate_back": NavigateBackTool,
    "take_screenshot": TakeScreenshotTool,
}


class GPT:

    def __init__(self, functions):
        self.messages = []
        self.system_messages = "You are helping me to automate UI testing. Find page content in other system messages and you can use it to answer my questions."
        self.functions = functions

    async def run_conversation(self, message):
        self.messages.append(message)
        print(message)
        # Step 1: send the conversation and available functions to GPT
        messages_gpt = self.get_messages_for_gpt()
        response = self.gpt_api_request(messages_gpt)
        response_message = response["choices"][0]["message"]
        tokens = response["usage"]
        logging.info(f"gpt context window: {messages_gpt}")
        logging.info(f"Tokens used so far (response): {tokens}\n")
        
        self.messages.append(response_message)
        self.write_log()
        return response_message
        

        # Step 2: check if GPT wanted to call a function
        if response_message.get("function_call"):
            # Step 3: call the function
            # Note: the JSON response may not always be valid; be sure to handle errors

            function_name = response_message["function_call"]["name"]
            function_to_call = available_functions[function_name]
            function_args = json.loads(
                response_message["function_call"]["arguments"])
            function_tool = function_to_call(async_browser=async_browser)
            function_response = await function_tool._arun(**function_args)

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
            # get a new response from GPT where it can see the function response
            second_response = self.gpt_api_request(messages_gpt)

            tokens = second_response["usage"]
            logging.info(f"gpt context window:  {messages_gpt}")
            logging.info(f"Tokens used so far (second response): {tokens}\n")

            self.messages.append(second_response["choices"][0]["message"])
            print(f"assistant: {second_response['choices'][0]['message']}")
            print(
                f"Tool response {function_response}")
        else:
            print(f"assistant: {response_message}")

    async def user_agent_loop(self):
        self.write_test_header()
        # append a system message to influence the AIs behaviour

        keep_agent_running = True

        while keep_agent_running:
            prompt_input = input("Please enter a prompt or type quit.\n")
            if prompt_input.lower() in ['']:
                continue
            elif prompt_input == 'quit':
                keep_agent_running = False
            else:
                function_call = True
                gpt_response = await self.run_conversation(self.construct_message(role="user", content=prompt_input))
                self.write_log()
                while function_call:
                    if gpt_response.get("function_call"):
                        # gpt wants to call a function, first validate with user
                        editing = True
                        while editing:                        
                            print(f"Assistant wants to call function: {gpt_response['function_call']['name'].strip()} \
                                with arguments: {gpt_response['function_call']['arguments'].strip()}")
                            edit_input = input("Call function (press enter) or edit function call (e)?\n")
                            if edit_input == 'e':
                                edited_response = gpt_response
                                edited_function_call = input("Enter function call:\n")
                                # TODO editing not supported yet
                                if edited_function_call == '':
                                    edited_function_call = gpt_response['function_call']['name']
                                # edited_function_arguments = input("Enter function arguments:\n")
                                self.get_available_arguments()
                                if edited_function_arguments == '':
                                    edited_function_arguments = gpt_response['function_call']['arguments']

                                if not self.validate_function_call(edited_function_call, edited_function_arguments):
                                    print("Function call is not valid. Please try again.")
                                    continue
                                gpt_response['function_call']['name'] = edited_function_call
                                gpt_response['function_call']['arguments'] = edited_function_arguments
                            elif edit_input == '':
                                editing = False
                                break
                            elif edit_input == 'quit':
                                editing = False
                                function_call = False
                                keep_agent_running = False
                                break
                            elif edit_input == 'p':
                                editing = False
                                function_call = False
                                break
                            else:
                                print("Please enter e or press enter.")
                        # call the function
                        function_name = gpt_response["function_call"]["name"]
                        function_to_call = available_functions[function_name]
                        function_args = json.loads(
                            gpt_response["function_call"]["arguments"])
                        function_tool = function_to_call(async_browser=async_browser)
                        function_response = await function_tool._arun(**function_args)
                        
                        gpt_response = await self.run_conversation(self.construct_message(role="function", name=function_name, content=function_response))
                        self.write_log()
                    else:
                        # no function call, print response and ask for new prompt
                        print(gpt_response)
                        function_call = False

        # write footer
        with open('tempfile', 'a') as f:
            f.write("});\n\n")

        file_path = f"tests/{'example'}.spec.ts"
        shutil.move('tempfile', file_path)

        return file_path

    def get_messages_for_gpt(self):
        # add system and context messages to the conversation
        messages = [{"role": "system", "content": self.system_messages}, {"role": "system", "content": "This is the \
                                                                          page content. text: ['Seznam', 'ball']"},
                    *self.messages[-10:]]
        return messages

    def gpt_api_request(self, messages_gpt):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages_gpt,
            functions=self.functions,
            function_call="auto",  # auto is default, but we'll be explicit
            temperature=0
        )
        return response

    def validate_function_call(self, function_call_name, function_call_arguments):
        if function_call_name not in available_functions:
            return False
        return True
    
    def construct_message(self, **kwargs):
        return { k: v for k,v in kwargs.items()}
        
    def write_log(self):
        with open('logfile', 'w') as f:
            f.write(json.dumps(self.messages, indent=4))
    
    def get_available_arguments(self, function_call):
        for function in self.functions:
            if function['name'] == function_call:
                return function['parameters']['properties']
        else:
            return None
    
    def write_test_header(self):
        with open('tempfile', 'w') as f:
            f.write("import { test, expect } from '@playwright/test';\n\n")
            f.write(
                f"test('{'My example test name'}', async ({{ page }}) => {{\n")

if __name__ == "__main__":
    logging.basicConfig(filename='token_usage.log',
                        encoding='utf-8', level=logging.INFO)
    open('token_usage.log', 'w').close()
    parser = argparse.ArgumentParser(
        description='Generate playwright typescript code from test specification')
    parser.add_argument(
        "-c", "--chat", help='Chat mode with agent. User can enter own real-time prompts',
        dest='chat_mode', action="store_true")
    args = parser.parse_args()
    open('logfile', 'w').close()

   # Initialize the playwright toolkit / tools
    async_browser = create_async_playwright_browser(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(
        async_browser=async_browser)
    tools = toolkit.get_tools()
    functions = [format_tool_to_openai_function(t) for t in tools]
    # print(functions[2]['parameters']['properties'])
    gpt = GPT(functions=functions)
    loop = asyncio.get_event_loop()
    test_file = loop.run_until_complete(
        gpt.user_agent_loop())
    print("Generated playwright typescript code: \n")
    with open(test_file, 'r') as f:
        print(f.read())

    # Why is there previous_webpage function? What does it mean???
