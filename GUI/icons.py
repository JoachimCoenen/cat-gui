import os
import re
from math import copysign
from typing import Any, TypedDict, Union

import qtawesome as qta
from PyQt5.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QIconEngine, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

from Cat.GUI.components import catWidgetMixins
from Cat.utils import DocEnum, getExePath


class CompositionMode(DocEnum):
	Normal = 0, "normal Mode"
	Erase  = 1, "erases Mode"
	Xor    = 2, "xor Mode"
	Crop   = 3, "crops using the provided icon as a mask"


class Options(TypedDict):
	mode: CompositionMode
	offset: tuple[float, float]
	scale: Union[tuple[float, float], float]


class CompositeIconEngine(QIconEngine):
	"""Specialization of QIconEngine used to combine icons."""

	defaultOptions: Options = {
		'mode': CompositionMode.Normal,
		'offset': (0.0, 0.0),
		'scale': (1.0, 1.0),
	}
	compositionModeMap = {
		CompositionMode.Normal: QPainter.CompositionMode_SourceOver,
		CompositionMode.Erase: QPainter.CompositionMode_DestinationOut,
		CompositionMode.Xor: QPainter.CompositionMode_Xor,
		CompositionMode.Crop: QPainter.CompositionMode_SourceIn
	}

	def __init__(self, icons: list[Union[QIcon, tuple[QIcon, Options]]]):
		super().__init__()
		self.icons = icons

	def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State):
		for icon in self.icons:
			iconRect = QRect(rect)
			if isinstance(icon, tuple):
				options: Options = self.defaultOptions.copy()
				options.update(icon[1])
				icon = icon[0]
				# if not isinstance(scale, (tuple, list)):
				# 	scale = (scale, scale)
			else:
				options = self.defaultOptions

			compositionMode = self.compositionModeMap[options['mode']]
			offset: tuple[float, float] = options['offset']
			scale: Union[tuple[float, float], float] = options['scale']
			if not isinstance(scale, (tuple, list)):
				scale: tuple[float, float] = (scale, scale)

			painter.save()
			painter.setCompositionMode(compositionMode)
			painter.translate(
				((offset[0] + (1 - scale[0]) * 0.5) * iconRect.width()),
				((offset[1] + (1 - scale[1]) * 0.5) * iconRect.height())
			)
			# painter.scale(
			# 	scale[0],
			# 	scale[1]
			# )

			iconSize = QSize(int(rect.size().width() * scale[0]), int(rect.size().height() * scale[1]))
			iconAbsSize = QSize(abs(iconSize.width()), abs(iconSize.height()))
			iconRect = QRect(rect)
			iconRect.setSize(iconSize)
			pm: QPixmap = icon.pixmap(iconAbsSize, mode, state)
			painter.scale(copysign(1, iconSize.width()), copysign(1, iconSize.height()))
			painter.drawPixmap(iconRect, pm)
			# icon.paint(painter, iconRect, mode=mode, state=state)

			painter.restore()

	def pixmap(self, size, mode, state):
		pm = QPixmap(size)
		pm.fill(Qt.transparent)
		self.paint(QPainter(pm), QRect(QPoint(0, 0), size), mode, state)
		return pm


class SVGIconEngine(QIconEngine):
	def __init__(self, svgString: bytes, **options):
		super().__init__()
		self.data: bytes = svgString  # QByteArray.fromStdString(svgString);

		self.options = self._parse_options({}, options)

	def _parse_options(self, specific_options, general_options):
		_default_options = {
			'color'         : catWidgetMixins.standardBaseColors.Icon,  # QColor(50, 50, 50),
			'color_disabled': catWidgetMixins.standardBaseColors.DisabledIcon,  # QColor(150, 150, 150),
			'opacity'       : 1.0,
			'scale_factor'  : 1.0,
		}

		options = dict(_default_options, **general_options)
		options.update(specific_options)

		# Handle colors for modes (Active, Disabled, Selected, Normal)
		# and states (On, Off)
		color = options.get('color')
		options.setdefault('color_on', color)
		options.setdefault('color_active', options['color_on'])
		options.setdefault('color_selected', options['color_active'])
		options.setdefault('color_on_active', options['color_active'])
		options.setdefault('color_on_selected', options['color_selected'])
		options.setdefault('color_on_disabled', options['color_disabled'])
		options.setdefault('color_off', color)
		options.setdefault('color_off_active', options['color_active'])
		options.setdefault('color_off_selected', options['color_selected'])
		options.setdefault('color_off_disabled', options['color_disabled'])

		return options

	def paint(self, painter: QPainter, rect: QRect, mode, state):
		options = self.options
		color_options = {
			QIcon.On : {
				QIcon.Normal  : options['color_on'],
				QIcon.Disabled: options['color_on_disabled'],
				QIcon.Active  : options['color_on_active'],
				QIcon.Selected: options['color_on_selected'],
			},

			QIcon.Off: {
				QIcon.Normal  : options['color_off'],
				QIcon.Disabled: options['color_off_disabled'],
				QIcon.Active  : options['color_off_active'],
				QIcon.Selected: options['color_off_selected'],
			}
		}

		color = color_options[state][mode]
		colorName =  color.name() if isinstance(color, QColor) else color
		renderer = QSvgRenderer(re.sub(b'"currentColor"', b'"' + colorName.encode('utf-8') + b'"', self.data))

		r = QRectF(rect)

		scale = options.get('scale', 1.)
		offset = options.get('offset', (0., 0.))
		painter.save()
		scaling = (
			((1 - scale) * 0.5) * r.width(),
			((1 - scale) * 0.5) * r.height()
		)

		translation = (
			offset[0] * r.width(),  # + scaling[0],
			offset[1] * r.height(),  # + scaling[1]
		)
		painter.translate(
			*translation
		)
		#painter.scale(scale, scale)

		renderer.render(painter, r.adjusted(+scaling[0], +scaling[1], -scaling[0], -scaling[1]))
		painter.restore()

	def pixmap(self, size, mode, state):
		# This function is necessary to create an EMPTY pixmap. It's called always
		# before paint()

		pm = QPixmap(size)
		pm.fill(Qt.transparent)
		r = QRect(QPoint(0, 0), size)
		self.paint(QPainter(pm), r, mode, state)
		return pm


def _resolveLambdas(options: dict[str, Any]) -> dict[str, Any]:
	return {key: val() if callable(val) else val for key, val in options.items()}


def _withDefaultColors(option: dict[str, Any], sharedColors: dict[str, Any]) -> dict[str, Any]:
	option2 = {**sharedColors, **option}
	if 'color' not in option2:
		option2.setdefault('color', lambda: catWidgetMixins.standardBaseColors.Icon)
		option2.setdefault('color_on', lambda: catWidgetMixins.standardBaseColors.Highlight)
		option2.setdefault('color_selected', lambda: catWidgetMixins.standardBaseColors.HighlightedText)
		option2.setdefault('color_disabled', lambda: catWidgetMixins.standardBaseColors.DisabledIcon)
		option2.setdefault('color_active', lambda: catWidgetMixins.standardBaseColors.Text)
	return option2


def iconCombiner(*icons: Union[QIcon, tuple[QIcon, dict]]):
	@property
	def getter(self) -> QIcon:
		return QIcon(CompositeIconEngine([(icon[0].__get__(self, type(self)), icon[1]) if isinstance(icon, tuple) else icon.__get__(self, type(self)) for icon in icons]))
	return getter


def iconFromSVG(svgString: bytes, **options):
	sharedColors = {
		'color_selected': lambda: catWidgetMixins.standardBaseColors.HighlightedText,
		'color_disabled': lambda: catWidgetMixins.standardBaseColors.DisabledIcon
	}
	origOptions = _withDefaultColors(options, sharedColors)

	@property
	def getter(self) -> QIcon:
		options2 = _resolveLambdas(origOptions)
		return QIcon(SVGIconEngine(svgString, **options2))
	return getter


def iconFromFile(name: str, ext: str = '.svg', **options):
	_iconFolder = os.path.dirname(getExePath())
	filePath = os.path.join(_iconFolder, f'{name}{ext}')
	if ext.lower() == '.svg':
		with open(filePath, 'rb') as f:
			svgString = f.read()
		return iconFromSVG(svgString, **options)
	else:
		return QIcon(filePath)


def iconGetter(*names, **kwargs):
	"""
	'char': char,
	'on': on,
	'off': off,
	'active': active,
	'selected': selected,
	'disabled': disabled,
	'on_active': on_active,
	'on_selected': on_selected,
	'on_disabled': on_disabled,
	'off_active': off_active,
	'off_selected': off_selected,
	'off_disabled': off_disabled,
	color = options.get('color'),
	options.setdefault('color_on', color),
	options.setdefault('color_active', options['color_on']),
	options.setdefault('color_selected', options['color_active']),
	options.setdefault('color_on_active', options['color_active']),
	options.setdefault('color_on_selected', options['color_selected']),
	options.setdefault('color_on_disabled', options['color_disabled']),
	options.setdefault('color_off', color),
	options.setdefault('color_off_active', options['color_active']),
	options.setdefault('color_off_selected', options['color_selected']),
	options.setdefault('color_off_disabled', options['color_disabled']),

	:return:
	"""
	if (options := kwargs.pop('options', None)) is None:
		options = [{} for _ in names]
	kwargs.setdefault('color_selected', lambda: catWidgetMixins.standardBaseColors.HighlightedText)
	kwargs.setdefault('color_disabled', lambda: catWidgetMixins.standardBaseColors.DisabledIcon)
	sharedColors = {k: kwargs.pop(k) for k in kwargs.keys() & {'color', 'color_on', 'color_active', 'color_selected', 'color_disabled'}}
	origOptions = [_withDefaultColors(option, sharedColors) for option in options]

	@property
	def getter(self) -> QIcon:
		options2 = [_resolveLambdas(opt) for opt in origOptions]
		icon = qta.icon(*names, **kwargs, options=options2)
		return icon
	return getter


iconGetter.__doc__ = qta.icon.__doc__


SVG_CLOSE_ICON_THIN = \
	b'''<svg width="16" height="16" version="1.1" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
			<g fill="none" stroke="currentColor" stroke-width="1.1">
				<path d="m3.5  3.5 9 9"/>
				<path d="m12.5 3.5 -9 9"/>
			</g>
		</svg>'''


SVG_CLOSE_ICON_FAT = \
	b'''<svg width="16" height="16" version="1.1" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
			<g fill="none" stroke="currentColor" stroke-width="2.7">
				<path d="m3.5  3.5 9 9"/>
				<path d="m12.5 3.5 -9 9"/>
			</g>
		</svg>'''


class _Icons:
	__slots__ = ()
	# util:
	btnClose: QIcon = iconFromSVG(
		SVG_CLOSE_ICON_THIN,
		color_active=QColor('#ffffff')
	)

	btnMinimize: QIcon = iconFromSVG(
		b'''<svg width="16" height="16" version="1.1" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
			<g fill="none" stroke="currentColor" stroke-width="1.0">
				<path d="m3 8.5 h10"/>
			</g>
		</svg>'''
	)

	btnMaximize: QIcon = iconFromSVG(
		b'''<svg width="16" height="16" version="1.1" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
			<g fill="none" stroke="currentColor" stroke-width="1.0">
				<path d="m3.5 3.5 h9 v9 h-9z"/>
			</g>
		</svg>'''
	)

	btnRestore: QIcon = iconFromSVG(
		b'''<svg width="16" height="16" version="1.1" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
			<g fill="none" stroke="currentColor" stroke-width="1">
				<path d="m3.5 5.5 h7 v7 h-7z"/>
				<path d="m5.5 5.5 v-2.0 h7 v7 h-2"/>
			</g>
		</svg>'''
	)
	btnMaximizeRestore: QIcon = iconCombiner(btnMaximize, btnRestore)


	boxMax: QIcon = iconFromSVG(
		b'''<svg width="16" height="16" version="1.1" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
				<g fill="none" stroke="currentColor" stroke-width="1.0">
					<path d="m0.5 0.5 h15 v15 h-15z"/>
				</g>
			</svg>'''
	)

	close: QIcon = iconFromSVG(SVG_CLOSE_ICON_FAT)

	closeTab: QIcon = iconFromSVG(
		SVG_CLOSE_ICON_FAT,
		color=lambda: catWidgetMixins.standardBaseColors.Border,
		color_disabled=lambda: catWidgetMixins.standardBaseColors.DisabledIcon,
		color_on=lambda: catWidgetMixins.standardBaseColors.Icon,
		color_selected=lambda: catWidgetMixins.standardBaseColors.Icon,
	)


icons = _Icons()
