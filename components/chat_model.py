import json
import openai
from components.logging_handler import LoggingHandler
from dataclasses import dataclass


@dataclass
class ProfiqDevAIConfig:
    """Configuration for the ProfiqDevAI
    These parameters should be used for chat_completion calls.

    Parameters:
    `project_name`: Name of the project.
    `test_case`: Name of the test case.
    `x_last_messages`: How many mesages from the conversation history the AI will work with. 
    The more messages, the higher the token count is."""
    project_name: str
    test_case: str
    x_last_messages: int = 10


@dataclass
class ChatCompletionInputs:
    """Inputs for the chat completion function
    These parameters are passed to every chat_completion call.

    Parameters:
    `gpt_model`: Name of the model to be used.
    `function_call`: Name of the function to be called.
    `conversation_history`: JSON string representing a list of conversation history.
    `functions`: JSON string representing a list of functions to be used.
    `system_messages`: JSON string representing a list of system messages.
    `context_messages`: JSON string representing a list of context messages.

    system_messages and context_messages are effectively the same for the AI model. The difference is that \
    system_messages are prepended at the beggining of conversation history, while context_messages are appended \
    at the end of conversation history. The best approach is to use system_messages for defining the AI behavior \
    and context_messages for adding context (e. g. HTML, description of web page)."""
    gpt_model: str
    conversation_history: str
    functions: str
    function_call: str = "none"
    system_messages: str = None
    context_messages: str = None


class ProfiqDevAI:

    def __init__(self, config: ProfiqDevAIConfig) -> None:
        """
        AI developer made by profiq."""

        self.project_name = config.project_name
        self.test_case = config.test_case
        self.x_last_messages = config.x_last_messages
        self.logging_handler = self._setup_logging_handler()
        self.llm = self._get_llm()

    def chat_completion(self, inputs: ChatCompletionInputs):
        """
        Chat completion. Pass inputs to the AI model and return the response."""
        functions = json.loads(
            inputs.functions)  # TODO: functions shouln't be a mandatory parameter, make it optional
        prompt_messages = self._get_prompts(
            inputs.system_messages, inputs.conversation_history, inputs.context_messages)
        function_call = self._format_function_call(
            inputs.function_call, functions)
        
        try:
            response = self.llm.chat.completions.create(
                model=inputs.gpt_model,
                messages=prompt_messages,
                functions=functions,
                function_call=function_call,
                # response_format={"type": "json_object"},
            )
            token_usage = response.usage
            token_summary = f"Prompt tokens: {str(token_usage.prompt_tokens)}  \n" \
                f"Completion tokens: {str(token_usage.completion_tokens)}  \n" \
                f"Total tokens: {str(token_usage.total_tokens)} \n"
            return response, token_summary
        except Exception as e:
            # So the web_ui script doesnt crash
            return e, -1

    def _get_llm(self):
        """Create an instance of the LLM. We create a new instance each time so that we can change the gpt_model during runtime"""
        return openai.OpenAI()

    def _setup_logging_handler(self):
        return LoggingHandler(self.project_name, self.test_case)

    def _get_prompts(self, system_messages: str, conversation_history: str, context_messages: str):
        prompt_messages = []
        if system_messages:
            system_messages = json.loads(system_messages)
            for system_message in system_messages:
                prompt_messages.append(
                    {"role": "system", "content": system_message})

        messages = json.loads(conversation_history)

        # logic for message retrieval.
        for message in messages[-self.x_last_messages:]:
            if message["role"] == "function":
                prompt_messages.append(
                    {"role": "function", "content": message["content"], "name": message["name"]})
            elif message["role"] == "assistant":
                prompt_messages.append(
                    {"role": "assistant", "content": message["content"]})
            elif message["role"] == "user":
                prompt_messages.append(
                    {"role": "user", "content": message["content"]})

        if context_messages:
            context_messages = json.loads(context_messages)
            for context_message in context_messages:
                prompt_messages.append(
                    {"role": "system", "content": context_message})

        return prompt_messages

    def _format_function_call(self, function_call: str = "none", functions: list = None):
        # auto -> model chooses if to call any function_call or not, none -> no function call
        if function_call not in ["auto", "none"]:
            self._validate_function(function_call, functions)
            return {"name": function_call}
        return function_call

    def _validate_function(self, function_call: str, functions: str):
        if function_call not in [function["name"] for function in functions]:
            raise ValueError(
                f"Function {function_call} not in functions defined for the model.")
