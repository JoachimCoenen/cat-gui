from __future__ import annotations
import itertools as it
import os
import platform
import re
import subprocess
import sys
import weakref
from collections import defaultdict
from enum import Enum
from functools import wraps
from typing import Any, Callable, ContextManager, Generic, IO, Iterable, Iterator, Optional, overload, Tuple, Type, TYPE_CHECKING, TypeVar, Union
from warnings import warn

try:
	from PyQt5.QtCore import Qt, QTimer
	from PyQt5.QtWidgets import QApplication
except ImportError:
	HAS_QT = False
	Qt, QTimer = None, None
	QApplication = None
else:
	HAS_QT = True


_TCallable = TypeVar('_TCallable', bound=Callable)
_TT = TypeVar('_TT')
_TD = TypeVar('_TD')
_TR = TypeVar('_TR')


if True:  # Anything, Nothing, Everything
	def Anything():
		""" Denotes Anyhing (=^= not None, at least one)."""
		return Anything


	def Nothing():
		""" Denotes Nothing (non existent, not even None)."""
		return Nothing


	def Everything():
		""" Denotes All (not just Some)."""
		return Everything

SINGLETON_FIELD = '__singleton__'


class Singleton:
	"""
	adapted from the Python documentation at https://www.python.org/download/releases/2.2/descrintro/#__new__.
	"""
	__slots__ = ()

	def __new__(cls, *args, **kwds):
		instance = cls.__dict__.get(SINGLETON_FIELD)
		if instance is not None:
			return instance
		cls.__singleton__ = instance = super(Singleton, cls).__new__(cls)
		instance.init(*args, **kwds)
		return instance

	def init(self, *args, **kwds):
		pass


@property
def NotImplementedField(self) :
	"""Used to define a field, that a subclass has to implement.
	::
		class WrapperABC(ABC):
			value1 = NotImplementedField
			value2 = NotImplementedField
			value3 = NotImplementedField

		class myWrapper(WrapperABC):
			value1 = 42

			@property
			def vlaue2(self):
				return '42!'

			@Serialized()
			def vlaue3(self) -> float:
				return 41.99999999

	"""
	raise NotImplementedError


class DocEnum(Enum):
	"""
	An Enum whose members can be documented.
	e.g.:
	::
		class Color(DocEnum):
		'''Some colors '''
			RED   = 1, "The color red"
			GREEN = 2, "The color green"
			BLUE  = 3, "The color blue. These docstrings are more useful in the real example"

	shamefully copied word for word from here: https://stackoverflow.com/a/50473952/8091657
	(What would we do without stackoverflow?)
	"""
	def __new__(cls, value, doc=None):
		self = object.__new__(cls)  # calling super().__new__(value) here would fail
		self._value_ = value
		if doc is not None:
			self.__doc__ = doc
		return self


class IdentityCtxMgr(ContextManager[_TT], Generic[_TT]):
	def __init__(self, value: _TT):
		self._value: _TT = value

	def __enter__(self) -> _TT:
		return self._value

	def __exit__(self, exc_type, exc_val, exc_tb):
		return


# Decorators:
if True:
	_TDecoratable = TypeVar('_TDecoratable', bound=Union[Type, Callable])

	def Decorator(classOrFunc: _TDecoratable) -> _TDecoratable:
		"""
		This is a decorator, used to mark functions and classes as a decorator explicitly.
		"""
		return classOrFunc


	@Decorator
	class CachedProperty(Generic[_TT]):
		def __init__(self, func: Callable[[Any], _TT]):
			self._func: Callable[[Any], _TT] = func

		def __get__(self, instance, owner) -> _TT:
			if instance is None:
				return self
			value = self._func(instance)
			object.__setattr__(instance, self._func.__name__, value)
			return value


if QTimer is not None and Qt is not None:
	class _DeferredCall:
		def __init__(self, decorator: DeferredCallOnceMethod, instance):
			self._decorator: DeferredCallOnceMethod = decorator
			self._instance = instance

		if TYPE_CHECKING:
			# make PyCharms inspections happy:
			@property
			def _decorator(self) -> DeferredCallOnceMethod:
				return DeferredCallOnceMethod(lambda: None)

			# make PyCharms inspections happy:
			@_decorator.setter
			def _decorator(self, d: DeferredCallOnceMethod):
				pass

		def __call__(self, *args, **kwargs) -> None:
			self._decorator.call(self._instance, args, kwargs)

		def callNow(self, *args, **kwargs) -> None:
			self._decorator.callNow(self._instance, args, kwargs)

		def cancelPending(self) -> None:
			self._decorator.cancelPending(self._instance)

		@property
		def isPending(self) -> bool:
			return self._decorator.isPending(self._instance)


	@Decorator
	class DeferredCallOnceMethod:
		def __init__(self, *, delay: int = 333):
			self._delay: int = delay
			self._versionCounters: dict[int, int] = defaultdict(int)
			self._pending: set[int] = set()
			self._method: Optional[Callable] = None

		def __get__(self, instance, owner):  # -> _DeferredCall:
			if instance is None:
				return self

			deferredCall = _DeferredCall(self, instance)
			return wraps(self._method)(deferredCall)

		def __call__(self, func: Callable) -> DeferredCallOnceMethod:
			self._method: Callable = func
			return self

		def _asyncCall(self, forVersion: int, forInstance: weakref.ReferenceType, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
			instance = forInstance()
			if instance is None:
				return
			if self._versionCounters[id(instance)] > forVersion:
				return

			self.callNow(instance, args, kwargs)

		def call(self, instance, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
			self._versionCounters[id(instance)] += 1
			version = self._versionCounters[id(instance)]
			self._pending.add(id(instance))

			forInstance = weakref.ref(instance)
			QTimer.singleShot(
				self._delay,
				Qt.CoarseTimer,
				lambda: self._asyncCall(version, forInstance, args, kwargs)
			)
			return None

		def callNow(self, instance, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
			self.cancelPending(instance)
			self._method(instance, *args, **kwargs)
			return None

		def cancelPending(self, instance) -> None:
			if self.isPending(instance):
				self._versionCounters[id(instance)] += 1
				self._pending.discard(id(instance))

		def isPending(self, instance) -> bool:
			return id(instance) in self._pending


if QApplication is not None:
	@Decorator
	def BusyIndicator(func: _TCallable) -> _TCallable:
		@wraps(func)
		def wrappedFunc(*args, **kwargs):
			QApplication.setOverrideCursor(Qt.WaitCursor)
			try:
				return func(*args, **kwargs)
			finally:
				QApplication.restoreOverrideCursor()

		return wrappedFunc
else:
	@Decorator
	def BusyIndicator(func: _TCallable) -> _TCallable:
		return func


# @Deprecated(...)
if True:
	def _deprecate(func: Callable, *, doc: Optional[str], msg: Optional[str], typeForMsg: str, nameForMsg: str):
		deprecateMsg: str = f"{typeForMsg} {nameForMsg} is deprecated.{f' {msg}' if msg else ''}"

		@wraps(func)
		def deprecatedFunc(*args, _cat_deprecate_msg_cat_=deprecateMsg, **kwargs):
			warn(f"{_cat_deprecate_msg_cat_}", DeprecationWarning, 2)
			return func(*args, **kwargs)
		# handle type annotations:
		if not getattr(func, '__no_type_check__', None):
			annotations = getattr(func, '__annotations__', None)
			if annotations is not None:
				setattr(deprecatedFunc, '__annotations__', annotations)

		doc = doc or func.__doc__ or ""
		deprecatedFunc.__doc__ = '*WARNING*: ' + deprecateMsg + ('\n\n' + doc if doc else '')
		return deprecatedFunc

	def _deprecateClass(cls: Type, *, doc: Optional[str], msg: Optional[str]):
		initFunc = getattr(cls, '__init__', None)
		if initFunc is None:
			def initFunc(self, *args, **kwargs):
				return super(cls, self).__init__(*args, **kwargs)
			initFunc.__name__ = '__init__'
			initFunc.__qualname__ = f'{cls.__qualname__}.{initFunc.__name__}'
			initFunc.__module__ = cls.__module__

		setattr(cls, '__init__', _deprecate(initFunc, doc=doc, msg=msg, typeForMsg=cls.__qualname__, nameForMsg=cls.__qualname__))
		return cls

	def _deprecateFunction(func: Callable, *, doc: Optional[str], msg: Optional[str]):
		return _deprecate(func, doc=doc, msg=msg, typeForMsg='Function', nameForMsg=func.__qualname__)

	def _makeDeprecated(funcMethodOrClass: Union[Callable, Type], *, doc: Optional[str], msg: Optional[str]):
		if isinstance(funcMethodOrClass, type):
			return _deprecateClass(funcMethodOrClass, doc=doc, msg=msg)
		else:
			return _deprecateFunction(funcMethodOrClass, doc=doc, msg=msg)


	@Decorator
	@overload
	def Deprecated(funcMethodOrClass: _TCallable, doc: Optional[str] = None, *, msg: Optional[str] = None) -> _TCallable:
		# just an overlaod
		pass


	@Decorator
	@overload
	def Deprecated(*, msg: Optional[str] = None) -> Callable[[_TCallable], _TCallable]:
		# just an overlaod
		pass


	@Decorator
	def Deprecated(*args, msg: Optional[str] = None):
		if args:
			funcMethodOrClass = args[0]
			if len(args) >= 2:
				doc = args[1]
			else:
				doc = None
			return _makeDeprecated(funcMethodOrClass, doc=doc, msg=msg)
		else:
			return lambda funcMethodOrClass, doc=None, msg=msg: _makeDeprecated(funcMethodOrClass, doc=doc, msg=msg)


# Files and Directories, os specific, ...:
if True:
	PLATFORM_IS_WINDOWS = platform.system() == 'Windows'
	PLATFORM_IS_DARWIN = platform.system() == 'Darwin'
	PLATFORM_IS_MAC_OS = PLATFORM_IS_DARWIN
	PLATFORM_IS_LINUX = platform.system() == 'Linux'
	if not any((PLATFORM_IS_WINDOWS, PLATFORM_IS_DARWIN, PLATFORM_IS_MAC_OS, PLATFORM_IS_LINUX)):
		raise RuntimeError(f"invalid platform: {platform.system()}!")

	if PLATFORM_IS_WINDOWS:
		FILE_BROWSER_COMMAND: str = os.path.join(os.getenv('WINDIR'), 'explorer.exe')
		FILE_BROWSER_DISPLAY_NAME: str = 'Explorer'
	elif PLATFORM_IS_DARWIN:  # macOS
		FILE_BROWSER_COMMAND: str = 'open'
		FILE_BROWSER_DISPLAY_NAME: str = 'Finder'
	elif PLATFORM_IS_LINUX:
		FILE_BROWSER_COMMAND: str = 'xdg-open'
		FILE_BROWSER_DISPLAY_NAME: str = 'Nautilus'
	else:
		FILE_BROWSER_COMMAND: str = ''
		FILE_BROWSER_DISPLAY_NAME: str = 'NO FILE BROWSER FOUND'

	class _ENCODINGS:
		@property
		def UTF_8(self) -> str:
			return 'utf-8'

		@property
		def LATIN_1(self) -> str:
			return 'latin_1'


	ENCODINGS = _ENCODINGS()

	def openOrCreate(
			file: Union[str, bytes, int, os.PathLike],
			mode: str = 'r',
			buffering: int = -1,
			encoding: Optional[str] = None,
			errors: Optional[str] = None,
			newline: Optional[str] = None,
			closefd: bool = True,
			opener: Optional[Callable[[str, int], int]] = None
	) -> IO[Any]:
		"""
		Open file and return a stream.  Raise OSError upon failure.
		see: open
		requires a writing mode ( w, x, a or + ) to be set (e.g. mode='wb').
		"""
		assert any(c in mode for c in 'wxa+')

		os.makedirs(os.path.dirname(file), exist_ok=True)
		return open(
			file=file,
			mode=mode,
			buffering=buffering,
			encoding=encoding,
			errors=errors,
			newline=newline,
			closefd=closefd,
			opener=opener
		)


	def safeOpen(
			file: Union[str, bytes, int, os.PathLike],
			mode: str = 'r',
			buffering: int = -1,
			encoding: Optional[str] = None,
			errors: Optional[str] = None,
			newline: Optional[str] = None,
			closefd: bool = True,
			opener: Optional[Callable[[str, int], int]] = None,
			*,
			onError: Callable[[OSError], None],
	) -> Maybe[IO[Any]]:
		"""
		Open file and return a stream.  Raise OSError upon failure.
		see: open
		requires a writing mode ( w, x, a or + ) to be set (e.g. mode='wb').
		"""
		try:
			opened = open(
				file=file,
				mode=mode,
				buffering=buffering,
				encoding=encoding,
				errors=errors,
				newline=newline,
				closefd=closefd,
				opener=opener
			)
		except OSError as e:
			onError(e)
			return EMPTY_MAYBE
		return Maybe[IO[Any]](opened)


	def getExePath() -> str:
		if getattr(sys, 'frozen', False):
			application_path = sys.executable
		else:
			import __main__
			application_path = os.path.abspath(__main__.__file__)
		return application_path


	def showInFileSystem(path: str):
		path = os.path.normpath(path)
		if PLATFORM_IS_WINDOWS:
			if os.path.isdir(path):
				subprocess.run([FILE_BROWSER_COMMAND, path])
			elif os.path.isfile(path):
				subprocess.run([FILE_BROWSER_COMMAND, '/select,', path])
		elif PLATFORM_IS_DARWIN:  # macOS
			subprocess.call([FILE_BROWSER_COMMAND, '-R', path])
		elif PLATFORM_IS_LINUX:
			subprocess.Popen([FILE_BROWSER_COMMAND, path])
		else:
			raise RuntimeError(f"invalid platform: {platform.system()}!")


	INVALID_PATH_CHARS = r'\/:*?"<>|'
	_INVALID_PATH_CHARS_ESCAPED = INVALID_PATH_CHARS\
			.replace('\\', '\\\\')\
			.replace(']', '\\]')
	INVALID_PATH_CHARS_PATTERN = re.compile(
		rf'[{_INVALID_PATH_CHARS_ESCAPED}]'
	)
	VALID_FILE_NAME_PATTERN = re.compile(
		rf'[^{_INVALID_PATH_CHARS_ESCAPED}]+'
	)


	def sanitizeFileName(name: str, sub: str = '-') -> str:
		return INVALID_PATH_CHARS_PATTERN.sub(sub, name)


class Maybe(Generic[_TT]):
	""" a Maybe monad """

	def __init__(self, aValue: Optional[_TT]):
		self._value: Optional[_TT] = aValue

	def get(self) -> Optional[_TT]:
		return self._value

	def orElse(self, default: _TD) -> Union[_TT, _TD]:
		return self._value if self._value is not None else default

	_EMPTY_DICT = {}

	def call(self, func: str, *args, kwargs: dict[str, Any] = _EMPTY_DICT, returns: Type[_TR] = Any) -> Maybe[_TR]:
		if self._value is None:
			return EMPTY_MAYBE
		else:
			return Maybe(getattr(self._value, func)(*args, **kwargs))

	def getattr(self, attr: str, returns: Type[_TR] = Any) -> Maybe[_TR]:
		if self._value is None:
			return EMPTY_MAYBE
		else:
			return Maybe(getattr(self._value, attr))

	@overload
	def map(self, func: Callable[[_TT, ...], Optional[_TR]], *args, **kwargs) -> Maybe[_TR]: ...
	@overload
	def map(self, func: Callable[[_TT, ...], _TR], *args, **kwargs) -> Maybe[_TR]: ...

	def map(self, func: Callable[[_TT, ...], Optional[_TR]], *args, **kwargs) -> Maybe[_TR]:
		"""
		same as Maybe.apply(...)
		:param func:
		:param args:
		:param kwargs:
		:return:
		"""
		if self._value is None:
			return EMPTY_MAYBE
		else:
			return Maybe(func(self._value, *args, **kwargs))

	apply = map

	def flatmap(self, func: Callable[[_TT, ...], Maybe[_TR]], *args, **kwargs) -> Maybe[_TR]:
		if self._value is None:
			return EMPTY_MAYBE
		else:
			return func(self._value, *args, **kwargs)

	def recursive(self, func: Callable[[_TT, ...], Optional[_TT]], *args, **kwargs) -> Maybe[_TT]:
		if self._value is None:
			return EMPTY_MAYBE
		else:
			last: _TT = self._value
			while True:
				new = func(last, *args, **kwargs)
				if new is None:
					return Maybe(last)
				last = new

	def __bool__(self) -> bool:
		return self._value is not None

	def __enter__(self) -> Maybe[_TT]:
		if self._value is not None:
			return Maybe(self.get().__enter__())
		else:
			return EMPTY_MAYBE
		#return  self..call('__enter__')

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self._value is not None:
			return self._value.__exit__(exc_type, exc_val, exc_tb)


EMPTY_MAYBE: Maybe = Maybe(None)

# findall(...), flatmap(...), outerZip(...), mix(...), ...:
if True:
	TT1 = TypeVar('TT1'); TF1 = TypeVar('TF1')
	TT2 = TypeVar('TT2'); TF2 = TypeVar('TF2')
	TT3 = TypeVar('TT3'); TF3 = TypeVar('TF3')
	TT4 = TypeVar('TT4'); TF4 = TypeVar('TF4')
	TT5 = TypeVar('TT5'); TF5 = TypeVar('TF5')
	TT6 = TypeVar('TT6'); TF6 = TypeVar('TF6')

	def findall(p: str, s: str):
		'''Yields all the positions of the pattern p in the string s.'''
		i = s.find(p)
		while i != -1:
			yield i
			i = s.find(p, i+1)


	def flatmap(func, *iterable):
		return it.chain.from_iterable(map(func, *iterable))


	class OuterZipStopIteration(Exception):
		pass

	@overload
	def outerZip(iterable1: Iterable[TT1], iterable2: Iterable[TT2], *, fillValues: Tuple[TF1, TF2]) -> Iterator[Tuple[Union[TT1, TF1], Union[TT2, TF2]]]:
		pass

	@overload
	def outerZip(iterable1: Iterable[TT1], iterable2: Iterable[TT2], iterable3: Iterable[TT3], *, fillValues: Tuple[TF1, TF2, TF3]) -> Iterator[Tuple[Union[TT1, TF1], Union[TT2, TF2], Union[TT3, TF3]]]:
		pass

	@overload
	def outerZip(iterable1: Iterable[TT1], iterable2: Iterable[TT2], iterable3: Iterable[TT3], iterable4: Iterable[TT4], *, fillValues: Tuple[TF1, TF2, TF3, TF4]) -> Iterator[Tuple[Union[TT1, TF1], Union[TT2, TF2], Union[TT3, TF3], Union[TT4, TF4]]]:
		pass

	@overload
	def outerZip(iterable1: Iterable[TT1], iterable2: Iterable[TT2], iterable3: Iterable[TT3], iterable4: Iterable[TT4], iterable5: Iterable[TT5], *, fillValues: Tuple[TF1, TF2, TF3, TF4, TF5]) -> Iterator[Tuple[Union[TT1, TF1], Union[TT2, TF2], Union[TT3, TF3], Union[TT4, TF4], Union[TT5, TF5]]]:
		pass

	@overload
	def outerZip(iterable1: Iterable[TT1], iterable2: Iterable[TT2], iterable3: Iterable[TT3], iterable4: Iterable[TT4], iterable5: Iterable[TT5], iterable6: Iterable[TT6], *, fillValues: Tuple[TF1, TF2, TF3, TF4, TF5, TF6]) -> Iterator[Tuple[Union[TT1, TF1], Union[TT2, TF2], Union[TT3, TF3], Union[TT4, TF4], Union[TT5, TF5], Union[TT6, TF6]]]:
		pass

	def outerZip(*args: Tuple[Iterable[_TT], ...], fillValues: Tuple[_TT, ...]) -> Iterator[Tuple[_TT, ...]]:
		argsLen = len(args)
		fillValuesLen = len(fillValues)
		if argsLen != fillValuesLen:
			if fillValuesLen < argsLen and fillValues[-1] is Ellipsis and fillValuesLen >= 2:
				fillValues = it.chain(fillValues[:-1], fillValues[:-2])
			else:
				raise ValueError(f"Length of fillvalues ({fillValuesLen}) is not equal to number of iterables ({argsLen}).")
		count = argsLen - 1

		def sentinel(default):
			nonlocal count
			if not count:
				raise OuterZipStopIteration
			count -= 1
			yield default

		iters = [it.chain(iterable, sentinel(fillvalue), it.repeat(fillvalue)) for iterable, fillvalue in zip(args, fillValues)]
		try:
			while iters:
				yield tuple(map(next, iters))
		except OuterZipStopIteration:
			pass

	# mix(...):
	@overload
	def mix(a: int, b: int, x: float) -> float: ...

	@overload
	def mix(a: float, b: float, x: float) -> float: ...

	@overload
	def mix(a: _TT, b: _TT, x: float) -> _TT: ...

	def mix(a: Any, b: Any, x: float) -> Any:
		return a + (b - a) * x

	# stable float summation:
	def kleinSum( floats: Iterable[float]) -> float:
		total: float = 0.0
		cs: float = 0.0
		ccs: float = 0.0

		for f in floats:
			t: float = total + f
			if abs(total) >= abs(f):
				c = (total - t) + f
			else:
				c = (f - t) + total
			total = t
			t = cs + c
			if abs(cs) >= abs(c):
				cc = (cs - t) + c
			else:
				cc = (c - t) + cs
			cs = t
			ccs += cc

		return total + cs + ccs


# format_full_exc()
if True:
	# full_exc_info() for printing a full traceback:
	# COPIED from https://stackoverflow.com/a/13210518/8091657
	# and added some type annotations:

	class FauxTb(object):
		def __init__(self, tb_frame, tb_lineno, tb_next, tb_lasti):
			self.tb_frame = tb_frame
			self.tb_lineno = tb_lineno
			self.tb_next = tb_next
			self.tb_lasti = tb_lasti


	def current_stack(skip=0):
		f = None  # just to make the type checker happy
		try:
			1/0
		except ZeroDivisionError:
			f = sys.exc_info()[2].tb_frame
		for i in range(skip + 2):
			f = f.f_back
		lst = []
		while f is not None:
			lst.append((f, f.f_lineno))
			f = f.f_back
		return lst


	def extend_traceback(tb, stack):
		"""Extend traceback with stack info."""
		head = tb
		for tb_frame, tb_lineno in stack:
			head = FauxTb(tb_frame, tb_lineno, head, -1)
		return head


	TBaseException = TypeVar('TBaseException', bound=BaseException)


	def full_exc_info(e: Optional[TBaseException] = None) -> Tuple[Type[TBaseException], TBaseException, FauxTb]:
		"""Like sys.exc_info, but includes the full traceback."""
		if e is not None:
			t, v, tb = type(e), e, e.__traceback__
		else:
			t, v, tb = sys.exc_info()
		full_tb = extend_traceback(tb, current_stack(1))
		return t, v, full_tb
	# END COPIED from


	def format_full_exc(e: Optional[TBaseException] = None, *, indentLvl: int = 0) -> str:
		from traceback import format_exception
		from ..utils.formatters import indentMultilineStr
		exc, value, tb = full_exc_info(e)
		text = ''.join(format_exception(exc, value, tb))
		return indentMultilineStr(text, indent=indentLvl).s

__all__ = [
	'Anything',
	'Nothing',
	'Everything',

	'NotImplementedField',
	'SINGLETON_FIELD',
	'Singleton',
	'DocEnum',
	'IdentityCtxMgr',

	'Decorator',
	'CachedProperty',

	'DeferredCallOnceMethod',
	'BusyIndicator',

	'Deprecated',

	'PLATFORM_IS_WINDOWS',
	'PLATFORM_IS_DARWIN',
	'PLATFORM_IS_MAC_OS',
	'PLATFORM_IS_LINUX',

	'FILE_BROWSER_COMMAND',
	'FILE_BROWSER_DISPLAY_NAME',

	'ENCODINGS',

	'openOrCreate',
	'safeOpen',
	'getExePath',
	'showInFileSystem',

	'INVALID_PATH_CHARS',
	'sanitizeFileName',

	'Maybe',

	'findall',
	'flatmap',
	'outerZip',
	'mix',
	'kleinSum',

	'full_exc_info',
	'format_full_exc',
]
