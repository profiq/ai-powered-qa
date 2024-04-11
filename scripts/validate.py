import json
import openai

client = openai.Client()

responses = []

with open("data/website_similarity_chat_html_valid.jsonl") as f:
    for line in f:
        record = json.loads(line)
        response = client.chat.completions.create(
            model="ft:gpt-3.5-turbo-0125:profiq::91tEA8VU",
            max_tokens=10,
            messages=record["messages"][:1],
            temperature=0.0,
        )
        print(response.choices[0].message.content)
        response = (
            "yes" if "yes" in response.choices[0].message.content.lower() else "no"
        )
        print(response, record["messages"][1]["content"])
        responses.append(1 if response == record["messages"][1]["content"] else 0)
        print("Success rate:", sum(responses) / len(responses))
