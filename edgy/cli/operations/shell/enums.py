from enum import Enum


class ShellOption(str, Enum):
    IPYTHON = "ipython"
    PTPYTHON = "ptpython"
    PYTHON = "python"
