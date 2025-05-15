# copied and modified from https://ideone.com/G4iIri by https://stackoverflow.com/users/2357112/user2357112.
from typing import MutableMapping, final, Iterator
from weakref import ref, WeakKeyDictionary, WeakValueDictionary


@final
# @as_dataclass(use_weakref=True, fast_new=True, )
class _Id[_TK]:
	__slots__ = ('_id', 'keyref', '__weakref__', )
	# _id: int
	# keyref: ref[_TK]

	def __init__(self, key: _TK):
		self._id: int = id(key)
		self.keyref: ref[_TK] = ref(key)

	def __hash__(self) -> int:
		return self._id

	def __eq__(self, other) -> bool:
		if not isinstance(other, _Id):
			return NotImplemented
		return self._id == other._id and self.keyref() is other.keyref()

	def __ne__(self, other) -> bool:
		if not isinstance(other, _Id):
			return NotImplemented
		return not (self._id == other._id and self.keyref() is other.keyref())


class WeakUnhashableKeyDict[_TK, _TT](MutableMapping[_TK, _TT]):
	"""
	WeakKeyDictionary implementation, that can handle non-hashable key by using their id(...).
	"""

	def __init__(self) -> None:
		self._keys: WeakValueDictionary[_Id[_TK], _TK] = WeakValueDictionary()  # keeps the `_Id`-typed keys alive
		self._values: WeakKeyDictionary[_Id[_TK], _TT] = WeakKeyDictionary()

	def __getitem__(self, key: _TK) -> _TT:
		return self._values.__getitem__(_Id(key))

	def __setitem__(self, key: _TK, value: _TT):
		_id = _Id(key)
		# NOTE This works because key holds on _id iif key exists,
		# and _id holds on value iif _id exists. Transitivity. QED.
		# Because key is only stored as a value, it does not need to be hashable.
		self._keys.__setitem__(_id, key)
		self._values.__setitem__(_id, value)

	def __delitem__(self, key: _TK) -> None:
		# first remove from _values, only then remove from _keys, because the entry in _keys keep the entry in _values alive
		self._values.__delitem__(_Id(key))
		self._keys.__delitem__(_Id(key))

	def keyrefs(self) -> list[ref[_TK]]:
		return self._keys.valuerefs()

	def keys(self) -> Iterator[_TK]:
		return self._keys.values()

	def values(self) -> Iterator[_TT]:
		return self._values.values()

	def items(self) -> Iterator[tuple[_TK, _TT]]:
		return ((key.keyref, value) for key, value in self._values.items())

	def __iter__(self) -> Iterator[_TK]:
		return self.keys()

	def __len__(self) -> int:
		return len(self._keys)
