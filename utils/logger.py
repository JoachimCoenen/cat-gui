from datetime import datetime
from functools import wraps
from typing import Any, Union

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


def _callLoggerIndentedRecursionSafe(isMemberFunc: bool = False, enabled: bool = True, maxDepth: int = 1, printArgs: bool = True):
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


def LogFunctionCall(enabled: bool = True, maxDepth=1, printArgs: bool = True):
	return _callLoggerIndentedRecursionSafe(isMemberFunc=False, enabled=enabled, maxDepth=maxDepth, printArgs=printArgs)


def LogMethodCall(enabled: bool = True, maxDepth: int = 1, printArgs: bool = True):
	return _callLoggerIndentedRecursionSafe(isMemberFunc=True, enabled=enabled, maxDepth=maxDepth, printArgs=printArgs)


DEBUG = 'DEBUG'
INFO = 'INFO'
WARNING = 'WARNING'
ERROR = 'ERROR'
FATAL = 'FATAL'

LOG_STYLES = [DEBUG, INFO, WARNING, ERROR, FATAL,]
MAX_LOG_STYLE_LENGTH = max(len(style) for style in LOG_STYLES)
PREFIX_TEMPLATE = f"{{time}} {{style:{MAX_LOG_STYLE_LENGTH}}}: "


def log(msg: Union[Exception, str], *args: Any, style: str, indentLvl: int = 0, stream: WriterObjectABC = None) -> None:
	if isinstance(msg, Exception):
		msg = f"{type(msg).__name__}: {str(msg)}"
	msg = ', '.join((str(msg), *(str(v) for v in args)))
	prefix = PREFIX_TEMPLATE.format(time=datetime.now().time(), style=style)
	printIndented(msg, prefix=prefix, indentLvl=indentLvl, stream=stream)


def debug(msg: Union[Exception, str], *args: Any, indentLvl: int = 0) -> None:
	log(msg, *args, style=DEBUG, indentLvl=indentLvl)


def info(msg: Union[Exception, str], *args: Any, indentLvl: int = 0) -> None:
	log(msg, *args, style=INFO, indentLvl=indentLvl)


def warning(msg: Union[Exception, str], *args: Any, indentLvl: int = 0) -> None:
	log(msg, *args, style=WARNING, indentLvl=indentLvl)


def error(msg: Union[Exception, str], *args: Any, indentLvl: int = 0) -> None:
	log(msg, *args, style=ERROR, indentLvl=indentLvl)


def exception(msg: Union[Exception, str], *args: Any, indentLvl: int = 0) -> None:
	if isinstance(msg, Exception):
		msg = format_full_exc(msg)
	error(msg, *args, indentLvl=indentLvl)


def fatal(msg, *args: Any, indentLvl: int = 0) -> None:
	if isinstance(msg, Exception):
		msg = format_full_exc(msg)
	log(msg, *args, style=FATAL, indentLvl=indentLvl)




_currentOutStream = PW()


def setLoggingStream(newStream: WriterObjectABC) -> None:
	_currentOutStream = newStream


__all__ = [
	"printIndented",
	"LogFunctionCall",
	"LogMethodCall",

	"log",
	"debug",
	"info",
	"warning",
	"error",
	"exception",
	"fatal",

	"setLoggingStream",
]
