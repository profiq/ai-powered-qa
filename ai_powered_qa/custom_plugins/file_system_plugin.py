import os

from ai_powered_qa.components.plugin import Plugin, tool


class FileSystemPlugin(Plugin):
    name: str = "FileSystemPlugin"
    root_directory: str
    _directory: str = ""
    _current_file: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def context_message(self) -> str:
        context = "Current directory structure:\n```text\n"
        context += f"{self._directory_structure()}\n"
        context += "```\n"
        if self._current_file:
            context += f"Current file: {self._current_file}\n\n"
            context += f"Current file contents:\n```\n{open(os.path.join(self.root_directory, self._current_file)).read()}```\n"
        return context

    @tool
    def open_file(self, file: str):
        """
        Open a file if you need the contents to respond to the user. You can create a new file by providing a path that doesn't exist.

        :param str file: Path to the file you want to open.
        """
        full_path = os.path.join(self.root_directory, self._directory, file)
        if not os.path.isfile(full_path):
            # Create the file if it doesn't exist
            open(full_path, "w").close()
        self._current_file = file
        return f"Opened file: {file}"

    @tool
    def update_current_file(self, content: str):
        """
        Update the current file with the provided content. Always specify the whole content of the file.

        :param str content: The content to write to the current file.
        """
        full_path = os.path.join(
            self.root_directory, self._directory, self._current_file
        )
        with open(full_path, "w") as file:
            file.write(content)
        return f"Updated file: {self._current_file}"

    def _directory_structure(self):
        directory = (
            self.root_directory
            if self._directory == ""
            else os.path.join(self.root_directory, self._directory)
        )

        if not os.path.isdir(directory):
            raise Exception(
                f"The provided path '{directory}' is not a valid directory."
            )

        structure = "."
        if directory != self.root_directory:
            structure += "."
        structure += "\n"

        # List first level directories and files
        items = os.listdir(directory)
        items.sort()  # Sort items for consistent output

        for item in items:
            if item.startswith("."):
                continue
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                structure += f"└── {item}\n"
                subdirectory_contents = os.listdir(item_path)
                subdirectory_contents.sort()  # Sort subdirectory contents
                for index, subitem in enumerate(subdirectory_contents):
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path):
                        prefix = (
                            "    └── "
                            if index == len(subdirectory_contents) - 1
                            else "    ├── "
                        )
                        structure += f"{prefix}{subitem}/\n"
                    else:
                        prefix = (
                            "    └── "
                            if index == len(subdirectory_contents) - 1
                            else "    ├── "
                        )
                        structure += f"{prefix}{subitem}\n"
            else:
                structure += f"└── {item}\n"

        return structure.strip()
