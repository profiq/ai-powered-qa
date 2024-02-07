import json
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from ai_powered_qa.components.interaction import Interaction
from ai_powered_qa.components.plugin import Plugin
from ai_powered_qa.components.constants import MODEL_TOKEN_LIMITS
from .utils import generate_short_id, md5, count_tokens
import yaml

load_dotenv()


AVAILABLE_MODELS = ["gpt-3.5-turbo-1106", "gpt-4-1106-preview"]


class Agent(BaseModel, validate_assignment=True, extra="ignore"):
    # Agent identifiers
    agent_name: str
    version: int = 0
    hash: str = ""

    # OpenAI API
    client: Any = Field(default_factory=OpenAI, exclude=True)
    model: str = Field(default="gpt-3.5-turbo-1106")

    # Agent configuration
    system_message: str = Field(default="You are a helpful assistant.")
    plugins: dict[str, Plugin] = Field(default_factory=dict)

    # Agent state
    history_name: str = Field(default_factory=generate_short_id, exclude=True)
    history: list = Field(default=[], exclude=True)

    goal: str

    def __init__(self, **data):
        super().__init__(**data)
        self.hash = self._compute_hash()

    def __setattr__(self, name, value):
        """Override the default __setattr__ method to update the hash and version when the agent's configuration changes."""
        super().__setattr__(name, value)
        if name not in ["hash", "version"]:
            self._maybe_increment_version()

    def _compute_hash(self):
        return md5(self.model_dump_json(exclude=["hash", "version"]))

    def _maybe_increment_version(self):
        new_hash = self._compute_hash()
        if self.hash != new_hash:
            self.version += 1
            self.hash = new_hash

    def add_plugin(self, plugin: Plugin):
        self.plugins[plugin.name] = plugin
        self._maybe_increment_version()

    def get_tools_from_plugins(self) -> list[dict]:
        tools = []
        p: Plugin
        for p in self.plugins.values():
            tools.extend(p.tools)
        return tools

    def generate_interaction(
        self,
        user_prompt: str = None,
        model=None,
        tool_choice: str = "auto",
        max_response_tokens=1000,
    ) -> Interaction:
        model = model or self.model
        max_history_tokens = MODEL_TOKEN_LIMITS[model] - max_response_tokens
        messages = self._get_messages_for_completion(
            user_prompt, model, max_history_tokens
        )
        request_params = {
            "model": model,
            "messages": messages,
            "tool_choice": (
                tool_choice
                if tool_choice in ["auto", "none"]
                else {"type": "function", "function": {"name": tool_choice}}
            ),
            "temperature": 0.1,
        }

        tools = self.get_tools_from_plugins()
        if len(tools) > 0:
            request_params["tools"] = tools
        completion = self.client.chat.completions.create(**request_params)

        return Interaction(
            request_params=request_params,
            user_prompt=user_prompt,
            agent_response=completion.choices[0].message,
        )

    def commit_interaction(self, interaction: Interaction) -> Interaction:
        interaction.committed = True
        user_prompt = interaction.user_prompt
        if user_prompt:
            self.history.append({"role": "user", "content": user_prompt})

        agent_response = interaction.agent_response

        self.history.append(agent_response.model_dump(exclude_unset=True))

        if agent_response.tool_calls:
            tool_responses = []
            for tool_call in agent_response.tool_calls:
                p: Plugin
                for p in self.plugins.values():
                    # iterate all plugins until the plugin with correct tool is found
                    result = p.call_tool(
                        tool_call.function.name,
                        **json.loads(tool_call.function.arguments),
                    )
                    if result is not None:
                        break
                else:
                    raise Exception(
                        f"Tool {tool_call.function.name} not found in any plugin!"
                    )
                tool_responses.append(
                    {
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tool_call.id,
                    }
                )
            interaction.tool_responses = tool_responses
            self.history.extend(tool_responses)
        return interaction

    def reset_history(self, history: list = [], history_name: str = None):
        self.history = history
        self.history_name = history_name or generate_short_id()
        p: Plugin
        for p in self.plugins.values():
            p.reset_history(self.history)

    def _get_messages_for_completion(
        self, user_prompt: str | None, model: str, max_tokens: int
    ) -> list[dict]:
        messages = [{"role": "system", "content": self.system_message}]
        context_message = self._generate_context_message()

        total_tokens = count_tokens(self.system_message, model)
        total_tokens += count_tokens(context_message, model)
        if user_prompt:
            total_tokens += count_tokens(user_prompt, model)

        messages_to_add = []
        i = 0

        while i < len(self.history):
            history_item = self.history[-i - 1]
            messages_to_add.insert(0, history_item)
            content_length = count_tokens(yaml.dump(history_item), model)

            while history_item["role"] == "tool":
                i += 1
                history_item = self.history[-i - 1]
                messages_to_add.insert(0, history_item)
                content_length += count_tokens(yaml.dump(history_item), model)

            if content_length + total_tokens > max_tokens:
                break
            total_tokens += content_length
            messages[1:1] = messages_to_add
            messages_to_add = []
            i += 1

        messages.append({"role": "user", "content": context_message})
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})

        return messages

    def _generate_context_message(self):
        contexts = [p.context_message for p in self.plugins.values()]
        return "\n\n".join(contexts)

    def _plan(self, model: str | None = None) -> str:
        model = model or self.model

        system_prompt = """
            You are an expert on creating plans for performing tasks on the 
            web. A user gives you information about:

            - high-level goal
            - the current context - what they see in the web browser
            - a list of tools that can be used
            - history of previous actions and their results

            Respond with a step-by-step plan of what to do next to accomplish
            the goal. Each step should contain a reference for a tool that can
            be used to execute the step. The explain why you chose the plan. 
            The explanation should refer to previous steps. Always translate text 
            input into the language of the website. 
            Avoid repeating the same steps that have already been done.

            Examples:

            ### Example input ###

            GOAL: I want to find a PC good for machine learning near Ostrava

            TOOLS:
            - thinking
            - click on element
            - navigate to a URL
            - select an option in a select box
            - type text into an input field

            CONTEXT:
            I see an empty search results page.

            HISTORY:
            1. I opened the web browser
            2. I navigated to bazos.cz
            3. I typed "PC for machine learning" into the search bar
            4. I pressed the submit button
            5. I was redirected to a search results page. It is empty.

            ### Example output ###

            6. Go back to the main page (navigate to a URL tool)
            7. Instead of using search, click the PC category button (click on 
               element tool)
            8. Select a subcategory for desktop PC (click on element tool)
            9. Evaluate the appropriateness for ML for each PC in the list 
               (thinking tool)

            REASONING:
            The search have failed so we need to try a different approach. There as PC category
            that likely contains some machine learning PC. We should explore this category.

            ### Example input ###

            GOAL: I want to buy a machine learning PC on Alza.cz

            TOOLS:
            - thinking
            - click on element
            - navigate to a URL
            - select an option in a select box
            - type text into an input field

            CONTEXT:
            I see an empty webpage with no contents

            HISTORY:
            1. I opened the web browser

            ### Example output ###

            2. Go to Alza.cz (navigate to a URL tool)
            3. Think about what parameters are important when choosing a PC 
               for machine learning (thinking tool)
            4. Go to the PC category (click on element tool)
            5. Set filters to only get PCs with parameters suitable for machine
               learning (type text into an input field tool)

            REASONING:
            You need to be on the Alza.cz webpage to buy a PC there. It is 
            likely that Alza.cz does not allow you to directly buy a PC for 
            machine learning. You need to think about what components you 
            want and what should be their parameters. Then you can go to the 
            PC section and use filters to only get PCs with parameters 
            suitable for machine learning.

            ### Example Input ###

            GOAL: I want to book a last-minute flight from New York to London.

            CONTEXT:
            [HTML OF THE CURRENT PAGE]

            TOOLS:
            - thinking
            - click on element
            - navigate to a URL
            - select an option in a select box
            - type text into an input field

            HISTORY:
            1. I opened the web browser.
            2. I navigated to a generic travel booking website.
            3. I selected "New York" in the "From" dropdown.
            4. I selected "London" in the "To" dropdown.
            5. I selected today's date for departure.
            6. I clicked the "Search" button.
            7. I received a message saying "No flights available".

            ### Example Output ###

            8. Navigate to another travel booking website that specializes 
               in last-minute flights (navigate to a URL tool).
            9. Use the thinking tool to consider the time difference and 
               decide on a flexible range of departure times.
            10. Select "New York" in the "From" dropdown (select an option 
                in a select box tool).
            11. Select "London" in the "To" dropdown (select an option in
                a select box tool).
            12. Consider selecting a range of dates for departure to increase 
                the chances of finding available flights (thinking tool).
            13. Click the "Search" button (click on element tool).
            14. If flights are available, review the options and select the most 
                suitable flight based on price and timing (thinking tool).

            REASONING:
            The initial approach on a general travel booking website failed due
            to no available flights for the specific date and route. Switching 
            to a website that specializes in last-minute flights increases the 
            chances of finding available options, as these platforms often have
            access to unsold inventory or last-minute cancellations. By 
            considering a flexible range of departure times and possibly dates,
            the likelihood of finding an available flight is further improved.
            This approach is more targeted and takes into account the urgency
            and specific needs of booking a last-minute flight, thus addressing
            the failure of the initial attempt.
        """

        plan_function = {
            "name": "print_plan",
            "description": "Prints the prepared plan for the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step": {"type": "string"},
                                "tool": {"type": "string"},
                            },
                        },
                        "description": "The steps of the plan",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "The reasoning behind the plan",
                    },
                },
            },
        }

        tools = "\n".join(
            [
                f"- {t['function']['name']} ({t['function']['description']})"
                for t in self.get_tools_from_plugins()
            ]
        )

        prompt = f"""
            GOAL: {self.goal}

            TOOLS:
            {tools}

            CONTEXT:
            {self._generate_context_message()}
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            tools=[{"type": "function", "function": plan_function}],
            tool_choice={"type": "function", "function": {"name": "print_plan"}},
        )

        return completion.choices[0].message

    def _execute_first_step(self, plan: str, model: str | None = None) -> str:
        model = model or self.model

        tools = "\n".join(
            [
                f"- {t['function']['name']} ({t['function']['description']})"
                for t in self.get_tools_from_plugins()
            ]
        )

        system_prompt = f"""
            You are an expert on executing tasks in a web browser according to a
            plan. A user gives you a plan for performing a series of tasks on the
            web. You have to execute the first step of the plan by invoking a proper
            tool from the list of available tools. The user also provides you with
            the current context - what they see in the web browser.

            AVAILABLE TOOLS:
            {tools}
        """

        prompt = f"""
            GOAL: {self.goal}

            PLAN:
            {plan}

            CONTEXT:
            {self._generate_context_message()}
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            tools=self.get_tools_from_plugins(),
        )

        agent_response = completion.choices[0].message
        if agent_response.tool_calls:
            for tool_call in agent_response.tool_calls:
                for p in self.plugins.values():
                    result = p.call_tool(
                        tool_call.function.name,
                        **json.loads(tool_call.function.arguments),
                    )
                    if result is not None:
                        break
                    else:
                        raise Exception(
                            f"Tool {tool_call.function.name} not found in any plugin!"
                        )

        return completion.choices[0].message

    def _reflect(self, last_action: str, model: str | None = None) -> str:
        model = model or self.model

        system_prompt = f"""
            You are an expert on evaluating and reflecting on task 
            performance. The user gives you information about:

            - their high-level goal, 
            - the current context - what they see in the web browser
            - their memories about what they did in the past and what they learned
            - latest task: the task the user just performed

            You respond with a short one paragaph reflection answering on the 
            previous action.
            What was the last action the user performed?
            What is the current situation of the user? 
            What does the current web page contain?
            Is there something you expected to see but you don't?
            What information on the webpage is relevant to the task?
            Was the high level goal achieved? If not, did the previous action 
            bring the user closer to accomplishing it? 
            Does the user need to try something else?

            Provide a detailed reasoning.

            Here is an example:

            ### Example input ###

            HIGH LEVEL GOAL: I want to find a PC good for machine learning near Ostrava

            CONTEXT:
            I see an empty search results page.
            
            PREVIOUS ACTIONS AND MEMORIES:
            1. I opened the web browser
            2. I navigated to bazos.cz
            3. I typed "PC for machine learning" into the search bar

            LAST ACTION:
            Press the submit button (click on element tool)

            ### Example output ###:
            
            The user finished the search for "PC for machine learning" by 
            clicking the search submit button. The user sees an empty results
            page.The goal is not yet accomplished. The search results page was
            empty. A different approach has to be examined. The search has
            failed, so we need to try a different approach. There as PC 
            category that likely contains some machine learning PC. We should
            explore this category.
        """

        prompt = f"""
            HIGH LEVEL GOAL: {self.goal}

            CONTEXT:
            {self._generate_context_message()}

            LAST ACTION:
            {last_action}
        """

        print(system_prompt, prompt)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        completion = self.client.chat.completions.create(
            model=model, messages=messages, temperature=0
        )

        return completion.choices[0].message.content
