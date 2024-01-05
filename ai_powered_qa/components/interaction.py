from pydantic import BaseModel, Field
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from ai_powered_qa.components.utils import generate_short_id


class Interaction(BaseModel):
    id: str = Field(default_factory=generate_short_id)
    committed: bool = False
    request_params: dict
    user_prompt: str | None
    agent_response: ChatCompletionMessage
    tool_responses: list[dict] | None = None
