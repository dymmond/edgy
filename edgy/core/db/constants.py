CASCADE = "CASCADE"
RESTRICT = "RESTRICT"
DO_NOTHING = "DO NOTHING"
SET_NULL = "SET NULL"
SET_DEFAULT = "SET DEFAULT"
PROTECT = "PROTECT"


class OLD_M2M_NAMING:
    """
    Placeholder class for indicating the old naming convention for many-to-many
    (M2M) relationships. This class does not contain any attributes or methods;
    it serves purely as a marker or type hint for configuration purposes.
    """


class NEW_M2M_NAMING:
    """
    Placeholder class for indicating the new naming convention for many-to-many
    (M2M) relationships. Similar to `OLD_M2M_NAMING`, this class is an empty
    marker used for configuration or type hinting to distinguish between
    different M2M naming strategies.
    """


class ConditionalRedirect(dict):
    """
    A dictionary subclass used to represent a conditional redirect.
    This class is intended to hold data related to HTTP redirects that
    might depend on certain conditions. It inherits from `dict` and
    can therefore store key-value pairs representing redirect parameters.
    """


__all__ = [
    "CASCADE",
    "RESTRICT",
    "DO_NOTHING",
    "SET_NULL",
    "SET_DEFAULT",
    "PROTECT",
    "ConditionalRedirect",
]
