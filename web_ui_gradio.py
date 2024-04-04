import gradio as gr
import json
import numpy as np
from io import BytesIO
from PIL import Image

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
    "plugins": {"PlaywrightPluginOnlyVisible": {"name": "PlaywrightPluginOnlyVisible"}}
}

DEFAULT_AGENT_NAME = "default_agent"

with gr.Blocks() as demo:
    gr_agent_state = gr.State()
    gr_interaction_state = gr.State()
    gr_editing_tool_index = gr.State()
    with gr.Accordion("Agent Config"):
        # Loading agent
        with gr.Group():
            gr_agent_name = gr.Textbox(label="Agent name", value=DEFAULT_AGENT_NAME)
            gr_load_agent_btn = gr.Button("Load Agent")
        # Agent config
        gr_agent_config_label = gr.Markdown("# Agent Config", visible=False)
        with gr.Group(visible=False) as gr_agent_config:
            gr_system_message = gr.Textbox(label="System Message")
            gr_default_model = gr.Dropdown(label="Model", choices=AVAILABLE_MODELS)
            gr_update_agent_btn = gr.Button("Update Agent")
    with gr.Accordion("Interaction", open=False) as gr_interaction_tab:
        # Loading history
        with gr.Group():
            gr_history_name = gr.Textbox(label="History name")
        # Interaction config
        with gr.Row():
            with gr.Column(scale=2):
                gr_browser = gr.Image()
            with gr.Column(scale=1):
                gr_messages = gr.Chatbot()
                gr_user_message = gr.Textbox(label="User Message")
                gr_tool_choice = gr.Dropdown(
                    label="Tool Choice", choices=["auto", "none"], value="auto"
                )
        gr_regenerate_interaction_btn = gr.Button("Regenerate Interaction")
        # Agent response
        with gr.Column():
            gr_agent_response_content = gr.Textbox(label="Agent Response Content")
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

    # UI helpers
    def update_tool_call_uis(interaction, gr_tool_uis):
        interaction_tool_calls = {}
        for index, (gr_row, gr_markdown, gr_edit, gr_delete) in enumerate(gr_tool_uis):
            if index < len(interaction.agent_response.tool_calls):
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

    # Event listeners
    @gr.on(
        triggers=[demo.load, gr_agent_name.submit, gr_load_agent_btn.click],
        inputs=[gr_agent_name],
        outputs=[
            gr_agent_state,
            gr_agent_config_label,
            gr_agent_config,
            gr_system_message,
            gr_default_model,
            gr_interaction_tab,
            gr_history_name,
        ],
    )
    def load_agent(agent_name):
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

    @gr.on(
        triggers=[gr_regenerate_interaction_btn.click],
        inputs=[gr_agent_state, gr_user_message, gr_tool_choice],
        outputs=[
            gr_interaction_state,
            gr_agent_response_content,
            gr_browser,
            gr_messages,
        ]
        + [item for tpl in gr_tool_uis for item in tpl],
    )
    def regenerate_interaction(agent, user_message, tool_choice):
        if agent is None:
            return {}
        interaction = agent.generate_interaction(
            user_prompt=user_message,
            tool_choice=tool_choice,
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
            if message["role"] == "user" or message["role"] == "system":
                interaction_messages.append([message["content"], None])
            else:
                interaction_messages.append([None, message["content"]])

        # Update tool call elements
        interaction_tool_calls = update_tool_call_uis(interaction, gr_tool_uis)

        return {
            gr_interaction_state: interaction,
            gr_agent_response_content: interaction.agent_response.content,
            gr_browser: image_array,
            gr_messages: interaction_messages,
            **interaction_tool_calls,
        }

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
                        value=tool_call_arguments["count"], visible=True
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


if __name__ == "__main__":
    demo.launch()
