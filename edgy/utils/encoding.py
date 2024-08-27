from typing import Optional
from urllib.parse import quote


def filepath_to_uri(path: Optional[str]) -> str:
    """
    Convert a file system path to a URI portion suitable for inclusion in a URL.

    Encode certain characters that would normally be recognized as special characters
    for URIs. Do not encode the ' character, as it is a valid character
    within URIs. See the encodeURIComponent() JavaScript function for details.

    Args:
        path (str): The file system path to convert.

    Returns:
        str: The URI portion suitable for inclusion in a URL.
    """
    if not path:
        return ""
    return quote(str(path).replace("\\", "/"), safe="/~!*()'")
