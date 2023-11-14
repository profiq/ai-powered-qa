from openai import OpenAI


class Agent:
    def __init__(
        self, system_message="You are a helpful assistant.", model="gpt-3.5-turbo-1106"
    ):
        self.client = OpenAI()

        self.system_message = system_message
        self.conversation_history = []

        self.model = model

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

    def save_state(self):
        # Logic to save the agent's state to self.save_path
        pass

    # Additional methods as needed.
