from ai_powered_qa.components.agent import Agent
from ai_powered_qa.custom_plugins.memory_plugin import MemoryPlugin
from ai_powered_qa.custom_plugins.playwright_plugin import PlaywrightPlugin
import json


def test_agent_playwright_response():
    agent = Agent(
        agent_name="test_reasoning_agent",
        goal="Find a me a cheap Macbook Pro on e-bay",
    )
    playwright_plugin = PlaywrightPlugin()
    memory_plugin = MemoryPlugin()
    agent.add_plugin(playwright_plugin)
    agent.add_plugin(memory_plugin)

    for _ in range(10):
        plan_response = agent._plan()
        steps = json.loads(plan_response.tool_calls[0].function.arguments)['steps']
        plan = "\n".join([f"{s['step']} ({s['tool']})" for s in steps])
        agent._execute_first_step(plan)
        last_action = plan.split("\n")[0]
        reflection = agent._reflect(last_action)
        memory = "I PERFORMED THE FOLLOWING ACTION: " + last_action + "\n" + reflection
        memory_plugin.save_memory(page="Bazos.cz", contents=memory)
        print("---------")
        print(plan)
        print(reflection)
        print(memory_plugin.context_message)

    playwright_plugin.close()
