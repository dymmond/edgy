from typing import TYPE_CHECKING, Any, Dict, Tuple, Type, Union

from pydantic import ConfigDict

from edgy.core.utils.models import create_edgy_model

if TYPE_CHECKING:
    from edgy import Model
    from edgy.core.db.models.metaclasses import MetaInfo


class ProxyModel:
    """
    When a model needs to be mirrored without affecting the
    original, this instance is triggered instead.
    """

    __name__: str
    __module__: str
    __bases__: Union[Tuple[Type["Model"]], None]
    __definitions__: Union[Dict[Any, Any], None]
    __metadata__: Union[Type["MetaInfo"], None]
    __qualname__: Union[str, None]
    __config__: Union[ConfigDict, None]
    __proxy__: bool = False
    __pydantic_extra__: Union[Any, None]

    def __init__(
        self,
        name: str,
        module: str,
        *,
        bases: Union[Tuple[Type["Model"]], None] = None,
        definitions: Union[Dict[Any, Any], None] = None,
        metadata: Union[Type["MetaInfo"], None] = None,
        qualname: Union[str, None] = None,
        config: Union[ConfigDict, None] = None,
        proxy: bool = False,
        pydantic_extra: Union[Any, None] = None,
    ) -> None:
        self.__name__ = name
        self.__module__ = module
        self.__bases__ = bases
        self.__definitions__ = definitions
        self.__metadata__ = metadata
        self.__qualname__ = qualname
        self.__config__ = config
        self.__proxy__ = proxy
        self.__pydantic_extra__ = pydantic_extra

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return create_edgy_model(
            __name__=self.__name__,
            __module__=self.__module__,
            __bases__=self.__bases__,
            __definitions__=self.__definitions__,
            __metadata__=self.__metadata__,
            __qualname__=self.__qualname__,
            __config__=self.__config__,
            __proxy__=self.__proxy__,
            __pydantic_extra__=self.__pydantic_extra__,
        )

    def __repr__(self) -> str:
        name = f"Proxy{self.__name__}"
        return f"<{name}: [{self.__definitions__}]"
