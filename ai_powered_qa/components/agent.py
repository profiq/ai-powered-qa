import json
from typing import Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator
from openai import OpenAI

from ai_powered_qa.components.interaction import Interaction
from ai_powered_qa.components.plugin import Plugin
from .utils import generate_short_id, md5
from .plugin_name_to_class import PLUGIN_NAME_TO_CLASS

load_dotenv()


class Agent(BaseModel, validate_assignment=True, extra="ignore"):
    # Agent identifiers
    agent_name: str
    version: int = 0
    hash: str = ""

    # OpenAI API
    client: Any = Field(default_factory=OpenAI, exclude=True)
    model: str = Field(default="gpt-3.5-turbo-1106")

    # Agent configuration
    system_message: str = Field(default="You are a helpful assistant.")
    plugins: dict[str, Plugin] = Field(default_factory=dict)

    # Agent state
    history_id: str = Field(default_factory=generate_short_id, exclude=True)
    history: list = Field(default=[], exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.hash = self._compute_hash()

    @model_validator(mode="before")
    @classmethod
    def register_plugins(cls, data: Any) -> Any:
        if isinstance(data, dict) and "plugins" in data:
            plugins = {}
            for plugin_name, plugin_config in data["plugins"].items():
                if isinstance(plugin_config, dict):
                    if plugin_name in PLUGIN_NAME_TO_CLASS:
                        plugin_class = PLUGIN_NAME_TO_CLASS[plugin_name]
                        plugins[plugin_name] = plugin_class(**plugin_config)
                    else:
                        raise ValueError(f"Invalid plugin name: {plugin_name}")
                else:
                    plugins[plugin_name] = plugin_config
            data["plugins"] = plugins
        return data

    def __setattr__(self, name, value):
        """Override the default __setattr__ method to update the hash and version when the agent's configuration changes."""
        super().__setattr__(name, value)
        if name not in ["hash", "version"]:
            self._maybe_increment_version()

    def _compute_hash(self):
        return md5(self.model_dump_json(exclude=["hash", "version"]))

    def _maybe_increment_version(self):
        new_hash = self._compute_hash()
        if self.hash != new_hash:
            self.version += 1
            self.hash = new_hash

    def add_plugin(self, plugin: Plugin):
        self.plugins[plugin.name] = plugin
        self._maybe_increment_version()

    def _get_tools_from_plugins(self) -> list[dict]:
        tools = []
        p: Plugin
        for p in self.plugins.values():
            tools.extend(p.tools)
        return tools

    def generate_interaction(self, user_prompt: str = None, model=None) -> Interaction:
        model = model or self.model
        _messages = [
            {"role": "system", "content": self.system_message},
            *(self.history[:-10]),
        ]

        _messages.append({"role": "user", "content": self._generate_context_message()})

        if user_prompt:
            _messages.append({"role": "user", "content": user_prompt})

        request_params = {
            "model": model,
            "messages": _messages,
        }
        tools = self._get_tools_from_plugins()
        if len(tools) > 0:
            request_params["tools"] = tools
        completion = self.client.chat.completions.create(**request_params)

        return Interaction(
            request_params=request_params,
            user_prompt=user_prompt,
            agent_response=completion.choices[0].message,
        )

    def commit_interaction(self, interaction: Interaction) -> Interaction:
        interaction.committed = True
        user_prompt = interaction.user_prompt
        if user_prompt:
            self.history.append({"role": "user", "content": user_prompt})

        agent_response = interaction.agent_response

        self.history.append(agent_response.model_dump(exclude_unset=True))

        if agent_response.tool_calls:
            tool_responses = []
            for tool_call in agent_response.tool_calls:
                p: Plugin
                for p in self.plugins.values():
                    # iterate all plugins until the plugin with correct tool is found
                    result = p.call_tool(
                        tool_call.function.name,
                        **json.loads(tool_call.function.arguments),
                    )
                    if result is not None:
                        break
                else:
                    raise Exception(
                        f"Tool {tool_call.function.name} not found in any plugin!"
                    )
                tool_responses.append(
                    {
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tool_call.id,
                    }
                )
            interaction.tool_responses = tool_responses
            self.history.extend(tool_responses)
        return interaction

    def reset_history(self):
        self.history = []
        self.history_id = generate_short_id()
        p: Plugin
        for p in self.plugins.values():
            p.reset_history(self.history)

    def _generate_context_message(self):
        contexts = [p.context_message for p in self.plugins.values()]
        return "\n\n".join(contexts)
