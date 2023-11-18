import openai
import docstring_parser
import inspect
import random

class Agent:
    def __init__(self, system_message="You are a helpful assistant.", model="gpt-3.5-turbo-1106"):
        self._system_message = system_message
        self._model = model
        self._client = openai.OpenAI()
        self._request_history = []
        self._conversation_history = []
        self._plugins = []
        self._tools = {}

    def get_completion(self, user_prompt: str, model=None):
        model = model or self._model
        functions = self._get_function_list()
        completion = self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": self._system_message},
                *self._conversation_history,
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            tools=functions
        )

        self._request_history.append(completion)
        return completion.choices[0].message

    def add_plugin(self, plugin):
        self._plugins.append(plugin)
        for t in plugin.tools:
            self._tools[t[0]['name']] = (t[1], plugin)

    def append_message(self, role: str, content: str, tool_calls: None|list = None):
        print(role, content, tool_calls)

        if not tool_calls:
            self._conversation_history.append({'role': role, 'content': content})
            return

        self._conversation_history.append({'role': 'assistant', 'content': content, 'tool_calls': tool_calls})

        for tool_call in tool_calls:
            print(tool_call)
            tool = self._tools[tool_call.function.name]
            result = tool[0]()
            self._conversation_history.append({'role': 'tool', 'content': str(result), 'tool_call_id': tool_call.id})


        completion = self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": self._system_message},
                *self._conversation_history,
            ],
            model=self._model,
            tools=self._get_function_list()
        )

        message = completion.choices[0].message
        self.append_message('assistant', message.content, message.tool_calls)
            

    def _get_function_list(self):
        functions = []
        for plugin in self._plugins:
            for t in plugin.tools:
                functions.append({"type": "function", "function": t[0]})
        print(functions)
        return functions


def tool(method):
    method.__tool__ = True
    return method


class Plugin:
    TYPE_MAP = {
        'int': 'integer',
    }

    def __init__(self):
        self._tools = []
        self._register_tools()

    @property
    def tools(self):
        return self._tools

    def _register_tools(self):
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '__tool__'):
                docstring = inspect.getdoc(method)
                docstring_parsed = docstring_parser.parse(docstring)
                tool_description = {
                    'name': name,
                    'description': docstring_parsed.short_description,
                    'parameters': {
                        'type': 'object',
                        'properties': self._build_param_object(docstring_parsed.params)
                    }
                }
                self._tools.append((tool_description, method))

    def _build_param_object(self, params):
        param_object = {}
        for param in params:
            param_object[param.arg_name] = {
                'type': self.TYPE_MAP.get(param.type_name, param.type_name),
                'description': param.description,
            }
        return param_object

class RandomNumberPlugin(Plugin):

    @tool
    def get_random_number(self, min_number: int = 0, max_number: int = 100):
        """
        Returns a random number in the specified range

        :param int min_number: The minimum number
        :param int max_number: The maximum number
        """
        return random.randint(min_number, max_number)


if __name__ == '__main__':
    agent = Agent()
    agent.add_plugin(RandomNumberPlugin())

    message = agent.get_completion("Get me a random number betweent 1 and 30.")
    agent.append_message('user', "Get me a random number between 1 and 30.")
    agent.append_message(message.role, message.content, message.tool_calls)
