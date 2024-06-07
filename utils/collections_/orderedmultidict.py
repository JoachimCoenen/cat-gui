from __future__ import annotations
from collections import deque, defaultdict, OrderedDict
from itertools import zip_longest
from typing import Any, Callable, Hashable, Iterable, Iterator, Optional, overload, Union, \
	MutableMapping


_SENTINEL_ = object()


class OrderedMultiDict[TK: Hashable, TV](MutableMapping[TK, TV]):
	def __init__(self, iterable: Optional[Iterable[tuple[TK, TV]]] = None):
		self._items: OrderedDict[int, tuple[TK, TV]] = OrderedDict()
		self._map: defaultdict[TK, deque[tuple[int, TV]]] = defaultdict(deque)
		self._index: int = 0

		if iterable is not None:
			self.load(iterable)

	def load(self, iterable: Iterable[tuple[TK, TV]]):
		"""
		Clear all existing key:value items and import all key:value items from
		<mapping>. If multiple values exist for the same key in <mapping>, they
		are all be imported.
		"""
		self.clear()
		for k, v in iterable:
			self.add(k, v)

	def copy(self) -> OrderedMultiDict[TK, TV]:
		other: OrderedMultiDict = self.__class__()
		other._items = self._items.copy()
		other._index = self._index
		del other._map
		other._map = {key: que.copy() for key, que in self._map.items()}
		return other

	def clear(self):
		self._map.clear()  # important! clear _map first!!
		self._items.clear()
		self._index = 0

	def _getAllOrNull(self, key: TK) -> Optional[deque[tuple[int, TV]]]:
		it = self._map.get(key)
		if it is not None:  # if key in self:
			result = it
			assert result
			return result
		else:
			return None

	def get[TT](self, key: TK, default: TT = None) -> TV | TT:
		""" same as getFirst(...)
		:param key:
		:param default:
		:return:
		"""
		vals = self._getAllOrNull(key)
		if vals is not None:  # if key in self:
			return vals[0][1]
		return default

	def getFirst[TT](self, key, default: TT = None) -> TV | TT:
		""" same as get(...)
		:param key:
		:param default:
		:return:
		"""
		vals = self._getAllOrNull(key)
		if vals is not None:  # if key in self:
			return vals[0][1]
		return default

	def getLast[TT](self, key: TK, default: TT = None) -> TV | TT:
		vals = self._getAllOrNull(key)
		if vals is not None:  # if key in self:
			return vals[-1][1]
		return default

	@overload
	def getall(self, key: TK) -> list[TV]:
		"""
		Returns: The list of values for <key> if <key> is in the dictionary,
		else <default>. If <default> is not provided, an empty list is
		returned.
		"""
		...

	@overload
	def getall[TT](self, key: TK, default: TT) -> list[TV] | TT:
		"""
		Returns: The list of values for <key> if <key> is in the dictionary,
		else <default>. If <default> is not provided, an empty list is
		returned.
		"""
		...

	def getall[TT](self, key: TK, default: TT = _SENTINEL_) -> list[TV] | TT:
		"""
		Returns: The list of values for <key> if <key> is in the dictionary,
		else <default>. If <default> is not provided, an empty list is
		returned.
		"""
		vals = self._getAllOrNull(key)
		if vals is not None:  # if key in self:
			return [v[1] for v in vals]
		elif default is _SENTINEL_:
			return []
		else:
			return default

	def setdefault(self, key: TK, default: TV) -> TV:
		vals = self._getAllOrNull(key)
		if vals is not None:  # if key in self:
			return vals[0][1]
		self.add(key, default)
		return default

	def setdefaultAll(self, key: TK, defaultlist: list[TV]) -> list[TV]:
		"""
		Similar to setdefault() except <defaultlist> is a list of values to set
		for <key>. If <key> already exists, its existing list of values is
		returned.

		If <key> isn't a key and <defaultlist> is an empty list, [], no values
		are added for <key> and <key> will not be added as a key.

		Returns: List of <key>'s values if <key> exists in the dictionary,
		otherwise <defaultlist>.
		"""
		vals = self._getAllOrNull(key)
		if vals is not None:  # if key in self:
			return self.getall(key)
		self.addAll(key, defaultlist)
		return defaultlist

	def setAll(self, key: TK, valueList: list[TV]):
		self._tryDeleteAll(key)
		self.addAll(key, valueList)

	def add(self, key: TK, value: TV):
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
		# if isinstance(key, int) or (isinstance(value, tuple) and isinstance(value[0], int)):
		# 	traceback.print_stack()
		index: int = self._index
		self._index += 1
		# self._map[0][key] = []

		values = self._map[key]  # entry in _map is created here if necessary
		if values:
			keyIndex = values[0][0]  # make sure the SAME key is always used, so we don`t loose our keys, since _map doesn't increment the refCount.
			key = self._items[keyIndex][0]
		self._items[index] = (key, value)
		values.append((index, value))  # entry in _map is created here if necessary

	def addAll(self, key: TK, valuelist: list[TV]):
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
		for value in valuelist:
			self.add(key, value)

	def extend(self, keyValuelist: list[tuple[TK, TV]]):
		for key, value in keyValuelist:
			self.add(key, value)

	@overload
	def pop(self, key: TK) -> TV:
		pass

	@overload
	def pop[TT](self, key: TK, default: TV) -> TV:
		pass

	@overload
	def pop[TT](self, key: TK, default: TT) -> TV | TT:
		pass

	def pop[TT](self, key: TK, default: TV | TT = _SENTINEL_) -> TV | TT:
		return self.popLast(key, default=default)

	@overload
	def popAll(self, key: TK) -> Union[list[TV]]:
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
		...

	@overload
	def popAll[TT](self, key: TK, default: TT) -> list[TV] | TT:
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
		...

	def popAll[TT](self, key: TK, default: TT = _SENTINEL_) -> list[TV] | TT:
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
		values = self._getAllOrNull(key)
		if values is not None:  # if key in self:
			result = []
			for val in values:
				result.append(val[1])
				del self._items[val[0]]
			del self._map[key]
			return result
		elif default is not _SENTINEL_:
			return default
		raise KeyError(key)

	@overload
	def popFirstItem(self) -> tuple[TK, TV]:
		""" """
		...

	@overload
	def popFirstItem[TT](self, *, default: TT) -> tuple[TK, TV] | TT:
		""" """
		...

	def popFirstItem[TT](self, *, default: TT = _SENTINEL_) -> tuple[TK, TV] | TT:
		try:
			item = self._items.popitem(last=False)[1]
		except KeyError:
			if default is not _SENTINEL_:
				return default
			raise

		values = self._getAllOrNull(item[0])
		if values is not None:  # if key in self:
			values.popleft()
			# # {
			# if 0 != values.size() - 1:
			# 	# Beware of move assignment to self
			# 	# see http://stackoverflow.com/questions/13127455/
			# 	values[0][0] = move(values.back())
			# values.pop_back()
			# # } // values.pop_front()
			if not values:
				del self._map[item[0]]

			return item
		else:
			raise RuntimeError("Bad State in OrderedMultiDict")

	@overload
	def popLastItem(self) -> tuple[TK, TV]:
		""" """
		...

	@overload
	def popLastItem[TT](self, *, default: TT) -> tuple[TK, TV] | TT:
		""" """
		...

	def popLastItem[TT](self, *, default: TT = _SENTINEL_) -> tuple[TK, TV] | TT:
		try:
			item = self._items.popitem(last=True)[1]
		except KeyError:
			if default is not _SENTINEL_:
				return default
			raise

		values = self._getAllOrNull(item[0])
		if values is not None:  # if key in self:
			values.pop()
			if not values:
				del self._map[item[0]]
			return item
		else:
			raise RuntimeError("Bad State in OrderedMultiDict")

	@overload
	def popFirst(self, key: TK) -> TV:
		"""
		Raises: KeyError if <key> is absent.
		"""
		pass

	@overload
	def popFirst[TT](self, key: TK, default: TT) -> TV | TT:
		"""
		returns default if <key> is absent.
		"""
		pass

	def popFirst[TT](self, key: TK, default: TT = _SENTINEL_) -> TV | TT:
		"""
		returns default if <key> is absent.
		"""
		values = self._getAllOrNull(key)
		if values is not None:  # if key in self:
			popped = values.popleft()
			del self._items[popped[0]]
			if not values:
				del self._map[key]
			return popped[1]
		elif default is not _SENTINEL_:
			return default
		raise KeyError(key)

	@overload
	def popLast(self, key: TK) -> TV:
		"""
		Raises: KeyError if <key> is absent.
		"""
		pass

	@overload
	def popLast[TT](self, key: TK, default: TT) -> TV | TT:
		"""
		returns default if <key> is absent.
		"""
		pass

	def popLast[TT](self, key: TK, default: TT = _SENTINEL_) -> TV | TT:
		"""
		returns default if <key> is absent.
		"""
		values = self._getAllOrNull(key)
		if values is not None:  # if key in self:
			popped = values.pop()
			del self._items[popped[0]]
			if not values:
				del self._map[key]
			return popped[1]
		elif default is not _SENTINEL_:
			return default
		raise KeyError(key)

	def _deleteAll(self, key: TK):
		"""
		Removes all entries for key. Raises a KeyError if key is not in the dictionary.

		Example:
			omd = omdict([(1,1), (1,11), (1,111), (2,2), (3,3)])
			omd.deleteAll(1)
			omd.getall() == [(2,2), (3,3)]
			omd.deleteAll(99)  # raises KeyError
		"""
		if not self._tryDeleteAll(key):
			raise KeyError(key)

	def _tryDeleteAll(self, key: TK) -> bool:
		"""
		Removes all entries for key.
		Returns True if key was in the dictionary, otherwise False.
		"""
		values = self._getAllOrNull(key)
		if values is not None:  # if key in self:
			for val in values:
				del self._items[val[0]]
			del self._map[key]
			return True
		else:
			return False

	def items(self) -> _ItemsView[TK, TV]:
		return _ItemsView(self)

	def keys(self) -> _KeysView[TK]:
		return _KeysView(self)

	def uniqueKeys(self) -> _UniqueKeysView[TK]:
		return _UniqueKeysView(self)

	def values(self) -> _ValuesView[TV]:
		return _ValuesView(self)

	def sort(self, *, key: Optional[Callable[[tuple[TK, TV]], Any]] = None, reverse: bool = False):
		self._items = OrderedDict(enumerate(sorted(self._items.values(), key=key, reverse=reverse)))

	def __eq__(self, other) -> bool:
		if type(self) is not type(other):
			return NotImplemented
		for i1, i2 in zip_longest(self.items(), other.items(), fillvalue=_SENTINEL_):
			if i1 != i2 or i1 is _SENTINEL_ or i2 is _SENTINEL_:
				return False
		return True

	def __ne__(self, other) -> bool:
		return not self.__eq__(other)

	def __len__(self) -> int:
		return len(self._items)

	def __iter__(self) -> Iterator[TK]:
		return iter(self.keys())

	def __contains__(self, key: TK) -> bool:
		# return key in self._map
		return key in self._map

	def __getitem__(self, key: TK) -> TV:
		vals = self._getAllOrNull(key)
		if vals:  # if key in self:
			# return self._map[0][key][0].second
			return vals[0][1]
		raise KeyError(key)

	def __setitem__(self, key: TK, value: TV) -> None:
		self.setAll(key, [value])

	def __delitem__(self, key: TK) -> None:
		self.pop(key)

	def __bool__(self) -> bool:
		return bool(self._map)

	def __str__(self) -> str:
		return '{%s}' % ', '.join(f'{repr(p[0])}: {repr(p[1])}' for p in self._items.values())

	def __repr__(self) -> str:
		return f'{self.__class__.__name__}({self._items.values()}!r)'

	def __getstate__(self):
		return list(self._items.values())

	def __setstate__(self, state: list):  # (self, TK, List[Tuple[TK, TV]])
		# self.load(state)
		self._items: OrderedDict[int, tuple[TK, TV]] = OrderedDict()
		for k, v in state:
			self.add(k, v)


class _ViewBase[TT]:

	def __init__(self, impl: OrderedMultiDict):
		self._impl: OrderedMultiDict = impl

	def __len__(self):
		return len(self._impl._items)


class _ItemsView[TK: Hashable, TV](_ViewBase[tuple[TK, TV]]):

	def __contains__(self, item: tuple[TK, TV]) -> bool:
		assert isinstance(item, tuple) or isinstance(item, list)
		assert len(item) == 2

		for i, v in self._impl.getall(item[0]):
			if v == item[1]:
				return True
		return False

	def __iter__(self) -> Iterator[tuple[TK, TV]]:
		return iter(self._impl._items.values())

	def __reversed__(self) -> Iterator[tuple[TK, TV]]:
		return reversed(self._impl._items.values())

	def __repr__(self):
		lst = []
		for item in self._impl._items.values():
			lst.append(f"{item[0]!r}: {item[1]!r}")
		body = ', '.join(lst)
		return f'{self.__class__.__name__}({body})'


class _ValuesView[TV](_ViewBase[TV]):

	def __contains__(self, value: TV) -> bool:
		for item in self._impl._items.values():
			if item[1] == value:
				return True
		return False

	def __iter__(self) -> Iterator[TV]:
		# return (v[1] for v in self._impl._items.values())
		for _, v in self._impl._items.values():
			yield v

	def __reversed__(self) -> Iterator[TV]:
		# return (v[1] for v in reversed(self._impl._items.values()))
		for _, v in reversed(self._impl._items.values()):
			yield v

	def __repr__(self):
		lst = []
		for item in self._impl._items.values():
			lst.append(f"{item[1]!r}")
		body = ', '.join(lst)
		return f'{self.__class__.__name__}({body})'


class _KeysView[TK: Hashable](_ViewBase[TK]):

	def __contains__(self, key: TK) -> bool:
		# return key in self._impl._map
		return key in self._impl._map

	def __iter__(self) -> Iterator[TK]:
		return (k for k, _ in self._impl._items.values())

	def __reversed__(self) -> Iterator[TK]:
		return (k for k, _ in reversed(self._impl._items.values()))

	def __repr__(self):
		lst = []
		for item in self._impl._items.values():
			lst.append(f"{item[0]!r}")
		body = ', '.join(lst)
		return f'{self.__class__.__name__}({body})'


class _UniqueKeysView[TK: Hashable](_ViewBase[TK]):

	def __contains__(self, key: TK) -> bool:
		# return key in self._impl._map
		return key in self._impl._map

	def __iter__(self) -> Iterator[TK]:
		alreadySeen: set = set()
		return (k for k, _ in self._impl._items.values() if k not in alreadySeen and not alreadySeen.add(k))

	def __reversed__(self) -> Iterator[TK]:
		alreadySeen: set = set()
		return (k for k, _ in reversed(self._impl._items.values()) if k not in alreadySeen and not alreadySeen.add(k))

	def __repr__(self):
		lst = []
		for key in self:
			lst.append(f"{key!r}")
		body = ', '.join(lst)
		return f'{self.__class__.__name__}({body})'

	def __len__(self):
		return len(self._impl._map)


__all__ = ['OrderedMultiDict']
