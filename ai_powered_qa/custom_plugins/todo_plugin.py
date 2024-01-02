from ai_powered_qa.components.plugin import Plugin, tool
from ai_powered_qa.components.agent import Agent


class TodoPlugin(Plugin):
    name: str = "TodoPlugin"
    todos: list[dict] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def context_message(self) -> str:
        ctx = "LIST OF TODOS:\n"
        for todo in self.todos:
            ctx += f"[{'COMPLETED' if todo['completed'] else 'TODO'}] {todo['title']}\n"
        return ctx

    @tool
    def add_todo(self, title: str):
        """
        Adds a new item to the todo list.

        :param str title: The title of the todo item.
        """
        self.todos.append({"title": title, "completed": False})
        return f"Added todo: {title}"

    @tool
    def mark_completed(self, title: str):
        """
        Marks a todo item as completed.

        :param str title: The title of the todo item.
        """
        for todo in self.todos:
            if todo["title"] == title:
                todo["completed"] = True
                return f"Marked todo as completed: {title}"
        return f"Could not find todo: {title}"

    @tool
    def remove(self, title: str):
        """
        Removes a todo item from the list.

        :param str title: The title of the todo item.
        """
        for todo in self.todos:
            if todo["title"] == title:
                self.todos.remove(todo)
                return f"Removed todo: {title}"
        return f"Could not find todo: {title}"


if __name__ == "__main__":
    todo_plugin = TodoPlugin()

    agent = Agent(agent_name="TodoAgent", model="gpt-4-1106-preview")
    agent.add_plugin(todo_plugin)
    interaction = agent.generate_interaction("Add grocery shopping to my todo list.")
    agent.commit_interaction(interaction)

    interaction = agent.generate_interaction("Add working on AI powered QA to my todo list.")
    agent.commit_interaction(interaction)

    print("Todos after adding items:")
    print(todo_plugin.context_message)

    interaction = agent.generate_interaction("Mark grocery shopping as completed.")
    agent.commit_interaction(interaction)

    print("Todos after marking grocery shopping as completed:")
    print(todo_plugin.context_message)

    interaction = agent.generate_interaction("Do I still have any incomplete items on my todo list?")
    print(interaction.agent_response)

    interaction = agent.generate_interaction("Remove all items from my todo list.")
    print(interaction)
    agent.commit_interaction(interaction)

    print("Todos after removing all completed items:")
    print(todo_plugin.context_message)
