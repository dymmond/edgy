from functools import cached_property
from typing import Dict, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class EdgySettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", ignored_types=(cached_property,))
    ipython_args: List[str] = ["--no-banner"]
    ptpython_config_file: str = "~/.config/ptpython/config.py"

    # General settings
    filter_operators: Dict[str, str] = {
        "exact": "__eq__",
        "iexact": "ilike",
        "contains": "like",
        "icontains": "ilike",
        "in": "in_",
        "gt": "__gt__",
        "gte": "__ge__",
        "lt": "__lt__",
        "lte": "__le__",
    }
    many_to_many_relation: str = "relation_{key}"
    dialects: Dict[str, str] = {"postgres": "postgres", "postgresql": "postgresql"}
