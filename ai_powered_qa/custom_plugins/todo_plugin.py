from ai_powered_qa.components import Plugin, tool


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
