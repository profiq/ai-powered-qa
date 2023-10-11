import argparse
import json


# File handling

def load_json_conversation(file_path: str) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


def write_test_header(file_path: str, language: str) -> None:
    if language == "playwright":
        with open(file_path, 'w') as f:
            f.write(f"import {{ test, expect }} from '@playwright/test';\n\n"
                    f"  test('Generated test', async ({{ page }}) => {{\n")


def write_test_code(file_path: str, language: str, code: str) -> None:
    if language == "playwright":
        with open(file_path, 'a') as f:
            f.write(f"    {code}")


def write_test_footer(file_path: str, language: str) -> None:
    if language == "playwright":
        with open(file_path, 'a') as f:
            f.write("});\n\n")


#   Tools functions
def navigate_browser(arguments: dict, language: str, file_path: str) -> None:
    address = arguments["url"]

    playwright_cmd = f"await page.goto('{address}');\n"
    write_test_code(file_path, language, playwright_cmd)


def click_element(arguments: dict, language: str, file_path: str) -> None:
    selector = arguments["selector"]
    index = f" >> nth={arguments['index']}" if arguments.get("index") is not None else ""

    playwright_cmd = f"await page.click(\"{selector}{index}\");\n"
    write_test_code(file_path, language, playwright_cmd)


def click_text(arguments: dict, language: str, file_path: str) -> None:
    text = arguments["text"]
    index = f".nth({arguments['index']})" if arguments.get("index") is not None else ""

    playwright_cmd = f"await page.getByText('{text}'){index}.click();\n"
    write_test_code(file_path, language, playwright_cmd)


def expect_test_id(arguments: dict, language: str, file_path: str) -> None:
    test_id = arguments["test_id"]

    playwright_cmd = f"await expect(page.getByTestId(/{test_id}/)).toBeVisible();\n"
    write_test_code(file_path, language, playwright_cmd)


def expect_text(arguments: dict, language: str, file_path: str) -> None:
    text = arguments["text"]
    index = arguments["index"] if arguments.get("index") is not None else ""

    playwright_cmd = f"await expect(page.getByText(/{text}/).nth({index})).toHaveText(/{text}/);\n"
    write_test_code(file_path, language, playwright_cmd)


def fill_element(arguments: dict, language: str, file_path: str) -> None:
    selector = arguments["selector"]
    text = arguments["text"]

    playwright_cmd = f"await page.locator(\"{selector}\").fill('{text}');\n"
    write_test_code(file_path, language, playwright_cmd)


tools = {
    "navigate_browser": navigate_browser,
    "click_element": click_element,
    "click_by_text": click_text,
    "expect_test_id": expect_test_id,
    "expect_text": expect_text,
    "fill_element": fill_element
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test code from conversation history")
    parser.add_argument("-f", "--file_path", help="Specify json conversation history file path.", dest="file_path",
                        required=True, action="store")
    parser.add_argument("-l", "--language", help="Specify language of generated code. Default is playwright",
                        dest="language", default="playwright")

    args = parser.parse_args()
    conversation_file = args.file_path
    lang = args.language

    generated_code_file = conversation_file.replace(".json", ".ts")

    messages = load_json_conversation(conversation_file)
    write_test_header(file_path=generated_code_file, language=lang)

    for msg in messages:
        try:
            tool = tools[msg["additional_kwargs"]["function_call"]["name"]]
            tool(json.loads(msg["additional_kwargs"]["function_call"]["arguments"]), args.language, generated_code_file)
        except KeyError:
            pass

    write_test_footer(file_path=generated_code_file, language=lang)
    print(f"Code generated into: {generated_code_file}")
