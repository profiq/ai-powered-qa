import os
from pydantic import field_validator

from ai_powered_qa.components.plugin import Plugin, tool
from ai_powered_qa.components.agent import Agent


class PlanningPlugin(Plugin):
    name: str = "PlanningPlugin"
    _plan: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def context_message(self) -> str:
        context = "Here are the steps you should take:\n```text\n"
        if self._plan == "":
            context += "No steps have been planned yet. Use the `update_plan` tool to plan next steps.\n```\n"
            return context
        context += f"{self._plan}\n"
        context += "```\n"
        return context

    @tool
    def update_plan(self, new_plan: str):
        """
        It's important to think about the steps you will take before using other tools. Always use this tool before taking steps that have not been planned.

        :param str new_plan: Numbered list of the steps you will take.
        """
        self._plan = new_plan
        return "Plan updated successfully"
