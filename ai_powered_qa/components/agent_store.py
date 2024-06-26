import os
import json
from glob import glob

from ai_powered_qa.components.agent import Agent
from ai_powered_qa.components.interaction import Interaction


class AgentStore:
    def __init__(self, directory: str, name_to_plugin_class: dict = {}):
        self._directory = directory
        self._name_to_plugin_class = name_to_plugin_class

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
            # Copy the default kwargs to avoid modifying the original dict
            agent_kwargs = default_kwargs.copy()
            if "plugins" in default_kwargs:
                plugins = {}
                for plugin_name, plugin_config in default_kwargs["plugins"].items():
                    plugins[plugin_name] = plugin_config
                agent_kwargs["plugins"] = plugins

            return Agent(agent_name=agent_name, **agent_kwargs)

        with open(file_path, "r") as file:
            config_data = json.load(file)

        if isinstance(config_data, dict) and "plugins" in config_data:
            plugins = {}
            for plugin_name, plugin_config in config_data["plugins"].items():
                if isinstance(plugin_config, dict):
                    if plugin_name in self._name_to_plugin_class:
                        plugin_class = self._name_to_plugin_class[plugin_name]
                        plugins[plugin_name] = plugin_class(**plugin_config)
                    else:
                        raise ValueError(f"Invalid plugin name: {plugin_name}")
                else:
                    plugins[plugin_name] = plugin_config
            config_data["plugins"] = plugins

        return Agent(**config_data)

    def save_history(self, agent: Agent):
        file_name = f"full_history.json"
        history_directory = os.path.join(
            self._directory, agent.agent_name, agent.history_name
        )
        file_path = os.path.join(history_directory, file_name)

        if not os.path.exists(history_directory):
            os.makedirs(history_directory)

        with open(file_path, "w") as file:
            file.write(json.dumps(agent.history, indent=4))

    def load_history(self, agent: Agent, history_name: str = None):
        file_name = f"full_history.json"
        history_directory = os.path.join(
            self._directory, agent.agent_name, history_name
        )
        file_path = os.path.join(history_directory, file_name)

        if not os.path.exists(file_path):
            return []

        with open(file_path, "r") as file:
            return json.load(file)

    def save_interaction(self, agent: Agent, interaction: Interaction):
        num_of_messages = len(interaction.request_params["messages"])
        file_name = f"interaction_{num_of_messages}_{interaction.id}.json"
        history_directory = os.path.join(
            self._directory, agent.agent_name, agent.history_name
        )
        file_path = os.path.join(history_directory, file_name)

        if not os.path.exists(history_directory):
            os.makedirs(history_directory)

        with open(file_path, "w") as file:
            file.write(interaction.model_dump_json(indent=4))
