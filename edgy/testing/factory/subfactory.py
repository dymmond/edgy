from typing import Any

import monkay

from edgy.testing import ModelFactory
from edgy.utils.compat import is_class_and_subclass


class SubFactory:
    def __init__(self, factory_class: Any, **kwargs: Any) -> None:
        """
        Initializes the SubFactory with a factory class and keyword arguments.

        Args:
            factory_class (Type[Any]): The factory class to use for building or creating instances.
            **kwargs (Any): Additional keyword arguments to pass to the factory class.
        """
        if isinstance(factory_class, str):
            factory_class = monkay.load(factory_class)

        if not is_class_and_subclass(factory_class, ModelFactory):
            raise ValueError(
                f"factory_class must be a subclass of ModelFactory or a string '.' dotted represented of the factory, got {type(factory_class)} instead."
            )

        self.__factory_class__ = factory_class
        self.kwargs = kwargs
        self.factory = None

    def build(self, _: Any = None) -> Any:
        """
        Builds an instance using the associated factory.

        Args:
            _ (Any, optional): Placeholder for compatibility with Factory Boy's internal calls. Defaults to None.

        Returns:
            Any: An instance built by the factory class.
        """
        self.factory = self.__factory_class__(**self.__factory_class__.__defaults__).build(
            **self.kwargs
        )
        return self.factory

    def __str__(self) -> str:
        """
        Returns a string representation of the SubFactory.

        Returns:
            str: A string representation of the SubFactory.
        """
        return str(self.factory)

    def __repr__(self) -> str:
        """
        Returns a string representation of the SubFactory.

        Returns:
            str: A string representation of the SubFactory.
        """
        return str(self)
