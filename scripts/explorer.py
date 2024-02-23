from dataclasses import dataclass, field
from inspect import cleandoc
import json
import logging

import numpy as np
from openai import OpenAI

from ai_powered_qa.custom_plugins.playwright_plugin.only_visible import (
    PlaywrightPluginOnlyVisible,
)


@dataclass
class Website:
    urls: list[str]
    title: str
    description: str
    embedding: np.ndarray
    actions: list[str] = field(default_factory=list)


logging.basicConfig(level=logging.INFO)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def find_similar(websites: list[Website], current: Website) -> Website | None:
    similarities = [cosine_similarity(w.embedding, current.embedding) for w in websites]
    max_similarity_idx = np.argmax(similarities)
    max_similarity = similarities[max_similarity_idx]
    if max_similarity > 0.91:
        return websites[max_similarity_idx]
    return None


def main():
    websites_visited: list[Website] = []

    client = OpenAI()
    plugin = PlaywrightPluginOnlyVisible(name="playwright", client=client)
    plugin.navigate_to_url("https://bazos.cz/")

    for _ in range(7):
        html = plugin.html
        url = plugin._page.url if plugin._page else None
        title = plugin.title

        prompt_description = cleandoc(
            f"""
            Analyze the following HTML and provide a specific and  extensive 
            description of its contents. Imagine you are describing the page
            to a person who cannot see it.

            The description should list interactive elements, such as links, 
            buttons or forms. It should also explain the specific purpose of
            the page and its content. When describing the content, think about
            the specific subpage you are visiting instead the whole web portal.
            
            Title: {title}

            {html}
            """
        )

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[{"role": "user", "content": prompt_description}],
            temperature=0.1,
        )

        description = completion.choices[0].message.content

        if not description:
            logging.error(f"No description generated for {url}")
            break

        logging.info(f"Description generated:\n {description}")

        response = client.embeddings.create(
            model="text-embedding-3-small", input=description
        )

        embedding = np.array(response.data[0].embedding)
        website_current = Website([url] if url else [], title, description, embedding)

        if len(websites_visited) > 0:
            website_similar = find_similar(websites_visited, website_current)
            if website_similar:
                logging.info(f"Found similar website: {website_similar.urls[0]}")
                website_current = website_similar
                if url and url not in website_current.urls:
                    website_current.urls.append(url)
            else:
                websites_visited.append(website_current)
        else:
            websites_visited.append(website_current)

        prompt_recommend = cleandoc(
            f"""
            You are a web crawler. Your goal is to analyze the textual 
            description of a webpage provided to you and recommend a next 
            action to perform to explore a given website further and learn
            about it as much as possible.

            You can perform one of the following actions:
            - Click on a link or button
            - Navigate to a URL - for example the previous one
            - Press Enter

            You are forbidden to leave the domain of the current website.

            Here is the textual description of the current page:

            URL: {url}
            Title: {title}

            {description}

            Here is the list of actions you have alread performed on
            this subpage, avoid repeating them:

            {str(website_current.actions)}

            Please recommend 3 actions to perform next and explain the
            reasoning behind your recommendation.
            """
        )

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[{"role": "user", "content": prompt_recommend}],
        )

        recommendation = completion.choices[0].message.content
        logging.info(f"Recommended actions: {recommendation}")

        prompt_execute = cleandoc(
            f"""
            You are an expert on executing action on the web. You are given
            a website HTML, it's short text description and a set of recommended
            actions to perform. Select one action randomly and perform it
            using available tools.

            Here is the list of actions you have alread performed on
            this subpage, avoid repeating them:

            {str(website_current.actions)}

            Here is the current context:

            {plugin.context_message}

            The recommended action is:

            {recommendation}
            """
        )

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": plugin.system_message},
                {"role": "user", "content": prompt_execute},
            ],
            tools=plugin.tools,
            temperature=0.2,
        )

        tool_calls = completion.choices[0].message.tool_calls
        if tool_calls and len(tool_calls) > 0:
            tool_to_call = tool_calls[0].function
            tool_name = tool_to_call.name
            tool_args = json.loads(tool_to_call.arguments)
            logging.info(f"Executing tool: {tool_name} with arguments: {tool_args}")
            plugin.call_tool(tool_name, **tool_args)
            website_current.actions.append(f"{tool_name} {tool_to_call.arguments}")

    plugin.close()
    print("Exploration finished.")
    print("Websites visited:")

    for w in websites_visited:
        print(w.urls)
        print(w.description)
        print(w.actions)
        print("--------")


if __name__ == "__main__":
    main()
