from pydantic import BaseModel
from openai.types.chat.chat_completion_message import ChatCompletionMessage


class Interaction(BaseModel):
    request_params: dict
    user_prompt: str
    agent_response: ChatCompletionMessage
