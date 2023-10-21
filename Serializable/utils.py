from __future__ import annotations

import enum
import sys
from typing import _eval_type, _GenericAlias, Any, Generic, MutableMapping, Tuple, Type, TypeVar, Union, Optional, Protocol
from ..utils import NoneType

try:
	from typing import get_args, get_origin
except ImportError:
	import collections.abc

	def get_origin(tp):
		# directly from Python 3.8 typing module
		"""Get the unsubscripted version of a type.

		This supports generic types, Callable, Tuple, Union, Literal, Final and ClassVar.
		Return None for unsupported types. Examples::

			get_origin(Literal[42]) is Literal
			get_origin(int) is None
			get_origin(ClassVar[int]) is ClassVar
			get_origin(Generic) is Generic
			get_origin(Generic[T]) is Generic
			get_origin(Union[T, int]) is Union
			get_origin(List[Tuple[T, T]][int]) == list
		"""
		if isinstance(tp, _GenericAlias):
			return tp.__origin__
		if tp is Generic:
			return Generic
		return None


	def get_args(tp) -> Tuple[Any, ...]:
		# directly from Python 3.8 typing module
		"""Get type arguments with all substitutions performed.

		For unions, basic simplifications used by Union constructor are performed.
		Examples::
			get_args(Dict[str, int]) == (str, int)
			get_args(int) == ()
			get_args(Union[int, Union[T, int], str][int]) == (int, str)
			get_args(Union[int, Tuple[T, int]][str]) == (int, Tuple[str, int])
			get_args(Callable[[], T][int]) == ([], int)
		"""
		if isinstance(tp, _GenericAlias):
			res = tp.__args__
			if get_origin(tp) is collections.abc.Callable and res[0] is not Ellipsis:
				res = (list(res[:-1]), res[-1])
			return res
		return ()
else:
	get_origin = get_origin
	get_args = get_args


def set_args(tp: _GenericAlias, args: Tuple[Any, ...]):
	# directly from Python 3.8 typing module
	"""Set type arguments with all substitutions performed.

	For unions, basic simplifications used by Union constructor are performed.
	Examples::
		get_args(Dict[str, int]) == (str, int)
		get_args(int) == ()
		get_args(Union[int, Union[T, int], str][int]) == (int, str)
		get_args(Union[int, Tuple[T, int]][str]) == (int, Tuple[str, int])
		get_args(Callable[[], T][int]) == ([], int)
	"""
	if not isinstance(tp, _GenericAlias):
		raise ValueError("tp must be a _GenericAlias.")

	if get_origin(tp) is collections.abc.Callable and args[0] is not Ellipsis:
		args = (*args[0], args[1])

	tp.__args__ = args


class _EvalTypeProtocol(Protocol):
	def __call__(self, t, globalns: dict[str, Any], localns: Optional[dict[str, Any]], recursive_guard=frozenset()):
		...


_eval_type: _EvalTypeProtocol = _eval_type


def typeHintMatchesType(typeHint: Any, type_: Type) -> bool:
	try:
		if typeHint.__origin__._name == 'Union':
			for arg in get_args(typeHint):
				if typeHintMatchesType(arg, type_):
					return True
			return False
		elif typeHint.__origin__._name == 'Optional':
			return type_ is NoneType or typeHintMatchesType(get_args(typeHint)[0], type_)
		# elif typeHint.__origin__._name == 'List':
		# 	return issubclass(List, type_)
		# elif typeHint.__origin__._name == 'Dict':
		# 	return issubclass(Dict, type_)
		# elif typeHint.__origin__._name == 'DefaultDict':
		# 	return issubclass(DefaultDict, type_)
		# elif typeHint.__origin__._name == 'Set':
		# 	return issubclass(Set, type_)
		# elif typeHint.__origin__._name == 'FrozenSet':
		# 	return issubclass(FrozenSet, type_)
		# elif typeHint.__origin__._name == 'Counter':
		# 	return issubclass(Counter, type_)
		# elif typeHint.__origin__._name == 'Deque':
		# 	return issubclass(Deque, type_)
		# elif typeHint.__origin__._name == 'ChainMap':
		# 	return issubclass(ChainMap, type_)
		# -Union = TypeAlias(object)
		# -Optional = TypeAlias(object)
		# List = TypeAlias(object)
		# Dict = TypeAlias(object)
		# DefaultDict = TypeAlias(object)
		# Set = TypeAlias(object)
		# FrozenSet = TypeAlias(object)
		# Counter = TypeAlias(object)
		# Deque = TypeAlias(object)
		# ChainMap = TypeAlias(object)
	except AttributeError:
		pass
	try:
		# todo investigate ??!
		return issubclass(typeHint.__origin__, type_)
	except AttributeError:
		pass

	if isinstance(typeHint, TypeVar):
		# TODO: handle co- & contra-variance
		if typeHint.__bound__ is not None:
			bound = typeHint.__bound__
			globals_ = sys.modules[typeHint.__module__].__dict__
			bound = _eval_type(bound, globals_, globals_)
			return typeMatchesTypeHint(type_, bound)
		if typeHint.__constraints__:
			globals_ = sys.modules[typeHint.__module__].__dict__
			for arg in get_args(typeHint):
				arg2 = _eval_type(arg, globals_, globals_)
				if typeMatchesTypeHint(type_, arg2):
					return True
			return False
		return True

	if typeHint is Any:  # TODO: INVESTIGATE, maybe if type_ is Any ??
		return True

	if typeHint is None:
		return type_ is None or type_ is NoneType

	try:
		if issubclass(typeHint, type_):
			return True
	except TypeError as e:
		typeHint = getattr(typeHint, '__supertype__', typeHint)
		type_ = getattr(type_, '__supertype__', type_)
		try:
			if issubclass(typeHint, type_):
				return True
		except Exception as e:
			e.args = (*e.args, f'issubclass(typeHint={typeHint!r}, type_={type_!r})')
			raise
	except Exception as e:
		e.args = (*e.args, f'issubclass(typeHint={typeHint!r}, type_={type_!r})')
		raise

	if typeHint is float and type_ is complex:
		return True

	if typeHint is int and (type_ is float or type_ is complex):
		return True
	return False


def typeMatchesTypeHint(type_: Type, typeHint: Any) -> bool:
	try:
		if typeHint.__origin__._name == 'Union':
			for arg in get_args(typeHint):
				if typeMatchesTypeHint(type_, arg):
					return True
			return False
		elif typeHint.__origin__._name == 'Optional':
			return type_ is NoneType or typeMatchesTypeHint(type_, get_args(typeHint)[0])
		# elif typeHint.__origin__._name == 'List':
		# 	return issubclass(type_, List)
		# elif typeHint.__origin__._name == 'Dict':
		# 	return issubclass(type_, Dict)
		# elif typeHint.__origin__._name == 'DefaultDict':
		# 	return issubclass(type_, DefaultDict)
		# elif typeHint.__origin__._name == 'Set':
		# 	return issubclass(type_, Set)
		# elif typeHint.__origin__._name == 'FrozenSet':
		# 	return issubclass(type_, FrozenSet)
		# elif typeHint.__origin__._name == 'Counter':
		# 	return issubclass(type_, Counter)
		# elif typeHint.__origin__._name == 'Deque':
		# 	return issubclass(type_, Deque)
		# elif typeHint.__origin__._name == 'ChainMap':
		# 	return issubclass(type_, ChainMap)
	# -Union = TypeAlias(object)
	# -Optional = TypeAlias(object)
	# List = TypeAlias(object)
	# Dict = TypeAlias(object)
	# DefaultDict = TypeAlias(object)
	# Set = TypeAlias(object)
	# FrozenSet = TypeAlias(object)
	# Counter = TypeAlias(object)
	# Deque = TypeAlias(object)
	# ChainMap = TypeAlias(object)
	except AttributeError:
		pass
	try:
		# todo investigate ??!
		return issubclass(type_, typeHint.__origin__)
	except AttributeError:
		pass

	if isinstance(typeHint, TypeVar):
		# TODO: handle co- & contra-variance
		if typeHint.__bound__ is not None:
			bound = typeHint.__bound__
			globals_ = sys.modules[typeHint.__module__].__dict__
			bound = _eval_type(bound, globals_, globals_)
			return typeMatchesTypeHint(type_, bound)
		if typeHint.__constraints__:
			globals_ = sys.modules[typeHint.__module__].__dict__
			for arg in get_args(typeHint):
				arg2 = _eval_type(arg, globals_, globals_)
				if typeMatchesTypeHint(type_, arg2):
					return True
			return False
		return True

	if typeHint is Any:
		return True

	if typeHint is None:
		return type_ is None or type_ is NoneType

	try:
		if issubclass(type_, typeHint):
			return True
	except TypeError as e:
		typeHint = getattr(typeHint, '__supertype__', typeHint)
		type_ = getattr(type_, '__supertype__', type_)
		try:
			if issubclass(type_, typeHint):
				return True
		except Exception as e:
			e.args = (*e.args, f'issubclass(type_={type_!r}, typeHint={typeHint!r})')
			raise
	except Exception as e:
		e.args = (*e.args, f'issubclass(type_={type_!r}, typeHint={typeHint!r})')
		raise

	if type_ is float and typeHint is complex:
		return True

	if type_ is int and (typeHint is float or typeHint is complex):
		return True

	return False


def valueMatchesType(value: Any, typeHint: Any) -> bool:
	return typeMatchesTypeHint(type(value), typeHint)


_TT = TypeVar('_TT')


def getValueOrValueOfProp(owner, value: _TT | property) -> _TT:
	return value.__get__(owner) if isinstance(value, property) else value


MemoType = MutableMapping[str, Any]
SerializationPath = Tuple[Union[str, int], ...]
MemoForSerialization = MutableMapping[int, SerializationPath]
MemoForDeserialization = MutableMapping[SerializationPath, Any]


class SerializationError(RuntimeError):  # TODO: find better baseClass for SerializationError(RuntimeError)
	def __init__(self, *args, path: SerializationPath, **contextValues):
		super(SerializationError, self).__init__(*args)
		self._path: SerializationPath = path
		self._contextValues: dict[str, Any] = contextValues

	def __str__(self):
		msg = super(SerializationError, self).__str__()
		msg += f' | at path = {self._path}'
		for name, value in self._contextValues.items():
			msg += f' | {name} = {value}'

		return msg


def getRef(reference: list[Union[str, int]], memo: MemoForDeserialization) -> Any:
	referenceY = tuple(reference)
	return memo[referenceY]


BASIC_TYPES = (int, float, complex, str, bytes, NoneType)
BASIC_TYPES_ENUM = (int, float, complex, str, bytes, NoneType, enum.Enum)


class PropertyDecorator:
	"""base class for all PropertyDecorator"""

	def __init__(self):
		self.innerDecorator: Optional[PropertyDecorator] = None


__all__ = [
	'get_origin',
	'get_args',
	'set_args',
	'_eval_type',

	'typeHintMatchesType',
	'typeMatchesTypeHint',
	'valueMatchesType',

	'getValueOrValueOfProp',

	'MemoType',
	'SerializationPath',
	'MemoForSerialization',
	'MemoForDeserialization',
	'SerializationError',
	'getRef',

	'BASIC_TYPES',
	'BASIC_TYPES_ENUM',
	'PropertyDecorator',
]