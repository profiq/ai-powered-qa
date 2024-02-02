from pydantic import BaseModel

from ai_powered_qa.components.plugin import Plugin, tool


class MemoryRecord(BaseModel):
    memory_type: str
    page: str
    contents: str


class MemoryPlugin(Plugin):
    name: str = "MemoryPlugin"
    memory_records: list[MemoryRecord] = []

    def __init__(self, **data):
        super().__init__(**data)

    @property
    def system_message(self) -> str:
        return "You can store memories of your experiences."

    @property
    def context_message(self) -> str:
        memories_output = ["YOUR MEMORIES (ID - TYPE (PAGE): CONTENTS):"]
        for i, memory in enumerate(self.memory_records):
            memories_output.append(
                f"{i} - {memory.memory_type} ({memory.page}):\n{memory.contents}\n"
            )
        return "\n".join(memories_output)

    @tool
    def save_memory(self, memory_type: str, page: str, contents: str):
        """
        Saves a new memory record.

        :param str memory_type: The type of memory to save, for example "task" or "elements"
        :param str page: The page where the memory was created, for example "Search results"
        :param str contents: The contents of the memory, for example "I can perform search here"
        """
        self.memory_records.append(
            MemoryRecord(memory_type=memory_type, page=page, contents=contents)
        )
        return "Memory saved!"
