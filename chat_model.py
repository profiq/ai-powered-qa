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
    project_name: str
    test_case: str
    x_last_messages: int = 10


@dataclass
class ChatCompletionInputs:
    gpt_model: str
    last_message: str
    conversation_history: str
    functions: dict
    function_call: str
    system_messages: str
    context_messages: str


class ProfiqDevAI:

    def __init__(self, config: ProfiqDevAIConfig) -> None:
        """
        The best AIdev you can imagine."""
        self.project_name = config.project_name
        self.test_case = config.test_case
        self.x_last_messages = config.x_last_messages
        # TODO loggin handler isnt working correctly
        self.logging_handler = self._setup_logging_handler()

    def chat_completion(self, inputs: ChatCompletionInputs):
        """
        Function to call the chat completion of the model."""
        llm = self._get_llm(inputs.gpt_model)
        prompt_messages = self._get_prompts(
            inputs.system_messages, inputs.conversation_history, inputs.context_messages, inputs.last_message)
        function_call = self._format_function_call(
            inputs.function_call, inputs.functions)

        try:
            response = llm(
                prompt_messages,
                functions=inputs.functions,
                function_call=function_call,
            )

            # function tokens are counted twice
            functions_tokens = int(llm.get_num_tokens(str(inputs.functions))/2)
            messages_tokens = llm.get_num_tokens_from_messages(prompt_messages)
            total_tokens = functions_tokens + messages_tokens

            token_counter_manual = f"Messages tokens: {str(messages_tokens)}  \n" \
                f"Functions tokens: {str(functions_tokens)}  \n" \
                f"Total tokens: {str(total_tokens)}"
            # print(response, type(response))
            # token_counter_langchain = f"Prompt tokens: {str(response.prompt_tokens)}  \n" \
            #     f"Completion tokens: {str(response.completion_tokens)}  \n" \
            #     f"Total tokens: {str(response.total_tokens)}"
                # TODO here needs to be a function to parse the response from the langchain world to our world. Verify that
            # accept json and return only json!!!
            # self._convert_langchain_to_json(response)
            return response, token_counter_manual
        except InvalidRequestError as e:
            return e._message

    def _get_llm(self, gpt_model: str):
        llm = ChatOpenAI(
            model=gpt_model,
            streaming=False,
            temperature=0,
            callbacks=[self.logging_handler]
        )
        return llm

    def _setup_logging_handler(self):
        return LoggingHandler(self.project_name, self.test_case)

    def _get_prompts(self, system_messages: json, conversation_history: json, context_messages: json, last_message: json):
        prompt_messages = []
        system_messages = json.loads(system_messages)
        for system_message in system_messages:
            prompt_messages.append(SystemMessage(content=system_message))

        messages = json.loads(conversation_history)
        messages.append(last_message)
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

    def _format_function_call(self, function_call: str, functions: list):
        # auto -> model chooses if to call any function_call or not, none -> no function call
        if function_call not in ["auto", "none"]:
            self._validate_function(function_call, functions)
            return {"name": function_call}
        return function_call

    def _validate_function(self, function_call: str, functions: list):
        if function_call not in [function["name"] for function in functions]:
            raise ValueError(
                f"Function {function_call} not in functions defined for the model.")

    def _validate_response(self):
        # TODO this method should validate if a returned function call is valid. Or should this be a user a task?
        pass

    def _convert_langchain_to_json(self, response):
        # TODO here needs to be a function to parse the response from the langchain world to our world.
        # Following the openAI API https://platform.openai.com/docs/api-reference/chat/object
        print(response)
        pass
