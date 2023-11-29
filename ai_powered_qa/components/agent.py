import openai
import json
from ai_powered_qa.components.plugin import Plugin


class Agent:
    def __init__(
        self, system_message="You are a helpful assistant.", model="gpt-3.5-turbo-1106"
    ):
        self._system_message = system_message
        self._model = model
        self._client = openai.OpenAI()
        self._request_history = []
        self._conversation_history = []
        self._plugins = {}

    def generate_interaction(self, user_prompt: str = None, model=None):
        model = model or self._model
        _messages = [
            {"role": "system", "content": self._system_message},
            *self._conversation_history,
        ]
        if user_prompt:
            _messages.append({"role": "user", "content": user_prompt})

        completion = self._client.chat.completions.create(
            messages=_messages,
            model=model,
            tools=self._get_tools_from_plugins(),
        )

        self._request_history.append(completion)
        return completion.choices[0].message

    def add_plugin(self, plugin: Plugin):
        self._plugins[plugin.name] = plugin

    def commit_interaction(self, role: str, content: str, tool_calls: None | list = None):
        print("appending message", role, content, tool_calls)

        if not tool_calls:
            self._conversation_history.append(
                {"role": role, "content": content})
            return

        self._conversation_history.append(
            {"role": "assistant", "content": content, "tool_calls": tool_calls}
        )

        for tool_call in tool_calls:
            print(f"tool_call: ", tool_call, "\n")

            p: Plugin
            for p in self._plugins.values():
                result = p.call_tool(tool_call.function.name, **json.loads(
                    tool_call.function.arguments))
                if result is not None:
                    break
            else:
                raise Exception(
                    f"Tool {tool_call.function.name} not found in any plugin!")
            self._conversation_history.append(
                {"role": "tool", "content": str(
                    result), "tool_call_id": tool_call.id}
            )

    def _get_tools_from_plugins(self):
        tools = []
        p: Plugin
        for p in self._plugins.values():
            tools.extend(p.tools)
        return tools
