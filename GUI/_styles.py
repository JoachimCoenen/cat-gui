from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Callable, Dict, Mapping, Optional, Union, Type, overload

from PyQt5 import QtCore

from Cat.utils import Decorator
from Cat.utils.collections_ import FrozenDict

if not hasattr(QtCore, 'Signal'):
	QtCore.Signal = QtCore.pyqtSignal


def applyStyle(widget, style: Optional[Style]):
	Styles.applyStyle(widget, style)


@dataclass(frozen=True)
class Style:
	options: FrozenDict[str, Union[str, Style]]

	def __init__(self, options: Mapping[str, Union[str, Style]]):
		super().__init__()
		options = FrozenDict(options)
		object.__setattr__(self, 'options', options)

	def __add__(self, other: Style) -> Style:
		if not isinstance(other, Style):
			raise ValueError(f"cannot add Style and {type(other).__name__}.")

		if other is EMPTY_STYLE:
			return self
		elif self is EMPTY_STYLE:
			return other
		else:
			return type(self)(self.options + other.options)

	def __iadd__(self, other: Style) -> Style:
		return self.__add__(other)

	def __sub__(self, other: Style):
		if not isinstance(other, Style):
			raise ValueError(f"cannot add Style and {type(other).__name__}.")

		if other is EMPTY_STYLE:
			return self
		elif self is EMPTY_STYLE:
			return self
		else:
			return type(self)(self.options - other.options)

	def __isub__(self, other: Style):
		return self.__sub__(other)

	def __eq__(self, other):
		if self is other:
			return True
		elif not isinstance(other, Style):
			return False
		else:
			return self.options == other.options

	def __ne__(self, other):
		return not self.__eq__(other)

	def __str__(self) -> str:
		return ' '.join(f'{key} {{ {value} }};' if isinstance(value, Style) else f'{key}: {value};' for key, value in self.options.items())

	def __repr__(self):
		body = dict.__repr__(self.options)
		return f"{self.__class__.__name__}({body})"


EMPTY_STYLE = Style({})


@Decorator
class _StyleProperty:

	def __init__(self, func: Callable, name: Optional[str]=None):
		self.func: Callable[[Styles], None] = func
		self._name = name or self.func.__name__

	@overload
	def __get__(self, instance: Styles, owner: Type[Styles]) -> Style:
		...

	@overload
	def __get__(self, instance: None, owner: Type[Styles]) -> _StyleProperty:
		...

	def __get__(self, instance: Styles, owner: Type[Styles]) -> Union[Style, _StyleProperty]:
		if instance is None:
			return self

		instance._propsToReset[self._name] = self
		value = self.func(instance)
		return value


class Styles:
	def __init__(self):
		self._propsToReset: Dict[str, _StyleProperty] = {}

	def reset(self):
		for name, prop in self._propsToReset.items():
			self.__dict__[name] = prop

	def addStyle(self, generator: Callable[[Styles], Style], name: str):
		self.__dict__[name] = _StyleProperty(generator, name)
		self._propsToReset.pop(name, None)

	@staticmethod
	def applyStyle(widget, style):
		# styleSheet = style(widget)
		assert isinstance(style, Style) or style is None
		styleSheet = str(style)
		if widget.styleSheet() != styleSheet:
			widget.setStyleSheet(styleSheet)

	@_StyleProperty
	def none(self) -> Style:
		return EMPTY_STYLE

	@_StyleProperty
	def title(self) -> Style:
		return Style({
			'font-weight': 'bold',
			'padding-top': '8px',
		})

	@_StyleProperty
	def bold(self) -> Style:
		return Style({
			'font-weight': 'bold',
		})

	@_StyleProperty
	def label(self) -> Style:
		return Style({
			'padding-right': '1px',
			'padding-left': '0px'
			})

	@_StyleProperty
	def hint(self) -> Style:
		return Style({
			'font-style': 'italic',
			# fontSize = widget.fontInfo().pointSize()
			# fontSize = QtWidgets.QApplication.font(widget).pointSize()
			# return f'font-size: {max(8,fontSize - 1)}pt; font-style: italic;'
		}) + self.label

	@_StyleProperty
	def warning(self) -> Style:
		return self.hint + Style({
			'color': 'rgb(127, 127, 0)',
		})

	@_StyleProperty
	def error(self) -> Style:
		return self.hint + Style({
			'color': 'rgb(255, 0, 0)',
		})

	@_StyleProperty
	def toggleLeft(self) -> Style:
		return self.label + Style({
			'padding-right': '10px'
		})

	@_StyleProperty
	def layoutingBorder(self) -> Style:
		return Style({
			'outline-color': '#000000',
			'outline-style': 'solid',
			#'outline-offset': '0px',
			'border-color': '#000000',
			'border-style': 'solid',
			'border-width': '1px',
			# fontSize = widget.fontInfo().pointSize()
			# fontSize = QtWidgets.QApplication.font(widget).pointSize()
			# r
		})

	if platform.system() == 'Windows':
		@_StyleProperty
		def hostWidgetStyle(self) -> Style:
			return Style({
				'font-family': 'Segoe UI',
				'font-size': '10pt',
			})  # + self.layoutingBorder
	else:
		@_StyleProperty
		def hostWidgetStyle(self) -> Style:
			return Style({
				'font-size': '10pt',
			})

	if platform.system() == 'Windows':
		@_StyleProperty
		def fixedWidthChar(self) -> Style:
			return Style({
				'font-family': 'Consolas',
			})  # + Style({'font-size': '9pt'})
	else:
		@_StyleProperty
		def fixedWidthChar(self) -> Style:
			return Style({
				'font-family': 'Courier New',
			})  # + Style({'font-size': '9pt'})


__styles: Styles = Styles()


def getStyles() -> Styles:
	return __styles


def setStyles(styles: Styles) -> None:
	global __styles
	if styles != __styles:
		__styles = styles

