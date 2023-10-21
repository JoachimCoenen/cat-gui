import os
import re
from dataclasses import dataclass
from functools import reduce, partial
from typing import Callable, AnyStr, Optional


def makeSearchPath(srcFolder: AnyStr, searchStr: AnyStr) -> tuple[AnyStr, AnyStr]:
	"""
	Creates a regex from a source directory path and a filter string.

	searchStr syntax:

	``?``
		any single char, except \\\\ or /
	``\\*``
		any multiple chars, except \\\\ or /  (name of a single folder or file)
	``\\*\\*``
		any multiple chars, including \\\\ or /  (files or folders within any subdirectories)

	examples:

	``'C:\\\\Users\\\\*'``
		all user folders on windows
	``'C:/Users/*/Downloads'``
		the download folder of all user folders on windows
	``'C:/Users/roo?/**'``
		all files of all users that have a four letter name starting with 'roo', 'Roo', 'ROO', etc...
	``'C:\\\\**\\\\desktop.ini'``
		all desktop.ini files on your ``C:`` drive
	``'/**/hello*there*/no?Way/'``
		something crazy...
	``'webapp/WEB-INF/model/**'``
		everything within ``webapp/WEB-INF/model/``

	:param srcFolder: The directory in which the changes should be detected.
	:param searchStr: A filter string. For syntax see docs.
	:return: a regex string.

	"""
	if isinstance(srcFolder, str):
		if not isinstance(searchStr, str):
			TypeError(f"a string-like object is required, not '{type(searchStr).__name__}'")
		return _innerMakeSearchPathStr(srcFolder, searchStr)
	elif isinstance(srcFolder, bytes):
		if not isinstance(searchStr, bytes):
			TypeError(f"a bytes-like object is required, not '{type(searchStr).__name__}'")
		return _innerMakeSearchPathBytes(srcFolder, searchStr)
	TypeError(f"a string-like or bytes-like object is required, not '{type(srcFolder).__name__}'")


_REPL_DICT_STR = {
	'/':   r'[/\\]',
	'/**': r'(?:[/\\](?!\.\.)[^/\\]+)*',  # any folder(s)
	'**':  r'(?:(?!\.\.)[^/\\]+)?(?:[/\\](?!\.\.)[^/\\]+)*',  # any folder(s)
	'*':   r'(?!\.\.)[^/\\]+',
	'?':   r'((?!\.+))?(?(-1)|(?<![/\\]))[^/\\]',
	'\\?': r'?',
	'.':   r'\.',
	':':   r':[/\\]?',
}


def _replFuncStr(matchObj: re.Match[str]) -> str:
	match = matchObj.group(0)
	result = _REPL_DICT_STR.get(match)
	if result is None:
		raise "Bad Match: '{}'".format(match)
	return result


_searchPathFinalizerStr: Callable[[str], str] = partial(re.compile(r'\\\?|/?\*\*|/|\*|\?|\.').sub, _replFuncStr)


def _innerMakeSearchPathStr(srcFolder: str, searchStr: str) -> tuple[str, str]:
	if searchStr:
		separator = '/' if searchStr[0] not in '/\\' and (not srcFolder or srcFolder[-1] not in '/\\') else ''
		fullFilterPath = srcFolder + separator + searchStr
	else:
		fullFilterPath = srcFolder

	fileStr = fullFilterPath.replace('\\', '/')  # re.sub(r'\\', '/', fullFilterPath)
	folderStr = reduce(lambda acc, v: v + '(\\?:/' + acc + ')\\?' if v and acc else acc or v, reversed(fileStr.split('/')), '')
	# folderStr = reduce(lambda acc, v: v + '(\\?:/' + acc + ')\\?' if v and acc else acc or v, reversed(re.split(r'[/]', fileStr)), '')

	# return re.sub(_REPL_PATTERN_STR, _replFuncStr, folderStr), re.sub(_REPL_PATTERN_STR, _replFuncStr, fileStr.strip('/\\'))
	return _searchPathFinalizerStr(folderStr), _searchPathFinalizerStr(fileStr.strip('/\\'))


_REPL_DICT_BYTES = {
	b'/':   rb'[/\\]',
	b'/**': rb'(?:[/\\](?!\.\.)[^/\\]+)*',  # any folder(s)
	b'**':  rb'(?:(?!\.\.)[^/\\]+)?(?:[/\\](?!\.\.)[^/\\]+)*',  # any folder(s)
	b'*':   rb'(?!\.\.)[^/\\]+',
	b'?':   rb'((?!\.+))?(?(-1)|(?<![/\\]))[^/\\]',
	b'\\?': rb'?',
	b'.':   rb'\.',
	b':':   rb':[/\\]?',
}


def _replFuncBytes(matchObj: re.Match[bytes]) -> bytes:
	match = matchObj.group(0)
	result = _REPL_DICT_BYTES.get(match)
	if result is None:
		raise "Bad Match: '{}'".format(match)
	return result


_searchPathFinalizerBytes: Callable[[bytes], bytes] = partial(re.compile(rb'\\\?|/?\*\*|/|\*|\?|\.').sub, _replFuncBytes)


def _innerMakeSearchPathBytes(srcFolder: bytes, searchStr: bytes) -> tuple[bytes, bytes]:
	if searchStr:
		separator = b'/' if searchStr[0] not in b'/\\' and (not srcFolder or srcFolder[-1] not in b'/\\') else b''
		fullFilterPath = srcFolder + separator + searchStr
	else:
		fullFilterPath = srcFolder

	fileStr = fullFilterPath.replace(b'\\', b'/')  # re.sub(rb'\\', b'/', fullFilterPath)
	folderStr = reduce(lambda acc, v: v + b'(\\?:/' + acc + b')\\?' if v and acc else acc or v, reversed(fileStr.split(b'/')), b'')
	# folderStr = reduce(lambda acc, v: v + b'(\\?:/' + acc + b')\\?' if v and acc else acc or v, reversed(re.split(rb'[/]', fileStr)), '')

	# return re.sub(_REPL_PATTERN_BYTES, _replFuncBytes, folderStr), re.sub(_REPL_PATTERN_BYTES, _replFuncBytes, fileStr.strip(b'/\\'))
	return _searchPathFinalizerBytes(folderStr), _searchPathFinalizerBytes(fileStr.strip(b'/\\'))


_BACKTRACK_PATTERN = re.compile(r"[/\\]\.\.")


@dataclass
class FindRecursiveResult:
	fileCount: int
	folderCount: int


@dataclass
class _FindRecursiveData:
	handleFile: Callable[[str], None]
	folderFilter: re.Pattern[str]
	finalFolderFilter: re.Pattern[str]
	filenamePattern: re.Pattern[str]
	result: FindRecursiveResult
	maxBacktrackCount: int


def processRecursively(srcFolder: str, folderFilter: str, handleFile: Callable[[str], None], *, filenameRegex: Optional[str] = None) -> FindRecursiveResult:
	""" 
		folderFilter syntax: 
			- ?   any single char, except \\ or /
			- *   any multiple chars, except \\ or /
			- **  any multiple chars, including \\ or /
	"""
	maxBacktrackCount = len(_BACKTRACK_PATTERN.findall(f'/{folderFilter}/'))
	srcFolder = os.path.abspath(srcFolder)
	folderFilter, finalFolderFilter = makeSearchPath(srcFolder, folderFilter)
	folderFilterPattern = re.compile(folderFilter)
	finalFolderFilterPattern = re.compile(finalFolderFilter)
	filenamePattern = re.compile(filenameRegex) if filenameRegex else None

	result = FindRecursiveResult(0, 0)
	_findRecursive(srcFolder, _FindRecursiveData(handleFile, folderFilterPattern, finalFolderFilterPattern, filenamePattern, result, maxBacktrackCount))
	return result


# def _findRecursive(srcFolder: str, handleFile: Callable[[str], None], folderFilter: re.Pattern, finalFolderFilter: re.Pattern, result: FindRecursiveResult, maxBacktrackCount=0, indentStr = ""):
def _findRecursive(srcFolder: str, data: _FindRecursiveData):
	for root, dirs, files in os.walk((os.path.normpath(srcFolder)), topdown=True):
		root = root.strip('\\/')
		if data.finalFolderFilter.fullmatch(root) is not None:
			filenamePattern = data.filenamePattern
			for name in files:
				if filenamePattern is None or filenamePattern.fullmatch(name) is not None:
					sourceFolder = f'{root}/{name}'
					data.handleFile(sourceFolder)
					data.result.fileCount += 1
		if data.folderFilter.fullmatch(srcFolder) is not None:
			if len(_BACKTRACK_PATTERN.findall(srcFolder)) < data.maxBacktrackCount:
				dirs.append('..')
			for dir_ in dirs:
				data.result.folderCount += 1
				newSrcFolder = f'{srcFolder}/{dir_}'
				_findRecursive(newSrcFolder, data)
		break


@dataclass
class _FindRecursiveData2:
	handleFile: Callable[[str, str], None]
	folderFilter: re.Pattern[str]
	finalFolderFilter: re.Pattern[str]
	result: FindRecursiveResult
	maxBacktrackCount: int


def processRecursively2(srcFolder: str, folderFilter: str, handleFile: Callable[[str, str], None]) -> FindRecursiveResult:
	"""
		folderFilter syntax:
			- ?   any single char, except \\ or /
			- *   any multiple chars, except \\ or /
			- **  any multiple chars, including \\ or /

	"""
	maxBacktrackCount = len(_BACKTRACK_PATTERN.findall(f'/{folderFilter}/'))
	srcFolder = os.path.abspath(srcFolder)
	folderFilter, finalFolderFilter = makeSearchPath(srcFolder, folderFilter)
	folderFilterCmpld = re.compile(folderFilter)
	finalFolderFilterCmpld = re.compile(finalFolderFilter)

	result = FindRecursiveResult(0, 0)
	_findRecursive2(srcFolder, _FindRecursiveData2(handleFile, folderFilterCmpld, finalFolderFilterCmpld, result, maxBacktrackCount))
	return result


# def _findRecursive2(srcFolder: str, handleFile: Callable[[str, str], None], folderFilter: re.Pattern, finalFolderFilter: re.Pattern, result: FindRecursiveResult, maxBacktrackCount=0, indentStr = ""):
def _findRecursive2(srcFolder: str, data: _FindRecursiveData2):
	for root, dirs, files in os.walk((os.path.normpath(srcFolder)), topdown=True):
		root = root.strip('\\/')
		if data.finalFolderFilter.fullmatch(root):
			for name in files:
				data.handleFile(root, name)
				data.result.fileCount += 1
		if data.folderFilter.fullmatch(srcFolder):
			if len(_BACKTRACK_PATTERN.findall(srcFolder)) < data.maxBacktrackCount:
				dirs.append('..')
			for dir_ in dirs:
				data.result.folderCount += 1
				newSrcFolder = f'{srcFolder}/{dir_}'
				_findRecursive2(newSrcFolder, data)
		break


__all__ = [
	'makeSearchPath',
	'FindRecursiveResult',
	'processRecursively',
	'processRecursively2',
]
