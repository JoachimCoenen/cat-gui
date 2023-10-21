# encoding: utf-8
# module utils.collections.orderedmultidictBase
# from D:/helper_scripts\utils\collections\orderedmultidictBase.cp37-win32.pyd
# no doc

# imports
import builtins as __builtins__ # <module 'builtins' (built-in)>
from typing import Any, Callable, Generic, Hashable, Iterable, Iterator, Optional, OrderedDict, overload, TypeVar, Union


# functions

_TT = TypeVar ('_TT')
_TV = TypeVar ('_TV')
_TK = TypeVar('_TK', bound=Hashable)

class OrderedMultiDictBase(Generic[_TK, _TV]):
	def __init__(self, iterable: Optional[Iterable[tuple[_TK, _TV]]] = None):
		self._items: OrderedDict[int, tuple[_TK, _TV]] = OrderedDict()
		self._map: dict[_TK, tuple[int, _TV]] = dict()
		pass

	def load(self, iterable: Iterable[tuple[_TK, _TV]]):
		"""
		Clear all existing key:value items and import all key:value items from
		<mapping>. If multiple values exist for the same key in <mapping>, they
		are all be imported.

		Returns: <self>.
		"""
		pass

	def copy(self) -> OrderedMultiDictBase[_TK, _TV]:
		pass

	def clear(self):
		pass

	def get(self, key, default: _TT = None) -> Union[_TV, _TT]:
		""" same as getFirst(...)
		:param key:
		:param default:
		:return:
		"""
		pass

	def getFirst(self, key, default: _TT = None) -> Union[_TV, _TT]:
		""" same as get(...)
		:param key:
		:param default:
		:return:
		"""
		pass

	def getLast(self, key, default: _TT = None) -> Union[_TV, _TT]:
		pass

	@overload
	def getall(self, key) -> list[_TV]:
		"""
		Returns: The list of values for <key> if <key> is in the dictionary,
		else <default>. If <default> is not provided, an empty list is
		returned.
		"""
		pass

	def getall(self, key, default: _TT = []) -> Union[list[_TV], _TT]:
		"""
		Returns: The list of values for <key> if <key> is in the dictionary,
		else <default>. If <default> is not provided, an empty list is
		returned.
		"""
		pass

	def setdefault(self, key: _TK, default: _TV) -> _TV:
		pass

	def setdefaultAll(self, key: _TK, defaultlist: list[_TV]) -> list[_TV]:
		"""
		Similar to setdefault() except <defaultlist> is a list of values to set
		for <key>. If <key> already exists, its existing list of values is
		returned.

		If <key> isn't a key and <defaultlist> is an empty list, [], no values
		are added for <key> and <key> will not be added as a key.

		Returns: List of <key>'s values if <key> exists in the dictionary,
		otherwise <defaultlist>.
		"""
		pass

	def setAll(self, key: _TK, valueList: list[_TV]):
		pass

	def add(self, key: _TK, value: _TV):
		"""
		Add <value> to the list of values for <key>. If <key> is not in the
		dictionary, then <value> is added as the sole value for <key>.

		Example:
		  omd = omdict()
		  omd.add(1, 1)  # omd.allitems() == [(1,1)]
		  omd.add(1, 11) # omd.allitems() == [(1,1), (1,11)]
		  omd.add(2, 2)  # omd.allitems() == [(1,1), (1,11), (2,2)]

		Returns: <self>.
		"""
		pass

	def addAll(self, key: _TK, valuelist: list[_TV]):
		"""
		Add the values in <valuelist> to the list of values for <key>. If <key>
		is not in the dictionary, the values in <valuelist> become the values
		for <key>.

		Example:
		  omd = omdict([(1,1)])
		  omd.addlist(1, [11, 111])
		  omd.allitems() == [(1, 1), (1, 11), (1, 111)]
		  omd.addlist(2, [2])
		  omd.allitems() == [(1, 1), (1, 11), (1, 111), (2, 2)]

		Returns: <self>.
		"""
		pass

	def extend(self, keyValuelist: list[tuple[_TK, _TV]]):
		pass

	@overload
	def pop(self, key: _TK) -> _TV:
		pass

	@overload
	def pop(self, key: _TK, default: Union[_TV, _TT]) -> Union[_TV, _TT]:
		pass

	@overload
	def popAll(self, key: _TK) -> Union[list[_TV]]:
		"""
		If <key> is in the dictionary, pop it and return its list of values. If
		<key> is not in the dictionary, return <default>. KeyError is raised if
		<default> is not provided and <key> is not in the dictionary.

		Example:
		  omd = omdict([(1,1), (1,11), (1,111), (2,2), (3,3)])
		  omd.poplist(1) == [1, 11, 111]
		  omd.allitems() == [(2,2), (3,3)]
		  omd.poplist(2) == [2]
		  omd.allitems() == [(3,3)]

		Raises: KeyError if <key> is absent in the dictionary and <default> isn't
		  provided.
		Returns: List of <key>'s values.
		"""
		pass

	@overload
	def popAll(self, key: _TK, default: list[_TT]) -> Union[list[_TV], list[_TT]]:
		"""
		If <key> is in the dictionary, pop it and return its list of values. If
		<key> is not in the dictionary, return <default>. KeyError is raised if
		<default> is not provided and <key> is not in the dictionary.

		Example:
		  omd = omdict([(1,1), (1,11), (1,111), (2,2), (3,3)])
		  omd.poplist(1) == [1, 11, 111]
		  omd.allitems() == [(2,2), (3,3)]
		  omd.poplist(2) == [2]
		  omd.allitems() == [(3,3)]

		Raises: KeyError if <key> is absent in the dictionary and <default> isn't
		  provided.
		Returns: List of <key>'s values.
		"""
		pass

	@overload
	def popFirstItem(self) -> tuple[_TK, _TV]:
		""" """
		pass

	@overload
	def popFirstItem(self, *, default: _TT) -> Union[tuple[_TK, _TV], _TT]:
		""" """
		pass

	@overload
	def popLastItem(self) -> tuple[_TK, _TV]:
		""" """
		pass

	@overload
	def popLastItem(self, *, default: _TT) -> Union[tuple[_TK, _TV], _TT]:
		""" """
		pass

	@overload
	def popFirst(self, key: _TK) -> _TV:
		"""
		Raises: KeyError if <key> is absent.
		"""
		pass

	@overload
	def popFirst(self, key: _TK, default: _TT) -> Union[_TV, _TT]:
		"""
		returns default if <key> is absent.
		"""
		pass

	@overload
	def popLast(self, key: _TK) -> _TV:
		"""
		Raises: KeyError if <key> is absent.
		"""
		pass

	@overload
	def popLast(self, key: _TK, default: _TT) -> Union[_TV, _TT]:
		"""
		returns default if <key> is absent.
		"""
		pass

	def items(self) -> _ItemsView[_TK, _TV]:
		pass

	def keys(self) -> _KeysView[_TK]:
		pass

	def uniqueKeys(self) -> _UniqueKeysView[_TK]:
		pass

	def values(self) -> _ValuesView[_TV]:
		pass

	def sort(self, *, key: Optional[Callable[[tuple[_TK, _TV]], Any]] = None, reverse: bool = False):
		pass

	def __eq__(self, other):
		pass

	def __ne__(self, other):
		pass

	def __len__(self):
		pass

	def __iter__(self) -> Iterator[_TK]:
		pass

	def __contains__(self, key: _TK):
		pass

	def __getitem__(self, key: _TK) -> _TV:
		pass

	def __setitem__(self, key: _TK, value: _TV):
		pass

	def __delitem__(self, key: _TK):
		pass

	def __nonzero__(self):
		pass

	def __str__(self):
		pass

	def __repr__(self):
		pass

	__weakref__ = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default
	"""list of weak references to the object (if defined)"""


	__dict__ = None # (!) real value is "mappingproxy({'__module__': 'utils.collections.orderedmultidictBase', '__doc__': 'docstring for OrderedMultiDictBase', '__init__': <cyfunction OrderedMultiDictBase.__init__ at 0x036F73B0>, 'load': <cyfunction OrderedMultiDictBase.load at 0x036F7420>, 'copy': <cyfunction OrderedMultiDictBase.copy at 0x036F7490>, 'clear': <cyfunction OrderedMultiDictBase.clear at 0x036F7500>, 'get': <cyfunction OrderedMultiDictBase.get at 0x036F7570>, 'getall': <cyfunction OrderedMultiDictBase.getall at 0x036F75E0>, 'setdefault': <cyfunction OrderedMultiDictBase.setdefault at 0x036F7650>, 'setdefaultAll': <cyfunction OrderedMultiDictBase.setdefaultAll at 0x036F76C0>, 'setAll': <cyfunction OrderedMultiDictBase.setAll at 0x036F7730>, 'add': <cyfunction OrderedMultiDictBase.add at 0x036F77A0>, 'addAll': <cyfunction OrderedMultiDictBase.addAll at 0x036F7810>, 'extend': <cyfunction OrderedMultiDictBase.extend at 0x036F7880>, '_popOne': <cyfunction OrderedMultiDictBase._popOne at 0x036F78F0>, 'pop': <cyfunction OrderedMultiDictBase.pop at 0x036F7960>, 'popAll': <cyfunction OrderedMultiDictBase.popAll at 0x036F79D0>, 'items': <cyfunction OrderedMultiDictBase.items at 0x036F7A40>, 'keys': <cyfunction OrderedMultiDictBase.keys at 0x036F7AB0>, 'values': <cyfunction OrderedMultiDictBase.values at 0x036F7B20>, 'sort': <cyfunction OrderedMultiDictBase.sort at 0x036F7B90>, '__eq__': <cyfunction OrderedMultiDictBase.__eq__ at 0x036F7C00>, '__ne__': <cyfunction OrderedMultiDictBase.__ne__ at 0x036F7C70>, '__len__': <cyfunction OrderedMultiDictBase.__len__ at 0x036F7CE0>, '__iter__': <cyfunction OrderedMultiDictBase.__iter__ at 0x036F7D50>, '__contains__': <cyfunction OrderedMultiDictBase.__contains__ at 0x036F7DC0>, '__getitem__': <cyfunction OrderedMultiDictBase.__getitem__ at 0x036F7E30>, '__setitem__': <cyfunction OrderedMultiDictBase.__setitem__ at 0x036F7EA0>, '__delitem__': <cyfunction OrderedMultiDictBase.__delitem__ at 0x036F7F10>, '__nonzero__': <cyfunction OrderedMultiDictBase.__nonzero__ at 0x036F7F80>, '__str__': <cyfunction OrderedMultiDictBase.__str__ at 0x036F8030>, '__repr__': <cyfunction OrderedMultiDictBase.__repr__ at 0x036F80A0>, '__dict__': <attribute '__dict__' of 'OrderedMultiDictBase' objects>, '__weakref__': <attribute '__weakref__' of 'OrderedMultiDictBase' objects>, '__hash__': None})"
	__hash__ = None


class _ViewBase(Generic[_TT]):
	# no doc
	def __init__(self, *args, **kwargs): # real signature unknown
		pass

	def __len__(self, *args, **kwargs): # real signature unknown
		pass

	def __iter__(self,) -> Iterator[_TT]:
		pass

	def __reversed__(self) -> Iterator[_TT]:
		pass

	def __repr__(self, *args, **kwargs): # real signature unknown
		pass

	__weakref__ = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default
	"""list of weak references to the object (if defined)"""

	__dict__ = None # (!) real value is "mappingproxy({'__module__': 'utils.collections.orderedmultidictBase', '__init__': <cyfunction _ViewBase.__init__ at 0x0369DE30>, '__len__': <cyfunction _ViewBase.__len__ at 0x0369DEA0>, '__dict__': <attribute '__dict__' of '_ViewBase' objects>, '__weakref__': <attribute '__weakref__' of '_ViewBase' objects>, '__doc__': None})"


class _ItemsView(_ViewBase[tuple[_TK, _TV]], Generic[_TK, _TV]):
	# no doc
	def __contains__(self, *args, **kwargs): # real signature unknown
		pass

	def __init__(self, *args, **kwargs): # real signature unknown
		pass

	__weakref__ = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default
	"""list of weak references to the object (if defined)"""

	_abc_impl = None # (!) real value is '<_abc_data object at 0x036F43E0>'
	__abstractmethods__ = frozenset()
	__dict__ = None # (!) real value is "mappingproxy({'__module__': 'utils.collections.orderedmultidictBase', '__contains__': <cyfunction _ItemsView.__contains__ at 0x0369DF10>, '__iter__': <cyfunction _ItemsView.__iter__ at 0x0369DF80>, '__reversed__': <cyfunction _ItemsView.__reversed__ at 0x036F7030>, '__repr__': <cyfunction _ItemsView.__repr__ at 0x036F70A0>, '__dict__': <attribute '__dict__' of '_ItemsView' objects>, '__weakref__': <attribute '__weakref__' of '_ItemsView' objects>, '__doc__': None, '__abstractmethods__': frozenset(), '_abc_impl': <_abc_data object at 0x036F43E0>})"


class _KeysView(_ViewBase[_TK], Generic[_TK]):
	# no doc
	def __contains__(self, *args, **kwargs): # real signature unknown
		pass

	def __init__(self, *args, **kwargs): # real signature unknown
		pass

	__weakref__ = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default
	"""list of weak references to the object (if defined)"""

	_abc_impl = None # (!) real value is '<_abc_data object at 0x036F4420>'
	__abstractmethods__ = frozenset()
	__dict__ = None # (!) real value is "mappingproxy({'__module__': 'utils.collections.orderedmultidictBase', '__contains__': <cyfunction _KeysView.__contains__ at 0x036F7260>, '__iter__': <cyfunction _KeysView.__iter__ at 0x036F72D0>, '__repr__': <cyfunction _KeysView.__repr__ at 0x036F7340>, '__dict__': <attribute '__dict__' of '_KeysView' objects>, '__weakref__': <attribute '__weakref__' of '_KeysView' objects>, '__doc__': None, '__abstractmethods__': frozenset(), '_abc_impl': <_abc_data object at 0x036F4420>})"


class _UniqueKeysView(_ViewBase[_TK], Generic[_TK]):
	# no doc
	def __contains__(self, *args, **kwargs): # real signature unknown
		pass

	def __init__(self, *args, **kwargs): # real signature unknown
		pass

	__weakref__ = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default
	"""list of weak references to the object (if defined)"""


	_abc_impl = None # (!) real value is '<_abc_data object at 0x036F4420>'
	__abstractmethods__ = frozenset()
	__dict__ = None # (!) real value is "mappingproxy({'__module__': 'utils.collections.orderedmultidictBase', '__contains__': <cyfunction _UniqueKeysView.__contains__ at 0x036F7260>, '__iter__': <cyfunction _UniqueKeysView.__iter__ at 0x036F72D0>, '__repr__': <cyfunction _UniqueKeysView.__repr__ at 0x036F7340>, '__dict__': <attribute '__dict__' of '_UniqueKeysView' objects>, '__weakref__': <attribute '__weakref__' of '_UniqueKeysView' objects>, '__doc__': None, '__abstractmethods__': frozenset(), '_abc_impl': <_abc_data object at 0x036F4420>})"


class _ValuesView(_ViewBase[_TV], Generic[_TV]):
	# no doc
	def __contains__(self, *args, **kwargs): # real signature unknown
		pass

	def __init__(self, *args, **kwargs): # real signature unknown
		pass

	__weakref__ = property(lambda self: object(), lambda self, v: None, lambda self: None)  # default
	"""list of weak references to the object (if defined)"""

	_abc_impl = None # (!) real value is '<_abc_data object at 0x036F4400>'
	__abstractmethods__ = frozenset()
	__dict__ = None # (!) real value is "mappingproxy({'__module__': 'utils.collections.orderedmultidictBase', '__contains__': <cyfunction _ValuesView.__contains__ at 0x036F7110>, '__iter__': <cyfunction _ValuesView.__iter__ at 0x036F7180>, '__repr__': <cyfunction _ValuesView.__repr__ at 0x036F71F0>, '__dict__': <attribute '__dict__' of '_ValuesView' objects>, '__weakref__': <attribute '__weakref__' of '_ValuesView' objects>, '__doc__': None, '__abstractmethods__': frozenset(), '_abc_impl': <_abc_data object at 0x036F4400>})"


# variables with complex values


__loader__ = None # (!) real value is '<_frozen_importlib_external.ExtensionFileLoader object at 0x036EBF30>'

__spec__ = None # (!) real value is "ModuleSpec(name='utils.collections.orderedmultidictBase', loader=<_frozen_importlib_external.ExtensionFileLoader object at 0x036EBF30>, origin='D:/helper_scripts\\\\utils\\\\collections\\\\orderedmultidictBase.cp37-win32.pyd')"

__test__ = {}

