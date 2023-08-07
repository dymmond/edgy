from typing import Optional

from edgy import SaffierSettings
from edgy.conf.enums import EnvironmentType


class MyCustomSettings(SaffierSettings):
    """
    My settings overriding default values and add new ones.
    """

    environment: Optional[str] = EnvironmentType.TESTING

    # new settings
    my_new_setting: str = "A text"
