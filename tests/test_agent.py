from ai_powered_qa.components.agent import Agent
from ai_powered_qa.components.plugin import PlaywrightPlugin, RandomNumberPlugin


def test_agent_with_rng():
    agent = Agent(agent_name="test_agent_with_rng")
    agent.add_plugin(RandomNumberPlugin())
    assert len(agent.plugins) == 1
    interaction = agent.generate_interaction(
        "Please generate a random number between 1 and 10"
    )
    agent_response = interaction.agent_response
    assert (
        agent_response.tool_calls[0].function.name
        == "RandomNumberPlugin_get_random_number"
    )
    agent.commit_interaction(interaction)
    assert len(agent.history) == 3


def test_agent_init():
    agent = Agent(agent_name="test_agent_init")
    assert agent.agent_name == "test_agent_init"


def test_agent_version_number():
    # Initialize agent
    agent = Agent(agent_name="test_agent_get_completion")
    assert agent.version == 0

    # Changing system_message increments the version
    agent.system_message = "You are a super helpful assistant"
    assert agent.version == 1

    # Adding a plugin increments the version
    agent.add_plugin(RandomNumberPlugin())
    assert agent.version == 2

    # Commiting an interaction does not increment the version (and doesn't change the hash)
    hash_before = agent.hash
    interaction = agent.generate_interaction(
        "Please generate a random number between 1 and 10"
    )
    agent.commit_interaction(interaction)
    # fake changing the system message to make sure hash computation got triggered
    agent.system_message = "You are a super helpful assistant"
    assert agent.version == 2
    assert agent.hash == hash_before
