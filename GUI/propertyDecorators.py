from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar, Union, Sequence, Iterable

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase

from Cat.GUI.enums import FileExtensionFilter
from Cat.Serializable.utils import PropertyDecorator
from Cat.utils.utils import sanitizeFileName, INVALID_PATH_CHARS


_T = TypeVar('_T')


class FolderPath(PropertyDecorator):
	"""docstring for FolderPath"""
	def __init__(self):
		super().__init__()


class FilePath(PropertyDecorator):
	"""docstring for FolderPath"""
	def __init__(self, filters: Sequence[FileExtensionFilter] = ()):
		super().__init__()
		self.filters = filters


class ReadOnlyLabel(PropertyDecorator):
	"""docstring for ReadOnlyLabel"""
	def __init__(self):
		super().__init__()


class NoUI(PropertyDecorator):
	"""docstring for FolderPath"""
	def __init__(self):
		super().__init__()


class Range(PropertyDecorator):
	"""docstring for Range"""
	def __init__(self, min: Union[int, float], max: Union[int, float], step: Optional[Union[int, float]] = None):
		super().__init__()
		self.min: Union[int, float] = min
		self.max: Union[int, float] = max
		self.step: Optional[Union[int, float]] = step


class Date(PropertyDecorator):
	"""Displays a Date edit field. Expects a string with a pythonic date in the format 'yyyy-MM-dd'."""
	def __init__(self):
		super().__init__()


class FontFamily(PropertyDecorator):
	"""Displays a FontFamily combobox field. Expects a string."""
	def __init__(
			self,
			writingSystem: QFontDatabase.WritingSystem = QFontDatabase.Any,
			bitmapScalable: Optional[bool] = None,
			scalable: Optional[bool] = None,
			smoothlyScalable: Optional[bool] = None,
			fixedPitch: Optional[bool] = None,
			private: Optional[bool] = None,
	):
		super().__init__()
		self.writingSystem         : QFontDatabase.WritingSystem = writingSystem

		self.mustBeBitmapScalable  : Optional[bool] = bitmapScalable
		self.mustBeScalable        : Optional[bool] = scalable
		self.mustBeSmoothlyScalable: Optional[bool] = smoothlyScalable
		self.mustBeFixedPitch      : Optional[bool] = fixedPitch
		self.mustBePrivateFamily   : Optional[bool] = private
		self.isAnyFilterSet: bool = any(map(
			lambda x: x is not None,
			(bitmapScalable, scalable, smoothlyScalable, fixedPitch, private)
		))


class Inlined(PropertyDecorator):
	"""docstring for Inlined"""
	def __init__(self):
		super().__init__()


class Framed(PropertyDecorator):
	"""docstring for Framed"""
	def __init__(self, **kwargs):
		super().__init__()
		self.kwargs = kwargs


class ToggleLeft(PropertyDecorator):
	"""docstring for ToggleLeft"""
	def __init__(self):
		super().__init__()


class ToggleSwitch(PropertyDecorator):
	"""For bool values. Displays a Switch instead of a checkbox."""
	def __init__(self):
		super().__init__()


class ComboBox(PropertyDecorator):
	"""docstring for ComboBox"""
	def __init__(self, choices: Iterable[str] | property, editable: bool | property = False):
		super().__init__()
		self.choices = choices
		self.editable: bool = editable


class Title(PropertyDecorator):
	"""docstring for Title"""

	def __init__(self, title: str):
		super().__init__()
		self.title: str = title


class Description(PropertyDecorator):
	"""docstring for Description"""
	def __init__(self, description: str, *, isMarkdown: bool = False, **kwargs):
		super().__init__()
		if isMarkdown:
			kwargs.setdefault('textFormat', Qt.MarkdownText)

		self.description: str = description
		self.kwargs: dict[str, Any] = kwargs


class DescriptionAbove(PropertyDecorator):
	"""docstring for DescriptionAbove"""
	def __init__(self, description: str, *, isMarkdown: bool = False, **kwargs):
		super().__init__()
		if isMarkdown:
			kwargs.setdefault('textFormat', Qt.MarkdownText)

		self.description: str = description
		self.kwargs: dict[str, Any] = kwargs


@dataclass
class ValidatorResult:
	message: str
	style: str


class Validator(PropertyDecorator):
	"""
	a Validator, recieves a function, that accepts value and returns a tuple (str, style), where style in {'info', 'help', 'warning', 'error'}.
	If str is empty or none, no message is displayed (aka. everythong is OK).
	"""
	def __init__(self, validator: Callable[[Any], Optional[ValidatorResult]], **kwargs):
		super().__init__()
		self.validator: Callable[[Any], Optional[ValidatorResult]] = validator
		self.kwargs = kwargs


def folderPathValidator(path: str) -> Optional[ValidatorResult]:
	import os
	if not os.path.lexists(path):
		return ValidatorResult('Folder not found', 'error')

	if not os.path.isdir(path):
		return ValidatorResult('Not a directory', 'error')
	return None


def fileNameValidator(name: str) -> Optional[ValidatorResult]:
	if name and sanitizeFileName(name) != name:
		return ValidatorResult(f"Illegal characters: {INVALID_PATH_CHARS}", 'error')
	return None


class List(PropertyDecorator):
	"""docstring for List"""
	def __init__(self):
		super().__init__()


class Dict(PropertyDecorator):
	"""docstring for Dict"""
	def __init__(self):
		super().__init__()


__all__ = [
	'PropertyDecorator',
	'FolderPath',
	'FilePath',
	'ReadOnlyLabel',
	'NoUI',
	'Range',
	'Date',
	'FontFamily',
	'Inlined',
	'Framed',
	'ToggleLeft',
	'ToggleSwitch',
	'ComboBox',
	'Title',
	'Description',
	'DescriptionAbove',
	'ValidatorResult',
	'Validator',
	'List',
	'Dict',
]