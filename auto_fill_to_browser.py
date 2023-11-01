import function_caller
import json


def load_json_conversation(file_path) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


async def browse_by_json(playwright_instance, messages: dict):
    for index, message in enumerate(messages):
        try:
            if index+1 != len(messages):
                if messages[index+1]["role"] == "function" and "Unable" not in messages[index+1]["content"]:
                    await function_caller.call_function(browser=playwright_instance,
                                                        json_function=message["additional_kwargs"]["function_call"])
        except KeyError:
            pass


# async def main():
#     playwright_instance = await function_caller.get_browser()
#     messages = load_json_conversation("admin_login.json")
#
#     await browse_by_json(playwright_instance, messages)

