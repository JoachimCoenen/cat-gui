# cython: profile=True
# distutils: language = c++
from __future__ import annotations

from libcpp.deque cimport deque
from libcpp.pair cimport pair

from cpython.ref cimport PyObject

from Cat.cpp.libcpp.unordered_map cimport unordered_map

cdef extern from "pyObjectPtrHash.h":
	cdef cppclass PyObjectPtrHash:
		size_t operator()(PyObject *) except+

	cdef cppclass PyObjectPtrHashEqual:
		size_t operator()(PyObject *) except+


# _TV = TypeVar('_TV')
# _TK = TypeVar('_TK', bound=Hashable)


ctypedef PyObject* ObjectPtr


cdef struct ObjectPtrHash:
	int age
	float volume


cdef class OrderedMultiDictBase


cdef class _ViewBase:
	cdef OrderedMultiDictBase _impl


cdef class _ItemsView(_ViewBase):
	pass


cdef class _ValuesView(_ViewBase):
	pass


cdef class _KeysView(_ViewBase):
	pass


cdef class _UniqueKeysView(_ViewBase):
	pass


cdef class OrderedMultiDictBase:
	"""docstring for OrderedMultiDictBase"""
	#__slots__ = ('_items', '_map', '_index')

	cdef public:
		object _items  # : OrderedDict[int, Tuple[_TK, _TV]]

	cdef size_t _index

	cdef unordered_map[ObjectPtr, deque[pair[size_t, ObjectPtr]], PyObjectPtrHash, PyObjectPtrHashEqual]*_map

	cpdef void load(self, iterable)

	cpdef void clear(self)

	cdef deque[pair[size_t, ObjectPtr]]* getAllOrNull(self, ObjectPtr key)


	cpdef object get(self, key: _TK, default=?)

	cpdef object getFirst(self, key: _TK, default=?)

	cpdef object getLast(self, key: _TK, default=?)

	cpdef list getall(self, key: _TK, default=?)

	cpdef object setdefault(self, key: _TK, default)

	cpdef list setdefaultAll(self, key: _TK, list defaultlist: list[_TV])

	cpdef void setAll(self, key: _TK, valueList: list[_TV])

	cpdef void add(self, key: _TK, value: _TV)

	cpdef void addAll(self, key: _TK, valuelist: list[_TV])

	# cpdef void insertFirst(self, key: _TK, value: _TV)

	# cpdef void insertAllFirst(self, key: _TK, valuelist: list[_TV])

	# cpdef void insertLast(self, key: _TK, value: _TV)

	# cpdef void insertAllLast(self, key: _TK, valuelist: list[_TV])

	cpdef void extend(self, keyValuelist: list[Tuple[_TK, _TV]])

	cpdef object pop(self, key: _TK, default=?)

	cpdef list popAll(self, key: _TK, list default: list[_TV] = ?)

	cpdef object popFirstItem(self, default=?)

	cpdef object popLastItem(self, default=?)

	cpdef object popFirst(self, key: _TK, default: _TV = ?)

	cpdef object popLast(self, key: _TK, default: _TV = ?)

	cpdef deleteAll(self, key: _TK)

	cdef bint _tryDeleteAll(self, ObjectPtr key: _TK)