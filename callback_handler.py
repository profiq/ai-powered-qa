import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from langchain.callbacks.base import AsyncCallbackHandler, BaseCallbackHandler
from langchain.callbacks import FileCallbackHandler
from langchain.schema.messages import BaseMessage
from langchain.schema.output import LLMResult
import json
import pprint
import os



class MyHandler(BaseCallbackHandler):

    def __init__(self, container, project, test_scenario) -> None:
        self.container = container
        self.empty = container.empty()
        self.status = None

        parent_folder = "callback_logs"
        if not os.path.exists(parent_folder):
            os.mkdir(parent_folder)
        child_folder = f"{project}_{test_scenario}"
        if not os.path.exists(child_folder):
            os.mkdir(child_folder)
        self.path_to_logs = f"{parent_folder}/{child_folder}"
        os.mkdir(f"{self.path_to_logs}")
        self.counter = 0




    def on_llm_end(self, response, run_id, parent_run_id, tags, **kwargs) -> None:
        llm_response = {"LLMResult": response}
        with open(f"{self.path_to_logs}/request_response_{self.counter}", "a") as f:
            pprint.pprint(llm_response, indent=4, stream=f)
        self.counter += 1
    def on_chat_model_start(self, serialized: Dict[str, Any], messages: List[List[BaseMessage]], *, run_id: UUID, parent_run_id: UUID | None = None, tags: List[str] | None = None, metadata: Dict[str, Any] | None = None, **kwargs: Any) -> Any:
        
        with open(f"{self.path_to_logs}/request_response_{self.counter}", "a") as f:
            request = {"serialized": serialized, "messages": messages, "run_id": run_id, "parent_run_id": parent_run_id, "tags": tags, "metadata": metadata, "kwargs": kwargs}
            pprint.pprint(request, indent=1, width=80, stream=f)

