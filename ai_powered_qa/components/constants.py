llm_models = ["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4"]
function_call_defaults = ["auto", "none"]


MODEL_TOKEN_LIMITS = {
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-3.5-turbo-1106": 16385,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-1106-preview": 128000,
}
