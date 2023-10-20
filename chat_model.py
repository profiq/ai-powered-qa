import json
from langchain.chat_models import ChatOpenAI
from logging_handler import LoggingHandler
from langchain.schema.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)
from dataclasses import dataclass


@dataclass
class ProfiqDevAIConfig:
    project_name: str
    test_case: str
    x_last_messages: int = 10


@dataclass
class ChatCompletionInputs:
    gpt_model: str
    conversation_history: str
    functions: dict
    function_call: str
    system_messages: str
    context_messages: str


class ProfiqDevAI():

    def __init__(self, config: ProfiqDevAIConfig) -> None:
        """
        The best AIdev you can imagine."""
        self.project_name = config.project_name
        self.test_case = config.test_case
        self.x_last_messages = config.x_last_messages
        # loggin handler isnt working correctly
        self.logging_handler = self._setup_logging_handler()

    def chat_completion(self, inputs: ChatCompletionInputs):
        """
        Function to call the chat completion of the model."""
        llm = self._get_llm(inputs.gpt_model)
        prompt_messages = self._get_prompts(inputs.system_messages, inputs.conversation_history, inputs.context_messages)
        function_call = self._format_function_call(
            inputs.function_call, inputs.functions)
        response = llm(
            prompt_messages,
            functions=inputs.functions,
            function_call=function_call,
        )
        # here needs to be a function to parse the response from the langchain world to our world.
        return response

    def _get_llm(self, gpt_model):
        llm = ChatOpenAI(
            model=gpt_model,
            streaming=False,
            temperature=0.1,
            callbacks=[self.logging_handler]
        )
        return llm

    def _setup_logging_handler(self):
        return LoggingHandler(self.project_name, self.test_case)

    def _get_prompts(self, system_messages, conversation_history, context_messages):
        prompt_messages = []
        system_messages = json.loads(system_messages)
        for system_message in system_messages:
            prompt_messages.append(SystemMessage(content=system_message))

        messages = json.loads(conversation_history)
        # logic for message retrieval. Can be x last messages, or summary ...
        for message in messages[-self.x_last_messages:]:
            if message["role"] == "function":
                prompt_messages.append(FunctionMessage(**message))
            elif message["role"] == "assistant":
                prompt_messages.append(AIMessage(**message))
            elif message["role"] == "user":
                prompt_messages.append(HumanMessage(**message))

        context_messages = json.loads(context_messages)
        for context_message in context_messages:
            prompt_messages.append(SystemMessage(content=context_message))

        return prompt_messages

    def _format_function_call(self, function_call, functions):
        # auto -> model chooses if to call any function_call or not, none -> no function call
        if function_call not in ["auto", "none"]:
            self._validate_function(function_call, functions)
            return {"name": function_call}
        return function_call

    def _validate_function(self, function_call, functions):
        if function_call not in functions:
            raise ValueError(
                f"Function {function_call} not in functions defined for the model.")
