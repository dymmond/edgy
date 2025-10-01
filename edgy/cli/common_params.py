from typing import Annotated, Any

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
    Option(
        False, is_flag=True, help=("Don't emit SQL to database - dump to standard output instead.")
    ),
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
MessageOption = Annotated[str | None, Option(..., "-m", required=False, help="Revision message")]


def directory_callback(ctx: Any, param: str, value: str | None) -> None:
    import edgy

    if value is not None:
        edgy.settings.migration_directory = value


DirectoryOption = Annotated[
    None,
    Option(
        None,
        "-d",
        help=('Migration script directory (default is "migrations")'),
        expose_value=False,
        type=str | None,
        is_eager=True,
        callback=directory_callback,
    ),
]
