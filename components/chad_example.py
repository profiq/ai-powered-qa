import json
import os
from glob import glob


class Agent:
    def __init__(self, name, config=None):
        self.name = name
        self.config = config or {}
        self.base_path = f"./{name}"
        self.current_version = self._find_latest_version()

    def _find_latest_version(self):
        """Find the latest version number of the configuration files."""
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
            return 0

        config_files = glob(f"{self.base_path}/{self.name}_config_v*.json")
        if not config_files:
            return 0

        latest_version = max(
            int(f.split("_v")[-1].split(".json")[0]) for f in config_files
        )
        return latest_version

    def save_config(self):
        """Save the current configuration data to a JSON file with versioning."""
        self.current_version += 1
        file_name = f"{self.name}_config_v{self.current_version}.json"
        file_path = os.path.join(self.base_path, file_name)

        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

        with open(file_path, "w") as file:
            json.dump(self.config, file, indent=4)

        return file_path

    @classmethod
    def load_config(cls, name, version=None):
        """Load the configuration data from a JSON file and create a new Agent instance."""
        base_path = f"./{name}"
        if version is None:
            # Find the latest version if not specified
            version = cls._find_latest_version_static(name, base_path)

        file_name = f"{name}_config_v{version}.json"
        file_path = os.path.join(base_path, file_name)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file {file_name} not found.")

        with open(file_path, "r") as file:
            config_data = json.load(file)

        return cls(name, config_data)

    @staticmethod
    def _find_latest_version_static(name, base_path):
        """Static method to find the latest version number of the configuration files."""
        if not os.path.exists(base_path):
            return 0

        config_files = glob(f"{base_path}/{name}_config_v*.json")
        if not config_files:
            return 0

        latest_version = max(
            int(f.split("_v")[-1].split(".json")[0]) for f in config_files
        )
        return latest_version


# Example usage
agent_name = "ExampleAgent"
agent = Agent(agent_name, {"setting1": "value1", "setting2": "value2"})

# Save configuration
saved_file_path = agent.save_config()

# Load configuration and create a new Agent instance
new_agent = Agent.load_config(agent_name)

saved_file_path, new_agent.name, new_agent.config
