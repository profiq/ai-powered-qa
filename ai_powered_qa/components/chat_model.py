import json
from dataclasses import dataclass

from langchain.chat_models import ChatOpenAI
from openai import BadRequestError
from langchain.schema.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)

from ai_powered_qa.components.logging_handler import LoggingHandler


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
    system_messages are prepended at the beginning of conversation history, while context_messages are appended \
    at the end of conversation history. The best approach is to use system_messages for defining the AI behavior \
    and context_messages for adding context (e.g. HTML, description of web page)."""
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

    def chat_completion(self, inputs: ChatCompletionInputs):
        """
        Chat completion. Pass inputs to the AI model and return the response."""
        functions = json.loads(inputs.functions)  # TODO: functions shouldn't be a mandatory parameter, make it optional
        llm = self._get_llm(inputs.gpt_model)
        prompt_messages = self._get_prompts(inputs.system_messages, inputs.conversation_history, inputs.context_messages)
        function_call = self._format_function_call(inputs.function_call, functions)

        try:
            response = llm(
                prompt_messages,
                functions=functions,
                function_call=function_call,
            )

            # function tokens are counted twice
            functions_tokens = int(llm.get_num_tokens(str(inputs.functions))/2)
            messages_tokens = llm.get_num_tokens_from_messages(prompt_messages)
            total_tokens = functions_tokens + messages_tokens

            token_counter = f"Messages tokens: {str(messages_tokens)}  \n" \
                            f"Functions tokens: {str(functions_tokens)}  \n" \
                            f"Total tokens: {str(total_tokens)}"

            # TODO here needs to be a function to parse the response from the langchain world to our world.
            # response = self._convert_langchain_to_json(response)
            return response, token_counter
        except BadRequestError as e:
            # So the web_ui script doesnt crash
            return e._message

    def _get_llm(self, gpt_model: str):
        """Create an instance of the LLM.
           We create a new instance each time so that we can change the gpt_model during runtime"""
        llm = ChatOpenAI(
            model=gpt_model,
            streaming=False,
            temperature=0,
            callbacks=[self.logging_handler]
        )
        return llm

    def _setup_logging_handler(self):
        return LoggingHandler(self.project_name, self.test_case)

    def _get_prompts(self, system_messages: str, conversation_history: str, context_messages: str):
        prompt_messages = []

        if system_messages:
            system_messages = json.loads(system_messages)
            for system_message in system_messages:
                prompt_messages.append(SystemMessage(content=system_message))

        messages = json.loads(conversation_history)

        # logic for message retrieval.
        for message in messages[-self.x_last_messages:]:
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

    def _format_function_call(self, function_call: str = "none", functions: list = None):
        # auto -> model chooses if to call any function_call or not, none -> no function call
        if function_call not in ["auto", "none"]:
            self._validate_function(function_call, functions)
            return {"name": function_call}
        return function_call

    @staticmethod
    def _validate_function(function_call: str, functions: str):
        if function_call not in [function["name"] for function in functions]:
            raise ValueError(
                f"Function {function_call} not in functions defined for the model.")

    @staticmethod
    def _convert_langchain_to_json(response):
        # Following the openAI API https://platform.openai.com/docs/api-reference/chat/object or just leave it as langchain api?
        json_response = {"choices": [
                            {"message": {
                                "content": response.content if response.content else None,
                                "role": "assistant",
                            }}
                        ]}
        # We only do 1 response. If that changes, this needs to be changed.
        function_call = response.additional_kwargs.get("function_call", None)
        if function_call:
            json_response["choices"][0]["message"]["function_call"] = function_call

        return json.dumps(json_response)
