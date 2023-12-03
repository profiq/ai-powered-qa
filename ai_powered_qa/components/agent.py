import json
from typing import Any, Dict, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import OpenAI

from ai_powered_qa.components.interaction import Interaction
from ai_powered_qa.components.plugin import Plugin
from .utils import generate_short_id, md5

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
    plugins: Dict[str, Plugin] = Field(default_factory=dict)

    # Agent state
    history_id: str = Field(default_factory=generate_short_id, exclude=True)
    # TODO: type correctly
    history: List[Any] = Field(default=[], exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.hash = self._compute_hash()

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

    def generate_interaction(self, user_prompt: str, model=None) -> Interaction:
        model = model or self.model
        request_params = {
            "model": model,
            "tools": self.get_tools_for_gpt(),
            "messages": [
                {"role": "system", "content": self.system_message},
                *self.history,
                {"role": "user", "content": user_prompt},
            ],
        }
        completion = self.client.chat.completions.create(**request_params)
        return Interaction(
            request_params=request_params,
            user_prompt=user_prompt,
            agent_response=completion.choices[0].message,
        )

    def add_plugin(self, plugin):
        self.plugins[plugin.name] = plugin
        self._maybe_increment_version()

    def commit_interaction(self, interaction: Interaction):
        user_prompt = interaction.user_prompt
        if user_prompt:
            self.history.append({"role": "user", "content": user_prompt})

        agent_response = interaction.agent_response

        self.history.append(agent_response)

        if agent_response.tool_calls:
            for tool_call in agent_response.tool_calls:
                result = self.call_tool(
                    tool_call.function.name, **json.loads(tool_call.function.arguments)
                )
                self.history.append(
                    {
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tool_call.id,
                    }
                )

    def get_tools_for_gpt(self) -> list[dict]:
        tools = []
        for plugin in self.plugins.values():
            tools.extend(plugin.get_tools_for_gpt())
        return tools

    def call_tool(self, tool_name: str, **kwargs):
        print(f"Calling tool {tool_name} with kwargs {kwargs}")
        for plugin in self.plugins.values():
            result = plugin.call_tool(tool_name, **kwargs)
            # Tool call was handled by plugin
            if result is not None:
                return result
        raise ValueError(f"No plugin could handle the tool '{tool_name}'")
