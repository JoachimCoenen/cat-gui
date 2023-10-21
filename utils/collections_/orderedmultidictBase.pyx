# cython: profile=True
# distutils: language = c++
# distutils: extra_compile_args = /Zc:__cplusplus

from __future__ import annotations
from collections import OrderedDict
from itertools import zip_longest
from typing import Iterator, TypeVar, Hashable, Callable, Optional, Tuple, Any

from libcpp.deque cimport deque
from libcpp.pair cimport pair
from libcpp.utility cimport move

from cython.operator cimport dereference as deref

#from Cat.cpp.libcpp.unordered_map cimport unordered_map

_LOGGING_ENABLED = False


# Marker that means no parameter was provided.
cdef object _absent = object()


_TV = TypeVar('_TV', covariant=False)
_TK = TypeVar('_TK', bound=Hashable)


cdef class _ViewBase:
	__slots__ = ()
	#__slots__ = ('_impl', )

	def __init__(self, impl: OrderedMultiDictBase):
		self._impl: OrderedMultiDictBase = impl

	def __len__(self):
		return len(self._impl._items)


cdef class _ItemsView(_ViewBase):
	__slots__ = ()

	def __contains__(self, item: Tuple[_TK, _TV]) -> bool:
		assert isinstance(item, tuple) or isinstance(item, list)
		assert len(item) == 2

		for i, v in self._impl.getAll(item[0]):
			if v == item[1]:
				return True
		return False

	def __iter__(self) -> Iterator[Tuple[_TK, _TV]]:
		return iter(self._impl._items.values())

	def __reversed__(self) -> Iterator[Tuple[_TK, _TV]]:
		return reversed(self._impl._items.values())

	def __repr__(self):
		lst = []
		for item in self._impl._items.values():
			lst.append("{!r}: {!r}".format(item[0], item[1]))
		body = ', '.join(lst)
		return '{}({})'.format(self.__class__.__name__, body)


cdef class _ValuesView(_ViewBase):
	__slots__ = ()

	def __contains__(self, value: _TV) -> bool:
		for item in self._impl._items.values():
			if item[1] == value:
				return True
		return False

	def __iter__(self) -> Iterator[_TV]:
		# return (v[1] for v in self._impl._items.values())
		for _, v in self._impl._items.values():
			yield v

	def __reversed__(self) -> Iterator[_TV]:
		# return (v[1] for v in reversed(self._impl._items.values()))
		for _, v in reversed(self._impl._items.values()):
			yield v

	def __repr__(self):
		lst = []
		for item in self._impl._items:
			lst.append("{!r}".format(item[1]))
		body = ', '.join(lst)
		return '{}({})'.format(self.__class__.__name__, body)


cdef class _KeysView(_ViewBase):
	__slots__ = ()

	def __contains__(self, key: _TK) -> bool:
		# return key in self._impl._map
		return self._impl._map.find(<ObjectPtr>key) != self._impl._map.end()

	def __iter__(self) -> Iterator[_TK]:
		return (k for k, _ in self._impl._items.values())

	def __reversed__(self) -> Iterator[_TV]:
		return (k for k, _ in reversed(self._impl._items.values()))

	def __repr__(self):
		lst = []
		for item in self._impl._items.values():
			lst.append("{!r}".format(item[0]))
		body = ', '.join(lst)
		return '{}({})'.format(self.__class__.__name__, body)


cdef class _UniqueKeysView(_ViewBase):
	__slots__ = ()
	
	def __contains__(self, key: _TK) -> bool:
		# return key in self._impl._map
		return self._impl._map.find(<ObjectPtr>key) != self._impl._map.end()

	def __iter__(self) -> Iterator[_TK]:
		alreadySeen: set = set()
		return (k for k, _ in self._impl._items.values() if k not in alreadySeen and not alreadySeen.add(k))

	def __reversed__(self) -> Iterator[_TV]:
		alreadySeen: set = set()
		return (k for k, _ in reversed(self._impl._items.values()) if k not in alreadySeen and not alreadySeen.add(k))

	def __repr__(self):
		lst = []
		for key in self:
			lst.append(f"{key!r}")
		body = ', '.join(lst)
		return f'{self.__class__.__name__}({body})'

	def __len__(self):
		return self._impl._map.size()


_SENTINEL_ = object()


cdef class OrderedMultiDictBase():
	"""docstring for OrderedMultiDictBase"""
	#__slots__ = ('_items', '_map', '_index')

	def __cinit__(self, iterable=None):
		self._map = new unordered_map[ObjectPtr, deque[pair[size_t, ObjectPtr]], PyObjectPtrHash, PyObjectPtrHashEqual]()
		self._index: int = 0

	def __dealloc__(self):
		self._map.clear()
		del self._map
		self._map = NULL
		#self._items.clear()

	def __init__(self, iterable=None):
		super().__init__()
		self._items: OrderedDict[int, Tuple[_TK, _TV]] = OrderedDict()
		# self._map: Dict[_TK, List[Tuple[int, _TV]]] = dict()
		# self._index: int = 0
		if iterable is not None:
			self.load(iterable)

	cpdef void load(self, iterable):
		"""
		Clear all existing key:value items and import all key:value items from
		<mapping>. If multiple values exist for the same key in <mapping>, they
		are all be imported.

		Returns: <self>.
		"""
		self.clear()
		for k, v in iterable:
			self.add(k, v)

	def copy(self):
		#return self.__class__(self.items())
		other: OrderedMultiDictBase = self.__class__()
		other._items =  self._items.copy()
		other._index =  self._index
		del other._map
		other._map = new unordered_map[ObjectPtr, deque[pair[size_t, ObjectPtr]], PyObjectPtrHash, PyObjectPtrHashEqual](self._map[0])

		return other

	cpdef void clear(self):
		self._map.clear() # important! clear _map first!!
		self._items.clear()
		self._index = 0

	cdef deque[pair[size_t, ObjectPtr]]* getAllOrNull(self, ObjectPtr key):
		it = self._map.find(key)
		if it != self._map.end():  # if key in self:
			result = &deref(it).second
			assert not result.empty()
			return result
		else:
			return NULL

	cpdef object get(self, key, default=None):  # -> _TV
		vals = self.getAllOrNull(<ObjectPtr>key)
		if vals:  # if key in self:
			# return <object>self._map[0][<ObjectPtr>key][0].second
			return <object>vals.front().second
		return default

	cpdef object getFirst(self, key, default=None):  # -> _TV
		vals = self.getAllOrNull(<ObjectPtr>key)
		if vals:  # if key in self:
			# return <object>self._map[0][<ObjectPtr>key][0].second
			return <object>vals.front().second
		return default

	cpdef object getLast(self, key, default=None):  # -> _TV
		vals = self.getAllOrNull(<ObjectPtr>key)
		if vals:  # if key in self:
			return <object>vals.back().second
		return default

	cpdef list getall(self, key, default=_SENTINEL_):  # -> List[_TV]
		"""
		Returns: The list of values for <key> if <key> is in the dictionary,
		else <default>. If <default> is not provided, an empty list is
		returned.
		"""
		vals = self.getAllOrNull(<ObjectPtr>key)
		if vals:  # if key in self:
			return [<object>v.second for v in vals[0]]
		if default is _SENTINEL_:
			return []
		else:
			return default

	cpdef object setdefault(self, key: _TK, default: _TV):  # -> _TV
		vals = self.getAllOrNull(<ObjectPtr>key)
		if vals:  # if key in self:
			return <object>vals.front().second
		self.add(key, default)
		return default

	cpdef list setdefaultAll(self, key: _TK, defaultlist: list[_TV]):  # (self, _TK, Optional[List[_TV]]) -> List[_TV]
		"""
		Similar to setdefault() except <defaultlist> is a list of values to set
		for <key>. If <key> already exists, its existing list of values is
		returned.

		If <key> isn't a key and <defaultlist> is an empty list, [], no values
		are added for <key> and <key> will not be added as a key.

		Returns: List of <key>'s values if <key> exists in the dictionary,
		otherwise <default>.
		"""
		vals = self.getAllOrNull(<ObjectPtr>key)
		if vals:  # if key in self:
			return self.getall(key)
		self.addAll(key, defaultlist)
		return defaultlist

	cpdef void setAll(self, key: _TK, valueList: Iterable[_TV]):  # (self, _TK, List[_TV]) -> List[_TV]
		self._tryDeleteAll(<ObjectPtr>key)
		self.addAll(key, valueList)

	cpdef void add(self, key: _TK, value: _TV):
		"""
		Add <value> to the list of values for <key>. If <key> is not in the
		dictionary, then <value> is added as the sole value for <key>.

		Example:
		  omd = omdict()
		  omd.add(1, 1)  # omd.getall() == [(1,1)]
		  omd.add(1, 11) # omd.getall() == [(1,1), (1,11)]
		  omd.add(2, 2)  # omd.getall() == [(1,1), (1,11), (2,2)]
		"""
		# if isinstance(key, int) or (isinstance(value, tuple) and isinstance(value[0], int)):
		# 	traceback.print_stack()
		index: size_t = self._index
		self._index += 1
		#self._map[0][key] = []

		values = &self._map[0][<ObjectPtr>key]  # entry in _map is created here if necessary
		if not values.empty():
			keyIndex = values[0].front().first # make sure the SAME key is always used, so we don`t loose our keys, since _map doesnt increment the refCount.
			key = self._items[keyIndex][0]
			#Py_IncRef
		self._items[index] = (key, value)
		cdef pair[size_t, ObjectPtr] pr = pair[size_t, ObjectPtr](index, <ObjectPtr>value)
		values.push_back(pr) # entry in _map is created here if necessary


	cpdef void addAll(self, key: _TK, valuelist: Iterable[_TV]):  # (self, _TK, List[_TV]) -> None
		"""
		Add the values in <valuelist> to the list of values for <key>. If <key>
		is not in the dictionary, the values in <valuelist> become the values
		for <key>.

		Example:
		  omd = omdict([(1,1)])
		  omd.addlist(1, [11, 111])
		  omd.getall() == [(1, 1), (1, 11), (1, 111)]
		  omd.addlist(2, [2])
		  omd.getall() == [(1, 1), (1, 11), (1, 111), (2, 2)]
		"""
		for value in valuelist:
			self.add(key, value)

	cpdef void extend(self, keyValuelist: Iterable[Tuple[_TK, _TV]]):
		for key, value in keyValuelist:
			self.add(key, value)

	# cpdef void insertFirst(self, key, value: _TV):
	# 	"""
	# 	insert <value> at the beginning of the list of values for <key>. If <key> is not in the
	# 	dictionary, then <value> is added as the sole value for <key>.

	# 	Example:
	# 	  omd = omdict()
	# 	  omd.add(1, 1)         # omd.getall() == [(1,1)]
	# 	  omd.add(2, 2)         # omd.getall() == [(1,1), (2,2)]
	# 	  omd.insertFirst(2, 9) # omd.getall() == [(1,1), (2,9), (2,2)]
	# 	"""
	# 	# if isinstance(key, int) or (isinstance(value, tuple) and isinstance(value[0], int)):
	# 	# 	traceback.print_stack()
	# 	index: size_t = self._index
	# 	self._index += 1
	# 	#self._map[0][key] = []

	# 	values = &self._map[0][<ObjectPtr>key]  # entry in _map is created here if necessary
	# 	if not values.empty():
	# 		keyIndex = values[0].front().first # make sure the SAME key is always used, so we don`t loose our keys, since _map doesnt increment the refCount.
	# 		key = self._items[keyIndex][0]
	# 		#Py_IncRef
	# 	self._items[index] = (key, value)
	# 	cdef pair[size_t, ObjectPtr] pr = pair[size_t, ObjectPtr](index, <ObjectPtr>value)
	# 	values.push_back(pr) # entry in _map is created here if necessary

	# cpdef void insertAllFirst(self, key, valuelist: List[_TV]):
	# 	"""
	# 	insert the values in <valuelist> at the beginning of the list of values for <key>. If <key> is not in the
	# 	dictionary, then <value> is added as the sole value for <key>.

	# 	Example:
	# 	  omd = omdict()
	# 	  omd.add(1, 1)                 # omd.getall() == [(1,1)]
	# 	  omd.add(2, 2)                 # omd.getall() == [(1,1), (2,2)]
	# 	  omd.insertAllFirst(2, [8, 9]) # omd.getall() == [(1,1), (2,8), (2,9), (2,2)]
	# 	"""
	# 	# if isinstance(key, int) or (isinstance(value, tuple) and isinstance(value[0], int)):
	# 	# 	traceback.print_stack()
	# 	index: size_t = self._index
	# 	self._index += 1
	# 	#self._map[0][key] = []

	# 	values = &self._map[0][<ObjectPtr>key]  # entry in _map is created here if necessary
	# 	if not values.empty():
	# 		keyIndex = values[0].front().first # make sure the SAME key is always used, so we don`t loose our keys, since _map doesnt increment the refCount.
	# 		key = self._items[keyIndex][0]
	# 		#Py_IncRef
	# 	self._items[index] = (key, value)
	# 	cdef pair[size_t, ObjectPtr] pr = pair[size_t, ObjectPtr](index, <ObjectPtr>value)
	# 	values.push_back(pr) # entry in _map is created here if necessary



	cpdef object pop(self, key: _TK, default=_absent):  # -> Union[_TV]
		return self.popLast(key, default=default)

	cpdef list popAll(self, key: _TK, default: list[_TV] = None):  # (self, _TK, List[_TV]) -> List[_TV]
		"""
		If <key> is in the dictionary, pop it and return its list of values. If
		<key> is not in the dictionary, return <default>. KeyError is raised if
		<default> is not provided and <key> is not in the dictionary.

		Example:
		  omd = omdict([(1,1), (1,11), (1,111), (2,2), (3,3)])
		  omd.popAll(1) == [1, 11, 111]
		  omd.getall() == [(2,2), (3,3)]
		  omd.popAll(2) == [2]
		  omd.getall() == [(3,3)]

		Raises: KeyError if <key> isn't in the dictionary and <default> isn't
		  provided.
		Returns: List of <key>'s values.
		"""
		values = self.getAllOrNull(<ObjectPtr>key)
		if values:  # if key in self:
			result = []
			for val in values[0]:
				i = val.first
				result.append(<object>val.second)
				del self._items[i]
			self._map.erase(<ObjectPtr>key)
			return result
		elif default is not None:
			return default
		raise KeyError(key)
	
	cpdef object popFirstItem(self, default=_absent):  # -> Tuple[_TK, _TV]
		cdef deque[pair[size_t, ObjectPtr]]* values
		cdef pair[size_t, ObjectPtr] popped
		try:
			item = self._items.popitem(last=False)[1]
		except KeyError:
			if default is not _absent:
				return default
			else:
				raise
		values = self.getAllOrNull(<ObjectPtr>item[0])
		if values:  # if key in self:

			values.pop_front() 
			# # {
			# if 0 != values.size() - 1:
			# 	# Beware of move assignment to self
			# 	# see http://stackoverflow.com/questions/13127455/
			# 	values[0][0] = move(values.back())
			# values.pop_back()
			# # } // values.pop_front()
			if values.empty():
				self._map.erase(<ObjectPtr>item[0])

			return item
		else:
			raise RuntimeError("Bad State in OrderedMultiDict")

	cpdef object popLastItem(self, default=_absent):  # -> Tuple[_TK, _TV]
		cdef deque[pair[size_t, ObjectPtr]]* values
		cdef pair[size_t, ObjectPtr] popped
		try:
			item = self._items.popitem(last=True)[1]
		except KeyError:
			if default is not _absent:
				return default
			else:
				raise
		values = self.getAllOrNull(<ObjectPtr>item[0])
		if values:  # if key in self:
			values.pop_back()
			if values.empty():
				self._map.erase(<ObjectPtr>item[0])
			return item
		else:
			raise RuntimeError("Bad State in OrderedMultiDict")

	cpdef object popFirst(self, key: _TK, default: _TV = _absent):  # -> _TV
		cdef deque[pair[size_t, ObjectPtr]]* values
		cdef pair[size_t, ObjectPtr] popped

		values = self.getAllOrNull(<ObjectPtr>key)
		if values:  # if key in self:
			popped = values.front()
			values.pop_front()
			index = popped.first
			value = <object>popped.second
			del self._items[index]
			if values.empty():
				self._map.erase(<ObjectPtr>key)
			return value
		elif default is not _absent:
			return default
		raise KeyError(key)

	cpdef object popLast(self, key: _TK, default: _TV = _absent):  # -> _TV
		cdef deque[pair[size_t, ObjectPtr]]* values
		cdef pair[size_t, ObjectPtr] popped

		values = self.getAllOrNull(<ObjectPtr>key)
		if values:  # if key in self:
			popped = values.back()
			values.pop_back()
			index = popped.first
			value = <object>popped.second
			del self._items[index]
			if values.empty():
				self._map.erase(<ObjectPtr>key)
			return value
		elif default is not _absent:
			return default
		raise KeyError(key)

	cpdef deleteAll(self, key: _TK):
		"""
		Removes all entries for key. Raises a KeyError if key is not in the dictionary.

		Example:
		  omd = omdict([(1,1), (1,11), (1,111), (2,2), (3,3)])
		  omd.deleteAll(1)
		  omd.getall() == [(2,2), (3,3)]
		  omd.deleteAll(99)  # raises KeyError
		"""
		if not self._tryDeleteAll(<ObjectPtr>key):
			raise KeyError(key)

	cdef bint _tryDeleteAll(self, ObjectPtr key: _TK):
		"""
		Removes all entries for key.
		Returns True if key was in the dictionary, otherwise False.
		"""
		values = self.getAllOrNull(key)
		if values:  # if key in self:
			for val in values[0]:
				i = val.first
				del self._items[i]
			self._map.erase(<ObjectPtr>key)
			return True
		else:
			return False

	def items(self):
		return _ItemsView(self)

	def keys(self):
		return _KeysView(self)

	def uniqueKeys(self):
		return _UniqueKeysView(self)

	def values(self):
		return _ValuesView(self)

	def sort(self, *, key: Optional[Callable[[Tuple[_TK, _TV]], Any]] = None, reverse: bool = False):
		self._items = OrderedDict(enumerate(sorted(self._items.values(), key=key, reverse=reverse)))

	def __eq__(self, other):
		if not hasattr(other, 'items'):
			return False
		for i1, i2 in zip_longest(self.items(), other.items(), fillvalue=_absent):
			if i1 != i2 or i1 is _absent or i2 is _absent:
				return False
		return True

	def __ne__(self, other):
		return not self.__eq__(other)

	def __len__(self):
		return len(self._items)

	def __iter__(self):
		return iter(self.keys())

	def __contains__(self, key: _TK):
		# return key in self._map
		return self._map.find(<ObjectPtr>key) != self._map.end()

	def __getitem__(self, key: _TK) -> _TV:
		vals = self.getAllOrNull(<ObjectPtr>key)
		if vals:  # if key in self:
			# return <object>self._map[0][<ObjectPtr>key][0].second
			return <object>vals.front().second
		raise KeyError(key)

	def __setitem__(self, key: _TK, value: _TV):
		self.setAll(key, [value])

	def __delitem__(self, key: _TK):
		self.pop(key)

	def __nonzero__(self):
		return not self._map.empty()

	def __str__(self):
		return '{%s}' % ', '.join(
			map(lambda p: f'{repr(p[0])}: {repr(p[1])}', self._items.items()))

	def __repr__(self):
		return '%s(%s)' % (self.__class__.__name__, self._items.items())

	def __getstate__(self):
		return list(self._items.values())

	def __setstate__(self, state: list):  # (self, _TK, List[Tuple[_TK, _TV]])
		# self.load(state)
		self._items: OrderedDict[int, Tuple[_TK, _TV]] = OrderedDict()
		for k, v in state:
			self.add(k, v)

	# def __reduce__()

	# def __or__(self, other):
	# 	return self.__class__(chain(_get_items(self), _get_items(other)))

	# def __ior__(self, other):
	# 	for k, v in _get_items(other):
	# 		self.add(k, value=v)
	# 	return self
