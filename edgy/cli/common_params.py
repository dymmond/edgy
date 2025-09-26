from typing import Annotated

from sayer import Argument, Option

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
RevisionHeadArgument = Annotated[str, Argument("head")]
TagOption = Annotated[
    str | None,
    Option(
        default=None,
        help=('Arbitrary "tag" name - can be used by custom env.py scripts.'),
    ),
]
ExtraArgOption = Annotated[
    list,
    Option((), "-x", multiple=True, help="Additional arguments consumed by custom env.py scripts"),
]
MessageOption = Annotated[str | None, Option(None, "-m", help="Revision message")]
