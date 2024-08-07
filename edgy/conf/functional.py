import copy
import operator
from typing import Any, Callable, TypeVar

empty = object()
RT = TypeVar("RT")


def new_method_proxy(func: Callable[..., RT]) -> Callable[..., RT]:
    def inner(self, *args: Any) -> RT:  # type: ignore
        if self._wrapped is empty:
            self._setup()
        return func(self._wrapped, *args)

    return inner


class LazyObject:  # pragma: no cover
    """
    A wrapper for another class that can be used to delay instantiation of the
    wrapped class.
    By subclassing, you have the opportunity to intercept and alter the
    instantiation. If you don't need to do that, use SimpleLazyObject.
    """

    # Avoid infinite recursion when tracing __init__ (#19456).
    _wrapped = None

    def __init__(self) -> None:
        # Note: if a subclass overrides __init__(), it will likely need to
        # override __copy__() and __deepcopy__() as well.
        self._wrapped = empty

    def __getattribute__(self, name: str) -> Any:
        if name == "_wrapped":
            # Avoid recursion when getting wrapped object.
            return super().__getattribute__(name)
        value: Any = super().__getattribute__(name)
        # If attribute is a proxy method, raise an AttributeError to call
        # __getattr__() and use the wrapped object method.
        if not getattr(value, "_mask_wrapped", True):
            raise AttributeError
        return value

    __getattr__ = new_method_proxy(getattr)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_wrapped":
            # Assign to __dict__ to avoid infinite __setattr__ loops.
            self.__dict__["_wrapped"] = value
        else:
            if self._wrapped is empty:
                self._setup()
            setattr(self._wrapped, name, value)

    def __delattr__(self, name: str) -> None:
        if name == "_wrapped":
            raise TypeError("can't delete _wrapped.")
        if self._wrapped is empty:
            self._setup()
        delattr(self._wrapped, name)

    def _setup(self) -> Any:
        """
        Must be implemented by subclasses to initialize the wrapped object.
        """
        raise NotImplementedError("subclasses of LazyObject must provide a _setup() method")

    # Because we have messed with __class__ below, we confuse pickle as to what
    # class we are pickling. We're going to have to initialize the wrapped
    # object to successfully pickle it, so we might as well just pickle the
    # wrapped object since they're supposed to act the same way.
    #
    # Unfortunately, if we try to simply act like the wrapped object, the ruse
    # will break down when pickle gets our id(). Thus we end up with pickle
    # thinking, in effect, that we are a distinct object from the wrapped
    # object, but with the same __dict__. This can cause problems (see #25389).
    #
    # So instead, we define our own __reduce__ method and custom unpickler. We
    # pickle the wrapped object as the unpickler's argument, so that pickle
    # will pickle it normally, and then the unpickler simply returns its
    # argument.
    def __reduce__(self) -> Any:
        if self._wrapped is empty:
            self._setup()
        return (unpickle_lazyobject, (self._wrapped,))

    def __copy__(self) -> Any:
        if self._wrapped is empty:
            # If uninitialized, copy the wrapper. Use type(self), not
            # self.__class__, because the latter is proxied.
            return type(self)()
        else:
            # If initialized, return a copy of the wrapped object.
            return copy.copy(self._wrapped)

    def __deepcopy__(self, memo: Any) -> Any:
        if self._wrapped is empty:
            # We have to use type(self), not self.__class__, because the
            # latter is proxied.
            result = type(self)()
            memo[id(self)] = result
            return result
        return copy.deepcopy(self._wrapped, memo)

    __bytes__: Any = new_method_proxy(bytes)
    __str__: Any = new_method_proxy(str)
    __bool__: Any = new_method_proxy(bool)

    # Introspection support
    __dir__: Any = new_method_proxy(dir)

    # Need to pretend to be the wrapped class, for the sake of objects that
    # care about this (especially in equality tests)
    __class__ = property(new_method_proxy(operator.attrgetter("__class__")))  # type: ignore
    __eq__: Any = new_method_proxy(operator.eq)
    __lt__: Any = new_method_proxy(operator.lt)
    __gt__: Any = new_method_proxy(operator.gt)
    __ne__: Any = new_method_proxy(operator.ne)
    __hash__: Any = new_method_proxy(hash)

    # List/Tuple/Dictionary methods support
    __getitem__: Any = new_method_proxy(operator.getitem)
    __setitem__: Any = new_method_proxy(operator.setitem)
    __delitem__: Any = new_method_proxy(operator.delitem)
    __iter__: Any = new_method_proxy(iter)
    __len__: Any = new_method_proxy(len)
    __contains__: Any = new_method_proxy(operator.contains)


def unpickle_lazyobject(wrapped: Any) -> Any:  # pragma: no cover
    """
    Used to unpickle lazy objects. Just return its argument, which will be the
    wrapped object.
    """
    return wrapped


class SimpleLazyObject(LazyObject):  # pragma: no cover
    """
    A lazy object initialized from any function.
    Designed for compound objects of unknown type. For builtins or objects of
    known type, use django.utils.functional.lazy.
    """

    def __init__(self, func: Callable[..., RT]) -> None:
        """
        Pass in a callable that returns the object to be wrapped.
        If copies are made of the resulting SimpleLazyObject, which can happen
        in various circumstances within Django, then you must ensure that the
        callable can be safely run more than once and will return the same
        value.
        """
        self.__dict__["_setupfunc"] = func
        super().__init__()

    def _setup(self) -> Any:
        self._wrapped = self._setupfunc()

    # Return a meaningful representation of the lazy object for debugging
    # without evaluating the wrapped object.
    def __repr__(self) -> str:
        repr_attr = self._setupfunc if self._wrapped is empty else self._wrapped
        return f"<{type(self).__name__}: {repr_attr!r}>"

    def __copy__(self) -> Any:
        if self._wrapped is empty:
            # If uninitialized, copy the wrapper. Use SimpleLazyObject, not
            # self.__class__, because the latter is proxied.
            return SimpleLazyObject(self._setupfunc)
        else:
            # If initialized, return a copy of the wrapped object.
            return copy.copy(self._wrapped)

    def __deepcopy__(self, memo: Any) -> Any:
        if self._wrapped is empty:
            # We have to use SimpleLazyObject, not self.__class__, because the
            # latter is proxied.
            result = SimpleLazyObject(self._setupfunc)
            memo[id(self)] = result
            return result
        return copy.deepcopy(self._wrapped, memo)

    __add__ = new_method_proxy(operator.add)

    @new_method_proxy
    def __radd__(self, other: Any) -> Any:
        return other + self
