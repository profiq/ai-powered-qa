import json
from openai import OpenAI


class Agent:
    def __init__(
        self, system_message="You are a helpful assistant.", model="gpt-3.5-turbo-1106"
    ):
        self.client = OpenAI()

        self.system_message = system_message
        self.conversation_history = []

        self.model = model

    @classmethod
    def load_from_file(cls, filename):
        """Loads the agent's state from a JSON file."""
        with open(filename) as f:
            data = json.load(f)
        return cls(system_message=data["system_message"], model=data["model"])

    def save_to_file(self, filename):
        """Saves the agent's state to a JSON file."""
        agent_state = {"system_message": self.system_message, "model": self.model}
        with open(filename, "w") as f:
            json.dump(agent_state, f)

    def load_conversation_history(self, filename):
        """Loads the agent's conversation history from a JSON file."""
        with open(filename) as f:
            self.conversation_history = json.load(f)

    def save_conversation_history(self, filename):
        """Saves the agent's conversation history to a JSON file."""
        with open(filename, "w") as f:
            json.dump(self.conversation_history, f)

    def get_completion(
        self, user_prompt, model="gpt-3.5-turbo-1106", function_call_option=None
    ):
        print(self.conversation_history)
        chat_completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": self.system_message},
                *self.conversation_history,
                user_prompt,
            ],
            model=model or self.model,
        )

        return chat_completion.choices[0].message.model_dump()

    def append_message(self, message):
        self.conversation_history.append(message)
