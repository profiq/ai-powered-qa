from ai_powered_qa.components.agent import Agent
from ai_powered_qa.custom_plugins.memory_plugin import MemoryPlugin
from ai_powered_qa.custom_plugins.playwright_plugin import PlaywrightPlugin
import json


def test_agent_playwright_response():
    agent = Agent(
        model="gpt-4-turbo-preview",
        agent_name="test_reasoning_agent",
        goal="Chci si najít jednopokojový byt v Ostravě na prodej na Bazos.cz",
    )
    playwright_plugin = PlaywrightPlugin()
    memory_plugin = MemoryPlugin()
    agent.add_plugin(playwright_plugin)
    agent.add_plugin(memory_plugin)

    for _ in range(10):
        plan_response = agent._plan_tree_of_thoughts()
        parsed_plan = json.loads(plan_response.tool_calls[0].function.arguments)
        selected_plan = parsed_plan[f'plan_assistant_{parsed_plan["selected_plan"]}']
        plan = "\n".join([f"{i+1}. {s}" for i, s in enumerate(selected_plan)])
        print(plan)
        agent._execute_first_step(plan)
        last_action = selected_plan[0]
        reflection = agent._reflect(last_action)
        memory = (
            "I PERFORMED THE FOLLOWING ACTION: " + last_action
        )  # + "\n" + reflection
        memory_plugin.save_memory(page="Bazos.cz", contents=memory)
        print("---------")
        print(reflection)
        print(memory_plugin.context_message)

    playwright_plugin.close()
