import streamlit as st
from dotenv import load_dotenv
from components.agent import Agent
from components.constants import function_call_defaults, llm_models

load_dotenv()


@st.cache_resource
def setup_llm():
    return Agent()


llm = setup_llm()


def on_submit():
    llm.append_message(
        {
            "role": "user",
            "content": st.session_state.user_prompt_content,
        }
    )
    st.session_state.user_prompt_content = ""

    llm.append_message(
        {
            "role": "assistant",
            "content": st.session_state.completion_content,
        }
    )
    st.session_state.completion_content = ""


@st.cache_data
def get_function_call_options(functions):
    options = function_call_defaults
    if functions:
        options.extend([func["name"] for func in functions])

    return options


def main():
    # System message
    with st.chat_message("system"):
        llm.system_message = st.text_area(
            label="System message",
            value=llm.system_message,
            label_visibility="collapsed",
        )

    # Write conversation history
    for key, message in enumerate(llm.conversation_history):
        if message["role"] == "function":
            with st.chat_message("function"):
                st.write(f"**{message['name']}**")
                st.write(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message("assistant"):
                if message["content"]:
                    message["content"] = st.text_area(
                        label="Assistant Message",
                        label_visibility="collapsed",
                        value=message["content"],
                        key=f"message_{key}_content",
                    )
                function_call = message.get("function_call", None)
                if function_call:
                    with st.status(function_call["name"], state="complete"):
                        st.text_area(
                            label="function_call",
                            value=function_call["arguments"],
                            label_visibility="collapsed",
                            key=f"message_{key}_function_call",
                        )
        elif message["role"] == "user":
            with st.chat_message("user"):
                message["content"] = st.text_area(
                    label="User Message",
                    label_visibility="collapsed",
                    value=message["content"],
                    key=f"message_{key}_content",
                )

    # Check last message
    last_message = llm.conversation_history[-1] if llm.conversation_history else None

    user_prompt = None
    # User message
    if last_message is None or last_message["role"] == "assistant":
        with st.chat_message("user"):
            user_prompt_content = st.text_area(
                "User prompt content",
                key="user_prompt_content",
                label_visibility="collapsed",
            )
            if user_prompt_content:
                user_prompt = {
                    "role": "user",
                    "content": user_prompt_content,
                }
            else:
                st.stop()

    # # Context message
    # context_message = "Here's your context:"
    # with st.chat_message("system"):
    #     context_message = st.text_area(label="Context message", value=context_message)

    functions = None

    # Completions params
    col1, col2 = st.columns(2)
    with col1:
        function_call_option = st.selectbox(
            "Force function call?",
            get_function_call_options(functions),
            help="'auto' leaves the decision to the model,"
            " 'none' forces a generated message, or choose a specific function.",
            index=0,
            key="function_call_option",
        )
    with col2:
        model = st.selectbox(
            "Change model?",
            llm_models,
            help="Change the llm. Be aware that gpt-4 is more expensive.",
            index=0,
            key="model",
        )
    # Call LLM
    try:
        response = llm.get_completion(
            user_prompt=user_prompt,
            model=model,
            function_call_option=function_call_option,
        )

        completion_content = response.get("content", "")

        # AI message
        with st.chat_message("assistant"):
            with st.form("completion"):
                st.text_area(
                    "Content",
                    value=completion_content,
                    key="completion_content",
                )

                function_call = response.get("function_call", None)
                if function_call:
                    st.text_input(
                        "Function call",
                        key="completion_function_name",
                    )
                    st.text_area(
                        "Arguments",
                        key="completion_function_arguments",
                    )
                st.form_submit_button(
                    "Commit agent completion",
                    on_click=on_submit,
                )

    except Exception as e:
        st.write(e)


if __name__ == "__main__":
    main()
