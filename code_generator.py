import argparse
import json


class LangHandler:
    def __init__(self, file_path, language):
        self.file_path = file_path
        self.language = language

        self.tools = {
            "navigate_browser": self.navigate_browser,
            "click_element": self.click_element,
            "click_by_text": self.click_by_text,
            "expect_test_id": self.expect_test_id,
            "expect_text": self.expect_text,
            "fill_element": self.fill_element
        }

    # File handling
    def write_to_file(self, command: str, overwrite: bool = False) -> None:
        with open(self.file_path, 'w' if overwrite else 'a') as f:
            f.write(command)

    def write_test_code(self, command: str) -> None:
        self.write_to_file(command=f"    {command}")

    def write_test_header(self) -> None:
        pass

    def write_test_footer(self) -> None:
        pass

    # Tools
    def navigate_browser(self, arguments: dict) -> None:
        pass

    def click_element(self, arguments: dict) -> None:
        pass

    def click_by_text(self, arguments: dict) -> None:
        pass

    def expect_test_id(self, arguments: dict) -> None:
        pass

    def expect_text(self, arguments: dict) -> None:
        pass

    def fill_element(self, arguments: dict) -> None:
        pass


class PlaywrightHandler(LangHandler):
    def __init__(self, file_path, language):
        super().__init__(file_path, language)
        self.file_path = file_path.replace(".json", ".ts")

    # File handling
    def write_test_header(self) -> None:
        command = (f"import {{ test, expect }} from '@playwright/test';\n\n"
                   f"  test('Generated test', async ({{ page }}) => {{\n")
        self.write_to_file(command=command, overwrite=True)

    def write_test_footer(self) -> None:
        self.write_to_file(command="});\n\n")

    # Tools
    def navigate_browser(self, arguments: dict) -> None:
        address = arguments["url"]

        playwright_cmd = f"await page.goto('{address}');\n"
        self.write_test_code(command=playwright_cmd)

    def click_element(self, arguments: dict) -> None:
        selector = arguments["selector"]
        index = f" >> nth={arguments['index']}" if arguments.get("index") is not None else ""

        playwright_cmd = f"await page.click(\"{selector}{index}\");\n"
        self.write_test_code(command=playwright_cmd)

    def click_by_text(self, arguments: dict) -> None:
        text = arguments["text"]
        index = f".nth({arguments['index']})" if arguments.get("index") is not None else ""

        playwright_cmd = f"await page.getByText('{text}'){index}.click();\n"
        self.write_test_code(command=playwright_cmd)

    def expect_test_id(self, arguments: dict) -> None:
        test_id = arguments["test_id"]

        playwright_cmd = f"await expect(page.getByTestId(/{test_id}/)).toBeVisible();\n"
        self.write_test_code(command=playwright_cmd)

    def expect_text(self, arguments: dict) -> None:
        text = arguments["text"]
        index = f".nth({arguments['index']})" if arguments.get("index") is not None else ""

        playwright_cmd = f"await expect(page.getByText(/{text}/){index}).toHaveText(/{text}/);\n"
        self.write_test_code(command=playwright_cmd)

    def fill_element(self, arguments: dict) -> None:
        selector = arguments["selector"]
        text = arguments["text"]

        playwright_cmd = f"await page.locator(\"{selector}\").fill('{text}');\n"
        self.write_test_code(command=playwright_cmd)


class CypressHandler(LangHandler):
    def __init__(self, file_path, language):
        super().__init__(file_path, language)
        self.file_path = file_path.replace(".json", ".cy.js")

    # File handling
    def write_test_header(self) -> None:
        command = (f"describe('Generated test', () => {{\n  "
                   f"it('test scenario', () => {{\n")
        self.write_to_file(command=command, overwrite=True)

    def write_test_footer(self) -> None:
        self.write_to_file(command="  })\n})")

    # Tools
    def navigate_browser(self, arguments: dict) -> None:
        address = arguments["url"]

        command = f"cy.visit('{address}');\n"
        self.write_test_code(command=command)

    def click_element(self, arguments: dict) -> None:
        selector = arguments["selector"]
        index = f"eq({arguments['index']})" if arguments.get("index") is not None else ""

        command = f"cy.get('{selector}'){index}.click();\n"
        self.write_test_code(command=command)

    def click_by_text(self, arguments: dict) -> None:
        text = arguments["text"]
        index = f".eq({arguments['index']})" if arguments.get("index") is not None else ""

        command = f"cy.contains('{text}'){index}.click();\n"
        self.write_test_code(command=command)

    def expect_test_id(self, arguments: dict) -> None:
        test_id = arguments["test_id"]

        command = f"cy.get('[data-testid=/{test_id}/]').should('be.visible');\n"
        self.write_test_code(command=command)

    def expect_text(self, arguments: dict) -> None:
        text = arguments["text"]
        index = f".eq({arguments['index']})" if arguments.get("index") is not None else ""

        command = f"cy.contains(/{text}/){index}.should('have.text', '{text}');\n"
        self.write_test_code(command=command)

    def fill_element(self, arguments: dict) -> None:
        selector = arguments["selector"]
        text = arguments["text"]

        command = f"cy.get('{selector}').type('{text}');\n"
        self.write_test_code(command=command)


def load_json_conversation(file_path: str) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test code from conversation history")
    parser.add_argument("-f", "--file_path", help="Specify json conversation history file path.", dest="file_path",
                        required=True, action="store")
    parser.add_argument("-l", "--language", help="Specify language of generated code. Default is playwright",
                        dest="language", default="playwright")

    args = parser.parse_args()
    conversation_file = args.file_path
    lang = args.language

    languages = {"playwright": PlaywrightHandler, "cypress": CypressHandler}
    messages = load_json_conversation(file_path=conversation_file)

    handler = languages[lang](file_path=conversation_file, language=lang)  # e.g. handler = CypressHandler()
    handler.write_test_header()

    for message in messages:
        try:
            tool = handler.tools[message["additional_kwargs"]["function_call"]["name"]]
            tool(arguments=json.loads(message["additional_kwargs"]["function_call"]["arguments"]))
        except KeyError:
            pass

    handler.write_test_footer()
    print(f"Code generated into: {handler.file_path}")
