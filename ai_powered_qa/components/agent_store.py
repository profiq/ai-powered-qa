from ai_powered_qa.components.agent import Agent


class AgentStore:
    def __init__(self, directory: str):
        self._directory = directory

    def store_agent(self, agent: Agent):
        pass
