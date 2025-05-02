# adopted from: https://github.com/Marco-Sulla/python-frozendict
# with some modifications.
# under the GNU LESSER GENERAL PUBLIC LICENSE v3, 29 June 2007

from __future__ import annotations

from collections import UserDict
from copy import deepcopy
from typing import Any, ClassVar, Iterable, Mapping, AbstractSet, overload, Callable, Self

from cat.utils.typing_ import SupportsKeysAndGetItem, SupportsItems, SupportsRichComparison


def notimplemented(self, *args, **kwargs):
    r"""
    Not implemented.
    """
    
    raise NotImplementedError(f"`{type(self).__name__}` object is immutable.")


def sortMapItemsByValue(item):
    return item[1]


_sentinel = object()


class FrozenDict[TK, TV](UserDict[TK, TV]):
    r"""
    A simple immutable dictionary.

    The API is the same as `dict`, without methods that can change the
    immutability.
    In addition, it supports __hash__(), a slightly modified version of the
    `set` API and some other useful method.
    """

    __slots__ = (
        "initialized",
        "_hash",
        "is_frozendict",
    )

    EMPTY: ClassVar[FrozenDict[Any, Any]]

    # Signature of `dict.fromkeys` should be kept identical to `fromkeys` methods of `dict`/`OrderedDict`/`ChainMap`/`UserDict` in `collections`
    # the true signature of `dict.fromkeys` is not expressible in the current type system.
    # See #3800 & https://github.com/python/typing/issues/548#issuecomment-683336963.
    @classmethod  # type: ignore
    @overload
    def fromkeys(cls, iterable: Iterable[TK], value: None = None) -> UserDict[TK, Any | None]: ...
    @classmethod
    @overload
    def fromkeys(cls, iterable: Iterable[TK], value: TV) -> UserDict[TK, TV]: ...

    @classmethod
    def fromkeys(cls, *args, **kwargs):
        r"""
        Identical to dict.fromkeys().
        """

        return cls(dict.fromkeys(*args, **kwargs))

    def __new__(cls, *args, **kwargs):
        r"""
        Almost identical to dict.__new__().
        """

        # enable attribute setting for __init__,
        # only for the first time
        cls.__setattr__ = object.__setattr__
        cls.__setitem__ = UserDict.__setitem__
        cls.update = UserDict.update

        has_kwargs = bool(kwargs)

        if len(args) == 1 and not has_kwargs:
            it = args[0]

            if isinstance(it, cls):
                it.initialized = 2
                return it

        use_empty = False

        if not has_kwargs:
            use_empty = True

            for arg in args:
                if arg:
                    use_empty = False
                    break

        if use_empty:
            try:
                self = cls.EMPTY
                return self
            except AttributeError:
                initialized = 3
        else:
            initialized = 0

        self = super().__new__(cls)
        self.initialized = initialized
        return self

    @overload
    def __init__(self, **kwargs: TV) -> None: ...
    @overload
    def __init__(self, _dict: Mapping[TK, TV], **kwargs: TV) -> None: ...
    @overload
    def __init__(self, iterable: Iterable[tuple[TK, TV]], **kwargs: TV) -> None: ...

    def __init__(self, *args, **kwargs):
        r"""
        Almost identical to dict.__init__(). It can't be reinvoked.
        """

        if self.initialized == 2:
            self.initialized = 1
            return

        cls = type(self)

        if self.initialized != 3 and self is cls.EMPTY:
            return

        if self.initialized == 1:
            # object is immutable, can't be initialized twice
            notimplemented(self)

        super().__init__(*args, **kwargs)  # type: ignore

        self._hash = None
        self.initialized = 1
        self.is_frozendict = True

        # object is created, now inhibit its mutability
        cls.__setattr__ = notimplemented
        cls.__setitem__ = notimplemented
        cls.update = notimplemented

    def get_deep(self, *args, default=_sentinel):
        r"""
        Get a nested element of the `FrozenDict`.

        The method accepts multiple arguments or a single one. If a single
        arguments is passed, it must be an iterable. These represent the
        keys or indexes of the nested element.

        The method first tries to get the value v1 of `FrozenDict` using the
        first key. If it found v1 and there's no other key, v1 is
        returned. Otherwise, the method tries to retrieve the value from v1
        associated to the second key/index, and so on.

        If in any point, for any reason, the value can't be retrieved, if
        `default` parameter is specified, its value is returned. Otherwise, a
        KeyError or a IndexError is raised.
        """

        if len(args) == 1:
            single = True

            it_tpm = args[0]

            try:
                len(it_tpm)
                it = it_tpm
            except TypeError:
                # maybe it's an iterator
                try:
                    it = tuple(it_tpm)
                except TypeError:
                    raise TypeError(f"`{self.get_deep.__name__}` called with a single argument supports only iterables, but {type(it_tpm).__name__} was given") from None
        else:
            it = args
            single = False

        if not it:
            if single:
                raise ValueError(f"`{self.get_deep.__name__}` argument is empty")
            else:
                raise TypeError(f"`{self.get_deep.__name__}` expects at least one argument")

        obj = self

        for k in it:
            try:
                obj = obj[k]
            except (KeyError, IndexError):
                if default is _sentinel:
                    raise

                return default

        return obj

    def hash_no_errors(self):
        r"""
        Calculates the hash if all values are hashable, otherwise returns -1
        """

        _hash = self._hash

        if _hash is None:
            # try to cache the hash. You have to use `object.__setattr__()`
            # because the `__setattr__` of the class is inhibited
            hash1 = 0

            for v in self.values():
                try:
                    hash_v = v.__hash__()
                except Exception:
                    hash_res = -1
                    object.__setattr__(self, "_hash", hash_res)
                    return hash_res

                hash1 ^= ((hash_v ^ 89869747) ^ (hash_v << 16)) * 3644798167

            hash2 = hash1 ^ ((len(self) + 1) * 1927868237)
            hash3 = (hash2 ^ ((hash2 >> 11) ^ (hash2 >> 25))) * 69069 + 907133923

            if hash3 == -1:
                hash_res = 590923713
            else:
                hash_res = hash3

            object.__setattr__(self, "_hash", hash_res)
        else:
            hash_res = _hash

        return hash_res

    def __hash__(self) -> int:
        r"""
        Calculates the hash if all values are hashable, otherwise raises a
        TypeError.
        """

        _hash = self.hash_no_errors()

        if _hash == -1:
            raise TypeError("Not all values are hashable.")

        return _hash

    def __repr__(self) -> str:
        r"""
        Identical to dict.__repr__().
        """

        body = super().__repr__()
        return f"{type(self).__name__}({body})"

    def copy(self) -> Self:
        r"""
        Return the object itself, as it's an immutable.
        """
        return self

    def __copy__(self, *args, **kwargs) -> Self:
        r"""
        See copy().
        """
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> FrozenDict[TK, TV]:
        r"""
        If hashable, see copy(). Otherwise, it returns a deepcopy.
        """

        _hash = self.hash_no_errors()
        if _hash == -1:
            tmp = deepcopy(dict(self), memo)
            return type(self)(tmp)

        return self.copy()

    def __reduce__(self) -> Any:
        r"""
        Support for `pickle`.
        """
        return type(self), (dict(self), )

    @overload
    def sorted(self, *, key: None = None, reverse: bool = False) -> FrozenDict[TK, TV]: ...
    @overload
    def sorted(self, *, key: Callable[[TK], SupportsRichComparison], reverse: bool = False) -> FrozenDict[TK, TV]: ...

    def sorted(self, *, key: Callable[[TK], SupportsRichComparison] | None = None, reverse: bool = False) -> FrozenDict[TK, TV]:
        r"""
        Return a new `FrozenDict`, with the element insertion sorted.
        The signature is the same of builtin `sorted()` function. The resulting
        `FrozenDict` is sorted by keys.
        """

        if not self:
            return self

        if key is None:
            def actual_key(item: tuple[TK, TV]) -> SupportsRichComparison:
                return item[0]   # type: ignore
        else:
            def actual_key(item: tuple[TK, TV]) -> SupportsRichComparison:
                return key(item[0])

        it_sorted = sorted(self.items(), key=actual_key, reverse=reverse)

        if it_sorted == list(self.keys()):
            return self

        return type(self)(it_sorted)

    @overload
    def __add__(self, other: SupportsKeysAndGetItem[TK, TV] | Iterable[tuple[TK, TV]]) -> FrozenDict[TK, TV]: ...
    @overload
    def __add__[TK2, TV2](self, other: SupportsKeysAndGetItem[TK2, TV2] | Iterable[tuple[TK2, TV2]]) -> FrozenDict[TK | TK2, TV | TV2]: ...

    def __add__[TK2, TV2](self, other: SupportsKeysAndGetItem[TK2, TV2] | Iterable[tuple[TK2, TV2]]) -> FrozenDict[TK | TK2, TV | TV2]:
        r"""
        If you add a dict-like object, a new `FrozenDict` will be returned, equal
        to the old `FrozenDict` updated with the other object.
        """

        tmp: dict[TK | TK2, TV | TV2] = dict(self)  # type: ignore
        tmp.update(other)  # type: ignore
        return type(self)(tmp)

    __or__ = __add__  # type: ignore

    def __sub__[TV2](self, other: Mapping[TK, TV2] | AbstractSet[TK]) -> FrozenDict[TK, TV]:
        r"""
        The method will create a new `FrozenDict`, result of the subtraction
        by `other`.

        If `other` is a `dict`-like, the result will have the items of the
        `FrozenDict` without the keys that are in `other`.

        If `other` is another type of iterable, the result will have the
        items of `FrozenDict` without the keys that are in `other`.
        """

        return type(self)(item for item in self.items() if item[0] not in other)

    def __and__(self, other: SupportsItems[TK, TV] | Iterable[TK]) -> FrozenDict[TK, TV]:
        r"""
        Returns a new `FrozenDict`, that is the intersection between `self`
        and `other`.

        If `other` is a `dict`-like object, the intersection will contain
        only the *items* in common.

        If `other` is another iterable, the intersection will contain
        the items of `self` which keys are in `other`.

        Iterables of pairs are *not* managed differently. This is for
        consistency reasons.

        Beware! The final order is dictated by the order of `other`. This
        allows the coder to change the order of the original `FrozenDict`.

        The last two behaviors breaks the `dict.items()` API, for consistency
        and practical reasons.
        """

        if hasattr(other, 'items') and callable(other.items):
            res = {k: v for k, v in other.items() if (k, v) in self.items()}
        elif hasattr(other, '__iter__') and callable(other.__iter__):
            res = {k: self[k] for k in other if k in self}
        else:
            return NotImplemented

        return type(self)(res)  # type: ignore

    def isdisjoint(self, other: SupportsItems[TK, TV]) -> bool:
        r"""
        Returns True if `other` dict-like object has no items in common,
        otherwise False. Equivalent to `not (`FrozenDict` & dict_like)`
        """

        if hasattr(other, 'items') and callable(other.items):
            return not (self & other)
        else:
            return NotImplemented


FrozenDict.clear = notimplemented  # type: ignore
FrozenDict.pop = notimplemented  # type: ignore
FrozenDict.popitem = notimplemented  # type: ignore
FrozenDict.setdefault = notimplemented  # type: ignore
FrozenDict.update = notimplemented  # type: ignore
FrozenDict.__delitem__ = notimplemented  # type: ignore
FrozenDict.__setitem__ = notimplemented  # type: ignore
FrozenDict.__delattr__ = notimplemented  # type: ignore
FrozenDict.__setattr__ = notimplemented  # type: ignore

FrozenDict.EMPTY = FrozenDict()


__all__ = [
    'FrozenDict', 
]


if __name__ == '__main__':
    fr1: FrozenDict[str, int] = FrozenDict({"ffrr11": 75})
    fr2: FrozenDict[str, int] = FrozenDict({"ffrr11": 75})
    fr3: FrozenDict[str, int] = FrozenDict({"ffrr11": 75, "ffrr33": 75})
    print(fr1)
    print(fr2)
    print(fr3)
