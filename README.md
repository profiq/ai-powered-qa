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

### Running the QA agent

We are developing a UI for the QA agent based on [Steamlit](https://streamlit.io/). You start this UI like this:

```bash
$ poetry run streamlit run web_ui_next.py
```

This command should automatically open a new browser tab with an interface with a layout similar to ChatGPT.

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


