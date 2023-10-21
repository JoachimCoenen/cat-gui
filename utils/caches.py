import sys
from _weakrefset import WeakSet
from abc import abstractmethod
from collections import defaultdict
from typing import AbstractSet, Any, Callable, cast, Container, Generic, Hashable, Protocol, Sized, TypeVar, Union

from ..utils.collections_ import OrderedDict
from ..utils.typing_ import override, typeRepr

_TT = TypeVar('_TT')
_TD = TypeVar('_TD')
_TK = TypeVar('_TK', bound=Hashable)
_TS = TypeVar('_TS')  # _TSelf

DEFAULT_MAX_SIZE = int(2**31) if True else sys.maxsize


class _PCacheBase(Sized, Container[_TK], Protocol[_TK, _TT]):

	@property
	@abstractmethod
	def maxSize(self) -> int: ...

	@property
	@abstractmethod
	def hits(self) -> int: ...

	@property
	@abstractmethod
	def misses(self) -> int: ...

	def clear(self) -> None: ...

	def reset(self) -> None: ...

	def pop(self, key: _TK, sentinel: _TD = None) -> Union[_TT, _TD]: ...

	def get(self, key: _TK, sentinel: _TD = None) -> Union[_TT, _TD]: ...

	def set(self, key: _TK, value: _TT) -> None: ...

	def __setitem__(self, key: _TK, value: _TT): ...

	@abstractmethod
	def __contains__(self, key: _TK) -> bool: ...


class PCache(_PCacheBase[_TK, _TT], Protocol[_TK, _TT]):
	#
	# @property
	# def name(self) -> Optional[str]: ...

	def copy(self: _TS) -> _TS: ...


class PGeneratingCache(_PCacheBase[_TK, _TT], Protocol[_TK, _TT]):

	def getOrGenerate(self, key: _TK) -> _TT: ...


class PGlobalCache(_PCacheBase[_TK, _TT], Protocol[_TK, _TT]):

	@property
	@abstractmethod
	def name(self) -> str: ...

	@property
	@abstractmethod
	def _argsForStrArgs(self) -> OrderedDict[str, str]: ...


class _CacheBase(Generic[_TK, _TT]):
	def __init__(self, *, maxSize: int = 128, collectionNestingDepth: int = 0):
		super(_CacheBase, self).__init__()
		if maxSize == -1:
			maxSize = DEFAULT_MAX_SIZE
		self._maxSize: int = maxSize
		self._storage: OrderedDict[_TK, _TT] = OrderedDict()
		self._hits: int = 0
		self._misses: int = 0
		self._collectionNestingDepth: int = collectionNestingDepth

	@property
	def maxSize(self) -> int:
		return self._maxSize

	@maxSize.setter
	def maxSize(self, value: int) -> None:
		if value == -1:
			value = DEFAULT_MAX_SIZE
		self._maxSize = value

	@property
	def hits(self) -> int:
		return self._hits

	@property
	def misses(self) -> int:
		return self._misses

	@property
	def collectionNestingDepth(self) -> int:
		return self._collectionNestingDepth

	def clear(self) -> None:
		self._storage.clear()

	def reset(self) -> None:
		self.clear()
		self._hits = 0
		self._misses = 0

	def pop(self, key: _TK, sentinel: _TD = None) -> Union[_TT, _TD]:
		result = self._storage.pop(key, sentinel)
		return result

	def get(self, key: _TK, sentinel: _TD = None) -> Union[_TT, _TD]:
		result = self._storage.get(key, sentinel)
		if result is not sentinel:
			self._hits += 1
			self._storage.move_to_end(key)  # move entry to back
		else:
			self._misses += 1
			pass
		return result

	def getDeep(self, key: tuple[Any, ...], sentinel: _TD = None) -> Union[Any, _TD]:
		SENTINEL = object()
		result = self._storage.get(key[0], SENTINEL)
		if result is not SENTINEL:
			self._storage.move_to_end(key[0])  # move entry to back
			for k in key[1:]:
				result = result.get(k, SENTINEL)
				if result is SENTINEL:
					break
		if result is SENTINEL:
			self._misses += 1
			return sentinel
		else:
			self._hits += 1
			return result

	def getDeep2(self, key1: _TK, key2: Any, sentinel: _TD = None) -> Union[Any, _TD]:
		SENTINEL = object()
		result = self._storage.get(key1, SENTINEL)
		if result is not SENTINEL:
			self._storage.move_to_end(key1)  # move entry to back
			result = result.get(key2, SENTINEL)
		if result is SENTINEL:
			self._misses += 1
			return sentinel
		else:
			self._hits += 1
			return result

	def set(self, key: _TK, value: _TT) -> None:
		self._storage[key] = value
		if len(self._storage) > self._maxSize:
			self._storage.popitem(last=False)

	def __setitem__(self, key: _TK, value: _TT):
		self._storage[key] = value
		if len(self._storage) > self._maxSize:
			self._storage.popitem(last=False)

	def __copy__(self: _TS) -> _TS:
		return self.copy()

	def __len__(self) -> int:
		return len(self._storage)

	def __contains__(self, key: _TK) -> bool:
		return self._storage.__contains__(key)

	@property
	def _argsForStrArgs(self) -> OrderedDict[str, str]:
		args = OrderedDict()
		args['maxSize'] = f"{-1 if self.maxSize == DEFAULT_MAX_SIZE else self.maxSize:_}"
		args['pressure'] = f"{len(self) / self.maxSize: _.1%}"
		args['entries'] = f"{len(self):_}"
		hitsNMisses = self.hits + self.misses
		args['hitRate'] = f"{(self.hits / hitsNMisses) if hitsNMisses > 0 else 0: _.1%}"
		args['hits'] = f"{self.hits:_}"
		args['misses'] = f"{self.misses:_}"

		def summerPart(arg):  # λx: partial(summer, x)
			return lambda arg2: sum(map(arg, arg2))

		summer = len
		for _ in range(self.collectionNestingDepth):
			summer = summerPart(summer)

		sumLen = summer(self._storage.values())
		args['nestedEntries'] = f"{sumLen:_}"

		return args

	@property
	def _argsForStr2(self) -> str:
		args = self._argsForStrArgs
		return ', '.join(f'{name}= {value}' for name, value in args.items())

	@property
	def _argsForStr(self) -> str:
		args = self._argsForStrArgs
		return ', '.join(f'{name}= {value}' for name, value in args.items())

	@property
	def _clsNameForStr(self) -> str:
		cls = getattr(self, '__orig_class__', type(self))
		return typeRepr(cls)

	def __str__(self) -> str:
		clsName = self._clsNameForStr
		argsStr = self._argsForStr
		return f"{clsName}({argsStr})"


class Cache(_CacheBase[_TK, _TT], Generic[_TK, _TT]):
	# def __init__(self, *, maxSize: int = 128, collectionNestingDepth: int = 0):
	# 	super(Cache, self).__init__(maxSize=maxSize, collectionNestingDepth=collectionNestingDepth)

	def copy(self: _TS) -> _TS:
		other = type(self)(maxSize=self.maxSize, collectionNestingDepth=self.collectionNestingDepth)
		other._storage = self._storage.copy()
		return other


_globalCaches = WeakSet[PGlobalCache]()


def getAllGlobalCaches() -> AbstractSet[PGlobalCache]:
	return cast(AbstractSet, _globalCaches)


class GlobalCache(Cache[_TK, _TT], Generic[_TK, _TT]):
	def __init__(self, name: str, *, maxSize: int = 128, collectionNestingDepth: int = 0):
		assert name is not None
		super(GlobalCache, self).__init__(maxSize=maxSize, collectionNestingDepth=collectionNestingDepth)
		self._name: str = name
		_globalCaches.add(self)

	@property
	def name(self) -> str:
		return self._name

	def copy(self: _TS) -> _TS:
		raise NotImplementedError('a global cache cannot be copied')

	@override
	@property
	def _argsForStrArgs(self) -> OrderedDict[str, str]:
		args = super(GlobalCache, self)._argsForStrArgs
		args['name'] = f"{self.name!r}"
		args.move_to_end('name', False)
		return args


class GeneratingCache(Cache[_TK, _TT], Generic[_TK, _TT]):
	def __init__(self, generator: Callable[[_TK], _TT], *, maxSize: int = 128, collectionNestingDepth: int = 0):
		super(GeneratingCache, self).__init__(maxSize=maxSize, collectionNestingDepth=collectionNestingDepth)
		self._generator: Callable[[_TK], _TT] = generator

	def copy(self: _TS) -> _TS:
		other = super(GeneratingCache, self).copy()
		other._generator = self._generator
		return other

	def get(self, key: _TK, sentinel: _TD = None) -> _TT:
		return self.getOrGenerate(key)

	__sentinel = object()

	def getOrGenerate(self, key: _TK) -> _TT:
		sentinel = self.__sentinel
		result = Cache.get(self, key, sentinel)  # no super().get(...) for performance reasons.
		if result is sentinel:
			result = self._generator(key)
			self.set(key, result)
		return result


class GlobalGeneratingCache(GeneratingCache[_TK, _TT], GlobalCache[_TK, _TT], Generic[_TK, _TT]):
	def __init__(self, name: str, generator: Callable[[_TK], _TT], *, maxSize: int = 128, collectionNestingDepth: int = 0):
		assert name is not None
		super(GeneratingCache, self).__init__(name=name, maxSize=maxSize, collectionNestingDepth=collectionNestingDepth)
		self._generator = generator

	def copy(self: _TS) -> _TS:
		raise NotImplementedError('a global cache cannot be copied')


class CachedGenerator(Generic[_TT]):
	__sentinel = object()

	def __init__(self, generator: Callable[[], _TT]):
		self._generator: Callable[[], _TT] = generator
		self._storage: _TT = self.__sentinel

	def __call__(self) -> _TT:
		if self._storage == self.__sentinel:
			self._storage = self._generator()
		return self._storage

	def reset(self) -> None:
		self._storage = self.__sentinel

	def clear(self) -> None:
		self._storage = self.__sentinel


def formatCacheStats(caches: list[PGlobalCache]) -> str:
	allArgs = [c._argsForStrArgs for c in caches]
	order: list[str] = []
	lengths: dict[str, int] = defaultdict(int)
	for args in allArgs:
		i = len(order)
		for name, value in args.items():
			if name not in lengths:
				order.insert(i, name)
				lengths[name] = len(name)
			lengths[name] = max(lengths[name], len(value))
			i = order.index(name) + 1

	# build String:

	def cell(name: str, value: str):
		spacing = ' ' * max(0, lengths[name] - len(value))
		return f' {spacing}{value} |'

	def divider(name: str):
		spacing = '-' * lengths[name]
		return f'-{spacing}-+'

	return '\n'.join([
		# header:
		"".join(cell(name, name) for name in order),
		"".join(divider(name) for name in order),
		# contents:
		*("".join(cell(name, args.get(name, '')) for name in order) for args in allArgs),
		"".join(divider(name) for name in order)
	])


__all__ = [
	'Cache',
	'GlobalCache',
	'GeneratingCache',
	'GlobalGeneratingCache',
	'CachedGenerator',
	'formatCacheStats',
]
