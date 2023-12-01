import json

import openai


class Agent:
    def __init__(
        self, system_message="You are a helpful assistant.", model="gpt-3.5-turbo-1106"
    ):
        self._system_message = system_message
        self._model = model
        self._client = openai.OpenAI()
        self._request_history = []
        self._conversation_history = []
        self._plugins = []
        self._tools = {}

    def get_completion(self, user_prompt: str, model=None):
        model = model or self._model
        completion = self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": self._system_message},
                *self._conversation_history,
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            tools=self._tools_for_gpt,
        )

        self._request_history.append(completion)
        return completion.choices[0].message

    def add_plugin(self, plugin):
        self._plugins.append(plugin)
        for t in plugin.tools:
            self._tools[t[0]["name"]] = t

    def append_message(self, role: str, content: str, tool_calls: None | list = None):
        print(role, content, tool_calls)

        if not tool_calls:
            self._conversation_history.append({"role": role, "content": content})
            return

        self._conversation_history.append(
            {"role": "assistant", "content": content, "tool_calls": tool_calls}
        )

        for tool_call in tool_calls:
            print(tool_call)
            tool = self._tools[tool_call.function.name]
            result = tool[1](**json.loads(tool_call.function.arguments))
            self._conversation_history.append(
                {"role": "tool", "content": str(result), "tool_call_id": tool_call.id}
            )

        completion = self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": self._system_message},
                *self._conversation_history,
            ],
            model=self._model,
            tools=self._tools_for_gpt,
        )

        message = completion.choices[0].message
        self.append_message("assistant", message.content, message.tool_calls)

    @property
    def _tools_for_gpt(self) -> list[dict]:
        tools = [{"type": "function", "function": t[0]} for t in self._tools.values()]
        return tools
