import hashlib
import random
import string


def generate_short_id():
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(6))


def md5(input_string: str) -> str:
    """Generate an MD5 hash for a given input string."""
    return hashlib.md5(input_string.encode()).hexdigest()
