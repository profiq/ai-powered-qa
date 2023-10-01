from typing import List, Type, cast

from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.tools.base import BaseTool
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.click import ClickTool
from .tools.playwright import *


class PlayWrightBrowserToolkit(PlayWrightBrowserToolkit):
    """Toolkit for PlayWright browser tools."""

    def get_tools(self) -> List[BaseTool]:
        # Add your tools here
        tool_classes: List[Type[BaseBrowserTool]] = [
            ClickTool,
            NavigateTool,
            # NavigateBackTool,
            # ExtractTextTool,
            # ExtractHyperlinksTool,
            # GetElementsTool,
            # CurrentWebPageTool,
            # ClickByTextTool,  # new actions
            # IframeClickTool,
            # IframeClickByTextTool,
            # IframeExpectHiddenTool,
            # IframeUploadTool,
            # ExpectTestIdTool,
            # ExpectTextTool,
            # ExpectTitleTool,
            FillTextTool,
            # TakeScreenshotTool,
            # PressTool,
            # WaitTool,
        ]

        tools = [
            tool_cls.from_browser(
                sync_browser=self.sync_browser, async_browser=self.async_browser
            )
            for tool_cls in tool_classes
        ]
        return cast(List[BaseTool], tools)
