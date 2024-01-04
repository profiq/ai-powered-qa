import asyncio

from openai import OpenAI

from ai_powered_qa.components import function_caller

client = OpenAI()
use_tools = True


class Assistant:
    """Useful links: https://platform.openai.com/docs/assistants/overview"""
    id = "asst_flOvo3QENM8COVXuij2lGaeB"


def get_new_assistant():
    """"""
    return client.beta.assistants.create(
        name="QA_assistant",
        instructions="You are a QA engineer controlling a browser. Your goal is to plan and go through a test scenario.",
        tools=function_caller.get_function_list_for_assistant() if use_tools else "",
        model="gpt-3.5-turbo-1106"
    )


def get_existed_assistant():
    return Assistant()


async def call_llm(assistant_id: str, thread_id: str, browser):
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=""
    )

    while run.status != 'completed':
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
        if run.status == "requires_action":

            for action in run.required_action.submit_tool_outputs.tool_calls:
                await function_caller.call_function(json_function=action.function, browser=browser)

            outputs = [
                        {
                            "tool_call_id": action.id,
                            "output": "done_exec",
                        } for action in run.required_action.submit_tool_outputs.tool_calls
            ]

            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=outputs
            )
    response = (client.beta.threads.messages.list(
        thread_id=thread_id
    ))

    for data in response.data:
        for content in data.content:
            print(content.text.value)


async def add_new_message(assistant_id: str, message: str, thread_id: str, browser):
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message
    )

    await call_llm(assistant_id=assistant_id, thread_id=thread_id, browser=browser)


async def run_assistant():
    thread = client.beta.threads.create()
    assistant = get_existed_assistant()

    browser = await function_caller.get_browser()

    await add_new_message(assistant_id=assistant.id,
                          message="Go to https://dev.app.serenityapp.com",
                          thread_id=thread.id,
                          browser=browser)

    await add_new_message(assistant_id=assistant.id,
                          message=f"based on the page content: {await function_caller.get_context_message(browser)} sign in with credentials email: pmanak-kirk.4008391697028023@dispostable.com and password: 'Serenity!' and click Sign-In",
                          thread_id=thread.id,
                          browser=browser)

    await add_new_message(assistant_id=assistant.id,
                          message=f"Propose some test cases based on the page content: {await function_caller.get_context_message(browser)}",
                          thread_id=thread.id,
                          browser=browser)


if __name__ == "__main__":
    asyncio.run(run_assistant())
