import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema.messages import BaseMessage
import os
import pickle

from langchain.schema.output import LLMResult


class LoggingHandler(BaseCallbackHandler):

    def __init__(self, project, test_scenario) -> None:
        logs_folder = "openai_request_logs"
        project_folder = f"{project}"
        test_folder = f"{test_scenario}"
        self.log_file_name = "request_"

        if not os.path.exists(logs_folder):
            os.mkdir(logs_folder)
        self.path_to_logs = f"{logs_folder}/{project_folder}/{test_folder}"

        if os.path.exists(self.path_to_logs):
            time = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
            self.path_to_logs += f"_{time}"
        os.makedirs(f"{self.path_to_logs}")
        self.counter = 0

    def on_chat_model_start(self,
                            serialized: Dict[str, Any],
                            messages: List[List[BaseMessage]],
                            *,
                            run_id: UUID,
                            parent_run_id: UUID | None = None,
                            tags: List[str] | None = None,
                            metadata: Dict[str, Any] | None = None,
                            **kwargs: Any) -> Any:
        with open(f"{self.path_to_logs}/{self.log_file_name}{self.counter}", "ab") as f:
            request = {"serialized": serialized, "messages": messages, "run_id": run_id,
                       "parent_run_id": parent_run_id, "tags": tags, "metadata": metadata, "kwargs": kwargs}
            pickle.dump(request, f)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        llm_response = {"LLMResult": response, "kwargs": kwargs}
        with open(f"{self.path_to_logs}/{self.log_file_name}{self.counter}", "ab") as f:
            pickle.dump(llm_response, f)
        self.counter += 1
