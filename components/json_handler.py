import datetime
import json
import os

from components.function_caller import call_function


def save_conversation_history(project_name: str, test_case: str, messages: list):
    path = f"conversation_history/{project_name}/{test_case}"
    start_time = datetime.datetime.now().strftime("%Y_%m_%d-%H:%M:%S")
    file_path = os.path.join(path, f"{test_case}_history_{start_time}.json")

    if not os.path.exists(path):
        os.makedirs(path)

    with open(file_path, "w") as f:
        f.write(json.dumps(messages, indent=4))


def load_conversation_history(json_file):
    try:
        with open(json_file, "r") as file:
            return json.load(file)
    except:
        return []


def get_user_message(st):
    return (
        {"choices": [
            {"message": {
                "content": st.session_state.user_message_content,
                "role": "user",
            }}
        ]}
    )


# def get_assistant_message(st):
#     return (
#         {
#             "role": "assistant",
#             "content": st.session_state.ai_message_content,
#             "additional_kwargs": {
#                 "function_call": {
#                     "name": st.session_state.ai_message_function_name,
#                     "arguments": st.session_state.ai_message_function_arguments,
#                 }
#             }
#             if st.session_state.ai_message_function_name
#             else {},
#         }
#     )


async def get_function_message(st, response):
    function_response = await call_function(browser=st.session_state.browser, json_function=response["choices"][0]["message"]["function_call"])
    return (
        {"choices": [
            {"message": {
                "content": function_response,
                "role": "function",
                "name": st.session_state.ai_message_function_name,
            }}
        ]}
    )
