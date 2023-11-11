# adopted from: https://github.com/Marco-Sulla/python-frozendict
# with some modifications.
# under the GNU LESSER GENERAL PUBLIC LICENSE v3, 29 June 2007

from __future__ import annotations

from typing import Any, ClassVar, Generic, Iterable, Iterator, Mapping, overload, Tuple, TypeVar, Union

_TT = TypeVar('_TT')
_TK = TypeVar('_TK')  # Key type.
_TV_co = TypeVar('_TV_co', covariant=True)  # Value type covariant containers.


class FrozenDict(Mapping[_TK, _TV_co], Generic[_TK, _TV_co]):
    r"""
    A simple immutable dictionary.

    The API is the same as `dict`, without methods that can change the
    immutability.
    In addition, it supports __hash__(), a slightly modified version of the
    `set` API and some other useful method.
    """

    # Signature of `dict.fromkeys` should be kept identical to `fromkeys` methods of `dict`/`OrderedDict`/`ChainMap`/`UserDict` in `collections`
    # the true signature of `dict.fromkeys` is not expressible in the current type system.
    # See #3800 & https://github.com/python/typing/issues/548#issuecomment-683336963.
    @classmethod
    @overload
    def fromkeys(cls, __iterable: Iterable[_TK], __value: None = ...) -> dict[_TK, Any | None]: ...
    @classmethod
    @overload
    def fromkeys(cls, __iterable: Iterable[_TK], __value: _TT) -> dict[_TK, _TT]: ...

    @overload
    def __init__(self, **kwargs: _TV_co) -> None: ...

    @overload
    def __init__(self, map: Mapping[_TK, _TV_co], **kwargs: _TV_co) -> None: ...

    @overload
    def __init__(self, iterable: Iterable[Tuple[_TK, _TV_co]], **kwargs: _TV_co) -> None: ...

    def get_deep(self, arg: _TK, /, *args, default=...):
        r"""
        Get a nested element of the `frozendict`.

        The method accepts multiple arguments or a single one. If a single
        arguments is passed, it must be an iterable. These represent the
        keys or indexes of the nested element.

        The method first tries to get the value v1 of `frozendict` using the
        first key. If it found v1 and there's no other key, v1 is
        returned. Otherwise, the method tries to retrieve the value from v1
        associated to the second key/index, and so on.

        If in any point, for any reason, the value can't be retrieved, if
        `default` parameter is specified, its value is returned. Otherwise, a
        KeyError or a IndexError is raised.
        """

    def hash_no_errors(self):
        r"""
        Calculates the hash if all values are hashable, otherwise returns -1
        """

    def __hash__(self, *args, **kwargs):
        r"""
        Calculates the hash if all values are hashable, otherwise raises a
        TypeError.
        """

    def __repr__(self, *args, **kwargs):
        r"""
        Identical to dict.__repr__().
        """

    def copy(self) -> FrozenDict[_TK, _TV_co]:
        r"""
        Return the object itself, as it's an immutable.
        """

    def __copy__(self, *args, **kwargs) -> FrozenDict[_TK, _TV_co]:
        r"""
        See copy().
        """

    def __deepcopy__(self, *args, **kwargs) -> FrozenDict[_TK, _TV_co]:
        r"""
        If hashable, see copy(). Otherwise, it returns a deepcopy.
        """

    def __reduce__(self, *args, **kwargs):
        r"""
        Support for `pickle`.
        """

    def sorted(self, *args, by="keys", **kwargs):
        r"""
        Return a new `frozendict`, with the element insertion sorted.
        The signature is the same of builtin `sorted()` function, except for
        the additional parameter `by`, that is "keys" by default and can also
        be "values" and "items". So the resulting `frozendict` can be sorted
        by keys, values or items.

        If you want more complicated sorts, see the documentation of
        `sorted()`. Take into mind that the parameters passed to the `key`
        function are the keys of the `frozendict` if `by == "keys"`, and are
        the items otherwise.

        PS: Note that sort by keys and items are identical. The only
        difference is when you want to customize the sorting passing a custom
        `key` function. You *could* achieve the same result using
        `by="values"`, since also sorting by values passes the items to the
        key function. But this is an implementation detail, and you should not
        rely on it.
        """

    def __add__(self, other: Union[Mapping[_TK, _TV_co], Iterable[Tuple[_TK, _TV_co]]]) -> FrozenDict[_TK, _TV_co]:
        r"""
        If you add a dict-like object, a new frozendict will be returned, equal
        to the old frozendict updated with the other object.
        """

    def __sub__(self, other: Union[Mapping[_TK, _TV_co], Iterable[Tuple[_TK, _TV_co]]]) -> FrozenDict[_TK, _TV_co]:
        r"""
        The method will create a new `frozendict`, result of the subtraction
        by `other`.

        If `other` is a `dict`-like, the result will have the items of the
        `frozendict` without the keys that are in `other`.

        If `other` is another type of iterable, the result will have the
        items of `frozendict` without the keys that are in `other`.
        """

    def __and__(self, other: Union[Mapping[_TK, _TV_co], Iterable[Tuple[_TK, _TV_co]]]) -> FrozenDict[_TK, _TV_co]:
        r"""
        Returns a new `frozendict`, that is the intersection between `self`
        and `other`.

        If `other` is a `dict`-like object, the intersection will contain
        only the *items* in common.

        If `other` is another iterable, the intersection will contain
        the items of `self` which keys are in `other`.

        Iterables of pairs are *not* managed differently. This is for
        consistency.

        Beware! The final order is dictated by the order of `other`. This
        allows the coder to change the order of the original `frozendict`.

        The last two behaviors breaks voluntarily the `dict.items()` API, for
        consistency and practical reasons.
        """

    def __or__(self, other: Union[Mapping[_TK, _TV_co], Iterable[Tuple[_TK, _TV_co]]]) -> FrozenDict[_TK, _TV_co]:
        r"""
        If you add a dict-like object, a new frozendict will be returned, equal
        to the old frozendict updated with the other object.
        """

    def isdisjoint(self, other: Mapping[_TK, _TV_co]) -> bool:
        r"""
        Returns True if `other` dict-like object has no items in common,
        otherwise False. Equivalent to `not (frozendict & dict_like)`
        """

    def __getitem__(self, key: _TK) -> _TV_co: ...

    def __contains__(self, key: _TK) -> bool: ...

    def __iter__(self) -> Iterator[_TK]: ...

    def __len__(self) -> int: ...

    EMPTY: ClassVar[FrozenDict[Any, Any]] = FrozenDict()


__all__ = [
    'FrozenDict', 
]


