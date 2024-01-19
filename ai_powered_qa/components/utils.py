import hashlib
import random
import string
import tiktoken


def generate_short_id():
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(6))


def md5(input_string: str) -> str:
    """Generate an MD5 hash for a given input string."""
    return hashlib.md5(input_string.encode()).hexdigest()


def count_tokens(text: str, model: str) -> int:
    """
    We use this mainly when pruning history to ensure that we don't go over the
    token limit
    """
    enc = tiktoken.encoding_for_model(model)
    text_encoded = enc.encode(text)
    return len(text_encoded)
