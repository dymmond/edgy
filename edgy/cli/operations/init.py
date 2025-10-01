from typing import Annotated

import sayer

from edgy.cli.base import init as _init
from edgy.cli.common_params import DirectoryOption


@sayer.command
def init(
    template: Annotated[
        str,
        sayer.Option("default", "-t", help='Repository template to use (default is "default")'),
    ],
    package: Annotated[
        bool,
        sayer.Option(
            False,
            is_flag=True,
            help="Write empty __init__.py files to the environment and version locations",
        ),
    ],
    directory: DirectoryOption,
) -> None:
    """Creates a new migration repository."""
    _init(template, package)
