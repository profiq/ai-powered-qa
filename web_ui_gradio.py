import gradio as gr
import json
import numpy as np
from io import BytesIO
from PIL import Image
from uuid import uuid4
import random


from openai.types.chat.chat_completion_message import ChatCompletionMessageToolCall

from ai_powered_qa.components.agent import AVAILABLE_MODELS
from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.components.utils import generate_short_id
from ai_powered_qa.custom_plugins.playwright_plugin.base import PlaywrightPlugin
from ai_powered_qa.custom_plugins.playwright_plugin.html_paging import (
    PlaywrightPluginHtmlPaging,
)
from ai_powered_qa.custom_plugins.playwright_plugin.only_visible import (
    PlaywrightPluginOnlyVisible,
)
from ai_powered_qa.custom_plugins.playwright_plugin.only_keyboard import (
    PlaywrightPluginOnlyKeyboard,
)


NAME_TO_PLUGIN_CLASS = {
    "PlaywrightPlugin": PlaywrightPlugin,
    "PlaywrightPluginHtmlPaging": PlaywrightPluginHtmlPaging,
    "PlaywrightPluginOnlyVisible": PlaywrightPluginOnlyVisible,
    "PlaywrightPluginOnlyKeyboard": PlaywrightPluginOnlyKeyboard,
}

agent_store = AgentStore(
    "agents",
    name_to_plugin_class=NAME_TO_PLUGIN_CLASS,
)

DEFAULT_AGENT_KWARGS = {
    "plugins": {
        "PlaywrightPluginOnlyKeyboard": NAME_TO_PLUGIN_CLASS[
            "PlaywrightPluginOnlyKeyboard"
        ]()
    },
}

DEFAULT_AGENT_NAME = "only_keyboard"

# MARK: UI
with gr.Blocks() as demo:
    gr_agent_state = gr.State()
    gr_langsmith_run_id = gr.State()
    gr_langsmith_session_id = gr.State(str(uuid4()))
    gr_interaction_state = gr.State()
    gr_editing_tool_index = gr.State()
    with gr.Accordion("Agent Config", open=False):
        # Loading agent
        with gr.Group():
            gr_agent_name = gr.Textbox(label="Agent name", value=DEFAULT_AGENT_NAME)
            gr_load_agent_btn = gr.Button("Load Agent")
        # Agent config
        gr_agent_config_label = gr.Markdown("# Agent Config", visible=False)
        with gr.Group(visible=False) as gr_agent_config:
            gr_system_message = gr.Textbox(label="System Message")
            gr_default_model = gr.Dropdown(
                label="Model", choices=AVAILABLE_MODELS, interactive=True
            )
            gr_update_agent_btn = gr.Button("Update Agent")
    with gr.Accordion("Load History", open=False):
        # Loading history
        with gr.Group():
            gr_history_name = gr.Textbox(label="History name")
            gr_new_history_btn = gr.Button("New History")
    with gr.Accordion("Interaction", open=False) as gr_interaction_tab:
        # Interaction config
        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                gr_browser = gr.Image(height=500)
            with gr.Column(scale=1):
                gr_messages = gr.Chatbot(height=500)
        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                gr_user_message = gr.Textbox(label="User Message")
            with gr.Column(scale=1):
                gr_tool_choice = gr.Dropdown(
                    label="Tool Choice", choices=["auto", "none"], value="auto"
                )
        gr_regenerate_interaction_btn = gr.Button("Regenerate Interaction")
        # Agent response
        with gr.Column():
            gr_agent_response_content = gr.Textbox(
                label="Agent Response Content", interactive=True
            )
        # Tool Calls
        gr_tool_uis = []
        for _ in range(10):
            with gr.Row(variant="compact", visible=False) as gr_tool_ui:
                gr_tool_uis.append(
                    (
                        gr_tool_ui,
                        gr.Markdown("# Tool UI", visible=False),
                        gr.Button("Edit", visible=False),
                        gr.Button("Delete", visible=False),
                    )
                )

        gr_commit_interaction_btn = gr.Button("Commit Interaction")

        # Tool call add/edit form
        with gr.Accordion("Add Tool Call", open=False) as gr_tool_call_form:
            gr_tool_call_type = gr.Dropdown(
                label="Tool call type",
                choices=["press_key", "input_text", "navigate_to_url"],
                value="press_key",
            )
            # Fields for press_key
            gr_press_key_key = gr.Textbox(label="Key", interactive=True)
            gr_press_key_count = gr.Number(label="Count", value=1, interactive=True)
            # Fields for input_text
            gr_input_text_text = gr.Textbox(
                label="Text", visible=False, interactive=True
            )
            # Fields for navigate_to_url
            gr_navigate_to_url_url = gr.Textbox(
                label="URL", visible=False, interactive=True
            )

            gr_tool_call_submit = gr.Button("Add Tool Call")

    # MARK: UI helpers
    def update_tool_call_uis(interaction, gr_tool_uis):
        interaction_tool_calls = {}
        for index, (gr_row, gr_markdown, gr_edit, gr_delete) in enumerate(gr_tool_uis):
            if interaction.agent_response.tool_calls and index < len(
                interaction.agent_response.tool_calls
            ):
                tool_call = interaction.agent_response.tool_calls[index]
                interaction_tool_calls[gr_row] = gr.Row(visible=True)
                interaction_tool_calls[gr_edit] = gr.Button(visible=True)
                interaction_tool_calls[gr_delete] = gr.Button(visible=True)
                interaction_tool_calls[gr_markdown] = gr.Markdown(
                    f"### {tool_call.function.name}: \n```json\n{tool_call.function.arguments}\n```",
                    visible=True,
                )
            else:
                interaction_tool_calls[gr_row] = gr.Row(visible=False)
                interaction_tool_calls[gr_edit] = gr.Button(visible=False)
                interaction_tool_calls[gr_delete] = gr.Button(visible=False)
                interaction_tool_calls[gr_markdown] = gr.Markdown(visible=False)
        return interaction_tool_calls

    # MARK: Event listeners
    #
    #
    #
    #
    # MARK: regenerate_interaction
    @gr.on(
        triggers=[gr_regenerate_interaction_btn.click],
        inputs=[
            gr_agent_state,
            gr_user_message,
            gr_tool_choice,
            gr_langsmith_session_id,
        ],
        outputs=[
            gr_interaction_state,
            gr_agent_response_content,
            gr_browser,
            gr_messages,
            gr_tool_choice,
            gr_langsmith_run_id,
        ]
        + [item for tpl in gr_tool_uis for item in tpl],
    )
    def regenerate_interaction(agent, user_message, tool_choice, session_id):
        if agent is None:
            return {}

        run_id = uuid4()

        interaction = agent.generate_interaction(
            user_prompt=user_message,
            tool_choice=tool_choice,
            langsmith_extra={
                "run_id": run_id,
                "metadata": {
                    "agent": agent.model_dump(exclude_unset=True),
                    "session_id": session_id,
                },
            },
        )

        # Update browser view
        playwright_plugin_name = next(
            key for key in agent.plugins.keys() if key.startswith("PlaywrightPlugin")
        )
        playwright_plugin = agent.plugins.get(playwright_plugin_name)
        buffer = playwright_plugin.buffer
        image = Image.open(BytesIO(buffer))
        image_array = np.array(image)

        # Update history
        interaction_messages = []
        for message in interaction.request_params["messages"]:
            message_text = f"{message['content']}\n" if message["content"] else ""
            if "tool_calls" in message:
                message_text += "\n\nTool Calls:\n"
                for tool_call in message["tool_calls"]:
                    message_text += f"{tool_call['function']['name']}: {tool_call['function']['arguments']}\n"
            if message["role"] == "user" or message["role"] == "system":
                interaction_messages.append([message["content"], None])
            else:
                interaction_messages.append([None, message_text])

        # Update tool call elements
        interaction_tool_calls = update_tool_call_uis(interaction, gr_tool_uis)

        # Update gr_tool_choice options
        tools = agent.get_tools_from_plugins()
        tool_names = ["auto", "none"] + [tool["function"]["name"] for tool in tools]

        return {
            gr_interaction_state: interaction,
            gr_agent_response_content: interaction.agent_response.content,
            gr_browser: image_array,
            gr_messages: interaction_messages,
            gr_tool_choice: gr.Dropdown(choices=tool_names),
            gr_langsmith_run_id: run_id,
            **interaction_tool_calls,
        }

    # MARK: update_agent
    @gr.on(
        triggers=[gr_update_agent_btn.click],
        inputs=[gr_agent_state, gr_system_message, gr_default_model],
        outputs=[gr_agent_state],
    )
    def update_agent(agent, system_message, model):
        if agent:
            agent.system_message = system_message
            agent.model = model
            agent_store.save_agent(agent)
        return {
            gr_agent_state: agent,
        }

    # MARK: load_agent
    def load_agent(agent_name, agent):
        if agent:
            agent.reset_history([], agent.history_name)
        loaded_agent = agent_store.load_agent(
            agent_name=agent_name,
            default_kwargs=DEFAULT_AGENT_KWARGS,
        )
        return {
            gr_agent_state: loaded_agent,
            gr_agent_config_label: gr.Markdown(visible=True),
            gr_agent_config: gr.Group(visible=True),
            gr_system_message: gr.Textbox(value=loaded_agent.system_message),
            gr_default_model: gr.Dropdown(value=loaded_agent.model),
            gr_interaction_tab: gr.Accordion(open=True),
            gr_history_name: gr.Textbox(value=loaded_agent.history_name),
        }

    gr.on(
        triggers=[demo.load, gr_agent_name.submit, gr_load_agent_btn.click],
        fn=load_agent,
        inputs=[gr_agent_name, gr_agent_state],
        outputs=[
            gr_agent_state,
            gr_agent_config_label,
            gr_agent_config,
            gr_system_message,
            gr_default_model,
            gr_interaction_tab,
            gr_history_name,
        ],
    ).then(
        fn=regenerate_interaction,
        inputs=[
            gr_agent_state,
            gr_user_message,
            gr_tool_choice,
            gr_langsmith_session_id,
        ],
        outputs=[
            gr_interaction_state,
            gr_agent_response_content,
            gr_browser,
            gr_messages,
            gr_tool_choice,
            gr_langsmith_run_id,
        ]
        + [item for tpl in gr_tool_uis for item in tpl],
    )

    # MARK: new_history
    def new_history(agent):
        history_name = str(uuid4())
        user_message = ""
        agent.reset_history([], history_name)
        session_id = str(uuid4())
        return {
            gr_agent_state: agent,
            gr_history_name: agent.history_name,
            gr_user_message: user_message,
            gr_langsmith_session_id: session_id,
        }

    gr.on(
        triggers=[gr_new_history_btn.click],
        fn=new_history,
        inputs=[gr_agent_state],
        outputs=[
            gr_agent_state,
            gr_history_name,
            gr_user_message,
            gr_langsmith_session_id,
        ],
    ).then(
        fn=regenerate_interaction,
        inputs=[
            gr_agent_state,
            gr_user_message,
            gr_tool_choice,
            gr_langsmith_session_id,
        ],
        outputs=[
            gr_interaction_state,
            gr_agent_response_content,
            gr_browser,
            gr_messages,
            gr_tool_choice,
            gr_langsmith_run_id,
        ]
        + [item for tpl in gr_tool_uis for item in tpl],
    )

    # MARK: update_tool_call_form
    @gr.on(
        triggers=[gr_tool_call_type.input],
        inputs=[gr_tool_call_type],
        outputs=[
            gr_press_key_key,
            gr_press_key_count,
            gr_input_text_text,
            gr_navigate_to_url_url,
            gr_tool_call_form,
        ],
    )
    def update_tool_call_form(tool_call_type):
        if tool_call_type == "press_key":
            return {
                gr_press_key_key: gr.Text(visible=True),
                gr_press_key_count: gr.Number(visible=True),
                gr_input_text_text: gr.Text(visible=False),
                gr_navigate_to_url_url: gr.Text(visible=False),
                gr_tool_call_form: gr.Accordion(open=True),
            }
        elif tool_call_type == "input_text":
            return {
                gr_press_key_key: gr.Text(visible=False),
                gr_press_key_count: gr.Number(visible=False),
                gr_input_text_text: gr.Text(visible=True),
                gr_navigate_to_url_url: gr.Text(visible=False),
                gr_tool_call_form: gr.Accordion(open=True),
            }
        elif tool_call_type == "navigate_to_url":
            return {
                gr_press_key_key: gr.Text(visible=False),
                gr_press_key_count: gr.Number(visible=False),
                gr_input_text_text: gr.Text(visible=False),
                gr_navigate_to_url_url: gr.Text(visible=True),
                gr_tool_call_form: gr.Accordion(open=True),
            }

    # MARK: submit_tool_call
    @gr.on(
        triggers=[gr_tool_call_submit.click],
        inputs=[
            gr_interaction_state,
            gr_editing_tool_index,
            gr_tool_call_type,
            gr_press_key_key,
            gr_press_key_count,
            gr_input_text_text,
            gr_navigate_to_url_url,
        ],
        outputs=[
            gr_interaction_state,
            gr_editing_tool_index,
            gr_tool_call_form,
            gr_tool_call_submit,
            gr_tool_call_type,
            gr_press_key_key,
            gr_press_key_count,
            gr_input_text_text,
            gr_navigate_to_url_url,
        ]
        + [item for tpl in gr_tool_uis for item in tpl],
    )
    def submit_tool_call(
        interaction,
        editing_tool_index,
        tool_call_type,
        press_key_key,
        press_key_count,
        input_text_text,
        navigate_to_url_url,
    ):
        if interaction is None:
            return {
                gr_interaction_state: interaction,
            }
        tool_call_arguments = {}
        if tool_call_type == "press_key":
            tool_call_arguments = {
                "key": press_key_key,
                "count": press_key_count,
            }
        elif tool_call_type == "input_text":
            tool_call_arguments = {
                "text": input_text_text,
            }
        elif tool_call_type == "navigate_to_url":
            tool_call_arguments = {
                "url": navigate_to_url_url,
            }
        if editing_tool_index is not None:
            # Edit existing tool call
            tool_call_id = f"call_{generate_short_id()}"
            interaction.agent_response.tool_calls[editing_tool_index] = (
                ChatCompletionMessageToolCall(
                    **{
                        "id": tool_call_id,
                        "function": {
                            "name": tool_call_type,
                            "arguments": json.dumps(tool_call_arguments),
                        },
                        "type": "function",
                    }
                )
            )
        else:
            # Add new tool call
            tool_call_id = f"call_{generate_short_id()}"
            if not interaction.agent_response.tool_calls:
                interaction.agent_response.tool_calls = []
            interaction.agent_response.tool_calls.append(
                ChatCompletionMessageToolCall(
                    **{
                        "id": tool_call_id,
                        "function": {
                            "name": tool_call_type,
                            "arguments": json.dumps(tool_call_arguments),
                        },
                        "type": "function",
                    }
                )
            )

        # Update tool call elements
        interaction_tool_calls = update_tool_call_uis(interaction, gr_tool_uis)

        return {
            gr_interaction_state: interaction,
            gr_editing_tool_index: None,
            gr_tool_call_form: gr.Accordion("Add Tool Call", open=False),
            gr_tool_call_submit: gr.Button("Add Tool Call"),
            gr_tool_call_type: gr.Dropdown(value="press_key"),
            gr_press_key_key: gr.Text(visible=True),
            gr_press_key_count: gr.Number(visible=True),
            gr_input_text_text: gr.Text(visible=False),
            gr_navigate_to_url_url: gr.Text(visible=False),
            **interaction_tool_calls,
        }

    # MARK: delete_tool_call
    @gr.on(
        triggers=[gr_delete.click for _, _, _, gr_delete in gr_tool_uis],
        inputs=[gr_interaction_state],
        outputs=[gr_interaction_state] + [item for tpl in gr_tool_uis for item in tpl],
    )
    def delete_tool_call(interaction, event: gr.EventData):
        if interaction is None:
            return {
                gr_interaction_state: interaction,
            }

        # Find the index of the tool call to delete
        index = -1
        for i, (_, _, _, gr_delete) in enumerate(gr_tool_uis):
            if event.target == gr_delete:
                index = i
                break

        if index == -1:
            return {
                gr_interaction_state: interaction,
            }

        # Delete the tool call
        interaction.agent_response.tool_calls.pop(index)

        # Update tool call elements
        interaction_tool_calls = update_tool_call_uis(interaction, gr_tool_uis)

        return {
            gr_interaction_state: interaction,
            **interaction_tool_calls,
        }

    # MARK: edit_tool_call
    @gr.on(
        triggers=[gr_edit.click for _, _, gr_edit, _ in gr_tool_uis],
        inputs=[gr_interaction_state],
        outputs=[
            gr_interaction_state,
            gr_editing_tool_index,
            gr_tool_call_form,
            gr_tool_call_submit,
            gr_tool_call_type,
            gr_press_key_key,
            gr_press_key_count,
            gr_input_text_text,
            gr_navigate_to_url_url,
        ]
        + [item for tpl in gr_tool_uis for item in tpl],
    )
    def edit_tool_call(interaction, event: gr.EventData):
        output_components = {
            gr_interaction_state: interaction,
        }
        if interaction is None:
            return output_components

        # Find the index of the tool call to edit
        index = -1
        for i, (_, _, gr_edit, _) in enumerate(gr_tool_uis):
            if event.target == gr_edit:
                index = i
                break

        if index == -1:
            return output_components

        output_components.update(
            {
                gr_tool_call_form: gr.Accordion("Edit Tool Call", open=True),
                gr_tool_call_submit: gr.Button("Edit Tool Call"),
                gr_editing_tool_index: index,
            }
        )

        # Edit the tool call
        tool_call = interaction.agent_response.tool_calls[index]
        tool_call_arguments = json.loads(tool_call.function.arguments)
        if tool_call.function.name == "press_key":
            output_components.update(
                {
                    gr_tool_call_type: gr.Dropdown(value="press_key"),
                    gr_press_key_key: gr.Text(
                        value=tool_call_arguments["key"], visible=True
                    ),
                    gr_press_key_count: gr.Number(
                        value=(
                            tool_call_arguments["count"]
                            if "count" in tool_call_arguments
                            else 1
                        ),
                        visible=True,
                    ),
                    gr_input_text_text: gr.Text(visible=False),
                }
            )
        elif tool_call.function.name == "input_text":
            output_components.update(
                {
                    gr_tool_call_type: gr.Dropdown(value="input_text"),
                    gr_press_key_key: gr.Text(visible=False),
                    gr_press_key_count: gr.Number(visible=False),
                    gr_input_text_text: gr.Text(
                        value=tool_call_arguments["text"], visible=True
                    ),
                }
            )
        elif tool_call.function.name == "navigate_to_url":
            output_components.update(
                {
                    gr_tool_call_type: gr.Dropdown(value="navigate_to_url"),
                    gr_press_key_key: gr.Text(visible=False),
                    gr_press_key_count: gr.Number(visible=False),
                    gr_input_text_text: gr.Text(visible=False),
                    gr_navigate_to_url_url: gr.Text(
                        value=tool_call_arguments["url"], visible=True
                    ),
                }
            )

        # Update tool call elements
        # TODO: change UI based on the active index
        interaction_tool_calls = update_tool_call_uis(interaction, gr_tool_uis)

        return {
            **output_components,
            **interaction_tool_calls,
        }

    # MARK: commit_interaction
    def commit_interaction(
        agent, interaction, user_message, agent_response_content, run_id, session_id
    ):
        if interaction is None:
            return {
                gr_interaction_state: interaction,
            }
        interaction.user_prompt = user_message if user_message else None
        interaction.agent_response.content = (
            agent_response_content if agent_response_content else None
        )

        # Save the committed interaction
        agent_store.save_interaction(
            agent,
            agent.commit_interaction(
                interaction=interaction,
                langsmith_extra={
                    "run_id": run_id,
                    "metadata": {
                        "agent": agent.model_dump(exclude_unset=True),
                        "session_id": session_id,
                    },
                },
            ),
        )
        # Save the history after the interaction was committed
        agent_store.save_history(agent)
        return {
            gr_interaction_state: interaction,
            gr_user_message: "",
        }

    gr.on(
        triggers=[gr_commit_interaction_btn.click],
        fn=commit_interaction,
        inputs=[
            gr_agent_state,
            gr_interaction_state,
            gr_user_message,
            gr_agent_response_content,
            gr_langsmith_run_id,
            gr_langsmith_session_id,
        ],
        outputs=[gr_agent_state, gr_interaction_state, gr_user_message],
    ).then(
        fn=regenerate_interaction,
        inputs=[
            gr_agent_state,
            gr_user_message,
            gr_tool_choice,
            gr_langsmith_session_id,
        ],
        outputs=[
            gr_interaction_state,
            gr_agent_response_content,
            gr_browser,
            gr_messages,
            gr_tool_choice,
            gr_langsmith_run_id,
        ]
        + [item for tpl in gr_tool_uis for item in tpl],
    )


if __name__ == "__main__":
    demo.launch()
