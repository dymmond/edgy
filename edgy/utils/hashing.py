from base64 import b32encode
from hashlib import blake2b


def hash_to_identifier(key: str) -> str:
    """
    A generic hasher for keys, which output stays a valid name for python
    and other languages.
    It is NOT supposed for the use in security critical contexts.

    It is for shortening and flattening known names and urls like database names or database urls or pathes.

    See edgy/cli/templates/default/script.py or edgy/core/db/querysets/base.py for the usage.
    """
    # prefix with _ for preventing a name starting with a number
    return f"_{b32encode(blake2b(key.encode(), digest_size=16).digest()).decode().rstrip('=')}"
