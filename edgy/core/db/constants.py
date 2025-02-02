CASCADE = "CASCADE"
RESTRICT = "RESTRICT"
DO_NOTHING = "DO NOTHING"
SET_NULL = "SET NULL"
SET_DEFAULT = "SET DEFAULT"
PROTECT = "PROTECT"


class OLD_M2M_NAMING: ...


class NEW_M2M_NAMING: ...


class ConditionalRedirect(dict): ...


__all__ = [
    "CASCADE",
    "RESTRICT",
    "DO_NOTHING",
    "SET_NULL",
    "SET_DEFAULT",
    "PROTECT",
    "ConditionalRedirect",
]
