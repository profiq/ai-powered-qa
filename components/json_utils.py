import datetime
import json
import os

from components.function_caller import call_function


def save_conversation_history(project_name: str, test_case: str, messages: list, autosave: bool = False):
    path = f"conversation_history/{project_name}/{test_case}"
    appendix = "autosave" if autosave else datetime.datetime.now().strftime("%Y_%m_%d-%H:%M:%S")
    file_path = os.path.join(path, f"{test_case}_history_{appendix}.json")

    if not os.path.exists(path):
        os.makedirs(path)

    with open(file_path, "w") as f:
        f.write(json.dumps(messages, indent=4))


def load_conversation_history(file_path):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def get_user_message(st):
    return (
        {
            "role": "user",
            "content": st.session_state.user_message_content,
        }
    )


def get_assistant_message(st):
    return (
        {
            "role": "assistant",
            "content": st.session_state.ai_message_content,
            "additional_kwargs": {
                "function_call": {
                    "name": st.session_state.ai_message_function_name,
                    "arguments": st.session_state.ai_message_function_arguments,
                }
            }
            if st.session_state.ai_message_function_name
            else {},
        }
    )


async def get_function_message(st, response):
    function_response = await call_function(browser=st.session_state.browser, json_function=response)
    return (
        {
            "role": "function",
            "name": st.session_state.ai_message_function_name,
            "content": function_response,
        }
    )


async def browse_by_json(playwright_instance, messages: dict):
    """Example:
       playwright_instance = await function_caller.get_browser()
       messages = load_json_conversation("admin_login.json")
       await browse_by_json(playwright_instance, messages)
     """
    for index, message in enumerate(messages):
        try:
            if index+1 != len(messages):
                if messages[index+1]["role"] == "function" and "Unable" not in messages[index+1]["content"]:
                    await call_function(browser=playwright_instance,
                                        json_function=message["additional_kwargs"]["function_call"])
        except KeyError:
            pass
