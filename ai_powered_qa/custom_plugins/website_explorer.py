from openai import OpenAI
from pydantic import PrivateAttr

from ai_powered_qa.components.plugin import Plugin, tool


class WebsiteExplorer(Plugin):
    name: str = "WebsiteExplorer"
    _client: OpenAI = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._client = OpenAI()

    @tool
    def find_element_to_perform_action(self, action_description: str, html: str):
        """
        Returns a list elements in a given piece of HTML that are best suited to peform
        a given action described by the user, for example: "which element would help me
        reject cookies"

        :param str action_description: A natural language description of the action
        :param str html: A piece of HTML to search through
        """

        system_prompt = """
            Your goal is to explore HTML and suggest Playwright compatible 
            element selectors to interact with to achieve a goal described 
            by the user. If possible, always list multiple candidates.

            Example 1:

            HTML:
            ```
            <form>
            <input type="text" name="username">
            </form>
            ```

            USER:
            Which field represents the username input

            ANSWER:
            input[name="username"]

            Example 2:

            HTML:
            <ul>
            <li><a href="/">Main page</a></li>
            <li><a href="/contact">Contact</a></li>
            <li><a href="/products">Products</a></li>
            </ul>

            USER:
            I want a link to the products page

            ANSWER:
            a[href="/products"]

            Example 3:

            HTML:
            <div data-testid="article-text-input">
            <textarea></textarea>
            </div>

            USER:
            I want the article text input field:

            ANSWER:
            div[data-testid="article-text-input"] > textarea
        """

        user_prompt = f"""
            Description: {action_description}

            {html}
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = self._client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.0,
        )

        return completion.choices[0].message.content
