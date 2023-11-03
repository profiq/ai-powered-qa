from components.function_caller import call_function


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
    return (
        {
            "role": "function",
            "name": st.session_state.ai_message_function_name,
            "content": await call_function(browser=st.session_state.browser, json_function=response),
        }
    )

