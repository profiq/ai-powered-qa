import os
import json
from glob import glob

from ai_powered_qa.components.agent import Agent


class AgentStore:
    def __init__(self, directory: str):
        self._directory = directory

    def save_agent(self, agent: Agent):
        file_name = f"{agent.agent_name}_config_v{agent.version}.json"
        agent_directory = os.path.join(self._directory, agent.agent_name)
        file_path = os.path.join(agent_directory, file_name)

        if not os.path.exists(agent_directory):
            os.makedirs(agent_directory)

        with open(file_path, "w") as file:
            file.write(agent.model_dump_json(indent=4))

    def _find_latest_version(self, agent_name: str) -> int:
        agent_directory = os.path.join(self._directory, agent_name)
        if not os.path.exists(agent_directory):
            return None

        config_files = glob(
            f"{self._directory}/{agent_name}/{agent_name}_config_v*.json"
        )
        if not config_files:
            return 0

        latest_version = max(
            int(f.split("_v")[-1].split(".json")[0]) for f in config_files
        )
        return latest_version

    def load_agent(
        self, agent_name: str, version: int = None, default_kwargs: dict = {}
    ) -> Agent:
        if version is None:
            version = self._find_latest_version(agent_name)

        file_name = f"{agent_name}_config_v{version}.json"
        file_path = os.path.join(self._directory, agent_name, file_name)

        if not os.path.exists(file_path):
            return Agent(agent_name=agent_name, **default_kwargs)

        with open(file_path, "r") as file:
            config_data = json.load(file)

        return Agent(**config_data)
