import pathlib
import sys
import typing
from dataclasses import dataclass

import edgedb
from edgedb.con_utils import find_edgedb_project_dir

from edgy.core.terminal import Print

printer = Print()


@dataclass
class EdgyProject:
    """
    Loads an arbitraty application into the object
    and returns the App.
    """

    project_dir: typing.Optional[str] = None

    def find_edgedb_project(self) -> str:
        """Looks up in the root where the project is located
        and tries to find an edge db project
        """
        try:
            project_dir = pathlib.Path(find_edgedb_project_dir())
        except edgedb.ClientConnectionError:
            printer.write_error(
                "Cannot find edgedb.toml: Edgy must be under an EdgeDB project directory."
            )
            sys.exit(1)
        return EdgyProject(project_dir=project_dir)
