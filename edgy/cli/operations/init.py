import click

from edgy.cli.env import EdgyProject
from edgy.core.terminal import OutputColour, Print, Terminal

printer = Print()
writter = Terminal()


@click.command(name="init")
def init(project: EdgyProject) -> None:
    """Creates a new migration repository."""
    location = writter.write_info(project.project_dir, colour=OutputColour.BRIGHT_CYAN)
    message = f"Valid Edgy project. edgedb.toml found in: {location}"
    printer.write_success(message)
