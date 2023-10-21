from __future__ import annotations

from abc import abstractmethod
import copy
import operator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, cast, NamedTuple, Optional, TYPE_CHECKING, Union

from PyQt5 import sip
from PyQt5.QtCore import pyqtSignal, QEvent, QMargins, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QCursor, QFocusEvent, QFont, QFontMetrics, qGray, QImage, QKeySequence, QLinearGradient, QMouseEvent, \
	QPaintDevice, QPainter, QPainterPath, QPaintEvent, QPen, QResizeEvent, QStaticText, QShortcutEvent, QPalette
from PyQt5.QtWidgets import QFrame, QLayout, QScrollBar, QSizePolicy, QWidget, QShortcut, QApplication

from Cat.GUI.utilities import CrashReportWrapped, safeEmit, connect
from Cat.utils import Decorator
from Cat.utils.profiling import MethodCallCounter

# global variables for debugging:
DO_DEBUG_PAINT_EVENT: bool = False

# cannot be changed at runtime:
NEVER_DO_DEBUG_PAINT_EVENT: bool = False


def centerOfRect(rect: QRect) -> QPoint:
	centerF = QRectF(rect).center()
	return QPoint(int(centerF.x()), int(centerF.y()))


QRect.__hash__ = lambda r: hash(("QRect", r.x(), r.y(), r.width(), r.height()))
QRectF.__hash__ = lambda r: hash(("QRect", r.x(), r.y(), r.width(), r.height()))
QColor.__copy__ = lambda c: QColor(c)


DEFAULT_PANEL_CORNER_RADIUS = 6.
DEFAULT_WINDOW_CORNER_RADIUS = 9.

Margins = tuple[int, int, int, int]

NO_MARGINS: Margins = (0, 0, 0, 0)

RoundedCorners = tuple[bool, bool, bool, bool]


class InnerCorners(NamedTuple):
	left: bool
	top: bool
	right: bool
	bottom: bool


def maskCorners(corners: RoundedCorners, mask: RoundedCorners) -> RoundedCorners:
	return cast(RoundedCorners, tuple(map(operator.and_, corners, mask)))


def joinCorners(corners1: RoundedCorners, corners2: RoundedCorners) -> RoundedCorners:
	return cast(RoundedCorners, tuple(map(operator.or_, corners1, corners2)))


def joinInnerCorners(corners1: InnerCorners, corners2: InnerCorners) -> InnerCorners:
	return InnerCorners(*map(operator.or_, corners1, corners2))


def selectInnerCorners(innerCorners: InnerCorners, mask: InnerCorners) -> RoundedCorners:
	ic = innerCorners
	m = mask
	return (
		(ic.left and m.top) or (ic.top and m.left),
		(ic.right and m.top) or (ic.top and m.right),
		(ic.left and m.bottom) or (ic.bottom and m.left),
		(ic.right and m.bottom) or (ic.bottom and m.right),
	)


class _CORNERS_CONSTS:
	def __init__(self):
		self.NONE:   RoundedCorners = (False, False, False, False)
		self.ALL:    RoundedCorners = (True,  True,  True,  True)
		self.LEFT:   RoundedCorners = (True,  False, True,  False)
		self.TOP:    RoundedCorners = (True,  True,  False, False)
		self.RIGHT:  RoundedCorners = (False, True,  False, True)
		self.BOTTOM: RoundedCorners = (False, False, True,  True)
		self.TOP_LEFT:     RoundedCorners = maskCorners(self.TOP, self.LEFT)
		self.TOP_RIGHT:    RoundedCorners = maskCorners(self.TOP, self.RIGHT)
		self.BOTTOM_LEFT:  RoundedCorners = maskCorners(self.BOTTOM, self.LEFT)
		self.BOTTOM_RIGHT: RoundedCorners = maskCorners(self.BOTTOM, self.RIGHT)


CORNERS: _CORNERS_CONSTS = _CORNERS_CONSTS()


class _INNER_CORNERS_CONSTS:
	def __init__(self):
		self.NONE:   InnerCorners = InnerCorners(False, False, False, False)
		self.ALL:    InnerCorners = InnerCorners(True,  True,  True,  True)
		self.LEFT:   InnerCorners = InnerCorners(True,  False, False,  False)
		self.TOP:    InnerCorners = InnerCorners(False,  True,  False, False)
		self.RIGHT:  InnerCorners = InnerCorners(False, False,  True, False)
		self.BOTTOM: InnerCorners = InnerCorners(False, False, False,  True)
		self.TOP_LEFT:     InnerCorners = InnerCorners(*joinCorners(self.TOP, self.LEFT))
		self.TOP_RIGHT:    InnerCorners = InnerCorners(*joinCorners(self.TOP, self.RIGHT))
		self.BOTTOM_LEFT:  InnerCorners = InnerCorners(*joinCorners(self.BOTTOM, self.LEFT))
		self.BOTTOM_RIGHT: InnerCorners = InnerCorners(*joinCorners(self.BOTTOM, self.RIGHT))
		self.BOTTOM_TOP: InnerCorners = InnerCorners(*joinCorners(self.BOTTOM, self.TOP))


INNER_CORNERS: _INNER_CORNERS_CONSTS = _INNER_CORNERS_CONSTS()

PreciseOverlap = tuple[int, int, int, int]
Overlap = Union[tuple[int, int], PreciseOverlap]

NO_OVERLAP: PreciseOverlap = (0, 0, 0, 0)

_DBG_OVERLAP_CNTR = 0
_DBG_OVERLAP_2_CNTR = 0
_DBG_OVERLAP_MASK_CNTR = 0
_DBG_OVERLAP_JOIN_CNTR = 0
_DBG_OVERLAP_ADJUST_CNTR = 0
_DBG_OVERLAP_SET_CNTR = 0


def _dbg_overlap_cntr_inc(o1: Overlap, which: str):
	global _DBG_OVERLAP_CNTR, _DBG_OVERLAP_2_CNTR, _DBG_OVERLAP_MASK_CNTR, _DBG_OVERLAP_JOIN_CNTR, _DBG_OVERLAP_ADJUST_CNTR, _DBG_OVERLAP_SET_CNTR
	_DBG_OVERLAP_CNTR += 1
	if len(o1) == 2:
		_DBG_OVERLAP_2_CNTR += 1
	match which:
		case 'mask':
			_DBG_OVERLAP_MASK_CNTR += 1
		case 'join':
			_DBG_OVERLAP_JOIN_CNTR += 1
		case 'adjust':
			_DBG_OVERLAP_ADJUST_CNTR += 1
		case 'set':
			_DBG_OVERLAP_SET_CNTR += 1
	if _DBG_OVERLAP_CNTR % 10 == 0:
		print(f"+---------------------------------+")
		print(f"| _DBG_OVERLAP_CNTR        | {_DBG_OVERLAP_CNTR: 5} |")
		print(f"| _DBG_OVERLAP_2_CNTR      | {_DBG_OVERLAP_2_CNTR: 5} |")
		print(f"| _DBG_OVERLAP_MASK_CNTR   | {_DBG_OVERLAP_MASK_CNTR: 5} |")
		print(f"| _DBG_OVERLAP_JOIN_CNTR   | {_DBG_OVERLAP_JOIN_CNTR: 5} |")
		print(f"| _DBG_OVERLAP_ADJUST_CNTR | {_DBG_OVERLAP_ADJUST_CNTR: 5} |")
		print(f"| _DBG_OVERLAP_SET_CNTR    | {_DBG_OVERLAP_SET_CNTR: 5} |")
		print(f"+---------------------------------+")


def toPreciseOverlap(o1: Overlap) -> PreciseOverlap:
	if len(o1) == 2:
		o1 = (
			max(0, o1[0]),
			max(0, o1[1]),
			max(0, -o1[0]),
			max(0, -o1[1])
		)
	return o1


def maskOverlap(o1: Overlap, o2: PreciseOverlap) -> PreciseOverlap:
	# _dbg_overlap_cntr_inc(o1, 'mask')
	o1 = toPreciseOverlap(o1)
	return min(o1[0], o2[0]), min(o1[1], o2[1]), min(o1[2], o2[2]), min(o1[3], o2[3])


def joinOverlap(o1: Overlap, o2: PreciseOverlap) -> PreciseOverlap:
	# _dbg_overlap_cntr_inc(o1, 'join')
	o1 = toPreciseOverlap(o1)
	return max(o1[0], o2[0]), max(o1[1], o2[1]), max(o1[2], o2[2]), max(o1[3], o2[3])


OverlapAdjustment = tuple[Optional[int], Optional[int], Optional[int], Optional[int]]


def adjustOverlap(o1: Overlap, adj: OverlapAdjustment) -> PreciseOverlap:
	# _dbg_overlap_cntr_inc(o1, 'adjust')
	o1 = toPreciseOverlap(o1)
	return (
		o1[0] if adj[0] is None else adj[0],
		o1[1] if adj[1] is None else adj[1],
		o1[2] if adj[2] is None else adj[2],
		o1[3] if adj[3] is None else adj[3],
	)


@Decorator
def PaintEventDebug(method: Callable[[QWidget, QPaintEvent], None]) -> Callable[[QWidget, QPaintEvent], None]:
	if NEVER_DO_DEBUG_PAINT_EVENT:
		return method
	hasFailed: bool = False

	def paintEvent(self: QWidget, event: QPaintEvent) -> None:
		nonlocal hasFailed
		method(self, event)
		if not DO_DEBUG_PAINT_EVENT:
			return
		if hasFailed:
			return
		try:
			with QPainter(self) as p:
				p.setRenderHint(QPainter.Antialiasing, True)
				hasHorMin = not bool(self.sizePolicy().horizontalPolicy() & (QSizePolicy.ShrinkFlag | QSizePolicy.IgnoreFlag))
				hasVertMin = not bool(self.sizePolicy().verticalPolicy() & (QSizePolicy.ShrinkFlag | QSizePolicy.IgnoreFlag))

				if not self.minimumSize().isNull():
					p.setBrush(Qt.NoBrush)
					p.setPen(QColor('blue'))
					minSize = self.minimumSize()
					p.drawRect(QRectF(0.5, 0.5, minSize.width() - 1.0, minSize.height() - 1.0))

				l = 0.5
				t = 0.5
				r = self.width() - 0.5
				b = self.height() - 0.5
				sizeHint = self.sizeHint()
				rMin = sizeHint.width() - 0.5
				bMin = sizeHint.height() - 0.5

				p.setBrush(Qt.NoBrush)
				p.setPen(QColor(79, 63, 255, 191))
				if hasHorMin:
					p.drawLine(QPointF(rMin, t), QPointF(rMin, b))
				if hasVertMin:
					p.drawLine(QPointF(l, bMin), QPointF(r, bMin))

				setPaintEventDebugLineColor(p, hasHorMin, isMin=False)
				p.drawLine(QPointF(l, t), QPointF(l, b))
				setPaintEventDebugLineColor(p, hasHorMin, isMin=r == rMin)
				p.drawLine(QPointF(r, t), QPointF(r, b))

				setPaintEventDebugLineColor(p, hasVertMin, isMin=False)
				p.drawLine(QPointF(l, t), QPointF(r, t))
				setPaintEventDebugLineColor(p, hasVertMin, isMin=b == bMin)
				p.drawLine(QPointF(l, b), QPointF(r, b))
		except ValueError as e:
			if str(e) != 'QPainter must be created with a device':
				raise
			else:
				hasFailed = True

	return paintEvent


def setPaintEventDebugLineColor(p: QPainter, hasMin: bool, isMin: bool) -> None:
	p.setBrush(Qt.NoBrush)
	blue = 255 if isMin else 0

	if hasMin:
		p.setPen(QColor(255, 0, blue, 127))
	else:
		p.setPen(QColor(0, 127, blue, 127))


class CatClickableMixin:
	doubleClicked = pyqtSignal(QMouseEvent)
	clicked = pyqtSignal(QMouseEvent)

	@CrashReportWrapped
	def mouseDoubleClickEvent(self: QWidget, event: QMouseEvent) -> None:
		safeEmit(self, self.doubleClicked, event)
		event.accept()
		super(CatClickableMixin, self).mouseDoubleClickEvent(event)

	@CrashReportWrapped
	def mouseReleaseEvent(self: QWidget, event: QMouseEvent) -> None:
		safeEmit(self, self.clicked, event)
		event.accept()
		super(CatClickableMixin, self).mouseReleaseEvent(event)


class CatFocusableMixin:
	focusReceived = pyqtSignal(Qt.FocusReason)
	focusLost = pyqtSignal(Qt.FocusReason)

	@CrashReportWrapped
	def focusInEvent(self: QWidget, event: QFocusEvent) -> None:
		super(CatFocusableMixin, self).focusInEvent(event)
		safeEmit(self, self.focusReceived, event.reason())

	@CrashReportWrapped
	def focusOutEvent(self: QWidget, event: QFocusEvent) -> None:
		super(CatFocusableMixin, self).focusOutEvent(event)
		safeEmit(self, self.focusLost, event.reason())


_NO_SHORTCUT_ID = 0


class ShortcutMixin:
	if TYPE_CHECKING:
		destroyed = pyqtSignal(Optional[QObject])

		def parent(self) -> Optional[QObject]: ...
		def event(self, event: QEvent) -> bool: ...
		def setFocus(self, reason: Qt.FocusReason) -> None: ...

	def __init__(self, *args, **kwargs):
		super(ShortcutMixin, self).__init__(*args, **kwargs)

		self.__currentShortcut: Optional[QShortcut] = None

		self._shortcut: Optional[QKeySequence] = None
		self._parentShortcut: Optional[QKeySequence] = None
		self._selfShortcut: Optional[QKeySequence] = None
		self._windowShortcut: Optional[QKeySequence] = None

	def _setShortcutInternal(self, key: QKeySequence, shortcutParent: QWidget, context: Qt.ShortcutContext) -> None:
		currentShortcut: Optional[QShortcut] = self.__currentShortcut
		if currentShortcut is None:
			currentShortcut = QShortcut(shortcutParent)
			currentShortcut.setKey(key)
			currentShortcut.setContext(context)
			connect(
				currentShortcut.activated,
				lambda: (self.shortcutEvent(QShortcutEvent(key, currentShortcut.id(), False)) if not sip.isdeleted(cast(QObject, self)) else None)
			)
			connect(
				currentShortcut.activatedAmbiguously,
				lambda: (self.shortcutEvent(QShortcutEvent(key, currentShortcut.id(), True)) if not sip.isdeleted(cast(QObject, self)) else None)
			)

			def itemDestroyed(x, currentShortcut=currentShortcut):
				currentShortcut.setEnabled(False)
				currentShortcut.setParent(cast(QObject, None))  # casting is order to avoid "Expected type 'QObject', got 'None' instead " error
				currentShortcut.deleteLater()

			connect(self.destroyed, itemDestroyed)
			self.__currentShortcut = currentShortcut
		else:
			currentShortcut.setKey(key)
			currentShortcut.setParent(shortcutParent)
			currentShortcut.setEnabled(True)

	def _resetShortcutInternal(self) -> None:
		currentShortcut: Optional[QShortcut] = self.__currentShortcut
		if currentShortcut is not None:
			currentShortcut.setEnabled(False)

	def _clearShortcutVars(self) -> None:
		self._shortcut = None
		self._parentShortcut = None
		self._selfShortcut = None
		self._windowShortcut = None

	def shortcutEvent(self, event: QShortcutEvent) -> None:
		if not self.event(event):
			self.setFocus(Qt.ShortcutFocusReason)

	def shortcut(self) -> Optional[QKeySequence]:
		return self._shortcut

	def setShortcut(self, key: Optional[QKeySequence]):
		self._clearShortcutVars()
		if key is None:
			self._resetShortcutInternal()
		else:
			shortcutParent = self.parent()
			context: Qt.ShortcutContext = Qt.WidgetWithChildrenShortcut
			self._setShortcutInternal(key, shortcutParent, context)
			self._shortcut = key

	def parentShortcut(self) -> Optional[QKeySequence]:
		return self._parentShortcut

	def setParentShortcut(self, key: Optional[QKeySequence]):
		self._clearShortcutVars()
		if key is None:
			self._resetShortcutInternal()
		else:
			shortcutParent = self.parent().parent()
			context: Qt.ShortcutContext = Qt.WidgetWithChildrenShortcut
			self._setShortcutInternal(key, shortcutParent, context)
			self._parentShortcut = key

	def selfShortcut(self) -> Optional[QKeySequence]:
		return self._selfShortcut

	def setSelfShortcut(self, key: Optional[QKeySequence]):
		self._clearShortcutVars()
		if key is None:
			self._resetShortcutInternal()
		else:
			shortcutParent = cast(QWidget, self)
			context: Qt.ShortcutContext = Qt.WidgetWithChildrenShortcut
			self._setShortcutInternal(key, shortcutParent, context)
			self._selfShortcut = key

	def windowShortcut(self) -> Optional[QKeySequence]:
		return self._windowShortcut

	def setWindowShortcut(self, key: Optional[QKeySequence]):
		self._clearShortcutVars()
		if key is None:
			self._resetShortcutInternal()
		else:
			shortcutParent = cast(QWidget, self)
			context: Qt.ShortcutContext = Qt.WindowShortcut
			self._setShortcutInternal(key, shortcutParent, context)
			self._windowShortcut = key


class UndoBlockableMixin:
	def __init__(self, *args, **kwargs):
		super(UndoBlockableMixin, self).__init__(*args, **kwargs)
		self._undoRedoEnabled: bool = True

	def undoRedoEnabled(self) -> bool:
		return self._undoRedoEnabled

	def setUndoRedoEnabled(self, undoRedoEnabled: bool) -> None:
		self._undoRedoEnabled = undoRedoEnabled

	@CrashReportWrapped
	def event(self, event: QEvent) -> bool:
		if event.type() == QEvent.ShortcutOverride:
			if not self._undoRedoEnabled and event in (QKeySequence.Undo, QKeySequence.Redo):
				event.ignore()
				return QWidget.event(self, event)
		return super(UndoBlockableMixin, self).event(event)


class CatSizePolicyMixin:
	if TYPE_CHECKING:
		def sizePolicy(self) -> QSizePolicy: ...
		def setSizePolicy(self, policy: QSizePolicy) -> None: ...

	def __init__(self, *args, **kwargs):
		super(CatSizePolicyMixin, self).__init__(*args, **kwargs)

	def hSizePolicy(self) -> QSizePolicy.Policy:
		return self.sizePolicy().horizontalPolicy()

	def setHSizePolicy(self, policy: QSizePolicy.Policy) -> None:
		sp = self.sizePolicy()
		if policy != sp.horizontalPolicy():
			sp.setHorizontalPolicy(policy)
			self.setSizePolicy(sp)

	def vSizePolicy(self) -> QSizePolicy.Policy:
		return self.sizePolicy().verticalPolicy()

	def setVSizePolicy(self, policy: QSizePolicy.Policy) -> None:
		sp = self.sizePolicy()
		if policy != sp.verticalPolicy():
			sp.setVerticalPolicy(policy)
			self.setSizePolicy(sp)


class CatScalableWidgetMixin:
	if TYPE_CHECKING:
		def updateGeometry(self) -> None: ...
		def parentWidget(self) -> Optional[QWidget]: ...
		def font(self) -> QFont: ...

	def __init__(self, *args, **kwargs):
		super(CatScalableWidgetMixin, self).__init__(*args, **kwargs)
		self._scale: float = 1.
		self._margins: Margins = self.defaultMargins

	@property
	def _baseIconHeight(self) -> int:
		return 16

	@property
	def _baseIconPadding(self) -> int:
		return 4

	@property
	def scaledWidgetSpacing(self) -> int:
		return int(6 * self._scale)

	smallDefaultMargins: Margins = (6, 6, 4, 4)
	defaultMargins: Margins = (12, 12, 4, 4)

	def margins(self) -> Margins:
		return self._margins

	def setMargins(self, margins: Margins) -> None:
		if self._margins != margins:
			self._margins = margins
			self.updateGeometry()

	@property
	def qMargins(self) -> QMargins:
		margins = self._margins
		return QMargins(
			int(round(margins[0] * self._scale)),
			int(round(margins[2] * self._scale)),
			int(round(margins[1] * self._scale)),
			int(round(margins[3] * self._scale)),
		)

	def getDefaultIconSize(self) -> QSize:
		iconHeight = int(self._baseIconHeight * self._scale)
		return QSize(iconHeight, iconHeight)

	def getDefaultIconPadding(self) -> int:
		return int(self._baseIconPadding * self._scale)

	def getIconTop(self, rect: QRect) -> int:
		contentRect = rect.marginsRemoved(self.qMargins)
		top = contentRect.y() + int(0.5 + (contentRect.height() - self.getDefaultIconSize().height()) / 2)
		return top

	def getDefaultTextHeight(self, font: QFont = None) -> int:
		font = font or (self.parentWidget() or self).font()
		return QFontMetrics(font).height()

	def getTextSize(self, text: Union[str, QStaticText], font: QFont = None) -> QSize:
		if isinstance(text, str):
			font = font or (self.parentWidget() or self).font()
			textSize = QFontMetrics(font).size(Qt.TextShowMnemonic, text)
		else:
			textSize = text.size().toSize()
		return textSize

	def getTextTop(self, rect: QRect, font: QFont = None) -> int:
		contentRect = rect.marginsRemoved(self.qMargins)
		top = centerOfRect(contentRect).y() - self.getDefaultTextHeight(font) // 2
		return top

	def getDefaultContentSize(self, allText: Union[str, QStaticText], iconsCount: float = 0, paddingsCount: int = 0, font: QFont = None) -> QSize:
		textsSize = self.getTextSize(allText, font)
		iconSize = self.getDefaultIconSize()
		paddingWidth = self.getDefaultIconPadding() * paddingsCount

		contentHeight = max(iconSize.height(), textsSize.height())
		contentWidth = textsSize.width() + int(iconSize.width() * iconsCount) + paddingWidth
		return QSize(contentWidth, contentHeight)

	def getDefaultMinimumSize(self, font: QFont = None) -> QSize:
		textHeight = self.getDefaultTextHeight(font)
		iconSize = self.getDefaultIconSize()

		contentHeight = max(iconSize.height(), textHeight)
		contentWidth = iconSize.width()
		mg = self.qMargins
		return QSize(contentWidth, contentHeight).grownBy(mg)

	def getDefaultSize(self, allText: Union[str, QStaticText], iconsCount: float = 0, paddingsCount: int = 0, font: QFont = None) -> QSize:
		contentSize = self.getDefaultContentSize(allText, iconsCount, paddingsCount, font)
		mg = self.qMargins
		return contentSize.grownBy(mg)

	def widthAvailableForText(self, size: QSize, iconsCount: int = 0, paddingsCount: int = 0) -> int:
		widthOfContents = self.getDefaultSize("", iconsCount, paddingsCount).width()
		return max(0, size.width() - widthOfContents)

	@staticmethod
	@CrashReportWrapped
	def updateGeometryCall(self):
		self.updateGeometry()

	@MethodCallCounter(enabled=False)
	def updateScaleFromFontMetrics(self, font: QFont = None) -> None:
		baseDPI = 96.0  # 72 | 96 | 120 | 150
		baseFontSize = 10.0
		baseScale = 1.0
		font = font or (self.parentWidget() or self).font()

		fontSizeFactor = font.pointSizeF() / baseFontSize
		dpiFactor = QFontMetrics(font).fontDpi() / baseDPI
		newScale = dpiFactor * fontSizeFactor * baseScale
		if self._scale != newScale:
			self._scale = newScale
			QTimer.singleShot(1, lambda: (CatScalableWidgetMixin.updateGeometryCall(self) if not (isinstance(self, QObject) and sip.isdeleted(self)) else None))


OverlapCharTpl = tuple[bool, bool, bool]


class OverlapCharacteristics(NamedTuple):
	# (can, req, has) aka. (can overlap, requires overlap, has border over full length
	left: OverlapCharTpl
	top: OverlapCharTpl
	right: OverlapCharTpl
	bottom: OverlapCharTpl


CAN_AND_REQ_OVERLAP = OverlapCharacteristics((True, True, True), (True, True, True), (True, True, True), (True, True, True))
CANT_BUT_REQ_OVERLAP = OverlapCharacteristics((False, True, True), (False, True, True), (False, True, True), (False, True, True))
CANT_AND_NO_OVERLAP = OverlapCharacteristics((False, False, False), (False, False, False), (False, False, False), (False, False, False))


class CatFramedWidgetMixin:
	if TYPE_CHECKING:
		def update(self) -> None: ...
		def layout(self) -> QLayout: ...

	def __init__(self, *args, **kwargs):
		super(CatFramedWidgetMixin, self).__init__(*args, **kwargs)
		self._cornerRadius: float = DEFAULT_PANEL_CORNER_RADIUS
		self._roundedCorners: RoundedCorners = CORNERS.ALL
		self._overlap: PreciseOverlap = NO_OVERLAP
		if not isinstance(self, CatScalableWidgetMixin):
			self._scale: float = 1.

	def setCornerRadius(self, cornerRadius: float) -> None:
		layout = self.layout()
		if layout is not self and isinstance(layout, CatFramedWidgetMixin):
			layout.setCornerRadius(cornerRadius)
		if self._cornerRadius != cornerRadius:
			self._cornerRadius = cornerRadius
			self.refresh()

	def cornerRadius(self) -> float:
		return self._cornerRadius

	def setRoundedCorners(self, roundedCorners: RoundedCorners) -> None:
		layout = self.layout()
		if layout is not self and isinstance(layout, CatFramedWidgetMixin):
			layout.setRoundedCorners(roundedCorners)
		if self._roundedCorners != roundedCorners:
			self._roundedCorners = roundedCorners
			self.refresh()

	def roundedCorners(self) -> RoundedCorners:
		return self._roundedCorners

	def setOverlap(self, overlap: Overlap) -> None:
		# _dbg_overlap_cntr_inc(overlap, 'set')
		overlap = toPreciseOverlap(overlap)

		layout = self.layout()
		if layout is not self and isinstance(layout, CatFramedWidgetMixin):
			layout.setOverlap(overlap)
		if self._overlap != overlap:
			self._overlap = overlap
			self.refresh()

	def overlap(self) -> PreciseOverlap:
		return self._overlap

	@property
	def overlapCharacteristics(self) -> OverlapCharacteristics:
		return self.getOverlapCharacteristicsForLayout(self.layout())

	def getOverlapCharacteristicsForLayout(self, layout: Optional[QLayout]) -> OverlapCharacteristics:
		if layout is not self and isinstance(layout, CatFramedWidgetMixin):
			c = layout.overlapCharacteristics
			characteristics = OverlapCharacteristics(
				(c[0][0], c[0][0] or c[0][1], True),
				(c[1][0], c[1][0] or c[1][1], True),
				(c[2][0], c[2][0] or c[2][1], True),
				(c[3][0], c[3][0] or c[3][1], True),
			)
			# characteristics = OverlapCharacteristics(
			# 	*((o[0], o[0] or o[1]) for o in c)
			# )
			# contentMargins: tuple[int, int, int, int] = self.getContentsMargins()
			# if contentMargins != NO_MARGINS:
			# 	characteristics = OverlapCharacteristics(
			# 		(True, True) if contentMargins[0] > 0 else characteristics[0],
			# 		(True, True) if contentMargins[1] > 0 else characteristics[1],
			# 		(True, True) if contentMargins[2] > 0 else characteristics[2],
			# 		(True, True) if contentMargins[3] > 0 else characteristics[3],
			# 	)
			return characteristics
		return CAN_AND_REQ_OVERLAP

	def refresh(self) -> None:
		self.update()

	def adjustSizeByOverlap(self, size: QSize) -> QSize:
		ol = self._overlap
		return size - QSize(ol[0] + ol[2], ol[1] + ol[3])

	def adjustRectByOverlap(self, rect: QRect) -> QRect:
		ol = self._overlap
		return rect.adjusted(
			-ol[0], -ol[1],
			ol[2], ol[3],
		)

	def revAdjustRectByOverlap(self, rect: QRect) -> QRect:
		ol = self._overlap
		return rect.adjusted(
			ol[0], ol[1],
			-ol[2], -ol[3],
		)

	def getBorderPath(self, rect: QRect, radiusDelta: float = 0., corners: RoundedCorners = None, penWidth: float = None) -> QPainterPath:
		radius = max(0., self._cornerRadius * self._scale + radiusDelta)
		corners = corners if corners is not None else self._roundedCorners
		return getBorderPath(rect, radius, corners, penWidth)


def getBorderPath(rect: QRect, radius: float, corners: RoundedCorners, penWidth: float = None) -> QPainterPath:
	adjust = penWidth / 2 if penWidth is not None else 0.5
	adjustedRect = QRectF(rect).adjusted(adjust, adjust, -adjust, -adjust)
	return _getBorderPath(adjustedRect, radius, corners)


@lru_cache(64)
def _getBorderPath(rect: QRectF, radius: float, corners: RoundedCorners) -> QPainterPath:

		path = QPainterPath()
		path.setFillRule(Qt.WindingFill)

		radius = min(radius, rect.width() / 2, rect.height() / 2)

		if radius == 0 or corners == CORNERS.NONE:
			path.addRect(rect)
			return path

		if corners == CORNERS.ALL:
			path.addRoundedRect(rect, radius, radius)
			return path

		l = rect.left()
		r = rect.right()
		t = rect.top()
		b = rect.bottom()

		dtl = radius * 2 if corners[0] else 0  # Top left corner not rounded
		dtr = radius * 2 if corners[1] else 0  # Top right corner not rounded
		dbl = radius * 2 if corners[2] else 0  # Bottom left corner not rounded
		dbr = radius * 2 if corners[3] else 0  # Bottom right corner not rounded

		path.moveTo(l, b - dbl/2)

		if dbl != 0:
			path.arcTo(l, b - dbl, dbl, dbl, 180., 90.)
		if dbr == 0:
			path.lineTo(r - dbr/2, b)
		else:
			path.arcTo(r - dbr, b - dbr, dbr, dbr, 270., 90.)
		if dtr == 0:
			path.lineTo(r, t + dtr/2)
		else:
			path.arcTo(r - dtr, t, dtr, dtr, 0., 90.)
		if dtl == 0:
			path.lineTo(l + dtl/2,  t)
		else:
			path.arcTo(l, t, dtl, dtl, 90., 90.)
		path.closeSubpath()  # path.lineTo(l, b - dbl/2)

		return path


CAT_FRAMED_SCROLL_AREA_USE_PIXMAP: bool = True


class CatFramedAreaMixin(CatFramedWidgetMixin, CatScalableWidgetMixin):
	if TYPE_CHECKING:
		def size(self) -> QSize: ...
		def rect(self) -> QRect: ...
		def pos(self) -> QPoint: ...
		def parentWidget(self) -> QWidget: ...
		def mapFromGlobal(self, a0: QPoint) -> QPoint: ...

	@abstractmethod
	def getBorderBrushes(self, rect: QRect) -> tuple[QBrush, QBrush, QBrush]:
		raise NotImplementedError()

	def __init__(self, *args, **kwargs):
		super(CatFramedAreaMixin, self).__init__()
		self._roundedCorners = CORNERS.NONE
		self._colorPalette = palettes.windowPanelColorPalette
		self._drawFocusFrame: bool = True

		if CAT_FRAMED_SCROLL_AREA_USE_PIXMAP:
			self._pixmap = QImage()
		self._pixmapNeedsRepaint: bool = True

	@CrashReportWrapped
	def resizeEvent(self, event: QResizeEvent) -> None:
		super(CatFramedAreaMixin, self).resizeEvent(event)
		if CAT_FRAMED_SCROLL_AREA_USE_PIXMAP:
			size = self.size()  # event.size()?
			if not any(self.roundedCorners()):
				size = QSize()
			if self._pixmap.size() != size:
				self._pixmap = QImage(size, QImage.Format_ARGB32_Premultiplied)
				self._pixmap.fill(QColor())
				self._pixmapNeedsRepaint = True

	@CrashReportWrapped
	def focusInEvent(self, event: QFocusEvent) -> None:
		super(CatFramedAreaMixin, self).focusInEvent(event)
		self._pixmapNeedsRepaint = True

	@CrashReportWrapped
	def focusOutEvent(self, event: QFocusEvent) -> None:
		super(CatFramedAreaMixin, self).focusOutEvent(event)
		self._pixmapNeedsRepaint = True

	def _repaintPixmap(self):
		if CAT_FRAMED_SCROLL_AREA_USE_PIXMAP and any(self.roundedCorners()):
			self.parentWidget().render(self._pixmap, -self.pos(), flags=QWidget.DrawWindowBackground)
			self._paintBorder(self._pixmap, fillCenter=True)

	def _paintBorder(self, paintDevice: QPaintDevice, fillCenter: bool = False):
		if CAT_FRAMED_SCROLL_AREA_USE_PIXMAP:
			rect = self.adjustRectByOverlap(self.rect())
			# get Colors:
			borderBrush1, borderBrush2, borderBrush3 = self.getBorderBrushes(rect)
			borderPen1 = QPen(borderBrush1, 1, cap=Qt.SquareCap, join=Qt.SvgMiterJoin)
			borderPen2 = QPen(borderBrush2, 1, cap=Qt.SquareCap, join=Qt.SvgMiterJoin)
			borderPen3 = QPen(borderBrush3, 2, cap=Qt.SquareCap, join=Qt.SvgMiterJoin)
			bkgBrush = QBrush()  # QBrush(bkgColor)

			if self._drawFocusFrame and self.hasFocus():
				borderRect = self.rect()
			else:
				borderRect = rect

			borderPath1 = self.getBorderPath(borderRect)
			borderPath2 = self.getBorderPath(borderRect.adjusted(1, 1, -1, -1), radiusDelta=-1)
			borderPath3 = self.getBorderPath(self.rect().adjusted(0, 0, -1, -1))

			try:
				with QPainter(paintDevice) as p:
					if fillCenter:
						p.setRenderHint(QPainter.Antialiasing, False)
						oldCM = p.compositionMode()
						p.setCompositionMode(QPainter.CompositionMode_DestinationOut)

						p.setPen(borderPen1)
						p.setBrush(QColor())
						p.drawPath(borderPath2)

						p.setCompositionMode(oldCM)

					p.setPen(borderPen3)
					p.setBrush(bkgBrush)
					p.drawPath(borderPath3)

					p.setRenderHint(QPainter.Antialiasing, True)
					p.setPen(borderPen1)
					p.setBrush(bkgBrush)
					p.drawPath(borderPath1)

					p.setPen(borderPen2)
					p.drawPath(borderPath2)
				self._pixmapNeedsRepaint = False
			except ValueError as e:
				if str(e) == 'QPainter must be created with a device':
					pass  # ignore!
				else:
					raise

	@MethodCallCounter(enabled=False)
	def paintFrame(self, event: QPaintEvent):
		self.updateScaleFromFontMetrics()
		if CAT_FRAMED_SCROLL_AREA_USE_PIXMAP:
			if self._pixmapNeedsRepaint:
				self._repaintPixmap()

			if any(self.roundedCorners()):
				with QPainter(self) as p:
					p.drawImage(QPoint(0, 0), self._pixmap)
			else:
				self._paintBorder(self, fillCenter=False)


class WidgetEventEater(QObject):
	def __init__(self, parent: CatFramedAbstractScrollAreaMixin):
		super(WidgetEventEater, self).__init__(cast(QWidget, parent))
		self._isAlreadyFilteringPaint: bool = False

	@CrashReportWrapped
	def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
		if event.type() == QPaintEvent.Paint and not self._isAlreadyFilteringPaint:
			self._isAlreadyFilteringPaint = True
			obj.event(event)
			self.parent().paintFrameOnWidget(event, obj)
			self._isAlreadyFilteringPaint = False
			return True
		return False


class CatFramedAbstractScrollAreaMixin(CatFramedAreaMixin):
	if TYPE_CHECKING:
		def setFrameStyle(self, style: int) -> None: ...
		def setLineWidth(self, width: int) -> None: ...
		def horizontalScrollBar(self) -> QScrollBar: ...
		def verticalScrollBar(self) -> QScrollBar: ...
		def viewport(self) -> QWidget: ...

	def __init__(self, *args, **kwargs):
		super(CatFramedAbstractScrollAreaMixin, self).__init__()

		self.setFrameStyle(QFrame.Box | QFrame.Plain)
		self.setLineWidth(2)

		self._widgetEventEater = WidgetEventEater(self)
		self.horizontalScrollBar().installEventFilter(self._widgetEventEater)
		self.verticalScrollBar().installEventFilter(self._widgetEventEater)

	@property
	def overlapCharacteristics(self) -> OverlapCharacteristics:
		return CANT_BUT_REQ_OVERLAP

	@CrashReportWrapped
	def event(self, event: QEvent) -> bool:
		if event.type() in (event.FocusIn, event.FocusOut):
			self.viewport().update()
		result = super(CatFramedAbstractScrollAreaMixin, self).event(event)
		if event.type() == QEvent.Paint:
			self.paintFrame(event)
		return result

	@CrashReportWrapped
	def setWidget(self, w: Optional[QWidget]) -> None:
		superObj = super(CatFramedAbstractScrollAreaMixin, self)
		if not hasattr(superObj, 'setWidget'):
			raise AttributeError(f"'{type(self).__name__}' object has no attribute 'setWidget'")

		oldW: Optional[QWidget] = self.widget()
		if oldW is not None:
			oldW.removeEventFilter(self._widgetEventEater)
		if w is not None:
			w.installEventFilter(self._widgetEventEater)
		superObj.setWidget(w)

	@MethodCallCounter(enabled=False)
	def paintFrameOnWidget(self, event: QPaintEvent, widget: QWidget):
		if CAT_FRAMED_SCROLL_AREA_USE_PIXMAP:
			if self._pixmapNeedsRepaint:
				self._repaintPixmap()
			tl = widget.mapToGlobal(QPoint(0, 0))
			tl = self.mapFromGlobal(tl)
			with QPainter(widget) as p:
				p.drawImage(-tl, self._pixmap)


def matchValue(c1: QColor, *, matchTo: QColor) -> QColor:
	br2 = qGray(matchTo.rgb())
	br1 = qGray(c1.rgb())
	val3 = c1.valueF() * br2 / br1 if br1 != 0 else matchTo.valueF()
	val3 = min(1., val3)
	c3 = QColor.fromHsvF(c1.hsvHueF(), c1.hsvSaturationF(), val3, matchTo.alphaF())
	return c3


def changeHue(c1: QColor, hue: int) -> QColor:
	c2 = QColor.fromHsvF(hue/360, c1.hsvSaturationF(), c1.valueF(), c1.alphaF())
	return matchValue(c2, matchTo=c1)


_CLEAR_COLOR = QColor(0, 0, 0, 0)


@dataclass
class BaseColors:
	Icon: QColor
	DisabledIcon: QColor

	Border: QColor
	DisabledBorder: QColor

	Window: QColor
	Panel: QColor
	Input: QColor  # formerly "Base"
	AltInput: QColor  # formerly "AlternateBase"
	Button: QColor

	Highlight: QColor
	InactiveHighlight: QColor
	DisabledHighlight: QColor

	LightHighlight: QColor

	Text: QColor
	HighlightedText: QColor
	ButtonText: QColor

	ToolTip: QColor
	ToolTipText: QColor

	Link: QColor
	LinkVisited: QColor


DEFAULT_COLORS = BaseColors(
	Icon=QColor('#606060'),
	DisabledIcon=QColor('#b4b4b4'),

	Border=QColor('#b9b9b9'),
	DisabledBorder=QColor('#cacaca'),

	Window=QColor('#f0f0f0'),
	Panel=QColor('#ffffff'),  # = BaseColor
	Input=QColor('#ffffff'),
	AltInput=QColor('#e9e7e3'),
	Button=QColor('#ffffff'),

	Highlight=QColor('#0072ff'),
	InactiveHighlight=QColor('#959595'),
	DisabledHighlight=QColor('#a0a0a0'),
	LightHighlight=QColor('#519fff'),

	Text=QColor('#000000'),
	HighlightedText=QColor('#ffffff'),
	ButtonText=QColor('#202020'),

	ToolTip=QColor('#ffffdc'),
	ToolTipText=QColor('#000000'),

	Link=QColor('#0000ff'),
	LinkVisited=QColor('#ff00ff'),
)


standardBaseColors = copy.copy(DEFAULT_COLORS)


def setGUIColors(newColors: BaseColors) -> None:
	if newColors is None:
		newColors = copy.copy(DEFAULT_COLORS)
	app = cast(QApplication, QApplication.instance())
	palette = app.palette()
	updatePalette(palette, newColors)
	app.setPalette(palette)
	global standardBaseColors
	standardBaseColors = newColors


def updatePalette(palette: QPalette, newColors: BaseColors):
	setColor(palette, palette.Window,          newColors.Window)
	setColor(palette, palette.WindowText,      newColors.Text)
	setColor(palette, palette.Base,            newColors.Input, disabled=newColors.Window)
	setColor(palette, palette.AlternateBase,   newColors.AltInput)
	setColor(palette, palette.ToolTipBase,     newColors.ToolTip)
	setColor(palette, palette.ToolTipText,     newColors.ToolTipText)
	placeholderText = QColor(newColors.Text)
	placeholderText.setAlpha(128)
	setColor(palette, palette.PlaceholderText, placeholderText)
	setColor(palette, palette.Text,            newColors.Text, disabled=newColors.DisabledIcon)
	setColor(palette, palette.Button,          newColors.Button, disabled=newColors.Window)
	setColor(palette, palette.ButtonText,      newColors.ButtonText, disabled=newColors.DisabledIcon)
	setColor(palette, palette.BrightText,      newColors.HighlightedText)  # ?
	# ----------------------------------------------------------------------------------------------
	setColor(palette, palette.Light,           newColors.Window)  # ?
	setColor(palette, palette.Midlight,        newColors.Border, disabled=newColors.DisabledBorder)
	setColor(palette, palette.Dark,            newColors.Border, disabled=newColors.DisabledBorder)
	setColor(palette, palette.Mid,             newColors.Border, disabled=newColors.DisabledBorder)
	setColor(palette, palette.Shadow,          newColors.Border, disabled=newColors.DisabledBorder)
	# ----------------------------------------------------------------------------------------------
	setColor(palette, palette.Highlight,       newColors.Highlight, disabled=newColors.DisabledHighlight, inactive=newColors.InactiveHighlight)
	setColor(palette, palette.HighlightedText, newColors.HighlightedText)
	# ----------------------------------------------------------------------------------------------
	setColor(palette, palette.Link,            newColors.Link)
	setColor(palette, palette.LinkVisited,     newColors.LinkVisited)


def setColor(palette: QPalette, role: QPalette.ColorRole, color: QColor, disabled: QColor = None, inactive: QColor = None) -> None:
	palette.setColor(palette.Active, role, color)
	palette.setColor(palette.Disabled, role, disabled or color)
	palette.setColor(palette.Inactive, role, inactive or color)


def borderColor2FromBorderColor(c1: QColor) -> QColor:
	c2 = QColor(c1.red(), c1.green(), c1.blue(), 52)
	return c2


@dataclass()  # slots=True)
class ColorSet:
	getNormal: Callable[[], QColor]
	getDisabled: Callable[[], QColor] = ...
	getInactive: Callable[[], QColor] = ...
	getSelected: Callable[[], QColor] = ...
	getOn: Optional[Callable[[], QColor]] = ...

	def __post_init__(self):
		self.getDisabled = self.getNormal if self.getDisabled is ... else self.getDisabled
		self.getInactive = self.getNormal if self.getInactive is ... else self.getInactive
		self.getSelected = self.getNormal if self.getSelected is ... else self.getSelected
		self.getOn = None if self.getOn is ... else self.getOn


CLEAR_COLOR_COLOR_SET = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
)


@dataclass()  # slots=True)
class ColorPalette:
	name: str = field()
	backgroundColor: ColorSet = field()
	borderColor: ColorSet = field()
	textColor: ColorSet = field()
	iconColor: ColorSet = field()
	backgroundColor2: ColorSet = field(default=...)
	borderColor2: ColorSet = field(default_factory=lambda: CLEAR_COLOR_COLOR_SET)
	indicatorColor: ColorSet = field(default_factory=lambda: CLEAR_COLOR_COLOR_SET)
	indicatorColor2: ColorSet = field(default=...)
	indicatorBorderColor: ColorSet = field(default_factory=lambda: CLEAR_COLOR_COLOR_SET)
	indicatorBorderColor2: ColorSet = field(default_factory=lambda: CLEAR_COLOR_COLOR_SET)

	def __post_init__(self):
		if self.backgroundColor2 is ...:
			self.backgroundColor2 = self.backgroundColor
		if self.indicatorColor2 is ...:
			self.indicatorColor2 = self.indicatorColor


_windowColor = ColorSet(
	getNormal=lambda: standardBaseColors.Window,
	getDisabled=lambda: standardBaseColors.Window,
)

_panelColor = ColorSet(
	getNormal=lambda: standardBaseColors.Panel,
	getDisabled=lambda: standardBaseColors.Window,
)

_iconColor = ColorSet(
	getNormal=lambda: standardBaseColors.Icon,
	getDisabled=lambda: standardBaseColors.DisabledIcon,
)

# Input

_inputColor = ColorSet(
	getNormal=lambda: standardBaseColors.Input,
	getDisabled=lambda: standardBaseColors.Window,
)

_inputTextColor = ColorSet(
	getNormal=lambda: standardBaseColors.Text,
	getDisabled=lambda: standardBaseColors.DisabledIcon,
)

_inputBorderColor = ColorSet(
	getNormal=lambda: standardBaseColors.Border,
	getDisabled=lambda: standardBaseColors.DisabledBorder,
	getSelected=lambda: standardBaseColors.LightHighlight,
)

_inputBorderColor2 = ColorSet(
	getNormal=_inputColor.getNormal,
	getDisabled=_inputColor.getDisabled,
	getInactive=_inputColor.getInactive,
	getSelected=lambda: borderColor2FromBorderColor(standardBaseColors.LightHighlight),
)

_inputBorderColor2b = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
	getSelected=lambda: borderColor2FromBorderColor(standardBaseColors.LightHighlight),
)

# Button

_buttonColor1 = ColorSet(
	getNormal=lambda: standardBaseColors.Button,
	getDisabled=lambda: standardBaseColors.Window,
)

_buttonColor2 = ColorSet(
	getNormal=lambda: standardBaseColors.Window,
)

_buttonTextColor = ColorSet(
	getNormal=lambda: standardBaseColors.ButtonText,
	getDisabled=lambda: standardBaseColors.DisabledIcon,
	getOn=lambda: standardBaseColors.Highlight,
)

_buttonBorderColor = ColorSet(
	getNormal=lambda: standardBaseColors.Border,
	getDisabled=lambda: standardBaseColors.DisabledBorder,
	getSelected=lambda: standardBaseColors.LightHighlight,
)

_buttonBorderColor2 = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
	getSelected=lambda: borderColor2FromBorderColor(standardBaseColors.LightHighlight),
)

# Frameless Button

_framelessButtonColor = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
)

_framelessButtonBorderColor = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
	getSelected=lambda: standardBaseColors.LightHighlight,
)

# Default Button

_buttonDefaultColor1 = ColorSet(
	getNormal=lambda: standardBaseColors.Highlight,
	getDisabled=lambda: standardBaseColors.Window,
	getInactive=lambda: standardBaseColors.InactiveHighlight,
	getSelected=lambda: standardBaseColors.Highlight,
)

_buttonDefaultColor2 = ColorSet(
	getNormal=lambda: standardBaseColors.Highlight,
	getDisabled=lambda: standardBaseColors.Window,
	getInactive=lambda: standardBaseColors.InactiveHighlight,
	getSelected=lambda: standardBaseColors.Highlight,
)

_buttonDefaultTextColor = ColorSet(
	getNormal=lambda: standardBaseColors.HighlightedText,
	getDisabled=lambda: standardBaseColors.DisabledIcon,
	getInactive=lambda: standardBaseColors.HighlightedText,
	getSelected=lambda: standardBaseColors.HighlightedText,
)

_buttonDefaultIconColor = ColorSet(
	getNormal=lambda: standardBaseColors.HighlightedText,
	getDisabled=lambda: standardBaseColors.DisabledIcon,
	getInactive=lambda: standardBaseColors.HighlightedText,
	getSelected=lambda: standardBaseColors.HighlightedText,
)

_buttonDefaultBorderColor = ColorSet(
	getNormal=lambda: standardBaseColors.Highlight,
	getDisabled=lambda: standardBaseColors.DisabledBorder,
	getInactive=_buttonDefaultColor1.getInactive,
	getSelected=lambda: standardBaseColors.LightHighlight,
)

_buttonDefaultBorderColor2 = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
)

# Switch

_switchOffColor = ColorSet(
	getNormal=lambda: standardBaseColors.DisabledHighlight,
)

_switchOnColor = ColorSet(
	getNormal=lambda: standardBaseColors.Highlight,
	getDisabled=lambda: standardBaseColors.DisabledHighlight,
)

_switchTextColor = ColorSet(
	getNormal=lambda: standardBaseColors.ButtonText,
	getDisabled=lambda: standardBaseColors.DisabledIcon,
)

_switchBorderColor = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
	getSelected=lambda: standardBaseColors.LightHighlight,
)

_switchBorderColor2 = ColorSet(
	getNormal=lambda: _CLEAR_COLOR,
	getSelected=lambda: borderColor2FromBorderColor(standardBaseColors.LightHighlight),
)

# TabBar

_tabBarIndicatorColor = ColorSet(
	getNormal=lambda: standardBaseColors.Highlight,
	getDisabled=lambda: standardBaseColors.DisabledBorder,
	getInactive=_buttonDefaultColor1.getInactive,
)


class palettes:  # just a namespace
	inputColorPalette = ColorPalette(
		name='inputColorPalette',
		backgroundColor=_inputColor,
		backgroundColor2=_inputColor,
		borderColor=_inputBorderColor,
		borderColor2=_inputBorderColor2,
		textColor=_inputTextColor,
		iconColor=_iconColor,
	)

	inputColorPaletteB = ColorPalette(
		name='inputColorPaletteB',
		backgroundColor=_inputColor,
		backgroundColor2=_inputColor,
		borderColor=_inputBorderColor,
		borderColor2=_inputBorderColor2b,
		textColor=_inputTextColor,
		iconColor=_iconColor,
	)

	panelColorPalette = ColorPalette(
		name='panelColorPalette',
		backgroundColor=_panelColor,
		backgroundColor2=_panelColor,
		borderColor=_inputBorderColor,
		borderColor2=_inputBorderColor2,
		textColor=_inputTextColor,
		iconColor=_iconColor,
	)

	windowPanelColorPalette = ColorPalette(
		name='windowPanelColorPalette',
		backgroundColor=_windowColor,
		backgroundColor2=_windowColor,
		borderColor=_inputBorderColor,
		borderColor2=_inputBorderColor2,
		textColor=_inputTextColor,
		iconColor=_iconColor,
	)

	buttonColorPalette = ColorPalette(
		name='buttonColorPalette',
		backgroundColor=_buttonColor1,
		backgroundColor2=_buttonColor1,
		borderColor=_buttonBorderColor,
		borderColor2=_buttonBorderColor2,
		textColor=_buttonTextColor,
		iconColor=_iconColor,
	)

	gradiantButtonColorPalette = ColorPalette(
		name='gradiantButtonColorPalette',
		backgroundColor=_buttonColor1,
		backgroundColor2=_buttonColor2,
		borderColor=_buttonBorderColor,
		borderColor2=_buttonBorderColor2,
		textColor=_buttonTextColor,
		iconColor=_iconColor,
	)

	framelessButtonColorPalette = ColorPalette(
		name='framelessButtonColorPalette',
		backgroundColor=_framelessButtonColor,
		backgroundColor2=_framelessButtonColor,
		borderColor=_framelessButtonBorderColor,
		borderColor2=_buttonBorderColor2,
		textColor=_buttonTextColor,
		iconColor=_iconColor,
	)

	defaultButtonColorPalette = ColorPalette(
		name='defaultButtonColorPalette',
		backgroundColor=_buttonDefaultColor1,
		backgroundColor2=_buttonDefaultColor2,
		borderColor=_buttonDefaultBorderColor,
		borderColor2=_buttonDefaultBorderColor2,
		textColor=_buttonDefaultTextColor,
		iconColor=_buttonDefaultIconColor,
	)

	switchOffColorPalette = ColorPalette(
		name='switchOffColorPalette',
		backgroundColor=_switchOffColor,
		borderColor=_switchBorderColor,
		borderColor2=_switchBorderColor2,
		textColor=_switchTextColor,
		iconColor=_iconColor,
		indicatorColor=_buttonColor1,
	)

	switchOnColorPalette = ColorPalette(
		name='switchOnColorPalette',
		backgroundColor=_switchOnColor,
		borderColor=_switchBorderColor,
		borderColor2=_switchBorderColor2,
		textColor=_switchTextColor,
		iconColor=_iconColor,
		indicatorColor=_buttonColor1,
	)

	progressBarColorPalette = ColorPalette(
		name='progressBarColorPalette',
		backgroundColor=_inputColor,
		backgroundColor2=_inputColor,
		borderColor=_inputBorderColor,
		borderColor2=_inputBorderColor2,
		textColor=_buttonTextColor,
		iconColor=_iconColor,
		indicatorColor=_buttonDefaultColor1,
		indicatorColor2=_buttonDefaultColor2,
		indicatorBorderColor=_buttonDefaultBorderColor,
	)

	tabBarColorPalette = ColorPalette(
		name='tabBarColorPalette',
		backgroundColor=_windowColor,
		backgroundColor2=_windowColor,
		borderColor=_inputBorderColor,
		borderColor2=_inputBorderColor2,
		textColor=_buttonTextColor,
		iconColor=_iconColor,
		indicatorColor=_buttonDefaultColor1,
		indicatorColor2=_buttonDefaultColor2,
		indicatorBorderColor=_tabBarIndicatorColor,
	)

	windowTabBarColorPalette = ColorPalette(
		name='windowTabBarColorPalette',
		backgroundColor=panelColorPalette.backgroundColor,
		backgroundColor2=panelColorPalette.backgroundColor2,
		borderColor=panelColorPalette.borderColor,
		borderColor2=panelColorPalette.borderColor2,
		textColor=_buttonTextColor,
		iconColor=_iconColor,
		indicatorColor=_buttonDefaultColor1,
		indicatorColor2=_buttonDefaultColor2,
		indicatorBorderColor=_tabBarIndicatorColor,
	)


class CatStyledWidgetMixin:
	if TYPE_CHECKING:
		def isEnabled(self) -> bool: ...
		def isActiveWindow(self) -> bool: ...
		def hasFocus(self) -> bool: ...
		def rect(self) -> QRect: ...
		def mapFromGlobal(self, a0: QPoint) -> QPoint: ...
		def update(self) -> None: ...

	def isHighlighted(self) -> bool:
		if self._neverInactive or self.isActiveWindow():
			return (self._highlightOnFocus and self.hasFocus()) or (self._highlightOnHover and self.rect().contains(self.mapFromGlobal(QCursor.pos()), False))
		else:
			return False

	def __init__(self, *args, **kwargs):
		super(CatStyledWidgetMixin, self).__init__(*args, **kwargs)
		self._neverInactive: bool = False
		self._highlightOnHover: bool = False
		self._highlightOnFocus: bool = False
		self._colorPalette: ColorPalette = palettes.panelColorPalette

	def _fromCS(self, colorSet: ColorSet, isOn: bool = False) -> QColor:
		if not self.isEnabled():
			return colorSet.getDisabled()
		elif isOn and colorSet.getOn is not None:
			return colorSet.getOn()
		elif not (self._neverInactive or self.isActiveWindow()):
			return colorSet.getInactive()
		elif self.isHighlighted():
			return colorSet.getSelected()
		else:
			return colorSet.getNormal()

	def colorPalette(self) -> ColorPalette:
		return self._colorPalette

	def setColorPalette(self, colorPalette: ColorPalette) -> None:
		if colorPalette != self._colorPalette:
			self._colorPalette = colorPalette
			self.update()

	def getBorderBrush(self, isOn: bool = False) -> QBrush:
		return QBrush(self._fromCS(self._colorPalette.borderColor, isOn))

	def getBorderBrush2(self, isOn: bool = False) -> QBrush:
		return QBrush(self._fromCS(self._colorPalette.borderColor2, isOn))

	def getBackgroundBrush(self, rect: QRect, isOn: bool = False) -> QBrush:
		fromCs = self._fromCS(self._colorPalette.backgroundColor, isOn)
		fromCs2 = self._fromCS(self._colorPalette.backgroundColor2, isOn)
		bkgGradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
		bkgGradient.setColorAt(0, fromCs)
		bkgGradient.setColorAt(1, fromCs2)
		return QBrush(bkgGradient)

	def getPressedBackgroundBrush(self, rect: QRect, isOn: bool = False) -> QBrush:
		fromCs = self._fromCS(self._colorPalette.backgroundColor, isOn)
		fromCs = QColor(0, 0, 0, 29) if fromCs.alpha() == 0 else fromCs.darker(113)
		fromCs2 = self._fromCS(self._colorPalette.backgroundColor2, isOn)
		fromCs2 = QColor(0, 0, 0, 29) if fromCs2.alpha() == 0 else fromCs2.darker(113)
		bkgGradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
		bkgGradient.setColorAt(0, fromCs2)
		bkgGradient.setColorAt(1, fromCs)
		return QBrush(bkgGradient)

	def getTextBrush(self, isOn: bool = False) -> QBrush:
		return QBrush(self._fromCS(self._colorPalette.textColor, isOn))

	def getIconBrush(self, isOn: bool = False) -> QBrush:
		return QBrush(self._fromCS(self._colorPalette.iconColor, isOn))

	def getIndicatorBrush(self, rect: QRect, isOn: bool = False) -> QBrush:
		bkgGradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
		bkgGradient.setColorAt(0, self._fromCS(self._colorPalette.indicatorColor, isOn))
		bkgGradient.setColorAt(1, self._fromCS(self._colorPalette.indicatorColor2, isOn))
		return QBrush(bkgGradient)

	def getIndicatorBorderBrush(self, isOn: bool = False) -> QBrush:
		return QBrush(self._fromCS(self._colorPalette.indicatorBorderColor, isOn))

	def getIndicatorBorderBrush2(self, isOn: bool = False) -> QBrush:
		return QBrush(self._fromCS(self._colorPalette.indicatorBorderColor2, isOn))
