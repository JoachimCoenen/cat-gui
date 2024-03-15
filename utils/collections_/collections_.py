from __future__ import annotations

import functools as ft
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Generic, Hashable, Iterable, Mapping, MutableMapping, overload, Protocol, Reversible, \
	SupportsIndex, TypeVar, Union, Any
from warnings import warn

_TK = TypeVar('_TK', bound=Hashable)
_TK2 = TypeVar('_TK2')
_TV = TypeVar('_TV')
_TD = TypeVar('_TD')


def _NOTHING():
	"""a sentinel"""
	return _NOTHING


class FromDictByTypeGetter(Protocol[_TK2, _TV]):
	def __call__(self, key: _TK2, default: _TD = None) -> Union[_TV, _TD]:
		pass


def getIfKeyIssubclass(dict_: Mapping[_TK2, _TV], cls: _TK2, default: _TD = None) -> Union[_TV, _TD]:
	""" Like dict.get(key, default), but also tests for superclasses of cls. it tests for superclasses in the order of the cls.__mro__ list.
		It calls dict_[cls], dict_[superclass of cls], dict_[super-superclass of cls], ... until it find an entry in dict.

		@returns: the value if the entry if found, else default
	"""
	for subCls in cls.__mro__:
		result = dict_.get(subCls, _NOTHING)
		if result is not _NOTHING:
			return result
	return default


def IfKeyIssubclassGetter(dict_: Mapping[_TK2, _TV]) -> FromDictByTypeGetter[_TK2, _TV]:
	return ft.partial(getIfKeyIssubclass, dict_)


def getIfKeyIssubclassOrEqual(dict_: Mapping[_TK2, _TV], cls: _TK2, default: _TD = None) -> Union[_TV, _TD]:
	""" Like getIfKeyIssubclass(dict_, cls, default), but also supports values that are not types or meta classes eg. 'Hello World!' or -42
		@see: getIfKeyIssubclass()

		@returns: the value if the entry if found, else default
	"""
	if isinstance(cls, type):
		for subCls in cls.__mro__:
			treeBuilder = dict_.get(subCls, None)
			if treeBuilder is not None:
				return treeBuilder
	else:
		return dict_.get(cls, default)
	return default


def IfKeyIssubclassOrEqualGetter(dict_: Mapping[_TK2, _TV]) -> FromDictByTypeGetter[_TK2, _TV]:
	return ft.partial(getIfKeyIssubclassOrEqual, dict_)


def getIfKeyIssubclassEqualOrIsInstance(dict_: Mapping[_TK2, _TV], cls: _TK2, default: _TD = None) -> Union[_TV, _TD]:
	""" Like getIfKeyIssubclass(dict_, cls, default), but also supports values that are not types or meta classes eg. 'Hello World!' or -42
		@see: getIfKeyIssubclass()

		@returns: the value if the entry if found, else default
	"""
	result = None
	if isinstance(cls, type):
		for subCls in cls.__mro__:
			result = dict_.get(subCls, None)
			if result is not None:
				return result
	else:
		result = dict_.get(cls, None)

	if result is None:
		for subCls in type(cls).__mro__:
			result = dict_.get(subCls, None)
			if result is not None:
				return result

	return result or default


def IfKeyIssubclassEqualOrIsInstanceGetter(dict_: Mapping[_TK2, _TV]) -> FromDictByTypeGetter[_TK2, _TV]:
	return ft.partial(getIfKeyIssubclassEqualOrIsInstance, dict_)


class AddToDictDecorator(Generic[_TK2, _TV]):
	""" used to create an AddToDictDecorator. e.g:
	::
			valueFormatters = {}
			Formatter = AddToDictDecorator(valueFormatters)

			@Formatter(list)
			def formatList(aList):
				pass

			@Formatter(xml.etree.ElementTree.Element)
			@Formatter(xml.etree.ElementTree.ElementTree)
			def formatXML(xml):
				# I don't know why you would need that, since etree can already do that. But hey, why not? ;-)
				pass
	"""
	def __init__(self, dict_: MutableMapping[_TK2, _TV]):
		super().__init__()
		self.dict_: MutableMapping[_TK2, _TV] = dict_

	def __call__(self, key: _TK2, *, forceOverride: bool = False, kwargs: dict[str, Any] = None) -> Callable[[_TV], _TV]:
		def addFuncOrClass(funcOrClass: _TV) -> _TV:
			if not forceOverride and key in self.dict_:
				raise KeyError(f"There already is an entry for {repr(key)}.")
			funcOrClassInDict = ft.partial(funcOrClass, **kwargs) if kwargs else funcOrClass
			self.dict_[key] = funcOrClassInDict
			return funcOrClass
		return addFuncOrClass


class Stack(list[_TV], Generic[_TV]):
	# Note: Formatter for Stack is in formatters.py, bc. formatters.py imports this py file.

	def isEmpty(self) -> bool:
		warn(f"use `not my_stack` instead.", DeprecationWarning, 2)
		return not self

	def push(self, p: _TV):
		self.append(p)

	def replace(self, val: _TV):
		self[-1] = val

	def peek(self) -> _TV:
		return self[-1]

	def peekn(self, n: int) -> _TV:
		return self[-n-1]

	def copy(self) -> Stack[_TV]:
		result = type(self)(self)
		return result

	@overload
	def __getitem__(self, i: SupportsIndex) -> _TV: ...

	@overload
	def __getitem__(self, s: slice) -> Stack[_TV]: ...

	def __getitem__(self, item):
		if isinstance(item, slice):
			return Stack(super(Stack, self).__getitem__(item))
		return super(Stack, self).__getitem__(item)

	def __str__(self) -> str:
		val = super(Stack, self).__str__()
		return f"{type(self).__name__}({val})"

	def __repr__(self) -> str:
		val = super(Stack, self).__repr__()
		return f"{type(self).__name__}({val})"


@dataclass
class ListTree(Generic[_TV]):
	value: _TV
	children: list[ListTree[_TV]]

	def add(self, value: _TV) -> ListTree[_TV]:
		child = ListTree(value, [])
		self.children.append(child)
		return child


@dataclass
class DictTree(Generic[_TK, _TV]):
	value: _TV
	children: dict[_TK, DictTree[_TK, _TV]]

	def add(self, key: _TK, value: _TV) -> DictTree[_TK, _TV]:
		child = DictTree(value, {})
		self.children[key] = child
		return child


@dataclass
class OrderedDictTree(Generic[_TK, _TV]):
	value: _TV
	children: OrderedDict[_TK, OrderedDictTree[_TK, _TV]]

	def add(self, key: _TK, value: _TV) -> OrderedDictTree[_TK, _TV]:
		child = OrderedDictTree(value, OrderedDict())
		self.children[key] = child
		return child


# Utility functions:
@overload
def first(s: Iterable[_TV]) -> _TV: ...


@overload
def first(s: Iterable[_TV], default: _TD) -> Union[_TV, _TD]: ...


def first(s: Iterable[_TV], default: _TD = _NOTHING) -> Union[_TV, _TD]:
	"""
	Return the first element from an ordered collection or an arbitrary element from
	an unordered collection. If default is given, it is returned if the collection is
	empty, otherwise StopIteration is raised.
	"""
	if default is _NOTHING:
		return next(iter(s))
	else:
		return next(iter(s), default)


@overload
def last(s: Reversible[_TV]) -> _TV: ...


@overload
def last(s: Reversible[_TV], default: _TD) -> Union[_TV, _TD]: ...


def last(s: Reversible[_TV], default: _TD = _NOTHING) -> Union[_TV, _TD]:
	"""
	Return the last element from an ordered collection or an arbitrary element from
	an unordered collection. If default is given, it is returned if the collection is
	empty, otherwise StopIteration is raised.
	"""
	if default is _NOTHING:
		return next(reversed(s))
	else:
		return next(reversed(s), default)


def find_index(it: Iterable[_TV], p: Callable[[_TV], bool], default: _TD = -1) -> Union[int, _TD]:
	return next((i for i, e in enumerate(it) if p(e)), default)
