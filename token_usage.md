## This file describes how much it costs (in tokens) to send a request to OPENAI API.

### Key findings:
- We have two functions and one system prompt we send to the model. This results in ~80-100 tokens per request. The second
response is little cheaper, because we don't need to sent the function definitons. 
- Currently there are only two functions, not sure how much a function would cost.