import json
from langchain.chat_models import ChatOpenAI
from openai import InvalidRequestError
from components.logging_handler import LoggingHandler
from langchain.schema.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)
from dataclasses import dataclass


@dataclass
class ProfiqDevAIConfig:
    """Configuration for the ProfiqDevAI
    These parameters should be used for chat_completion calls.

    Parameters:
    """


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

        self.logging_handler = self._setup_logging_handler()

    def chat_completion(self, inputs: ChatCompletionInputs):
        """
        Chat completion. Pass inputs to the AI model and return the response."""
        functions = inputs.functions
        llm = self._get_llm(inputs.gpt_model)
        prompt_messages = self._get_prompts(
            inputs.system_messages, inputs.conversation_history, inputs.context_messages
        )
        function_call = self._format_function_call(inputs.function_call, functions)

        llm_args = {}

        if inputs.functions is not None:
            llm_args["functions"] = inputs.functions
            llm_args["function_call"] = function_call

        response = llm(prompt_messages, **llm_args)

        # function tokens are counted twice
        functions_tokens = int(llm.get_num_tokens(str(inputs.functions)) / 2)
        messages_tokens = llm.get_num_tokens_from_messages(prompt_messages)
        total_tokens = functions_tokens + messages_tokens

        # TODO here needs to be a function to parse the response from the langchain world to our world.
        # self._convert_langchain_to_json(response)
        return response

    def _get_llm(self, gpt_model: str):
        """Create an instance of the LLM. We create a new instance each time so that we can change the gpt_model during runtime"""
        llm = ChatOpenAI(
            model=gpt_model,
            streaming=False,
            temperature=0,
            callbacks=[self.logging_handler],
        )
        return llm

    def _setup_logging_handler(self):
        return LoggingHandler()

    def _get_prompts(
        self, system_messages: str, conversation_history: str, context_messages: str
    ):
        prompt_messages = []

        if system_messages:
            system_messages = json.loads(system_messages)
            for system_message in system_messages:
                prompt_messages.append(SystemMessage(content=system_message))

        messages = json.loads(conversation_history)

        # logic for message retrieval.
        for message in messages[-10:]:
            if message["role"] == "function":
                prompt_messages.append(FunctionMessage(**message))
            elif message["role"] == "assistant":
                prompt_messages.append(AIMessage(**message))
            elif message["role"] == "user":
                prompt_messages.append(HumanMessage(**message))

        if context_messages:
            context_messages = json.loads(context_messages)
            for context_message in context_messages:
                prompt_messages.append(SystemMessage(content=context_message))

        return prompt_messages

    def _format_function_call(
        self, function_call: str = "none", functions: list = None
    ):
        # auto -> model chooses if to call any function_call or not, none -> no function call
        if function_call not in ["auto", "none"]:
            self._validate_function(function_call, functions)
            return {"name": function_call}
        return function_call

    def _validate_function(self, function_call: str, functions: str):
        if function_call not in [function["name"] for function in functions]:
            raise ValueError(
                f"Function {function_call} not in functions defined for the model."
            )

    def _convert_langchain_to_json(self, response):
        # Following the openAI API https://platform.openai.com/docs/api-reference/chat/object or just leave it as langchain api?
        json_response = {
            "choices": [
                {
                    "message": {
                        "content": response.content if response.content else None,
                        "role": "assistant",
                    }
                }
            ]
        }
        # We only do 1 response. If that chages, this needs to be changed.
        function_call = response.additional_kwargs.get("function_call", None)
        if function_call:
            json_response["choices"][0]["message"]["function_call"] = function_call

        return json.dumps(json_response)
