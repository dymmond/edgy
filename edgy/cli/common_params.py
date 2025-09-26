from typing import Annotated

from sayer import Option

VerboseOption = Annotated[bool, Option(False, "-v", is_flag=True, help="Use more verbose output.")]
ForceNullFieldOption = Annotated[
    list[str],
    Option(
        (),
        "--nf",
        multiple=True,
        help='Force field being nullable. Syntax model:field or ":field" for auto-detection of models with such a field.',
    ),
]
SQLOption = Annotated[
    bool,
    Option(is_flag=True, help=("Don't emit SQL to database - dump to standard output instead.")),
]
