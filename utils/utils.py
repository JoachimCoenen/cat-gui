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
from types import TracebackType, FrameType
from typing import Any, Callable, ContextManager, IO, Iterable, Iterator, Type, overload, cast, Self, AnyStr
from warnings import warn

from cat.utils.typing_ import BoundMethod

try:
	from PyQt5.QtCore import Qt, QTimer, pyqtBoundSignal
	from PyQt5.QtWidgets import QApplication
except ImportError:
	HAS_QT = False
	Qt = QTimer = QApplication = pyqtBoundSignal = None  # type: ignore 
else:
	HAS_QT = True


def __onCrash__(exception: Exception) -> None:
	pass


onCrash = __onCrash__


if True:  # Anything, Nothing, Everything
	class _SingletonTypeMetaclass(type):
		def __instancecheck__(self, instance) -> bool:
			return instance is self

	class Anything(metaclass=_SingletonTypeMetaclass):
		""" Denotes Anything (=^= not None, at least one)."""
		def __new__(cls, *args, **kwargs) -> Type[Anything] | Anything:  # type: ignore
			return Anything


	class Nothing(metaclass=_SingletonTypeMetaclass):
		""" Denotes Nothing (non existent, not even None)."""
		def __new__(cls, *args, **kwargs) -> Type[Nothing] | Nothing:  # type: ignore
			return Nothing


	class Everything(metaclass=_SingletonTypeMetaclass):
		""" Denotes All (not just Some)."""
		def __new__(cls, *args, **kwargs) -> Type[Everything] | Everything:  # type: ignore
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

	def init(self, *args, **kwds) -> None:
		pass


@property
def NotImplementedField(self):
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


class IdentityCtxMgr[TT](ContextManager[TT]):
	def __init__(self, value: TT):
		self._value: TT = value

	def __enter__(self) -> TT:
		return self._value

	def __exit__(self, exc_type, exc_val, exc_tb):
		return


# Decorators:
if True:
	def Decorator[T: Type | Callable](classOrFunc: T) -> T:
		"""
		This is a decorator, used to mark functions and classes as a decorator explicitly.
		"""
		return classOrFunc


	@Decorator
	class CachedProperty[TT]:
		def __init__(self, func: Callable[[Any], TT]):
			self._func: Callable[[Any], TT] = func

		@overload
		def __get__(self, instance: None, owner: type | None = None) -> Self: ...
		@overload
		def __get__(self, instance: Any, owner: type | None = None) -> TT:  ...

		def __get__(self, instance: Any | None, owner: type | None = None) -> TT | Self:
			if instance is None:
				return self
			value = self._func(instance)
			object.__setattr__(instance, self._func.__name__, value)
			return value


	@overload
	def CrashReportWrapped[**Args, R](func: None = None) -> Callable[[Callable[Args, R]], Callable[Args, R]]: ...
	@overload
	def CrashReportWrapped[**Args, R](func: Callable[Args, R]) -> Callable[Args, R]:  ...

	@Decorator
	def CrashReportWrapped[**Args, R](func: Callable[Args, R] | None = None):
		"""
		:param func: func must NOT be a BoundMethod.
		"""
		if func is None:
			return lambda f: CrashReportWrapped(f)

		if isCrashReportWrapped(func):
			return func  # no need to wrap twice

		if isinstance(func, BoundMethod):
			raise TypeError("cannot wrap a BoundMethod")

		@wraps(func)
		def call(*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except Exception as e:
				print(format_full_exc())
				from cat.utils.logging_ import logError
				logError(format_full_exc())
				onCrash(e)
				raise
		call.__CrashReportWrapped__ = True  # type: ignore 
		return call


	def isCrashReportWrapped(slot: Callable) -> bool:
		return getattr(slot, '__CrashReportWrapped__', False) is True


if QTimer is not None and Qt is not None:

	__sentinel = object()

	@overload
	def runLaterSafe(msec: int, func: Callable[[], None] | pyqtBoundSignal, /) -> None:
		"""
		Schedule func() to be run in about msec milliseconds. Requires a running Qt event loop.
		:param msec:
		:param func:
		:return:
		"""
		...

	@overload
	def runLaterSafe(msec: int, timerType: Qt.TimerType, func: Callable[[], None] | pyqtBoundSignal, /) -> None:
		...

	def runLaterSafe(arg1, arg2, arg3=__sentinel) -> None:
		"""
		:param arg1: `msec: int` milliseconds.
		:param arg2: either `func: Callable[[], None] | pyqtBoundSignal` or `timerType: Qt.TimerType`.
		:param arg3: `func: Callable[[], None] | pyqtBoundSignal` if arg2 is timerType else NOT SET.
		:return:
		"""
		if arg3 is __sentinel:
			QTimer.singleShot(arg1, CrashReportWrapped(arg2))
		else:
			QTimer.singleShot(arg1, arg2, CrashReportWrapped(arg3))


	class _DeferredCall:
		def __init__(self, decorator: _DeferredCallOnceMethod, instance):
			self._decorator: _DeferredCallOnceMethod = decorator
			self._instance = instance

		def __call__(self, *args, **kwargs) -> None:
			self._decorator.call(self._instance, args, kwargs)

		def callNow(self, *args, **kwargs) -> None:
			self._decorator.callNow(self._instance, args, kwargs)

		def cancelPending(self) -> None:
			self._decorator.cancelPending(self._instance)

		@property
		def isPending(self) -> bool:
			return self._decorator.isPending(self._instance)


	class _DeferredCallOnceMethod:
		def __init__(self, delay: int, method: Callable):
			self._delay: int = delay
			self._versionCounters: dict[int, int] = defaultdict(int)
			self._pending: set[int] = set()
			self._method: Callable = method

		@overload
		def __get__(self, instance: None, owner: type | None = None) -> Self: ...
		@overload
		def __get__(self, instance: Any, owner: type | None = None) -> _DeferredCall:  ...

		def __get__(self, instance, owner=None):  # -> _DeferredCall:
			if instance is None:
				return self

			deferredCall = _DeferredCall(self, instance)
			return wraps(self._method)(deferredCall)

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
			runLaterSafe(
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


	@Decorator
	def DeferredCallOnceMethod(*, delay: int = 333) -> Callable[[Callable], _DeferredCallOnceMethod]:
		def decorator(method: Callable) -> _DeferredCallOnceMethod:
			return _DeferredCallOnceMethod(delay, method)

		return decorator


if QApplication is not None:
	@Decorator
	def BusyIndicator[**Args, R](func: Callable[Args, R]) -> Callable[Args, R]:
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
	def BusyIndicator[TCallable](func: TCallable) -> TCallable:
		return func


# @Deprecated(...)
if True:
	def _deprecate(func: Callable, *, doc: str | None, msg: str | None, typeForMsg: str, nameForMsg: str):
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

	def _deprecateClass(cls: Type, *, doc: str | None, msg: str | None):
		initFunc = getattr(cls, '__init__', None)
		if initFunc is None:
			def initFunc(self, *args, **kwargs):
				return super(cls, self).__init__(*args, **kwargs)
			initFunc.__name__ = '__init__'
			initFunc.__qualname__ = f'{cls.__qualname__}.{initFunc.__name__}'
			initFunc.__module__ = cls.__module__

		setattr(cls, '__init__', _deprecate(initFunc, doc=doc, msg=msg, typeForMsg=cls.__qualname__, nameForMsg=cls.__qualname__))
		return cls

	def _deprecateFunction(func: Callable, *, doc: str | None, msg: str | None):
		return _deprecate(func, doc=doc, msg=msg, typeForMsg='Function', nameForMsg=func.__qualname__)

	def _makeDeprecated(funcMethodOrClass: Callable | Type, *, doc: str | None, msg: str | None):
		if isinstance(funcMethodOrClass, type):
			return _deprecateClass(funcMethodOrClass, doc=doc, msg=msg)
		else:
			return _deprecateFunction(funcMethodOrClass, doc=doc, msg=msg)


	@Decorator
	@overload
	def Deprecated[TCallable](funcMethodOrClass: TCallable, doc: str | None = None, /, *, msg: str | None = None) -> TCallable:
		# just an overload
		pass


	@Decorator
	@overload
	def Deprecated[TCallable](*, msg: str | None = None) -> Callable[[TCallable], TCallable]:
		# just an overload
		pass


	@Decorator
	def Deprecated(*args, msg: str | None = None):
		if args:
			funcMethodOrClass = args[0]
			if len(args) >= 2:
				doc = args[1]
			else:
				doc = None
			return _makeDeprecated(funcMethodOrClass, doc=doc, msg=msg)
		else:
			return lambda funcMethodOrClass: _makeDeprecated(funcMethodOrClass, doc=None, msg=msg)


# Files and Directories, os specific, ...:
if True:
	PLATFORM_IS_WINDOWS: bool = platform.system() == 'Windows'
	PLATFORM_IS_DARWIN: bool = platform.system() == 'Darwin'
	PLATFORM_IS_MAC_OS: bool = PLATFORM_IS_DARWIN
	PLATFORM_IS_LINUX: bool = platform.system() == 'Linux'
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


	def openOrCreate(
			file: str | bytes | os.PathLike,
			mode: str = 'r',
			buffering: int = -1,
			encoding: str | None = None,
			errors: str | None = None,
			newline: str | None = None,
			closefd: bool = True,
			opener: Callable[[str, int], int] | None = None
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


# findall(...), flatmap(...), mix(...), ...:
if True:

	def findall(p: AnyStr, s: AnyStr) -> Iterator[int]:
		"""Yields all the positions of the pattern p in the string s."""
		i = s.find(p)
		while i != -1:
			yield i
			i = s.find(p, i+1)

	@overload
	def flatmap[T1, R](self, func: Callable[[T1], Iterable[R]], iter1: Iterable[T1], /) -> Iterable[R]: ...
	@overload
	def flatmap[T1, T2, R](self, func: Callable[[T1, T2], Iterable[R]], iter1: Iterable[T1], iter2: Iterable[T2], /) -> Iterable[R]: ...
	@overload
	def flatmap[T1, T2, T3, R](self, func: Callable[[T1, T2, T3], Iterable[R]], iter1: Iterable[T1], iter2: Iterable[T2], iter3: Iterable[T3], /) -> Iterable[R]: ...
	@overload
	def flatmap[T1, T2, T3, T4, R](self, func: Callable[[T1, T2, T3, T4], Iterable[R]], iter1: Iterable[T1], iter2: Iterable[T2], iter3: Iterable[T3], iter4: Iterable[T4], /) -> Iterable[R]: ...
	@overload
	def flatmap[T1, T2, T3, T4, T5, R](self, func: Callable[[T1, T2, T3, T4, T5], Iterable[R]], iter1: Iterable[T1], iter2: Iterable[T2], iter3: Iterable[T3], iter4: Iterable[T4], iter5: Iterable[T5], /) -> Iterable[R]: ...
	@overload
	def flatmap[R](self, func: Callable[..., Iterable[R]], iter1: Iterable[Any], iter2: Iterable[Any], iter3: Iterable[Any], iter4: Iterable[Any], iter5: Iterable[Any], iter6: Iterable[Any], /, *iterables: Iterable[Any]) -> Iterable[R]: ...
	
	def flatmap[R](func: Callable[..., Iterable[R]], *iterable) -> Iterable[R]:
		return it.chain.from_iterable(map(func, *iterable))

	# mix(...):
	@overload
	def mix(a: int, b: int, x: float) -> float: ...

	@overload
	def mix(a: float, b: float, x: float) -> float: ...

	@overload
	def mix[TT](a: TT, b: TT, x: float) -> TT: ...

	def mix(a: Any, b: Any, x: float) -> Any:
		return a + (b - a) * x

	# stable float summation:
	def kleinSum(floats: Iterable[float]) -> float:
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

	class FauxTb:
		def __init__(self, tb_frame: FrameType, tb_lineno: int, tb_next: TracebackType | FauxTb | None, tb_lasti: int):
			self.tb_frame: FrameType = tb_frame
			self.tb_lineno: int = tb_lineno
			self.tb_next: TracebackType | FauxTb | None = tb_next
			self.tb_lasti: int = tb_lasti


	def current_stack(skip: int = 0) -> list[tuple[FrameType, int]]:
		f = None  # just to make the type checker happy
		try:
			1/0
		except ZeroDivisionError:
			f = sys.exc_info()[2].tb_frame  # type: ignore
		for i in range(skip + 2):
			f = f.f_back  # type: ignore
		lst = []
		while f is not None:
			lst.append((f, f.f_lineno))
			f = f.f_back
		return lst


	def extend_traceback(tb: TracebackType | None, stack: list[tuple[FrameType, int]]) -> TracebackType | None:
		"""Extend traceback with stack info."""
		head: TracebackType | FauxTb | None = tb
		for tb_frame, tb_lineno in stack:
			head = FauxTb(tb_frame, tb_lineno, head, -1)
		return cast(TracebackType | None, head)
	# END COPIED from


	def exc_info[E: BaseException](e: E | None = None) -> tuple[Type[E], E, TracebackType | None]:
		"""Like sys.exc_info, but includes the full traceback."""
		if e is not None:
			return type(e), e, e.__traceback__
		else:
			return sys.exc_info()  # type: ignore


	def full_exc_info[E: BaseException](e: E | None = None) -> tuple[Type[E], E, TracebackType | None]:
		"""Like sys.exc_info, but includes the full traceback."""
		t, v, tb = exc_info(e)
		full_tb = extend_traceback(tb, current_stack(1))
		return t, v, full_tb
	# END COPIED from


	def format_full_exc(e: BaseException | None = None) -> str:
		from traceback import format_exception
		exc, value, tb = full_exc_info(e)
		return ''.join(format_exception(exc, value, tb))


	def format_exc_no_traceback(e: BaseException | None = None) -> str:
		from traceback import format_exception_only
		exc, value, tb = exc_info(e)
		return ''.join(format_exception_only(exc, value))


__all__ = [
	'onCrash',

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

	'CrashReportWrapped',
	'isCrashReportWrapped',
	'runLaterSafe',

	'DeferredCallOnceMethod',
	'BusyIndicator',

	'Deprecated',

	'PLATFORM_IS_WINDOWS',
	'PLATFORM_IS_DARWIN',
	'PLATFORM_IS_MAC_OS',
	'PLATFORM_IS_LINUX',

	'FILE_BROWSER_DISPLAY_NAME',

	'openOrCreate',
	'getExePath',
	'showInFileSystem',

	'INVALID_PATH_CHARS',
	'sanitizeFileName',

	'findall',
	'flatmap',
	'mix',
	'kleinSum',

	'exc_info',
	'full_exc_info',
	'format_full_exc',
	'format_exc_no_traceback',
]
