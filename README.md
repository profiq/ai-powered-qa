# AI Agent for QA

This repository contains two distinct parts:

1. a framework for developing autonomous agents built on top of LLM models we are developing at profiq,
2. an agent based on this framework for automating QA for web applications.

You can read more about our agent framework in our [blog article](https://www.profiq.com/from-chatgpt-to-smart-agents-the-next-frontier-in-app-integration).

## Setup

1. Clone the repository
2. We use [Poetry](https://python-poetry.org) to manage dependencies so you need to install it
3. Create a virtual environment and install all dependencies by running:

```bash
$ poetry install
```

4. If you want to use the QA agent, you also need to install test browsers for Playwright

```bash
$ poetry run playwright install
```

## Usage

### Environment variables

You will need at least an [OpenAI API](https://platform.openai.com) key.
You should put it in a `.env` file like this:

```shell
OPENAI_API_KEY="<YOUR_OPENAI_API_KEY>"
```

You can use `.env.example` as a template if you want to use additional features, like [Anthropic](https://www.anthropic.com/) models, or [LangSmith](https://www.langchain.com/langsmith) tracing.

### Running the QA agent

We have a couple example usages of the agent.
One is a [Streamlit](https://streamlit.io/) interface, currently defaulting to an agent that sees a visible portion of the HTML, and can interact with it using selectors.
You can run it like this:

```bash
$ poetry run streamlit run web_ui_next.py
```

This command should automatically open a new browser tab with an interface with a layout similar to ChatGPT.

The streamlit UI is a bit un-intuitive when the interaction and app state get more complex, so we've also created another UI for the agent using [Gradio](https://gradio.app). This one currently defaults to an accessibility agent, that uses only keyboard, and you can run it using

```bash
$ poetry run gradio web_ui_gradio.py
```

Both interfaces are work in progress and are continually evolving. Please submit an issue if you have any problems or ideas for improvements.

### Creating a new agent in Python

An agent can be created as an instance of the `ai_powered_qa.components.agent.Agent` class and by registering
all plugins you want to use.

```python
from ai_powered_qa.components.agent import Agent
from ai_powered_qa.custom_plugins.todo_plugin import TodoPlugin

agent = Agent(agent_name="TodoAgent", model="gpt-4-1106-preview")
todo_plugin = TodoPlugin()
agent.add_plugin(todo_plugin)
```

You can then run a simple interaction like this:

```python
interaction = agent.generate_interaction("Add grocery shopping to the todo list.")
agent.commit_interaction(interaction)
```

### Writing custom plugins

All plugins have to inherit from the `ai_powered_qa.components.plugin.Plugin` class. We recommend
checking out some existing plugins in the `ai_powered_qa/custom_plugins` directory and our
[blog article](https://www.profiq.com/from-chatgpt-to-smart-agents-the-next-frontier-in-app-integration).
