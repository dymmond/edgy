from __future__ import annotations

from base64 import b32encode
from hashlib import blake2b


def hash_to_identifier(key: str | bytes) -> str:
    """
    Generates a unique, short, and valid identifier from a given key (string or bytes).

    This function is designed for non-security-critical contexts where a
    consistent, compact, and language-friendly identifier is needed for
    internal naming conventions (e.g., database names, URLs, file paths).
    It is not suitable for cryptographic hashing or sensitive data.

    The identifier generated:
    -   Is unique for a given input key.
    -   Is short (fixed length due to `digest_size=16`).
    -   Starts with an underscore `_` to ensure it's a valid Python identifier
        and to prevent it from starting with a number.
    -   Uses Base32 encoding for a URL-safe and case-insensitive output.
    -   Removes padding characters (`=`) from the end for a cleaner look.

    Args:
        key (str | bytes): The input string or bytes to be hashed.

    Returns:
        str: A unique, valid identifier string.

    Examples:
        ```python
        hash_to_identifier("my_database_name")  # e.g., "_L5XQ2Z7OQYF..."
        hash_to_identifier(b"[http://example.com/api/v1/users](http://example.com/api/v1/users)")
        # e.g., "_K1N3Y2P0R2..."
        ```

    See `edgy/cli/templates/default/script.py` or `edgy/core/db/querysets/base.py` for typical usage.
    """
    # Ensure the key is in bytes format for hashing.
    if isinstance(key, str):
        key = key.encode()
    # calculate blake2b and b32 encode digest. Strip = afterwards
    return f"_{b32encode(blake2b(key, digest_size=16).digest()).decode().rstrip('=')}"


# This string representation of the function is kept for backward compatibility
# and for use in Edgy migrations, allowing the exact function logic to be
# embedded and potentially changed in future versions without breaking old migrations.
# It explicitly includes 'from __future__ import annotations' for compatibility
# with older Python versions that might not default to postponed evaluation of annotations.
hash_to_identifier_as_string: str = """
def hash_to_identifier(key: str | bytes) -> str:
    from base64 import b32encode
    from hashlib import blake2b
    if isinstance(key, str):
        key = key.encode()
    return f"_{b32encode(blake2b(key, digest_size=16).digest()).decode().rstrip('=')}"
"""
