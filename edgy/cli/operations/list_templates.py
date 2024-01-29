"""
Client to interact with Edgy models and migrations.
"""

import click

from edgy.cli.base import list_templates as template_list


@click.command(name="list-templates")
def list_templates() -> None:
    """
    Lists all the available templates available to Edgy
    """
    template_list()
