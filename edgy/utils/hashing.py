from __future__ import annotations

from base64 import b32encode
from hashlib import blake2b


def hash_to_identifier(key: str | bytes) -> str:
    """
    A generic hasher for keys, which output stays a valid name for python
    and other languages.
    It is NOT supposed for the use in security critical contexts.

    It is for shortening and flattening known names and urls like database names or database urls or pathes.

    See edgy/cli/templates/default/script.py or edgy/core/db/querysets/base.py for the usage.
    """
    if isinstance(key, str):
        key = key.encode()
    # prefix with _ for preventing a name starting with a number
    # Note: the prefixing with underscore is expected by migrations
    return f"_{b32encode(blake2b(key, digest_size=16).digest()).decode().rstrip('=')}"


# for migrations, so the function can be changed in future
# needs however either python 3.10 or from __future__ import annotations
hash_to_identifier_as_string: str = """
def hash_to_identifier(key: str | bytes) -> str:
    from base64 import b32encode
    from hashlib import blake2b
    if isinstance(key, str):
        key = key.encode()
    return f"_{b32encode(blake2b(key, digest_size=16).digest()).decode().rstrip('=')}"
"""
