import enum
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any, ContextManager, Callable, Protocol

from ..utils import format_full_exc, formatters
from ..utils.formatters import formatFuncCall, formatVal, indentMultilineStr, PW, WriterObjectABC


def printIndented(val, *, prefix: str = '', indentLvl: int = 0, enabled: bool = True, stream: WriterObjectABC = None):
	additionalIndentLvl = 1 + indentLvl
	if not enabled:
		return
	stream = stream if stream is not None else _currentOutStream
	if callable(val):
		val = val()
	global _m_indent_lvl
	_m_indent_lvl += additionalIndentLvl
	indentStr = prefix + (formatters.INDENT * _m_indent_lvl)
	indentMultilineStr(str(val), indent=indentStr, s=stream)
	stream += '\n'
	_m_indent_lvl -= additionalIndentLvl
	stream.flush()


_isEnabledGlobal = True
_m_indent_lvl = -1
__callingDict = list()  # used to detect infinite Recursion cause by the IndentLeveledBare function.


def _indentLeveledRecursionSafe(isMemberFunc: bool = False, enabled: bool = True, maxDepth: int = 1, printArgs: bool = True):
	def transformer(func):
		if not enabled:
			return func

		@wraps(func)
		def wrapped(*args, **kwargs):
			global _isEnabledGlobal
			global _m_indent_lvl

			if not _isEnabledGlobal:
				return func(*args, **kwargs)

			# indentation:
			lastMAX_INDENTS = formatters.MAX_INDENTS
			newMAX_INDENTS = _m_indent_lvl + 0 + maxDepth
			try:
				formatters.MAX_INDENTS = newMAX_INDENTS
				indentStr = formatters.INDENT *_m_indent_lvl

				# recursion:
				funcId = (args[0], func) if isMemberFunc else (None, func)

				if any( (funcId[0] is f[0]) and (funcId[1] is f[1]) for f in __callingDict):
					printIndented(f"Infinite recursion prevented in `_indentLeveledRecursionSafe()` (`@LoggedIndentedMethod()` and `@LoggedIndentedFunction`).")
					formatters.MAX_INDENTS = lastMAX_INDENTS
					result = func(*args, **kwargs)
					return result

				__callingDict.append(funcId)

				# nameing:
				valueName = ''
				typeName = ''
				if isMemberFunc:
					self = args[0]
					# if not valueName and hasattr(self, 'fullName'):
					#	valueName = self.fullName
					#	valueName = valueName if isinstance(valueName, str) else ''

					if not valueName and hasattr(self, 'name'):
						valueName = self.name
						valueName = valueName if isinstance(valueName, str) else ''

					if not valueName and hasattr(self, '__name__'):
						valueName = self.__name__
						valueName = valueName if isinstance(valueName, str) else ''
					cls = type(self)
					if not typeName:
						typeName = cls.__name__
						typeName = typeName if isinstance(typeName, str) else ''

				moduleName = func.__module__ if hasattr(func, '__module__') else ''

				# recursion:
				__callingDict.remove(funcId)

				# call func:
				if printArgs:
					printIndented(f"{formatFuncCall(func, args, kwargs, isMemberFunc, tab=_m_indent_lvl, newLine='', singleIndent='')}      {valueName} ({typeName} in {moduleName})")
				else:
					if isMemberFunc:
						printIndented(f"{formatFuncCall(func, (args[0],), isMemberFunc=True, tab=_m_indent_lvl, newLine='', singleIndent='')}      {valueName} ({typeName} in {moduleName})")
					else:
						printIndented(f"{formatFuncCall(func, isMemberFunc=False, tab=_m_indent_lvl, newLine='', singleIndent='')}      {valueName} ({typeName} in {moduleName})")
				try:
					formatters.MAX_INDENTS = lastMAX_INDENTS
					_m_indent_lvl +=1
					result = func(*args, **kwargs)
					formatters.MAX_INDENTS = newMAX_INDENTS
				except Exception as e:
					formatters.MAX_INDENTS -= 1
					_m_indent_lvl -=1
					printIndented(f"!{func.__name__} throws: {e}")
					if func.__name__ == "tryGetValue":
						import traceback
						traceback.print_exc()
					raise e
				else:
					formatters.MAX_INDENTS -= 1
					_m_indent_lvl -=1
					if isinstance(result, (bool, int, float, str )) \
							or isinstance(result, str) and len(result) < 128-2 \
							or isinstance(result, (list, tuple)) and len(result) < 4:
						printIndented(f"{func.__name__} returns: {result}")
					else:
						printIndented(f"{func.__name__} returns: {formatVal(type(result), tab=_m_indent_lvl)}")
				return result
			finally:
				formatters.MAX_INDENTS = lastMAX_INDENTS
		return wrapped
	return transformer


def LoggedIndentedMethod(enabled: bool = True, maxDepth: int = 1, printArgs: bool = True):
	return _indentLeveledRecursionSafe(isMemberFunc=True, enabled=enabled, maxDepth=maxDepth, printArgs=printArgs)


def LoggedIndentedFunction(enabled: bool = True, maxDepth=1, printArgs: bool = True):
	return _indentLeveledRecursionSafe(isMemberFunc=False, enabled=enabled, maxDepth=maxDepth, printArgs=printArgs)


class LogLevel(enum.IntEnum):
	FATAL = 50
	ERROR = 40
	WARN = 30
	INFO = 20
	DEBUG = 10
	ALWAYS = 0


_LOG_LEVEL_STRS = {
	LogLevel.FATAL: "FATAL  ",
	LogLevel.ERROR: "ERROR  ",
	LogLevel.WARN:  "WARNING",
	LogLevel.INFO:  "INFO   ",
	LogLevel.DEBUG: "DEBUG  ",
}

_loggingEnabled = True
_currentLogELevel = LogLevel.DEBUG
_currentBaseIndentLevel = 0


def isEnabledFor(level: LogLevel):
	"""
	Is this logger enabled for level 'level'?
	"""
	return _loggingEnabled and level >= _currentLogELevel

def logDebug(e: Exception | str, *args: Any, indentLvl: int = 0, stream: WriterObjectABC = None, includeTraceback: bool = True):
	_log(e, args, LogLevel.DEBUG, indentLvl, stream, includeTraceback)


def logInfo(e: Exception | str, *args: Any, indentLvl: int = 0, stream: WriterObjectABC = None, includeTraceback: bool = True):
	_log(e, args, LogLevel.INFO, indentLvl, stream, includeTraceback)


def logWarning(e: Exception | str, *args: Any, indentLvl: int = 0, stream: WriterObjectABC = None, includeTraceback: bool = True):
	_log(e, args, LogLevel.WARN, indentLvl, stream, includeTraceback)


def logError(e: Exception | str, *args: Any, indentLvl: int = 0, stream: WriterObjectABC = None, includeTraceback: bool = True):
	_log(e, args, LogLevel.ERROR, indentLvl, stream, includeTraceback)


def logFatal(e: Exception | str, *args: Any, indentLvl: int = 0, stream: WriterObjectABC = None, includeTraceback: bool = True):
	_log(e, args, LogLevel.FATAL, indentLvl, stream, includeTraceback)


def _log(e: Exception | str, args: tuple[Any, ...], level: LogLevel, indentLvl: int = 0, stream: WriterObjectABC = None, includeTraceback: bool = True):
	if isEnabledFor(level):
		msg = formatLogMessage(e, args, includeTraceback=includeTraceback)
		printIndented(msg, prefix=getLogPrefix(level), indentLvl=indentLvl + _currentBaseIndentLevel, stream=stream)


def getLogPrefix(logLevel: LogLevel):
	return f"{datetime.now().time()} {_LOG_LEVEL_STRS[logLevel]}: "


def formatLogMessage(e: Exception | str, args: tuple[Any, ...], *, includeTraceback: bool):
	if isinstance(e, Exception):
		e = formatException(e, includeTraceback=includeTraceback)
	msg = ', '.join((str(e), *(str(v) for v in args)))
	return msg


def formatException(e: Exception, *, includeTraceback: bool) -> str:
	if includeTraceback:
		return format_full_exc(e)
	else:
		return f"{type(e).__name__}: {str(e)}"


class LoggingFunction(Protocol):
	def __call__(self, e: Exception | str, *args: Any, indentLvl: int = 0, stream: WriterObjectABC = None, includeTraceback: bool = True) -> None:
		...


class _LoggingIndentFunction(Protocol):
	def __call__(self, e: Exception | str = None, *args: Any, stream: WriterObjectABC = None, includeTraceback: bool = True) -> ContextManager:
		...


def _loggingIndent(name: str, level: LogLevel) -> Callable[[], ContextManager]:
	"""
	contextmanager that increases th indentation for all contained logging operations.
	:return:
	"""
	@contextmanager
	def loggingIndent(e: Exception | str = None, *args: Any, stream: WriterObjectABC = None, includeTraceback: bool = True):
		"""
		contextmanager that increases th indentation for all contained logging operations.
		:return:
		"""
		global _currentBaseIndentLevel
		isEnabled = isEnabledFor(level)
		if isEnabled:
			if e is not None:
				_log(e, args, level, stream=stream, includeTraceback=includeTraceback)
			_currentBaseIndentLevel += 1
		try:
			yield
		finally:
			if isEnabled:
				_currentBaseIndentLevel = max(0, _currentBaseIndentLevel - 1)
	loggingIndent.__name__ = name
	return loggingIndent


loggingIndentDebug: _LoggingIndentFunction = _loggingIndent('loggingIndentDebug', LogLevel.DEBUG)
"""contextmanager that increases th indentation for all contained logging operations if the log level is greater or equal to LogLevel.DEBUG."""
loggingIndentInfo: _LoggingIndentFunction = _loggingIndent('loggingIndentInfo', LogLevel.INFO)
"""contextmanager that increases th indentation for all contained logging operations if the log level is greater or equal to LogLevel.INFO."""
loggingIndentWarning: _LoggingIndentFunction = _loggingIndent('loggingIndentWarning', LogLevel.WARN)
"""contextmanager that increases th indentation for all contained logging operations if the log level is greater or equal to LogLevel.WARN."""
loggingIndentFatal: _LoggingIndentFunction = _loggingIndent('loggingIndent', LogLevel.FATAL)
"""contextmanager that increases th indentation for all contained logging operations if the log level is greater or equal to LogLevel.FATAL."""
loggingIndent: _LoggingIndentFunction = _loggingIndent('loggingIndent', LogLevel.ALWAYS)
"""contextmanager that increases th indentation for all contained logging operations independent of the log level."""


# @contextmanager
# def loggingIndent():
# 	"""
# 	contextmanager that increases th indentation for all contained logging operations.
# 	:return:
# 	"""
# 	global _currentBaseIndentLevel
# 	_currentBaseIndentLevel += 1
# 	try:
# 		yield
# 	finally:
# 		_currentBaseIndentLevel = max(0, _currentBaseIndentLevel - 1)


_currentOutStream = PW()


def setLoggingStream(newStream: WriterObjectABC) -> None:
	global _currentOutStream
	_currentOutStream = newStream


__all__ = [
	"LoggedIndentedMethod",
	"LoggedIndentedFunction",
	"printIndented",

	"logDebug",
	"logInfo",
	"logWarning",
	"logError",
	"logFatal",

	"loggingIndentDebug",
	"loggingIndentInfo",
	"loggingIndentWarning",
	"loggingIndent",

	"setLoggingStream",
]
