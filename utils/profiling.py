
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, ClassVar, Optional, Union

from . import Decorator, override
from .utils import kleinSum

HAS_TIMER = False
try:
	from timerit import Timer
except ModuleNotFoundError as e:
	print("Module '{}' not found.".format('timerit'))
else:
	HAS_TIMER = True


if not HAS_TIMER:
	class Timer(object):
		def __init__(self, label='', verbose=None, newline=True):
			self.label = label
			self.verbose = verbose
			self.newline = newline
			self.tstart = -1.0
			self.elapsed = -1.0
			self.write = sys.stdout.write
			self.flush = sys.stdout.flush

		def __enter__(self):
			return self

		def __exit__(self, ex_type, ex_value, trace):
			if trace is not None:
				return False


USE_SCALENE = False
USE_B_PROFILE_CUSTOM = True


HAS_SCALENE = False
HAS_B_PROFILE_CUSTOM = False
HAS_B_PROFILE = False
HAS_PROFILER = False


if not HAS_PROFILER and USE_SCALENE:
	try:
		from scalene import scalene_profiler
	except ModuleNotFoundError:
		scalene_profiler = None
		if USE_SCALENE:
			print("USE_SCALENE == True, but 'scalene' Module not found. falling back to 'bprofile'.")
	else:
		HAS_SCALENE = True
		HAS_PROFILER = True
else:
	scalene_profiler = None


if not HAS_PROFILER and USE_B_PROFILE_CUSTOM:
	try:
		from .bprofileCustom import BProfile as BProfileCustom

	except ModuleNotFoundError as e:
		print("Custom 'bprofile' Module not found. looking for default...")
	else:
		HAS_B_PROFILE_CUSTOM = True
		HAS_PROFILER = True


if not HAS_PROFILER:
	try:
		from bprofile import BProfile
	except ModuleNotFoundError as e:
		print("Module 'bprofile' not found.")
	else:
		HAS_B_PROFILE = True
		HAS_PROFILER = True


if HAS_B_PROFILE_CUSTOM:
	_Profile = BProfileCustom

if HAS_B_PROFILE:
	_Profile = BProfile

if HAS_SCALENE or not HAS_PROFILER:
	@dataclass
	class _Profile:
		output_path: str
		threshold_percent: float = 2.5
		report_interval: float = 5
		colourNodesBySelftime: Optional[bool] = False
		enabled: bool = True
		time_of_last_report: float = field(default=0., init=False, compare=False)

		_hasStartedProfiler: bool = field(default=False, init=False, compare=False)
		_hasEnteredCount: int = field(default=False, init=False, compare=False)

		_isAnyRunning: ClassVar[bool] = False

		def set_enabled(self, enabled: bool): 
			pass

		def __call__(self, *args, **kwargs):
			pass

		if not HAS_PROFILER:
			def __enter__(self):
				pass

			def __exit__(self, exc_type, exc_value, tracebacks):
				return False
		else:
			def __enter__(self):
				if self._hasEnteredCount == 0:
					if self.enabled and not _Profile._isAnyRunning and not self._hasStartedProfiler:
						_Profile._isAnyRunning = True
						print(f"] [ STARTING PROFILER")
						scalene_profiler.start()
						self._hasStartedProfiler = True
				self._hasEnteredCount += 1

			def __exit__(self, exc_type, exc_value, tracebacks):
				try:
					if self._hasEnteredCount == 1:
						if self._hasStartedProfiler:
							scalene_profiler.stop()
							self._hasStartedProfiler = False
							_Profile._isAnyRunning = False
				finally:
					self._hasEnteredCount = max(0, self._hasEnteredCount - 1)
				return False


@dataclass(eq=False)
class TimedAction:

	# class var:
	_recursionDepth: ClassVar[int] = 0
	_SINGLE_INDENT: ClassVar[str] = '  '

	label: str = ''
	details: str = ''
	verbose: bool = True
	doPrint: bool = True
	doLog: bool = False
	_timer: Timer = field(default_factory=Timer, init=False)

	@property
	def elapsed(self) -> float:
		return self._timer.elapsed

	@classmethod
	def logNPrint(cls, msg: str, doPrint: bool = True, doLog: bool = False) -> None:
		indentStr = cls._SINGLE_INDENT * TimedAction._recursionDepth
		if doPrint:
			print(f'{indentStr}{msg}')
		if doLog:
			logDebug(f'{indentStr}{msg}')

	def __enter__(self):
		if self.verbose:
			self.logNPrint(f"[ ] {self.label} {self.details} ...", self.doPrint, self.doLog)
		TimedAction._recursionDepth += 1
		self._timer.__enter__()
		return self

	def __exit__(self, ex_type, ex_value, trace):
		result = self._timer.__exit__(ex_type, ex_value, trace)
		secondsStr = f'{self.elapsed:8.3f} s'
		successStr = 'successful' if trace is None else 'FAILED'
		TimedAction._recursionDepth -= 1
		self.logNPrint(f"[ ] {self.label}: {secondsStr} ({successStr})", self.doPrint, self.doLog)
		return False


# @Decorator
@dataclass(eq=False)
class TimedFunction:
	enabled: Union[Callable[[Any], bool], bool] = True
	verbose: Union[Callable[[Any], bool], bool] = True
	details: Union[Callable[[Any], str], str] = ''
	doPrint: Union[Callable[[Any], bool], bool] = True
	doLog: Union[Callable[[Any], bool], bool] = False

	def getLabel(self, func: Callable, funcName: str, args: tuple, kwargs: dict) -> str:
		return f"{funcName}()"

	def __call__(self, func):
		if not self.enabled:
			return func

		def _getOrCall(val, args, kwargs):
			if callable(val):
				return val(*args, **kwargs)
			return val

		funcName = func.__name__

		@wraps(func)
		def timedFunc(*args, **kwargs):
			enabled = _getOrCall(self.enabled, args, kwargs)
			if not enabled:
				return func(*args, **kwargs)

			verbose = _getOrCall(self.verbose, args, kwargs)
			details = _getOrCall(self.details, args, kwargs)
			doPrint = _getOrCall(self.doPrint, args, kwargs)
			doLog = _getOrCall(self.doLog, args, kwargs)

			label = self.getLabel(func, funcName, args, kwargs)

			with TimedAction(label, details=details, verbose=verbose, doPrint=doPrint, doLog=doLog):
				return func(*args, **kwargs)
		return timedFunc


# @Decorator
@dataclass(eq=False)
class TimedMethod(TimedFunction):

	objectName: Union[Callable[[Any], str], str, None] = None

	@override
	def getLabel(self, func: Callable, funcName: str, args: tuple, kwargs: dict) -> str:
		typeName = type(args[0]).__name__
		objectName = self.objectName
		if objectName is None:
			objectName = typeName
		else:
			if callable(objectName):
				objectName = objectName(args[0])
			objectName = f"{typeName}<{objectName}>"
		return f"{objectName}.{funcName}()"


class ProfiledAction:
	"""docstring for MethodTimer"""

	def __init__(self, name: str, threshold_percent: float = 1., report_interval: float = 5., colourNodesBySelftime: bool = False, enabled: bool = True):
		super().__init__()
		self._name = name
		self._threshold_percent = threshold_percent
		self._report_interval = report_interval
		self._colourNodesBySelftime = colourNodesBySelftime
		self._enabled = enabled
		self._recursionDepth: int = 0
		if enabled:
			self.profiler = self._makeProfiler()
		else:
			self.profiler = None

	def _makeProfiler(self):
		path, _, name = self.name.rpartition('/')
		path = f'{path}/profiling/' if path else 'profiling/'
		return _Profile(f'{path}profileReport_{name}.png', threshold_percent=self.threshold_percent, enabled=self._enabled)

	@property
	def name(self) -> str:
		return self._name

	@property
	def threshold_percent(self) -> float:
		return self._threshold_percent

	@threshold_percent.setter
	def threshold_percent(self, value: float):
		self._threshold_percent = value

	@property
	def report_interval(self) -> float:
		return self._report_interval

	@report_interval.setter
	def report_interval(self, value: float):
		self._report_interval = value

	if HAS_B_PROFILE_CUSTOM:
		@property
		def colourNodesBySelftime(self) -> bool:
			return self._colourNodesBySelftime

		@colourNodesBySelftime.setter
		def colourNodesBySelftime(self, value: bool):
			self._colourNodesBySelftime = value
	else:
		# colourNodesBySelftime will be defined in __init__(...)
		pass

	@property
	def enabled(self) -> bool:
		return self._enabled

	@enabled.setter
	def enabled(self, value: bool):
		self._enabled = value
		if value and self.profiler is None:
			self.profiler = self._makeProfiler()

	def _setValues(self):
		self.profiler.threshold_percent = self._threshold_percent
		self.profiler.report_interval = self._report_interval
		self.profiler.colourNodesBySelftime = self._colourNodesBySelftime
		self.profiler.set_enabled(self._enabled)

	def __enter__(self):
		if self.profiler is not None:
			if self._recursionDepth == 0:
				self._setValues()
				self.profiler.__enter__()
			self._recursionDepth += 1

	def __exit__(self, exc_type, exc_value, tracebacks):
		if self.profiler is not None:
			self._recursionDepth -= 1
			if self._recursionDepth == 0:
				return self.profiler.__exit__(exc_type, exc_value, tracebacks)


@Decorator
class ProfiledFunction:
	"""docstring for MethodTimer"""
	def __init__(
			self,
			threshold_percent: Union[Callable[[Any], float], float] = 1.,
			report_interval: Union[Callable[[Any], float], float] = 5.,
			colourNodesBySelftime: Union[Callable[[Any], Optional[bool]], bool, None] = False ,
			enabled: Union[Callable[[Any], bool], bool] = True
	):
		super().__init__()
		self.options = dict(threshold_percent=threshold_percent, report_interval=report_interval, colourNodesBySelftime=colourNodesBySelftime , enabled=enabled)
		
	def __call__(self, func):
		if not self.options['enabled']:
			return func

		funcName = func.__name__
		self.profiler = ProfiledAction(funcName, enabled=True)

		@wraps(func)
		def profiledFunction(*args, **kwargs):
			for attr, value in self.options.items():
				if callable(value):
					value = value(*args, **kwargs)
				setattr(self.profiler, attr, value)

			with self.profiler:
				return func(*args, **kwargs)
		return profiledFunction


@Decorator
class FunctionCallCounter:
	"""docstring for FunctionCallCounter"""

	callCounts: dict[str, int] = defaultdict(int)
	callTimes: dict[str, list[float]] = defaultdict(list)

	def __init__(self, enabled=True, minPrintCount: int = 100):
		self.enabled = enabled
		self.minPrintCount = minPrintCount
		self._timer: Timer = Timer()

	def setLabel(_self_, _func_, _funcName_, args, kwargs):
		_self_._label = f"{_funcName_}()"

	def __call__(self, func):
		if not self.enabled:
			return func

		funcName = func.__name__

		@wraps(func)
		def timedFunc(*args, **kwargs):
			self.setLabel(func, funcName, args, kwargs)
			with self:
				return func(*args, **kwargs)
		return timedFunc

	def __enter__(self):
		self._timer.__enter__()
		return self

	def __exit__(self, ex_type, ex_value, trace):
		self._timer.__exit__(ex_type, ex_value, trace)

		self.callCounts[self._label] += 1
		self.callTimes[self._label].append(self._timer.elapsed)

		callCount = self.callCounts[self._label]
		if callCount % self.minPrintCount == 0:
			totalTime = kleinSum(self.callTimes[self._label])
			self.callTimes[self._label] = [totalTime]
			print(f"[ ] {self._label}: callCount: {callCount}. total: {totalTime:8.3f} s elapsed, {totalTime/callCount:8.3f} / call.")


@Decorator
class MethodCallCounter(FunctionCallCounter):
	def setLabel(_self_, _func_, _funcName_, args, kwargs):
		typeName = type(args[0]).__name__
		_self_._label = f"{typeName}.{_funcName_}()"


from ..utils.logging_ import logDebug, logInfo, logWarning, logError, logFatal, printIndented

__all__ = [
	"Timer",
	"TimedAction",
	"TimedFunction",
	"TimedMethod",

	"ProfiledAction",
	"ProfiledFunction",

	"FunctionCallCounter",
	"MethodCallCounter",

	"printIndented",

	"logDebug",
	"logInfo",
	"logWarning",
	"logError",
	"logFatal",
]
