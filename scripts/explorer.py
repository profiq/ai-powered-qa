from dataclasses import asdict, dataclass, field
from inspect import cleandoc
import json
import logging
import random
import time

import numpy as np
from openai import OpenAI
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
import yaml

from ai_powered_qa.custom_plugins.playwright_plugin.html_paging import (
    PlaywrightPluginHtmlPaging,
)


@dataclass
class Website:
    urls: list[str]
    title: str
    parts_description: dict
    embedding: np.ndarray
    actions: list[dict] = field(default_factory=list)
    from_websites: list[int] = field(default_factory=list)


logging.basicConfig(level=logging.INFO)


def accept_cookies_if_present(client: OpenAI, plugin: PlaywrightPluginHtmlPaging):
    html = plugin._run_async(plugin._get_page_content())
    _, no_parts = plugin._get_html_part(html)

    prompt_has_cookies = """
        You are an expert on HTML. You are given a website HTML and you are
        asked to check if the website shows a cookie consent banner.

        Here is the current HTML:

        ----- HTML START -----
        {html_part}
        ----- HTML END -----

        Does the website show a cookie consent banner? Answer with 'yes' or 'no'.
    """

    for i in range(1, no_parts + 1):
        plugin._part = i
        html_part, _ = plugin._get_html_part(html)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "user",
                    "content": prompt_has_cookies.format(html_part=html_part),
                }
            ],
            temperature=0.1,
        )
        response = completion.choices[0].message.content
        if response and "yes" in response.lower():
            logging.info("Website has cookies.")
            execute_action(
                client, plugin, "Click on the buttom for accepting cookies", i
            )
            break


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def find_similar(websites: list[Website], current: Website) -> Website | None:
    similarities = [cosine_similarity(w.embedding, current.embedding) for w in websites]
    logging.info(current.urls[0])
    for i, sim in enumerate(similarities):
        logging.info(f"Similarity with {websites[i].urls[0]}: {sim}")
    max_similarity_idx = np.argmax(similarities)
    max_similarity = similarities[max_similarity_idx]
    if max_similarity > 0.92:
        return websites[max_similarity_idx]
    return None


def describe_html(client: OpenAI, plugin: PlaywrightPluginHtmlPaging) -> dict:
    html = plugin._run_async(plugin._get_page_content())
    title = plugin.title
    _, no_parts = plugin._get_html_part(html)
    full_description = {}

    prompt_description = cleandoc(
        """
        Analyze the following HTML and provide a specific and  extensive 
        description of its contents. Imagine you are describing the page
        to a person who cannot see it.

        Describe each main section (for example main menu, search, footer, filters) 
        of the subpage. The description of each section should list interactive 
        elements, such as links, buttons or forms. It should also explain the specific purpose of
        the page and its content. When describing the content, think about
        the specific subpage you are visiting instead the whole web portal.
        
        Each element should be represented by a separate record:

        INCORRECT EXAMPLE:
        Links to specific categories like 'Oblíbené inzeráty', 'Moje inzeráty', and 'Přidat inzerát'

        CORRECT EXAMPLE:
        A link to the user's favorite ads
        A link to the user's ads
        A link to the form for adding a new ad

        On the other hand, avoid being too specific, describe the purpose of the element 
        instead of its specific content.

        CORRECT EXAMPLE:
        Link to an external article
        Link to a login form
        Link to FAQ
        Link to a category
        Link to a product page
        Link to shopping cart
        Location input
        Language switcher

        Title: {title}

        {html}
        """
    )

    describe_function: ChatCompletionToolParam = {
        "type": "function",
        "function": {
            "name": "describe_html",
            "description": "Describe the subpage from its HTML",
            "parameters": {
                "type": "object",
                "properties": {
                    "basic_purpose": {
                        "type": "string",
                        "description": "Top level description of the subpage's purpose. E.g. 'This is a form for adding a new user'",
                    },
                    "sections": {
                        "type": "array",
                        "description": "List of sections on the page. E.g. 'A list of products', 'A form for adding a new user'",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": "Description of the section. E.g. 'A list of products'",
                                },
                                "interactive_elements": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {
                                                "type": "string",
                                                "description": "Type of the interactive element. E.g. 'link', 'button'",
                                            },
                                            "description": {
                                                "type": "string",
                                                "description": "Description of the interactive element. E.g. 'A link to the homepage'",
                                            },
                                        },
                                        "required": ["type", "description"],
                                    },
                                    "description": "List of interactive elements on the page. E.g. 'A link to the homepage'",
                                },
                            },
                        },
                    },
                },
                "required": ["basic_purpose", "sections"],
            },
        },
    }

    for i in range(1, no_parts + 1):
        plugin._part = i
        html_part, _ = plugin._get_html_part(html)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "user",
                    "content": prompt_description.format(title=title, html=html_part),
                }
            ],
            tools=[describe_function],
            temperature=0.05,
            tool_choice={"type": "function", "function": {"name": "describe_html"}},
        )

        tool_calls = completion.choices[0].message.tool_calls
        if tool_calls and len(tool_calls) > 0:
            description = json.loads(tool_calls[0].function.arguments)
            if description:
                full_description[i] = description

    return full_description


def description_to_string(description: dict) -> str:
    description_text = ""

    for part, desc in description.items():
        description_text += f"Part {part}:\n"
        description_text += description_part_to_string(desc)
        description_text += "\n\n"

    return description_text


def description_part_to_string(description: dict) -> str:
    description_parts = ["Basic purpose: " + description["basic_purpose"]]

    for section in description["sections"]:
        elements = "\n".join(
            f"{e['type']}: {e['description']}" for e in section["interactive_elements"]
        )
        description_parts.append(
            cleandoc(
                """
                Section: {description}

                Interactive elements: 
                {elements}
                """
            ).format(description=section["description"], elements=elements)
        )

    return "\n\n".join(description_parts)


def execute_action(
    client: OpenAI, plugin: PlaywrightPluginHtmlPaging, action: str, part: int = 1
):
    plugin.move_to_html_part(part)
    prompt_execute = cleandoc(
        f"""
        You are an expert on executing action on the web. You are given
        a website HTML, it's short text description and an action to perform.
        You can execute a sequence of multiple actions if needed.

        If a login is required, please use the following credentials:
        username: 
        password: 

        If a tool requires a selector, the selector has to be
        compatible with Playwright and the element should be present
        in HTML.

        Here is the current context:

        {plugin.context_message}

        The recommended action is:

        {action}
        """
    )

    plugin.move_to_html_part(1)

    messages = [
        {"role": "system", "content": plugin.system_message},
        {"role": "user", "content": prompt_execute},
    ]

    while True:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=messages,
            tools=plugin.tools,
            temperature=0.1,
        )

        tool_calls = completion.choices[0].message.tool_calls
        messages.append(completion.choices[0].message)
        if tool_calls and len(tool_calls) > 0:
            for tool_call in tool_calls:
                tool_to_call = tool_call.function
                tool_name = tool_to_call.name
                tool_args = json.loads(tool_to_call.arguments)
                logging.info(
                    f"Executing tool: {tool_name} with arguments: {tool_args}, html part: {part}"
                )
                plugin.call_tool(tool_name, **tool_args)
                messages.append(
                    {
                        "role": "tool",
                        "content": "OK",
                        "tool_call_id": tool_call.id,
                    }
                )
        else:
            break


def main():
    websites_visited: list[Website] = []
    domain = "news.ycombinator.com"
    start_url = f"https://{domain}"

    client = OpenAI()
    plugin = PlaywrightPluginHtmlPaging(name="playwright", client=client)
    plugin.navigate_to_url(start_url)
    time.sleep(2)
    accept_cookies_if_present(client, plugin)
    action_status = "failure"

    for _ in range(15):
        time.sleep(2)
        plugin._part = 1
        html = plugin.html
        title = plugin.title
        url = plugin._page.url if plugin._page else None

        if not url:
            logging.info("No URL found. Navigating back to the start")
            plugin.navigate_to_url(start_url)
            website_current = None
            continue

        if url and domain not in url:
            logging.info(f"Left the domain of {domain}. Navigating back to the start")
            plugin.navigate_to_url(start_url)
            website_current = None
            continue

        website_previous_id = None

        for i, w in enumerate(websites_visited):
            if w == website_current:
                website_previous_id = i
                break

        website_current = get_website_by_url(websites_visited, url)

        if website_current:
            logging.info(f"Already visited website: {url}")
        else:
            description = describe_html(client, plugin)
            description_text = description_to_string(description)
            logging.info(f"Description generated:\n {description_text}")
            response = client.embeddings.create(
                model="text-embedding-3-small", input=html
            )
            embedding = np.array(response.data[0].embedding)
            website_current = Website(
                [url] if url else [], title, description, embedding
            )

            if len(websites_visited) == 0:
                websites_visited.append(website_current)
            else:
                website_similar = find_similar(websites_visited, website_current)
                if website_similar:
                    logging.info(f"Found similar website: {website_similar.urls[0]}")
                    website_current = website_similar
                    if url and url not in website_current.urls:
                        website_current.urls.append(url)
                else:
                    websites_visited.append(website_current)

        if (
            website_previous_id is not None
            and website_previous_id not in website_current.from_websites
            and action_status == "success"
        ):
            website_current.from_websites.append(website_previous_id)

        if len(website_current.actions) == 0:
            try:
                website_current.actions = get_action_recommendations(
                    client, website_current
                )
            except ValueError as e:
                logging.info(f"No action recommendations: {e}")
                plugin.navigate_to_url(start_url)
                continue

        actions_to_recommend = [a for a in website_current.actions if "status" not in a]
        recommendation = random.choice(actions_to_recommend)
        part = recommendation["part"]
        logging.info(f"Recommended action: {recommendation['description']}")

        execute_action(client, plugin, recommendation["description"], part)
        action_status = "success" if plugin.html != html else "failure"
        logging.info(f"Action status: {action_status}")
        recommendation["status"] = action_status

    plugin.close()
    print("Exploration finished.")
    print("Websites visited:")

    for w in websites_visited:
        w_dict = asdict(w)
        del w_dict["embedding"]
        print(yaml.dump(w_dict))
        print("--------")

    print("digraph G {")
    for i, w in enumerate(websites_visited):
        print(f'w_{i} [label="{w.urls[0]}"];')

    for i, w in enumerate(websites_visited):
        for j in w.from_websites:
            print(f"w_{j} -> w_{i};")
    print("}")


def get_website_by_url(websites: list[Website], url: str) -> Website | None:
    for w in websites:
        if url in w.urls:
            return w
    return None


def get_action_recommendations(client: OpenAI, website: Website) -> list[dict]:
    prompt_recommend = cleandoc(
        f"""
        You are a web crawler. Your goal is to analyze the textual 
        description of a webpage provided to you and recommend a next 
        action to perform or a sequence of actions that need to be executed
        together. Choose actions that maximize learning new things about
        the website.

        Here are some examples of good recommendation:
        - Login with username and password
        - Search for a MacBook
        - Switch to a different city
        - Visit a 'PC' category
        - Add the item to the cart
        - Send a contact form with a sample question

        You only have access to following tools:
        - Click on a link or button
        - Login with username and password
        - Fill and submit a whole form at once

        Only consider elements listed in the description of the current page.

        Here is the textual description of the current page:

        URL: {website.urls[0]}
        Title: {website.title}

        {description_to_string(website.parts_description)}

        Please recommend up to 5 actions or sequences of actions to perform next 
        and explain the reasoning behind your recommendation.
        """
    )

    recommend_actions_tool: ChatCompletionToolParam = {
        "type": "function",
        "function": {
            "name": "recommend_actions",
            "description": "Recommend actions to perform next",
            "parameters": {
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": "Recommended action or sequence of actions to perform next",
                                },
                                "part": {
                                    "type": "number",
                                    "description": "Part of the HTML to which the action is related",
                                },
                            },
                            "required": ["description", "part"],
                        },
                    }
                },
            },
        },
    }

    completion = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": prompt_recommend}],
        tools=[recommend_actions_tool],
        temperature=0.1,
        tool_choice={"type": "function", "function": {"name": "recommend_actions"}},
    )

    tool_calls = completion.choices[0].message.tool_calls
    if not tool_calls or len(tool_calls) == 0:
        raise ValueError("No recommendation tool called.")

    recommendations = json.loads(tool_calls[0].function.arguments)

    if "actions" not in recommendations or len(recommendations["actions"]) == 0:
        raise ValueError("No recommendations generated")

    return recommendations["actions"]


if __name__ == "__main__":
    main()
