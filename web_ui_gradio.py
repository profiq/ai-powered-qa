import gradio as gr

from ai_powered_qa.components.agent import AVAILABLE_MODELS
from ai_powered_qa.components.agent_store import AgentStore
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

with gr.Blocks() as agent_framework:
    agent = gr.State()
    with gr.Tab("Agent Config"):
        with gr.Group():
            name = gr.Textbox(label="Agent name")
            load_agent_btn = gr.Button("Load Agent")

        agent_config_label = gr.Markdown("# Agent Config", visible=False)
        with gr.Group(visible=False) as agent_config:
            system_message = gr.Textbox(label="System Message")
            default_model = gr.Dropdown(label="Model", choices=AVAILABLE_MODELS)
            update_agent_btn = gr.Button("Update Agent")

    with gr.Tab("Interaction") as interaction_tab:
        with gr.Row():
            with gr.Column(scale=2):
                browser = gr.Image()
            with gr.Column(scale=1):
                user_message = gr.Textbox(label="User Message")
                tool_choice = gr.Dropdown(label="Tool Choice", choices=["auto", "none"])

    @gr.on(
        triggers=[name.submit, load_agent_btn.click],
        inputs=[name],
        outputs=[
            agent,
            agent_config_label,
            agent_config,
            system_message,
            default_model,
            interaction_tab,
        ],
    )
    def load_agent(name):
        loaded_agent = agent_store.load_agent(
            agent_name=name,
            default_kwargs=DEFAULT_AGENT_KWARGS,
        )
        return {
            agent: loaded_agent,
            agent_config_label: gr.Markdown(visible=True),
            agent_config: gr.Group(visible=True),
            system_message: gr.Textbox(value=loaded_agent.system_message),
            default_model: gr.Dropdown(value=loaded_agent.model),
            interaction_tab: gr.Tab(visible=True),
        }


if __name__ == "__main__":
    agent_framework.launch()
