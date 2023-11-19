import os
import json
import random
import string
import datetime
from glob import glob
from typing import Any, List
from pydantic import BaseModel, Field
from openai import OpenAI
from .utils import md5


def generate_short_id():
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(6))


class Agent(BaseModel, validate_assignment=True, extra="ignore"):
    client: Any = Field(default_factory=OpenAI, exclude=True)
    base_path: str = Field(default="./agents", exclude=True)
    agent_name: str
    version: int = 0
    hash: str = ""
    system_message: str = Field(default="You are a helpful assistant.")

    history_id: str = Field(default_factory=generate_short_id, exclude=True)
    # TODO: type correctly
    history: List[Any] = Field(default=[], exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.hash = self._compute_hash()

    def _compute_hash(self):
        return md5(self.model_dump_json(exclude=["hash", "version"]))

    def __setattr__(self, name, value):
        """Override the default __setattr__ method to update the hash and version when the agent's configuration changes."""
        super().__setattr__(name, value)
        new_hash = self._compute_hash()
        if name not in ["hash", "version"] and self.hash != new_hash:
            self.version += 1
            self.hash = new_hash

    @staticmethod
    def _find_latest_version_static(agent_name, base_path):
        """Static method to find the latest version number of the configuration files."""
        config_files = glob(f"{base_path}/{agent_name}/agent_config_v*.json")
        if not config_files:
            return 0

        latest_version = max(
            int(f.split("_v")[-1].split(".json")[0]) for f in config_files
        )
        return latest_version

    @classmethod
    def load_from_file(cls, agent_name, base_path="./agents", version=None):
        """Loads the agent's state from a JSON file."""

        if version is None:
            # Find the latest version if not specified
            version = cls._find_latest_version_static(agent_name, base_path)

        file_name = f"agent_config_v{version}.json"
        file_path = os.path.join(base_path, agent_name, file_name)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file {file_name} not found.")

        with open(file_path, "r") as file:
            config_data = json.load(file)

        return cls(**config_data)

    def save_config(self):
        """Saves the agent's config to a JSON file."""
        file_name = f"agent_config_v{self.version}.json"
        dir_path = os.path.join(self.base_path, self.agent_name)
        file_path = os.path.join(dir_path, file_name)

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(file_path, "w") as file:
            file.write(self.model_dump_json(indent=4))

        return file_path

    def load_history(self, filename):
        """Loads the agent's history from a JSON file."""
        file_path = os.path.join(self.base_path, self.agent_name, "histories", filename)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"History file {filename} not found.")

        with open(file_path, "r") as file:
            self.history = json.load(file)
            self.history_id = generate_short_id()

    def save_history(self, history_name="noname"):
        """Saves the agent's history to a JSON file."""
        file_name = f"{self.history_id}_{history_name}.json"
        dir_path = os.path.join(self.base_path, self.agent_name, "histories")
        file_path = os.path.join(dir_path, file_name)

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(file_path, "w") as file:
            json.dump(self.history, file, indent=4)

        return file_path

    def clear_history(self):
        self.history_id = generate_short_id()
        self.history = []

    def get_completion(
        self, user_prompt, model="gpt-3.5-turbo-1106", function_call_option=None
    ):
        request_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_message},
                *self.history,
                {"role": "user", "content": user_prompt},
            ],
        }

        chat_completion = self.client.chat.completions.create(**request_params)

        completion = chat_completion.choices[0].message.model_dump(exclude_none=True)

        self.save_request(request_params, completion)

        return completion

    def save_request(self, request_params, completion):
        """Saves the request to a JSON file."""
        current_datetime = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        file_name = f"{self.history_id}_{current_datetime}_{self.version}.json"
        dir_path = os.path.join(self.base_path, self.agent_name, "requests")
        file_path = os.path.join(dir_path, file_name)

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(file_path, "w") as file:
            json.dump(
                {"request": request_params, "response": completion}, file, indent=4
            )

        return file_path

    def append_message(self, message):
        self.history.append(message)


# /agents
# -- <agent_name>/agent_config.json
# -- <agent_name>/conversations/<conversation_id>.json
# -- <agent_name>/requests/<conversation_id|request_id>.json

# Agent Name includes the timestamp of when it was created; when configuration changes, the timestamp should be updated, so that we version the agent config.
# Conversation ID can the the timestamp when the conversation started. (When I load an older conversation, it get's a new ID, so as to not overwrite the old one.)
# Request ID is the timestamp of when the request was made.
