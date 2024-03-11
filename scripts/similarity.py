from playwright.sync_api import Page, sync_playwright
import bs4
import difflib
import json
from ai_powered_qa.custom_plugins.playwright_plugin import clean_html
import openai

prompt_basis = (
    "Here is the HTML diff between two websites (what was added to the "
    "second website)Can you tell me whether they are functionally "
    "similar? (yes/no): \n\n"
)

html_cache = {}


def main():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    client = openai.Client()
    responses = []

    with open("./data/website_similarity.txt", "r") as f:
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            website1, website2, similarity = line.split(" ")
            html1 = get_html(page, website1).splitlines()
            html2 = get_html(page, website2).splitlines()
            diff = difflib.unified_diff(html1, html2, lineterm="")
            diff = "\n".join(d[1:].strip() for d in diff if d.startswith("+"))
            record = {
                "prompt": prompt_basis
                + "Website URL 1: "
                + website1
                + "\nWebsite URL 2: "
                + website2
                + "\n\nDiff:\n\n"
                + diff[:4800]
                + "\n\nAnswer: ",
                "completion": similarity,
            }
            #print(json.dumps(record))
            response = client.completions.create(
                model="ft:babbage-002:profiq:htmldiff:90Un4ZTL",
                prompt=record["prompt"],
                max_tokens=10,
                temperature=0.0,
            )
            print(response.choices[0].text)
            response = "yes" if "yes" in response.choices[0].text.lower() else "no"
            print(response, record["completion"])
            responses.append(1 if response == record["completion"] else 0)
            print("Success rate:", sum(responses) / len(responses))

    playwright.stop()


def get_html(page: Page, url: str) -> str:
    if url not in html_cache:
        page.goto(url)
        html = page.content()
        soup = bs4.BeautifulSoup(html, "html.parser")
        clean_html.clean_attributes(soup)
        clean_html.remove_useless_tags(soup)
        html_cache[url] = soup.get_text()
    return html_cache[url]


if __name__ == "__main__":
    main()
