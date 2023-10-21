from typing import Generic, Hashable, MutableMapping, TYPE_CHECKING, TypeVar
from .orderedmultidictBase import OrderedMultiDictBase

_TV = TypeVar('_TV')
_TK = TypeVar('_TK', bound=Hashable)

if TYPE_CHECKING:
	class OrderedMultiDict(OrderedMultiDictBase[_TK, _TV], MutableMapping[_TK, _TV], Generic[_TK, _TV]):
		__slots__ = ()
		# @property
		# def data(self) -> dict[_TK, list[_TV]]:
		# 	return self._map
		pass
else:
	class OrderedMultiDict(OrderedMultiDictBase, MutableMapping[_TK, _TV], Generic[_TK, _TV]):
		__slots__ = ()
		# @property
		# def data(self) -> dict[_TK, list[_TV]]:
		# 	return self._map
		pass
