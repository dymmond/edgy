"""
Client to interact with Edgy models and migrations.
"""

import sayer

from edgy.cli.base import list_templates as template_list


@sayer.command
def list_templates() -> None:
    """
    Lists all the available templates available to Edgy
    """
    template_list()
