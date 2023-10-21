from __future__ import annotations

from abc import ABC, abstractmethod
import dataclasses
from typing import Any, final, IO, Callable, Optional, Mapping, Type, Union

from .collections_ import AddToDictDecorator, Stack, getIfKeyIssubclassOrEqual, OrderedDict, OrderedMultiDict

import collections


class WriterObjectABC(ABC):
	"""docstring for WriterObjectABC"""

	@abstractmethod
	def __iadd__(self, other):
		return NotImplemented

	@abstractmethod
	def write(self, other):
		return NotImplemented

	@abstractmethod
	def flush(self):
		return NotImplemented


FormattingFunc = Callable[[Any, int, Mapping[type, 'FormattingFunc'], str, str, str, WriterObjectABC], None]


_valueFormatters: dict[type, FormattingFunc] = {}
Formatter = AddToDictDecorator(_valueFormatters)

_predicatedValueFormatters: OrderedDict[Callable[[type], bool], FormattingFunc] = OrderedDict()
PredicatedFormatter = AddToDictDecorator(_predicatedValueFormatters)


class FW(WriterObjectABC):
	"""docstring for FW"""
	def __init__(self, file: IO[Any]):
		super(FW, self).__init__()
		self.s: IO[Any] = file
		self.write = file.write

	def __iadd__(self, other):
		assert isinstance(other, str)
		self.s.write(other)
		return self

	def write(self, other: str):
		print(other, end='')

	def flush(self):
		self.s.flush()


class PW(WriterObjectABC):
	"""Writes to the console by calling print()"""
	def __init__(self):
		super(PW, self).__init__()
		self.s = SW()

	def __iadd__(self, other: str):
		self.s += other
		return self

	def write(self, other: str):
		self.s += other

	def flush(self):
		self.s.flush()
		print(self.s, end='')
		self.s = SW()
		pass

	def __del__(self):
		self.flush()


class PWDirect(WriterObjectABC):
	"""docstring for PW"""
	def __init__(self):
		super().__init__()
		self.s = SW()

	def __iadd__(self, other: str):
		print(other, end='')
		return self

	def write(self, other: str):
		print(other, end='')

	def flush(self):
		pass

	def __del__(self):
		self.flush()


class SW(WriterObjectABC):
	"""docstring for SW"""
	def __init__(self, initStr: str = ''):
		super(SW, self).__init__()
		self.s = str(initStr)
							
	def __iadd__(self, other: str):
		self.s += other
		return self

	def write(self, other: str):
		self.s += other

	def flush(self):
		pass

	def __str__(self):
		return self.s

	def __repr__(self):
		return f"SW({repr(self.s)})"

	def copy(self):
		other = self.__class__()
		other.s = str(self.s)
		return other


INDENT = '  '


def formatDictOnly(v: dict, *, tab: int = 0,  singleIndent: str = INDENT, separator: str = ',', newLine: str = '\n', indentFirstLine: bool = True, s=None):
	localFormatters = {dict: formatDict}
	formatVal(v, tab=tab, localFormatters=localFormatters, singleIndent=singleIndent, separator=separator, newLine=newLine, indentFirstLine=indentFirstLine, s=s)
	return s


def indentMultilineStr(text: str, *, indent: Union[str, int], indentFirstLine: Union[str, int, bool] = True, prefix: str = '', s=None):
	s = s or SW()

	if not indent and not prefix and (not indentFirstLine or isinstance(indentFirstLine, bool)):
		s += text
		return s

	splitLines = text.splitlines()
	if not splitLines:
		s += text
		return s

	if type(indent) is int:
		indent = INDENT * indent
	indent = indent + prefix

	iter_ = iter(splitLines)
	firstLine = next(iter_)

	if isinstance(indentFirstLine, bool):
		if indentFirstLine:
			s += indent
		else:
			s += prefix
	elif isinstance(indentFirstLine, int):
		s += INDENT * indentFirstLine + prefix
	else:
		s += indentFirstLine + prefix

	s += firstLine

	for line in iter_:
		s += '\n'
		s += indent
		s += line
	if len(text) > 0 and text[-1] == '\n':
		s += '\n'
	return s


def formatAnythingElse(
		v: Any, tab: int, localFormatters: Mapping[type, FormattingFunc],
		singleIndent: str, separator: str, newLine: str, s: WriterObjectABC
):
	try:
		s += repr(v)
	except RecursionError as e:
		print(str(v))
		raise


def getFormatter(localFormatters: Mapping[type, FormattingFunc], cls) -> FormattingFunc:
	# , localPredicateFormatters: OrderedDict[Callable[[type], bool], FormattingFunc]
	result = getIfKeyIssubclassOrEqual(localFormatters, cls, None)
	if result is not None:
		return result

	for predicate, formattingFunc in _predicatedValueFormatters.items():
		if predicate(cls):
			return formattingFunc

	return formatAnythingElse


def formatVal(
		v: Any,
		*,
		tab: int = 0,
		localFormatters: Optional[Mapping] = None,
		formatterAdjust: Optional[Mapping[Type, FormattingFunc]] = None,
		singleIndent: str = INDENT,
		separator: str = ',',
		newLine: str = '\n',
		indentFirstLine: bool = True,
		s: Optional[WriterObjectABC] = None
):
	if localFormatters is None:
		localFormatters = _valueFormatters
		if formatterAdjust:
			localFormatters = localFormatters.copy()
			localFormatters.update(formatterAdjust)
	s = s or SW()
	if tab != 0 and indentFirstLine:
		s += singleIndent * tab
	_formatVal(v, tab, localFormatters, singleIndent, separator, newLine, s)
	return s


MAX_INDENTS = 120 // 10


def _formatVal(v, tab, localFormatters, singleIndent, separator, newLine, s):
	if tab < MAX_INDENTS:
		formatter = getFormatter(localFormatters, type(v))
		formatter(v, tab, localFormatters, singleIndent, separator, newLine, s)
	else:
		formatAnythingElse(v, tab, localFormatters, singleIndent, separator, newLine, s)


def formatListLike2(iterable, tab, localFormatters, singleIndent, separator, newLine, s, parenthesies, skipLastSeparator=True, formatListItem=_formatVal):
	tab += 1
	indent = singleIndent * tab
	try:
		firstItem = next(iterable)
		s += parenthesies[0] + newLine + indent
		formatListItem(firstItem, tab, localFormatters, singleIndent, separator, newLine, s)

	except StopIteration:
		s += parenthesies[0] + parenthesies[1]
		return

	for item in iterable:
		s += separator + newLine + indent
		formatListItem(item, tab, localFormatters, singleIndent, separator, newLine, s)
	if not skipLastSeparator:
		s += separator
	else:
		s += newLine + singleIndent*(tab-1) + parenthesies[1]


@Formatter(list)
def formatList(v, tab, localFormatters, singleIndent, separator, newLine, s):
	formatListLike2(iter(v), tab, localFormatters, singleIndent, separator, newLine, s, '[]')


@Formatter(tuple)
def formatTuple(v, tab, localFormatters, singleIndent, separator, newLine, s):
	formatListLike2(iter(v), tab, localFormatters, singleIndent, separator, newLine, s, '()')


@Formatter(set)
@Formatter(frozenset)
def formatSet(v, tab, localFormatters, singleIndent, separator, newLine, s):
	formatListLike2(iter(v), tab, localFormatters, singleIndent, separator, newLine, s, '{}')


def formatDictItem(v, tab, localFormatters, singleIndent, separator, newLine, s):
	key, val = v
	_formatVal(key, tab, localFormatters, singleIndent, separator, newLine, s)
	s += ": "
	_formatVal(val, tab, localFormatters, singleIndent, separator, newLine, s)


@Formatter(dict)
def formatDict(v, tab, localFormatters, singleIndent, separator, newLine, s):
	formatListLike2(iter(v.items()), tab, localFormatters, singleIndent, separator, newLine, s, '{}', formatListItem=formatDictItem)


@Formatter(Stack)
def formatStack(v, tab, localFormatters, singleIndent, separator, newLine, s):
	formatType(type(v), tab, localFormatters, singleIndent, separator, newLine, s)
	formatListLike2(iter(v), tab, localFormatters, singleIndent, separator, newLine, s, ('([','])'))


@Formatter(collections.UserList)
def formatUserList(v, tab, localFormatters, singleIndent, separator, newLine, s):
	formatType(type(v), tab, localFormatters, singleIndent, separator, newLine, s)
	formatListLike2(iter(v), tab, localFormatters, singleIndent, separator, newLine, s, ('([','])'))


@Formatter(collections.ChainMap)
@Formatter(collections.UserDict)
@Formatter(OrderedMultiDict)
def formatUserDict(v, tab, localFormatters, singleIndent, separator, newLine, s):
	formatType(type(v), tab, localFormatters, singleIndent, separator, newLine, s)
	formatListLike2(iter(v.items()), tab, localFormatters, singleIndent, separator, newLine, s, ('({','})'), formatListItem=formatDictItem)


@Formatter(type)
def formatType(v, tab, localFormatters, singleIndent, separator, newLine, s):
	if hasattr(v, '__module__'):
		s += v.__module__ + '.'
	s += v.__name__


def __NEW_DUMMY():
	def __DUMMY():
		pass
	return __DUMMY


class FuncArgs(object):
	"""docstring for FuncArgs"""
	def __init__(self, *args, **kwargs):
		super().__init__()
		self.args = args
		self.kwargs = kwargs


class FuncCall(object):
	"""docstring for FuncArgs"""
	def __init__(self, func, funcArgs, isMemberFunc):
		super().__init__()
		self.func = func
		self.funcArgs = funcArgs
		self.object = None
		if isMemberFunc:
			self.object = self.funcArgs.args[0]
			self.funcArgs.args = self.funcArgs.args[1:]


def formatKwArg(v, tab, localFormatters, singleIndent, separator, newLine, s):
	key, val = v
	s += key + " = "
	# _formatVal(val, tab, localFormatters, singleIndent, separator, newLine, s)
	# inlined from _formatVal():
	if tab < MAX_INDENTS:
		formatter = getFormatter(localFormatters, type(val))
		formatter(val, tab, localFormatters, singleIndent, separator, newLine, s)
	else:
		formatAnythingElse(val, tab, localFormatters, singleIndent, separator, newLine, s)


def formatFuncArgs(args=(), kwargs={}, tab=0, singleIndent = INDENT, separator=',', newLine='\n', s=None):
	return formatVal(FuncArgs(*args, **kwargs), tab=tab, singleIndent=singleIndent, separator=separator, newLine=newLine, s=s)


def formatFuncCall(func, args=(), kwargs={}, isMemberFunc=True, tab=0, singleIndent = INDENT, separator=',', newLine='\n', s=None):
	return formatVal(FuncCall(func, FuncArgs(*args, **kwargs), isMemberFunc), tab=tab, singleIndent=singleIndent, separator=separator, newLine=newLine, s=s)


@Formatter(FuncArgs)
def _formatFuncArgs(v, tab, localFormatters, singleIndent, separator, newLine, s):
	skipkwArgs = not v.kwargs
	formatListLike2(iter(v.args), tab, localFormatters, singleIndent, separator, newLine, s, ('(', ''), skipLastSeparator=skipkwArgs)
	formatListLike2(iter(v.kwargs.items()), tab, localFormatters, singleIndent, separator, newLine, s, ('', ')'), formatListItem=formatKwArg)


@Formatter(FuncCall)
def _formatFuncCall(v, tab, localFormatters, singleIndent, separator, newLine, s):
	if v.object is not None:
		# formatType(v.object if isinstance(v.object, type) else type(v.object))
		objectName = v.object.__name__ if isinstance(v.object, type) else type(v.object).__name__
		s += objectName + '.'

	s += v.func.__name__
	_formatFuncArgs(v.funcArgs, tab, localFormatters, singleIndent, separator, newLine, s)


def formatPythonObject(
		v: Any, tab: int = 0, localFormatters: Optional[Mapping] = None,
		singleIndent: str = INDENT, separator: str = ',', newLine: str = '\n',
		s: Optional[WriterObjectABC] = None
):
	if localFormatters is None:
		localFormatters = _valueFormatters
	s = s or SW()
	_formatPythonObject(v, tab, localFormatters, singleIndent, separator, newLine, s)
	return s


def _formatPythonObject(v, tab, localFormatters, singleIndent, separator, newLine, s):
		formatType(type(v), tab, localFormatters, singleIndent, separator, newLine, s)

		iterable = (tpl for tpl in ((attr, getattr(v, attr)) for attr in dir(v) if not attr.startswith('__')) if not callable(tpl[1]))
		formatListLike2(iterable, tab, localFormatters, singleIndent, separator, newLine, s, '()', formatListItem=formatKwArg)


try:
	from ..Serializable.serializableDataclasses import shouldFormatVal
except ImportError:
	def shouldFormatVal(field: dataclasses.Field, val: Any) -> bool:
		return field.repr is True


__EMPTY_DICT = {}


@PredicatedFormatter(lambda cls: dataclasses.is_dataclass(cls))
def formatDataclasses(v, tab, localFormatters, singleIndent, separator, newLine, s):
	s += type(v).__name__

	allFields: tuple[dataclasses.Field, ...] = dataclasses.fields(v)
	evaluatedFields = [(field, getattr(v, field.name), field.metadata.get('cat', __EMPTY_DICT).get('customPrintFunc', None)) for field in allFields]
	iterable = ((field.name, func(v, val) if func is not None else val) for field, val, func in evaluatedFields if shouldFormatVal(field, val))

	formatListLike2(iterable, tab, localFormatters, singleIndent, separator, newLine, s, '()', formatListItem=formatKwArg)


@final
class Indentation:
	__slots__ = ('emitter',)

	def __init__(self, emitter: Emitter):
		self.emitter: Emitter = emitter

	def __enter__(self):
		self.emitter.tabs += 1

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.emitter.tabs -= 1
		return False


class StringBuilder:
	def __init__(self):
		self.fragments: list[str] = []
		self._len:int = 0

	def __iadd__(self, other: str):
		self.fragments.append(other)
		self._len += len(other)
		return self

	def __len__(self):
		return self._len

	def __str__(self):
		return ''.join(self.fragments)


@dataclasses.dataclass(eq=False)
class Emitter:
	singleIndent: str = '\t'
	tabs: int = 0
	output: StringBuilder = dataclasses.field(default_factory=StringBuilder)
	sol: int = 0

	def addNewLineAndIndent(self):
		self.sol = len(self.output)
		self.output += '\n' + (self.singleIndent * self.tabs)

	def writeLine(self, line: str):
		self.sol = len(self.output)
		self.addNewLineAndIndent()
		self.output += line

	def writeLines(self, lines: str):
		self.sol = len(self.output)
		indentedLines = indentMultilineStr(lines, indent=self.singleIndent*self.tabs, indentFirstLine=True).s
		self.output += '\n'
		self.output += indentedLines

	def getFinalSource(self) -> str:
		self.postProcess()
		if not (self.output.fragments and self.output.fragments[-1].endswith('\n')):
			self.output.fragments.append('\n')
		return str(self.output)

	def postProcess(self):
		"""
		overwrite this method to post process the generated code.
		"""
		pass

__all__ = [
	"WriterObjectABC",
	"FW",
	"PW",
	"PWDirect",
	"SW",
	"formatDictOnly",
	"indentMultilineStr",
	"formatVal",
	"formatFuncArgs",
	"formatFuncCall",
	"Formatter",
	"FuncArgs",
	"FuncCall",
	"_formatVal",
	"Indentation",
	"StringBuilder",
	"Emitter",
]
