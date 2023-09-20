## This file describes how much it costs (in tokens) to send a request to OPENAI API.

### Key findings:
- We have two functions and one system prompt we send to the model. This results in ~80-100 tokens per request. The second
response is little cheaper, because we don't need to sent the function definitons. 
- Currently there are only two functions, not sure how much a function would cost to send to GPT.

- I am giving gpt a simple page content as a system message. It can be sometimes a little misleading. For example, if
there is a text element in the page and you misspell it, gpt might and might not find it. Sometimes it corrects the word,
sometimes it doesn't. Investigating...