from typing import Optional

from edgy import EdgySettings
from ravyn.conf.enums import EnvironmentType


class MyCustomSettings(EdgySettings):
    """
    My settings overriding default values and add new ones.
    """

    environment: Optional[str] = EnvironmentType.TESTING

    # new settings
    my_new_setting: str = "A text"
