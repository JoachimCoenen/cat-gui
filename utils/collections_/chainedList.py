from __future__ import annotations
from typing import TypeVar, Generic, Iterator, Sequence

_TT = TypeVar("_TT")


class ChainedList(Sequence[_TT], Generic[_TT]):
	def __init__(self,  *lists: list[_TT]) -> None:
		self._lists: tuple[list[_TT], ...] = lists

	def copy(self) -> ChainedList[_TT]: ...

	# def append(self, __object: _TT) -> None: ...

	# def extend(self, __iterable: Iterable[_TT]) -> None: ...

	# def pop(self, __index: int = ...) -> _TT: ...

	# def index(self, __value: _TT, __start: int = ..., __stop: int = ...) -> int: ...
	def index(self, __value: _TT) -> int:
		index = 0
		for l in self._lists:
			try:
				index += l.index(__value)
				return index
			except ValueError:
				index += len(l)
		raise ValueError(f'{__value!r} is not in list')

	def count(self, __value: _TT) -> int:
		count = 0
		for l in self._lists:
			count += l.count(__value)
		return count

	def __len__(self) -> int:
		return sum(map(len, self._lists))

	def __iter__(self) -> Iterator[_TT]:
		for l in self._lists:
			yield from l

	def __str__(self) -> str:
		return f"{type(self).__name__}{self._lists}"

	def __getitem__(self, i: int) -> _TT:
		i2 = i
		for l in self._lists:
			lenl = len(l)
			if i2 < lenl:
				return l[i2]
			i2 -= lenl
		raise IndexError("list index out of range")

	def __contains__(self, o: _TT) -> bool:
		for l in self._lists:
			if o in l:
				return True
		return False
	#
	# def __gt__(self, x: List[_TT]) -> bool: ...
	#
	# def __ge__(self, x: List[_TT]) -> bool: ...
	#
	# def __lt__(self, x: List[_TT]) -> bool: ...
	#
	# def __le__(self, x: List[_TT]) -> bool: ...
