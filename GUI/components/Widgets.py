from __future__ import annotations

from math import ceil, inf
from typing import List, NamedTuple, Optional, TYPE_CHECKING, Tuple, cast, overload

from PyQt5 import sip
from PyQt5.QtCore import QAbstractTableModel, QEvent, QItemSelection, QItemSelectionModel, QModelIndex, QObject, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, QSizeF, \
	Qt, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QAbstractTextDocumentLayout, QBrush, QColor, QCursor, QFocusEvent, QFont, QFontMetrics, QIcon, QKeyEvent, QKeySequence, QMouseEvent, QMoveEvent, QMovie, \
	QPaintEvent, QPainter, QPainterPath, QPalette, QPen, QPicture, QPixmap, QPolygonF, QResizeEvent, QScreen, QShortcutEvent, QStaticText, QTextDocument, QTextLayout, QTextLine, \
	QTextOption, QValidator
from PyQt5.QtWidgets import QAbstractButton, QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QGraphicsBlurEffect, QGraphicsEffect, QGridLayout, QLabel, \
	QLayout, QLineEdit, QPushButton, QRadioButton, QScrollArea, QShortcut, QSizePolicy, QStyle, QStyleOptionViewItem, QStyledItemDelegate, QTableView, QTextEdit, QTreeView, QWidget

from ..utilities import connectSafe, safeEmit
from ...GUI.components.catWidgetMixins import CAN_BUT_NO_BORDER_OVERLAP, CORNERS, CatClickableMixin, CatFocusableMixin, CatFramedAbstractScrollAreaMixin, CatFramedAreaMixin, \
	CatFramedWidgetMixin, CatScalableWidgetMixin, CatSizePolicyMixin, CatStyledWidgetMixin, ColorPalette, OverlapCharacteristics, PaintEventDebug, ShortcutMixin, \
	UndoBlockableMixin, centerOfRect, getBorderPath, palettes
from ...GUI.components.renderArea import Pens
from ...GUI.components.treeModel import DataTreeModel, TreeItemBase, TreeModel
from ...utils.utils import CrashReportWrapped

# global variables for debugging:
DEBUG_LAYOUT: bool = False


def getLayoutBorderPen(self: CatStyledWidgetMixin) -> QPen:
	layoutBorderColor = QColor((97*2)//3, 128, 0)
	layoutBorderColor.setAlphaF(0.5)
	layoutBorderPen = QPen(QBrush(layoutBorderColor), 1.)
	return layoutBorderPen


def paintGridLayoutBorders(p: QPainter, layout: QLayout) -> None:
	if not DEBUG_LAYOUT:
		return
	p.setPen(QPen(QColor('blue'), 0.5))
	p.setBrush(Qt.NoBrush)
	if isinstance(layout, QGridLayout):
		for r in range(layout.rowCount()):
			for c in range(layout.columnCount()):
				rect = layout.cellRect(r, c)
				p.drawRect(rect)

	for child in layout.children():
		if isinstance(child, QLayout):
			paintGridLayoutBorders(p, child)


class CatToolbarSpacer(QWidget, CatSizePolicyMixin, CatFramedWidgetMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.setColorPalette(palettes.panelColorPalette)
		self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
		self._roundedCorners = CORNERS.NONE

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		return self.adjustSizeByOverlap(self.getDefaultSize('', 0, 0))

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		minSize = self.adjustSizeByOverlap(self.getDefaultMinimumSize())
		minSize.setWidth(0)
		return minSize

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		self.updateScaleFromFontMetrics()
		rect = self.adjustRectByOverlap(self.rect())

		# get Colors:
		borderBrush = self.getBorderBrush()
		bkgColor1 = self.getBackgroundBrush(rect)
		# do drawing:
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.setPen(QPen(borderBrush, 1))
			p.setBrush(bkgColor1)
			borderPath = self.getBorderPath(rect)
			p.drawPath(borderPath)


class CatPanel(QWidget, CatSizePolicyMixin, CatFramedWidgetMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self._roundedCorners = CORNERS.NONE
		self._default: bool = False
		self._windowPanel: bool = False
		self._neverInactive = True
		self._updateColorPalette()

	def isDefault(self) -> bool:
		return self._default

	def setDefault(self, default: bool) -> None:
		if default != self._default:
			self._default = default
			self._updateColorPalette()

	def isWindowPanel(self) -> bool:
		return self._windowPanel

	def setWindowPanel(self, windowPanel: bool) -> None:
		if windowPanel != self._windowPanel:
			self._windowPanel = windowPanel
			self._updateColorPalette()

	def _updateColorPalette(self) -> None:
		if self.isDefault():
			colorPalette = palettes.defaultButtonColorPalette
		elif self.isWindowPanel():
			colorPalette = palettes.windowPanelColorPalette
		else:
			colorPalette = palettes.panelColorPalette
		self.setColorPalette(colorPalette)

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		drawLayoutBorders = False
		self.updateScaleFromFontMetrics()
		rect = self.adjustRectByOverlap(self.rect())

		# get Colors:
		bkgBrush = self.getBackgroundBrush(rect)
		borderBrush = self.getBorderBrush()
		if drawLayoutBorders:
			layoutBorderPen = getLayoutBorderPen(self)
		else:
			layoutBorderPen = None

		# do drawing:
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.setPen(QPen(borderBrush, 1))
			p.setBrush(bkgBrush)
			borderPath = self.getBorderPath(rect)
			p.drawPath(borderPath)

			if drawLayoutBorders:
				p.setPen(layoutBorderPen)
				p.setBrush(Qt.NoBrush)
				p.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))

			paintGridLayoutBorders(p, self.layout())

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		superMinSizeHint = super(CatPanel, self).minimumSizeHint()
		selfMinSizeHint = self.adjustSizeByOverlap(self.getDefaultMinimumSize())
		return QSize(
			max(superMinSizeHint.width(), selfMinSizeHint.width()),
			max(superMinSizeHint.height(), selfMinSizeHint.height())
		)


class CatSeparator(QWidget, CatSizePolicyMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self._orientation: Qt.Orientation = Qt.Horizontal
		self.setColorPalette(palettes.panelColorPalette)
		self.updateSizePolicy()

	def orientation(self) -> Qt.Orientation:
		return self._orientation

	def setOrientation(self, value: Qt.Orientation) -> None:
		if self._orientation != value:
			self._orientation = value
			self.updateSizePolicy()

	def updateSizePolicy(self) -> None:
		if self._orientation == Qt.Horizontal:
			self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
		else:
			self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
		self.update()
		self.updateGeometry()

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		self.updateScaleFromFontMetrics()
		# get Colors:
		borderBrush = self.getBorderBrush()

		# do drawing:
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.setPen(QPen(borderBrush, 1))
			p.setBrush(borderBrush)
			p.drawRect(self.rect())

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		minSize = max(1, int(1 * self._scale))
		return QSize(minSize, minSize)
		# if self._orientation == Qt.Horizontal:
		# 	return QSize(minSize, 0)
		# else:
		# 	return QSize(0, minSize)


class CatOverlay(QWidget):

	def __init__(self, parent: Optional[QWidget] = None):
		super(CatOverlay, self).__init__(parent)

	@classmethod
	def addDialogBlur(cls, target: QWidget) -> QGraphicsEffect:
		if target.graphicsEffect() is None:
			ef = QGraphicsBlurEffect(target)
			ef.setBlurHints(QGraphicsBlurEffect.QualityHint)
			ef.setBlurRadius(5)
			target.setGraphicsEffect(ef)
			target.graphicsEffect().setEnabled(False)
		return target.graphicsEffect()

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		backgroundColor = QColor('black')
		backgroundColor.setAlphaF(0.25)
		with QPainter(self) as p:
			p.fillRect(self.rect(), backgroundColor)


class CatLabel(CatClickableMixin, QLabel, CatSizePolicyMixin, CatScalableWidgetMixin):
	"""
	IconWidget gives the ability to display an icon as a widget

	if supports the same arguments as icon()
	for example
	music_icon = qta.IconWidget('fa5s.music',
								color='blue',
								color_active='orange')

	it also have setIcon() and setIconSize() functions
	"""

	def __init__(self, parent: Optional[QWidget] = None):
		super(CatLabel, self).__init__(parent=parent)
		self._icon: Optional[QIcon] = QIcon()
		self._updatingPixmapFromIcon: bool = False
		self._scale: float = 1.
		self._iconScale: float = 0.8

	def icon(self) -> QIcon:
		return self._icon

	def setIcon(self, icon: QIcon):
		self.clear()
		self._icon = icon
		self._updatePixMapFromIcon()

	def setText(self, text: str) -> None:
		self._icon = QIcon()
		super(CatLabel, self).setText(text)

	def setPixmap(self, pixmap: QPixmap) -> None:
		self._icon = QIcon()
		self._setPixmapInner(pixmap)

	def _setPixmapInner(self, pixmap: QPixmap):
		super(CatLabel, self).setPixmap(pixmap)

	def setPicture(self, picture: QPicture) -> None:
		self._icon = QIcon()
		super(CatLabel, self).setPicture(picture)

	def setMovie(self, movie: QMovie) -> None:
		self._icon = QIcon()
		super(CatLabel, self).setMovie(movie)

	def iconScale(self) -> float:
		return self._iconScale

	def setIconScale(self, scale: float):
		oldScale = self._iconScale
		self._iconScale = scale
		if oldScale != scale and not self._icon.isNull():
			self._updatePixMapFromIcon()

	@CrashReportWrapped
	def clear(self) -> None:
		if not self._updatingPixmapFromIcon:
			self._icon = QIcon()
			super(CatLabel, self).clear()

	def _updatePixMapFromIcon(self):
		self._updatingPixmapFromIcon = True
		try:
			cm = self.getContentsMargins()
			width = int(20 * self._scale * self._iconScale)
			height = int(20 * self._scale * self._iconScale)
			width -= cm[0] + cm[2]
			height -= cm[1] + cm[3]
			size = min(width, height)
			if self.pixmap() is None or self.pixmap().size() != QSize(size, size):
				self._setPixmapInner(self._icon.pixmap(size, size))
		finally:
			self._updatingPixmapFromIcon = False

	@CrashReportWrapped
	def update(self, *args, **kwargs):
		if not self._icon.isNull():
			self._updatePixMapFromIcon()
		return super(CatLabel, self).update(*args, **kwargs)

	@CrashReportWrapped
	def resizeEvent(self, event: QResizeEvent) -> None:
		if not self._icon.isNull():
			self._updatePixMapFromIcon()
		super(CatLabel, self).resizeEvent(event)
		# recalculate sizeHint by forcing a call to QLabelPrivate::updateLabel, because of a Qt bug... :(
		e = QEvent(QEvent.ContentsRectChange)
		QApplication.sendEvent(self, e)

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		superSizeHint = super(CatLabel, self).sizeHint()
		if self.hasHeightForWidth():
			# fixing a Qt bug... :(
			w = self.width()
			h = self.heightForWidth(w) # this somehow causes a repaint
			superSizeHint.setHeight(h)
		return superSizeHint

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		self.updateScaleFromFontMetrics()
		if not self._icon.isNull():
			self._updatePixMapFromIcon()
		super(CatLabel, self).paintEvent(event)


class CatElidedLabel(CatClickableMixin, QLabel):

	elisionChanged = pyqtSignal(bool)

	def __init__(self, parent: QWidget = None):
		super(CatElidedLabel, self).__init__(parent)
		self._isElided: bool = False
		self._elideMode: Qt.TextElideMode = Qt.ElideRight
		self._layoutedText: list[tuple[str, int]]
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

	def elideMode(self) -> Qt.TextElideMode:
		return self._elideMode

	def setElideMode(self, value: Qt.TextElideMode):
		self._elideMode = value

	def isElided(self) -> bool:
		return self._isElided

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		msh = super(CatElidedLabel, self).minimumSizeHint()
		msh.setWidth(0)
		return msh

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		sizeHint = super(CatElidedLabel, self).sizeHint()
		sizeHint2 = QSize(
			sizeHint.width(),
			max(sizeHint.height(), self.totalHeightForLines())
		)
		return sizeHint2

	@CrashReportWrapped
	def heightForWidth(self, width: int) -> int:
		h = super(CatElidedLabel, self).heightForWidth(width)
		h2 = max(h, self.totalHeightForLines())
		return h2

	def totalHeightForBlock(self, block: str, font: QFont, fontMetrics: QFontMetrics) -> int:
		contentsRect = self.contentsRect()
		contentsRect.marginsAdded(self.contentsMargins())
		y = 0
		textLayout = QTextLayout(block, font)
		if not self.wordWrap():
			return y + fontMetrics.lineSpacing()

		textLayout.beginLayout()
		try:
			while True:
				line: QTextLine = textLayout.createLine()
				if not line.isValid():
					return y
				line.setLineWidth(contentsRect.width())
				y = y + fontMetrics.lineSpacing()
		finally:
			textLayout.endLayout()

	def totalHeightForLines(self) -> int:
		fontMetrics = self.fontMetrics()
		y: int = self.contentsRect().top()
		text = self.text().splitlines(keepends=True)
		for block in text:
			y += self.totalHeightForBlock(block, self.font(), fontMetrics)
		return max(0, y + fontMetrics.height() - fontMetrics.lineSpacing())

	def drawLine(self, block: str, y: int, font: QFont, fontMetrics: QFontMetrics, linesIO: List[Tuple[str, int]]) -> Tuple[bool, int]:
		contentsRect = self.contentsRect()
		contentsRect.marginsAdded(self.contentsMargins())
		textLayout = QTextLayout(block, font)
		textLayout.beginLayout()
		try:
			while True:
				line: QTextLine = textLayout.createLine()

				if not line.isValid():
					return False, y

				line.setLineWidth(contentsRect.width())
				nextLineY: int = y + fontMetrics.lineSpacing()

				index = line.textStart()
				if contentsRect.height() + 1 >= nextLineY + fontMetrics.lineSpacing():
					lineText = block[index:index + line.textLength()]
					lineWidth = fontMetrics.boundingRect(lineText).width()
					if lineWidth > contentsRect.width():
						lineText = fontMetrics.elidedText(lineText, self.elideMode(), contentsRect.width())
					linesIO.append((lineText, y,))
					y = nextLineY
				else:
					lastLine: str = block[index:]
					elidedLastLine: str = fontMetrics.elidedText(lastLine, self.elideMode(), contentsRect.width())
					if elidedLastLine.endswith('\n'):
						elidedLastLine = elidedLastLine.rstrip('\n') + '…'
					linesIO.append((elidedLastLine, y))
					line = textLayout.createLine()
					didElide = line.isValid()
					return True, y
		finally:
			textLayout.endLayout()

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		super(QLabel, self).paintEvent(event)
		contentsRect = self.contentsRect()

		with QPainter(self) as p:
			fontMetrics = p.fontMetrics()
			font = p.font()

			didElide: bool = False
			y: int = contentsRect.top()
			left: int = contentsRect.x() + 3

			lines: List[Tuple[str, int]] = []
			text = self.text().splitlines(keepends=True)
			for block in text:
				didElide, y = self.drawLine(block, y, font, fontMetrics, linesIO=lines)
				if didElide:
					break
			for line, y in lines:
				p.drawText(QPoint(left, y + fontMetrics.ascent()), line)

			if didElide != self._isElided:
				self._isElided = didElide
				safeEmit(self, self.elisionChanged, didElide)


class CatTextField(CatFocusableMixin, ShortcutMixin, UndoBlockableMixin, CatFramedAreaMixin, QLineEdit, CatSizePolicyMixin, CatStyledWidgetMixin):
	"""a QTextField with a keyPressed signal"""
	def __init__(self, parent: Optional[QWidget] = None):
		super(CatTextField, self).__init__(parent)
		self._capturesTab = False
		self.setFrame(True)
		self.setMargins(self.smallDefaultMargins)
		self._roundedCorners = CORNERS.NONE
		self._colorPalette = palettes.inputColorPalette
		self._highlightOnFocus = True

	keyPressed = pyqtSignal(QLineEdit, QKeyEvent)

	def isCapturingTab(self):
		return self._capturesTab

	def setCapturingTab(self, v):
		self._capturesTab = v

	def plainText(self):
		return self.text()

	def setPlainText(self, text):
		return self.setText(text)

	def refresh(self) -> None:
		self._pixmapNeedsRepaint = True
		super(CatTextField, self).refresh()

	@CrashReportWrapped
	def keyPressEvent(self, event: QKeyEvent):
		super(CatTextField, self).keyPressEvent(event)
		safeEmit(self, self.keyPressed, self, event)

	@CrashReportWrapped
	def event(self, event):
		if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Tab) and self._capturesTab:
			safeEmit(self, self.keyPressed, self, event)
			return True
		return super(CatTextField, self).event(event)

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		defaultSize = self.getDefaultSize('xxxxxxxxxxxxxxxxx', 0, 0)  # 17 times the letter 'x'
		return self.adjustSizeByOverlap(defaultSize)

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		defaultSize = self.getDefaultSize('M', 0, 0)
		return self.adjustSizeByOverlap(defaultSize)

	def getBorderBrushes(self, rect: QRect) -> tuple[QBrush, QBrush, QBrush]:
		return self.getBorderBrush(), self.getBorderBrush2(), self.getBackgroundBrush(rect)

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		super(CatTextField, self).paintEvent(event)
		self.paintFrame(event)


class CatMultiLineTextField(CatFocusableMixin, ShortcutMixin, UndoBlockableMixin, CatFramedAbstractScrollAreaMixin, QTextEdit, CatStyledWidgetMixin):
	"""a QTextField with a keyPressed signal"""
	def __init__(self):
		super().__init__()
		self._capturesTab = False
		self._roundedCorners = CORNERS.NONE
		self._colorPalette = palettes.inputColorPaletteB
		self.setLineWidth(1)
		self._highlightOnFocus = True

	keyPressed = pyqtSignal(QTextEdit, QKeyEvent)

	def isCapturingTab(self):
		return self._capturesTab

	def setCapturingTab(self, v):
		self._capturesTab = v

	@CrashReportWrapped
	def keyPressEvent(self, event: QKeyEvent):
		super().keyPressEvent(event)
		safeEmit(self, self.keyPressed, self, event)

	@CrashReportWrapped
	def event(self, event: QEvent) -> bool:
		if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Tab) and self._capturesTab:
			safeEmit(self, self.keyPressed, self, event)
			return True
		result = super().event(event)
		return result

	def plainText(self):
		return self.toPlainText()

	def cursorPosition(self) -> int:
		textCursor = self.textCursor()
		return textCursor.position()

	def setCursorPosition(self, position: int):
		textCursor = self.textCursor()
		textCursor.setPosition(position)
		self.setTextCursor(textCursor)

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		super(CatMultiLineTextField, self).paintEvent(event)
		self.paintFrameOnWidget(event, self.viewport())

	def getBorderBrushes(self, rect: QRect) -> tuple[QBrush, QBrush, QBrush]:
		return self.getBorderBrush(), self.getBorderBrush2(), QBrush(Qt.NoBrush)


class CatComboBox(CatFocusableMixin, ShortcutMixin, UndoBlockableMixin, CatFramedAreaMixin, QComboBox, CatSizePolicyMixin, CatStyledWidgetMixin):
	"""a QTextField with a keyPressed signal"""
	def __init__(self, parent: Optional[QWidget] = None):
		super(CatComboBox, self).__init__(parent)
		self._capturesTab = False
		self.setFrame(True)
		self.setMargins(self.smallDefaultMargins)
		self._roundedCorners = CORNERS.NONE
		self._colorPalette = palettes.inputColorPalette
		self._highlightOnFocus = True

	keyPressed = pyqtSignal(QLineEdit, QKeyEvent)

	def isCapturingTab(self):
		return self._capturesTab

	def setCapturingTab(self, v):
		self._capturesTab = v

	def plainText(self):
		return self.currentText()

	def setPlainText(self, text):
		return self.setCurrentText(text)

	def refresh(self) -> None:
		self._pixmapNeedsRepaint = True
		super(CatComboBox, self).refresh()

	@CrashReportWrapped
	def keyPressEvent(self, event: QKeyEvent):
		super(CatComboBox, self).keyPressEvent(event)
		safeEmit(self, self.keyPressed, self, event)

	@CrashReportWrapped
	def event(self, event):
		if (event.type()==QEvent.KeyPress) and (event.key()==Qt.Key_Tab) and self._capturesTab:
			safeEmit(self, self.keyPressed, self, event)
			return True
		return super(CatComboBox, self).event(event)

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		defaultSize = self.getDefaultSize('xxxxxxxxxxxxxxxxx', 1, 1)  # 17 times the letter 'x'
		return self.adjustSizeByOverlap(defaultSize)

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		defaultSize = self.getDefaultSize('M', 0, 0)
		return self.adjustSizeByOverlap(defaultSize)

	def getBorderBrushes(self, rect: QRect) -> tuple[QBrush, QBrush, QBrush]:
		return self.getBorderBrush(), self.getBorderBrush2(), self.getBackgroundBrush(rect)

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		self.updateScaleFromFontMetrics()
		super(CatComboBox, self).paintEvent(event)
		self.paintFrame(event)


class CatScrollArea(CatFramedAbstractScrollAreaMixin, QScrollArea, CatStyledWidgetMixin):
	"""a QTextField with a keyPressed signal"""
	def __init__(self):
		super().__init__()
		self._roundedCorners = CORNERS.NONE
		self._colorPalette = palettes.windowPanelColorPalette
		self.setLineWidth(1)
		self._sizeHint: QSize = QSize()

	def getBorderBrushes(self, rect: QRect) -> tuple[QBrush, QBrush, QBrush]:
		bkgBrush = self.getBackgroundBrush(rect)
		return self.getBorderBrush(), bkgBrush, bkgBrush

	def sizeHint(self) -> QSize:
		if self.sizeAdjustPolicy() == QScrollArea.AdjustIgnored:
			return QSize(256, 192)

		if not self._sizeHint.isValid() or self.sizeAdjustPolicy() == QScrollArea.AdjustToContents:
			f = 2 * self.frameWidth()
			frame = QSize(f, f)
			vNoScroll = self.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
			hNoScroll = self.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
			vbarHidden = self.verticalScrollBar().isHidden() or vNoScroll
			hbarHidden = self.horizontalScrollBar().isHidden() or hNoScroll

			scrollbars = QSize(
				0 if vbarHidden else self.verticalScrollBar().sizeHint().width(),
				0 if hbarHidden else self.horizontalScrollBar().sizeHint().height()
			)
			self._sizeHint = frame + scrollbars + self.viewportSizeHint()

		return self._sizeHint

	def minimumSizeHint(self) -> QSize:
		vNoScroll = self.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
		hNoScroll = self.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
		vbarHidden = self.verticalScrollBar().isHidden() or vNoScroll
		hbarHidden = self.horizontalScrollBar().isHidden() or hNoScroll

		scrollbars = QSize(
			0 if vbarHidden else self.verticalScrollBar().sizeHint().width(),
			0 if hbarHidden else self.horizontalScrollBar().sizeHint().height()
		)

		superMinSizeHint = super(CatScrollArea, self).minimumSizeHint()
		if self.widget() is not None:
			viewportMinSizeHint = self.widget().minimumSizeHint() + scrollbars
		else:
			viewportMinSizeHint = self.viewport().minimumSizeHint() + scrollbars

		minSizeHint = QSize(
			viewportMinSizeHint.width() if hNoScroll else superMinSizeHint.width(),
			viewportMinSizeHint.height() if vNoScroll else superMinSizeHint.height()
		)
		return minSizeHint

	def paintFrameOnWidget(self, event: QPaintEvent, widget: QWidget):
		super(CatScrollArea, self).paintFrameOnWidget(event, widget)
		if DEBUG_LAYOUT:
			with QPainter(widget) as p:
				if widget.layout() is not None:
					p.setPen(Qt.NoPen)
					p.setBrush(self.getBackgroundBrush(self.rect()))
					p.drawRect(self.rect())
					paintGridLayoutBorders(p, widget.layout())


class SpinBoxStrippingResult(NamedTuple):
	text: str
	cursorPos: int


class SpinBoxValidateResult(NamedTuple):
	text: str
	cursorPos: int
	state: QValidator.State
	value: int


class Int64SpinBox(CatFocusableMixin, ShortcutMixin, UndoBlockableMixin, QAbstractSpinBox):
	# adapted from https://stackoverflow.com/a/32628421/8091657.
	def __init__(self, parent=None):
		super().__init__(parent)
		self.m_minimum: int = -9_223_372_036_854_775_808
		self.m_maximum: int = +9_223_372_036_854_775_807
		self.m_value: int = 0
		self.m_singleStep: int = 1
		self.m_prefix: str = ''
		self.m_suffix: str = ''
		self.m_specialValueText: str = ''
		# cached value:
		self._cachedText: str = ''
		self._cachedState: QValidator.State = QValidator.Invalid
		self._cachedValue: int = 0

		connectSafe(self.lineEdit().editingFinished, self.onEditFinished)
		connectSafe(self.editingFinished, self.onEditFinished)

	def _hasSpecialValue(self) -> bool:
		return self.m_value == self.m_minimum and self.specialValueText()

	def _updateEdit(self):
		newText: str = self.m_specialValueText if self._hasSpecialValue() else self.m_prefix + self.textFromValue(self.m_value) + self.m_suffix
		edit =  self.lineEdit()
		if newText == edit.displayText():  # or cleared:
			return

		empty: bool = len(edit.text()) != 0
		cursor: int = edit.cursorPosition()
		selsize: int = len(edit.selectedText())

		# ??? blocker: QSignalBlocker = QSignalBlocker(edit);
		edit.setText(newText)

		if not self._hasSpecialValue():
			cursor = min(max(len(self.m_prefix), cursor), len(edit.displayText()) - len(self.m_suffix))
			if selsize > 0:
				edit.setSelection(cursor, selsize)
			else:
				edit.setCursorPosition(len(self.m_prefix) if empty else cursor)

		self.update()

	def value(self) -> int:
		return self.m_value

	def setValue(self, val: int):
		self.setValueInternal(val, True)

	def prefix(self) -> str:
		return self.m_prefix

	def setPrefix(self, prefix: str):
		self.m_prefix = prefix
		self._updateEdit()
		self.updateGeometry()

	def suffix(self) -> str:
		"""
		\property QSpinBox::suffix
		\brief the suffix of the spin box

		The suffix is appended to the end of the displayed value. Typical
		use is to display a unit of measurement or a currency symbol. For
		example:

		\snippet code/src_gui_widgets_qspinbox.cpp 1

		To turn off the suffix display, set this property to an empty
		string. The default is no suffix. The suffix is not displayed for
		the minimum() if specialValueText() is set.

		If no suffix is set, suffix() returns an empty string.

		\sa prefix(), setPrefix(), specialValueText(), setSpecialValueText()
		"""
		return self.m_suffix

	def setSuffix(self, suffix: str):
		self.m_suffix = suffix
		self._updateEdit()
		self.updateGeometry()

	@CrashReportWrapped
	def specialValueText(self) -> str:
		return self.m_specialValueText

	@CrashReportWrapped
	def setSpecialValueText(self, specialValueText: str):
		self.m_specialValueText = specialValueText
		self._updateEdit()

	def _stripped(self, text: str, cursorPos: int) -> SpinBoxStrippingResult:
		if len(self.m_specialValueText) == 0 or text != self.m_specialValueText:
			begin: int = 0
			end: int = len(text)
			changed: bool = False
			if len(self.prefix()) and text.startswith(self.prefix()):
				begin += len(self.prefix())
				changed = True

			if len(self.suffix()) and text.endswith(self.suffix()):
				end -= len(self.suffix())
				changed = True

			if changed:
				text = text[begin:end]
				cursorPos = max(0, min(end, cursorPos) - begin)

		charsToStrip = ' \f\n\r\t\v'

		text = text.rstrip(charsToStrip)
		s: int = len(text)
		cursorPos = min(cursorPos, s)
		text = text.lstrip(charsToStrip)
		cursorPos -= s - len(text)
		return SpinBoxStrippingResult(text, cursorPos)

	def cleanText(self) -> str:
		"""
		property QSpinBox::cleanText

		The text of the spin box excluding any prefix, suffix,
		or leading or trailing whitespace.
		:param self:
		:return:
		"""
		return self._stripped(self.lineEdit().displayText(), self.lineEdit().cursorPosition()).text

	def singleStep(self) -> int:
		return self.m_singleStep

	def setSingleStep(self, val: int):
		if val > 0:
			self.m_singleStep = val
			self._updateEdit()

	def minimum(self) -> int:
		return self.m_minimum

	def setMinimum(self, minimum: int):
		self.m_minimum = minimum
		if minimum > self.m_maximum:
			self.m_maximum =  minimum

		if self.m_value < minimum:
			self.setValueInternal(minimum, True)
		elif self.m_value == minimum and self.m_specialValueText:
			self._updateEdit()

		self.updateGeometry()

	def maximum(self) -> int:
		return self.m_maximum

	def setMaximum(self, maximum: int):
		self.m_maximum = maximum

		if maximum < self.m_minimum:
			self.m_minimum = maximum

		if self.m_value > maximum:
			self.setValueInternal(maximum, True)
		elif self.m_value == self.m_minimum and self.m_specialValueText:
			self._updateEdit()

	def setValueInternal(self, val: int, doUpdate: bool):
		old = self.m_value
		self.m_value = min(max(self.m_minimum, val), self.m_maximum)
		if doUpdate:
			self._updateEdit()
		self.update()
		if self.m_value != old:
			safeEmit(self, self.valueChanged, val)

	@CrashReportWrapped
	def stepBy(self, steps: int):
		new_value = self.m_value
		new_value += steps * self.m_singleStep

		self.setValue(new_value)

	@CrashReportWrapped
	def stepEnabled(self) -> QAbstractSpinBox.StepEnabled:
		val = self.value()
		result = QAbstractSpinBox.StepEnabled()
		if val > self.minimum():
			result |= self.StepDownEnabled
		if val < self.maximum():
			result |= self.StepUpEnabled
		return result

	def _validateAndInterpret(self, input: str, cursorPos: int) -> SpinBoxValidateResult:
		if self._cachedText == input and input:
			state = self._cachedState
			value = self._cachedValue
			return SpinBoxValidateResult(input, cursorPos, state, value)

		maximum = self.m_maximum
		minimum = self.m_minimum

		strippedInput, cursorPos = self._stripped(input, cursorPos)
		state: QValidator.State = QValidator.Acceptable
		value: int = minimum

		inputIsEmpty = not strippedInput
		if maximum != minimum \
			and (inputIsEmpty
				or (minimum < 0 and inputIsEmpty == "-")
				or (maximum >= 0 and inputIsEmpty == "+")
		):
			state = QValidator.Intermediate
		elif strippedInput.startswith('-') and minimum >= 0:
			state = QValidator.Invalid  # special-case -0 will be interpreted as 0 and thus not be invalid with a range from 0-100
		else:
			ok: bool = False
			try:
				value = int(strippedInput)
				ok = True
			except ValueError:
				pass

			if not ok:
				state = QValidator.Invalid
			elif value >= minimum and value <= maximum:
				state = QValidator.Acceptable
			elif maximum == minimum:
				state = QValidator.Invalid
			else:
				if (value >= 0 and value > maximum) or (value < 0 and value < minimum):
					state = QValidator.Invalid
				else:
					state = QValidator.Intermediate

		if state != QValidator.Acceptable:
			value = minimum if maximum > 0 else maximum
		input = self.m_prefix + strippedInput + self.m_suffix
		cursorPos += len(self.m_prefix)
		self._cachedText = input
		self._cachedState = state
		self._cachedValue = value

		return SpinBoxValidateResult(input, cursorPos, state, value)

	def valueFromText(self, text: str) -> int:
		cursorPos: int = self.lineEdit().cursorPosition()
		return self._validateAndInterpret(text, cursorPos).value

	def textFromValue(self, val: int) -> str:
		return str(val)

	@CrashReportWrapped
	def Xvalidate(self, input: str, pos: int) -> Tuple[QValidator.State, str, int]:
		validateResult = self._validateAndInterpret(input, pos)
		return validateResult.state, validateResult.text, validateResult.cursorPos
	@CrashReportWrapped
	def updateTextFromValue(self):
		self.lineEdit().setText(self.m_prefix + self.textFromValue(self.m_value) + self.m_suffix)

	@CrashReportWrapped
	def onEditFinished(self):
		cursorPos: int = self.lineEdit().cursorPosition()
		value = self._validateAndInterpret(self.text(), cursorPos).value
		self.setValueInternal(value, True)

	@CrashReportWrapped
	def onEditChanged(self, text: str):
		pos: int = self.lineEdit().cursorPosition()
		if self.validate(text, pos)[0] == QValidator.Acceptable:
			self.setValueInternal(self.valueFromText(text), True)
		else:
			self.updateTextFromValue()

	# Q_SIGNALS:
	valueChanged = pyqtSignal(int)


class CatButton(CatFocusableMixin, ShortcutMixin, QPushButton, CatSizePolicyMixin, CatFramedWidgetMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None):
		super(CatButton, self).__init__(parent=parent)
		self.setCheckable(False)
		self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
		self._elideMode: Qt.TextElideMode = Qt.ElideNone
		self._normalColorPalette: ColorPalette = palettes.buttonColorPalette
		self._defaultColorPalette: ColorPalette = palettes.defaultButtonColorPalette
		self._updateColorPalette()
		self._highlightOnHover = True
		self._highlightOnFocus = True
		self.resize(0, 0)
		self._layoutContents()

	def elideMode(self) -> Qt.TextElideMode:
		return self._elideMode

	def setElideMode(self, mode: Qt.TextElideMode) -> None:
		self._elideMode = mode
		self.update()

	def getElidedText(self) -> str:
		iconCount = 0 if self.icon().isNull() else 1
		textCount = 0 if not self.text() else 1
		gapsCount = max(0, iconCount + textCount - 1)
		widthAvailable = self.widthAvailableForText(self.size(), iconCount, gapsCount)
		fm = self.fontMetrics()
		return fm.elidedText(self.text(), self.elideMode(), widthAvailable, Qt.TextShowMnemonic)

	@CrashReportWrapped
	def setIcon(self, icon: QIcon) -> None:
		if self.icon() != icon:
			super(CatButton, self).setIcon(icon)
			self.refresh()

	@CrashReportWrapped
	def setText(self, text: str) -> None:
		if self.text() != text:
			super(CatButton, self).setText(text)
			self.refresh()

	def refresh(self) -> None:
		self._layoutContents()
		super(CatButton, self).refresh()

	def _layoutContents(self) -> None :
		rect = self.adjustRectByOverlap(self.rect())

		if self.isDefault():
			font = QFont(self.font())
			font.setWeight(font.weight() + 7)
		else:
			font = self.font()
		borderBrush2 = self.getBorderBrush2()

		# layout elements:
		text = self.getElidedText()
		hasIcon = not self.icon().isNull()
		contentSize = self.getDefaultContentSize(text, int(hasIcon), 1 if (hasIcon and text) else 0)
		translation = rect.left() + (rect.width() - contentSize.width()) // 2

		iconSize = self.getDefaultIconSize()
		iconRect = QRect(
			translation,
			self.getIconTop(rect),
			iconSize.width(),
			iconSize.height()
		)

		textSize = self.getTextSize(text, font)
		textRect = QRect(
			iconRect.right() + 1 + self.getDefaultIconPadding() if hasIcon else translation,
			self.getTextTop(rect, font),
			textSize.width(),
			textSize.height()
		)

		if borderBrush2.color().alpha() > 0:
			borderRect = self.rect()
		else:
			borderRect = rect
		borderPath = self.getBorderPath(borderRect)

		borderPath2 = self.getBorderPath(borderRect.adjusted(1, 1, -1, -1), radiusDelta=-1)

		self._iconRect: QRect = iconRect
		self._textRect: QRect = textRect
		self._borderPath: QPainterPath = borderPath
		self._borderPath2: QPainterPath = borderPath2

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		iconCount = 0 if self.icon().isNull() else 1
		textCount = 0 if not self.text() else 1
		gapsCount = max(0, iconCount + textCount - 1)

		return self.adjustSizeByOverlap(self.getDefaultSize(self.text(), iconCount, gapsCount))

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		return self.adjustSizeByOverlap(self.getDefaultMinimumSize())

	@CrashReportWrapped
	def resizeEvent(self, event: QResizeEvent):
		self.refresh()
		super(CatButton, self).resizeEvent(event)

	@CrashReportWrapped
	def moveEvent(self, event: QMoveEvent) -> None:
		self.refresh()
		super(CatButton, self).moveEvent(event)

	def focusInEvent(self, event: QFocusEvent) -> None:
		super(CatButton, self).focusInEvent(event)
		self.refresh()

	def focusOutEvent(self, event: QFocusEvent) -> None:
		super(CatButton, self).focusOutEvent(event)
		self.refresh()

	def enterEvent(self, event: QEvent) -> None:
		super(CatButton, self).enterEvent(event)
		self.refresh()

	def leaveEvent(self, event: QEvent) -> None:
		super(CatButton, self).leaveEvent(event)
		self.refresh()

	def _updateColorPalette(self) -> None:
		if self.isDefault():
			colorPalette = self._defaultColorPalette
		else:
			colorPalette = self._normalColorPalette
		self._colorPalette = colorPalette

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		self._updateColorPalette()
		drawLayoutBorders = False

		self.updateScaleFromFontMetrics()
		rect = self.adjustRectByOverlap(self.rect())
		borderWidth = 1.
		if self.isDefault():
			font = QFont(self.font())
			font.setWeight(font.weight() + 7)
		else:
			font = self.font()
		isOn = self.isChecked()
		bkgBrush = self.getPressedBackgroundBrush(rect, isOn) if self.isDown() or self.isChecked() else self.getBackgroundBrush(rect, isOn)
		textColor = self.getTextBrush(isOn)
		borderBrush = self.getBorderBrush(isOn)
		borderBrush2 = self.getBorderBrush2(isOn)
		borderPen = QPen(borderBrush, borderWidth)
		borderPen2 = QPen(borderBrush2, borderWidth)
		if drawLayoutBorders:
			layoutBorderPen = getLayoutBorderPen(self)
		else:
			layoutBorderPen = None

		text = self.getElidedText()
		hasIcon = not self.icon().isNull()

		# do drawing:
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.setPen(borderPen)
			p.setBrush(bkgBrush)
			p.drawPath(self._borderPath)

			p.setPen(borderPen2)
			p.setBrush(Qt.NoBrush)
			p.drawPath(self._borderPath2)

			if hasIcon:
				mode = QIcon.Active if self.isHighlighted() else QIcon.Normal
				mode = QIcon.Selected if self.isDefault() else mode
				mode = mode if self.isEnabled() else QIcon.Disabled

				p.drawPixmap(self._iconRect, self.icon().pixmap(
					self._iconRect.size(),
					mode=mode,
					state=QIcon.On if isOn else QIcon.Off
				))

				if drawLayoutBorders:
					p.setPen(layoutBorderPen)
					p.setBrush(Qt.NoBrush)
					p.drawRect(QRectF(self._iconRect).adjusted(0.5, 0.5, -0.5, -0.5))

			if text:
				p.setPen(QPen(textColor, 1))
				p.setFont(font)
				p.drawText(self._textRect, Qt.TextShowMnemonic, text)

				if drawLayoutBorders:
					p.setPen(layoutBorderPen)
					p.setBrush(Qt.NoBrush)
					p.drawRect(QRectF(self._textRect).adjusted(0.5, 0.5, -0.5, -0.5))

			if drawLayoutBorders:
				p.setPen(layoutBorderPen)
				p.setBrush(Qt.NoBrush)
				p.drawRect(QRectF(rect.marginsRemoved(self.qMargins)).adjusted(0.5, 0.5, -0.5, -0.5))

	def shortcutEvent(self, event: QShortcutEvent) -> None:
		if not event.isAmbiguous():
			self.animateClick()
		else:
			super(CatButton, self).shortcutEvent(event)


class CatToolButton(CatButton):
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.setCheckable(False)
		self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		self.setMargins(self.smallDefaultMargins)
		self._roundedCorners = CORNERS.NONE
		self._elideMode: Qt.TextElideMode = Qt.ElideNone


class CatGradiantButton(CatButton):
	def __init__(self, parent=None):
		super(CatGradiantButton, self).__init__(parent=parent)
		self._normalColorPalette = palettes.gradiantButtonColorPalette
		self._updateColorPalette()


class CatFramelessButton(CatButton):
	def __init__(self, parent=None):
		super(CatFramelessButton, self).__init__(parent=parent)
		self._normalColorPalette = palettes.framelessButtonColorPalette
		self._updateColorPalette()

	@property
	def overlapCharacteristics(self) -> OverlapCharacteristics:
		return CAN_BUT_NO_BORDER_OVERLAP


class Switch(CatFocusableMixin, ShortcutMixin, QAbstractButton, CatSizePolicyMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None, track_diameter=17, thumb_radius=8):
		super().__init__(parent=parent)
		self.setCheckable(True)
		self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

		self._onColorPalette = palettes.switchOnColorPalette
		self._offColorPalette = palettes.switchOffColorPalette
		self._updateColorPalette()
		self._highlightOnHover = False
		self._highlightOnFocus = True

		self._track_diameter = track_diameter
		self._thumb_margin = 1
		self._scale: float = 1.0

		self._offsetState = 0

	@property
	def trackDiameter(self) -> int:
		return int(self._track_diameter * self._scale)

	@property
	def thumbDiameter(self) -> int:
		return self.trackDiameter - 2 * self.thumbMargin

	@property
	def thumbWidth(self) -> int:
		return self.thumbDiameter if self.isEnabled() else self.thumbDiameter + int(round(6 * self._scale))

	@property
	def trackRadius(self) -> float:
		return self.trackDiameter * 0.5

	@property
	def thumbRadius(self) -> float:
		return self.thumbDiameter * 0.5

	@property
	def trackMargin(self) -> int:
		return max(0, -self.thumbMargin)

	@property
	def thumbMargin(self) -> int:
		return int(round(self._thumb_margin * self._scale))

	@property
	def yOffset(self) -> float:
		return max(self.thumbDiameter, self.trackDiameter) / 2

	@property
	def xOffset(self) -> float:
		baseOffset = self.thumbMargin + self.thumbWidth / 2
		return (baseOffset * (1-self.offsetState) + self.offsetState * (self.toggleWidth() - baseOffset)) + self.toggleOffset()

	@pyqtProperty(float)
	def offsetState(self):
		return self._offsetState

	@offsetState.setter
	def offsetState(self, value):
		self._offsetState = value
		self.update()

	def iconWidth(self) -> int:
		if self.icon() and not self.icon().isNull():
			return int(self.trackDiameter)
		else:
			return 0

	def toggleOffset(self) -> int:
		iconWidth = self.iconWidth()
		if iconWidth > 0:
			iconWidth += 4
		return iconWidth

	def toggleWidth(self) -> int:
		return self.width() - self.toggleOffset()

	@CrashReportWrapped
	def sizeHint(self):
		return QSize(
			int(2 * self.trackDiameter + 2 * self.trackMargin + self.toggleOffset()),
			int(self.trackDiameter + 2 * self.trackMargin),
		)

	@CrashReportWrapped
	def setChecked(self, checked):
		super().setChecked(checked)
		self.moveKnobTo(self.isChecked())

	@CrashReportWrapped
	def resizeEvent(self, event):
		super().resizeEvent(event)

	def _updateColorPalette(self) -> None:
		if self.isChecked():
			colorPalette = self._onColorPalette
		else:
			colorPalette = self._offColorPalette
		self._colorPalette = colorPalette

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		self.updateScaleFromFontMetrics()
		self._updateColorPalette()

		rect = self.rect()

		# get Colors:
		if self.thumbRadius > self.trackRadius:
			track_brush = self.getIndicatorBrush(rect)
			track_border1 = self.getIndicatorBorderBrush()
			track_border2 = self.getIndicatorBorderBrush2()
			thumb_brush = self.getBackgroundBrush(rect)
			thumb_border1 = self.getBorderBrush()
			thumb_border2 = self.getBorderBrush2()
			text_color = self.getTextBrush()

			track_opacity = 0.5
			thumb_text = ''
		else:
			track_brush = self.getBackgroundBrush(rect)
			track_border1 = self.getBorderBrush()
			track_border2 = self.getBorderBrush2()
			thumb_brush = self.getIndicatorBrush(rect)
			thumb_border1 = self.getIndicatorBorderBrush()
			thumb_border2 = self.getIndicatorBorderBrush2()
			text_color = self.getTextBrush()
			track_opacity = 1
			thumb_text = \
				'✔' if self.isChecked() else \
				'✕'

			if True or not self.isEnabled():
				thumb_text = ''

		thumb_opacity = 1.0
		text_opacity = 1.0

		trackRect = QRectF(
			self.trackMargin + self.toggleOffset(),
			self.trackMargin,
			self.toggleWidth() - 2 * self.trackMargin,
			self.height() - 2 * self.trackMargin,
		).adjusted(0.5, 0.5, -0.5, -0.5)

		trackBorderRect1 = trackRect
		trackBorderRect2 = trackBorderRect1.adjusted(1, 1, -1, -1)

		thumbRect = QRectF(
			(self.xOffset - self.thumbWidth / 2),
			self.thumbMargin,
			self.thumbWidth,
			self.thumbDiameter,
		).adjusted(0.5, 0.5, -0.5, -0.5)

		thumbRect2 = thumbRect.adjusted(1, 1, -1, -1)

		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			if self.icon() and not self.icon().isNull():
				p.drawPixmap(0, 0, self.icon().pixmap(
					QSize(self.iconWidth(), self.iconWidth()),
					mode=QIcon.Normal if self.isEnabled() else QIcon.Disabled,
					state=QIcon.On if self.isChecked() else QIcon.Off
				))

			trackRadius = self.trackRadius
			p.setPen(Qt.NoPen)
			p.setBrush(track_brush)
			p.setOpacity(track_opacity)
			p.drawRoundedRect(trackRect, trackRadius, trackRadius)

			p.setPen(QPen(track_border1, 1))
			p.setBrush(Qt.NoBrush)
			p.drawRoundedRect(trackBorderRect1, trackRadius, trackRadius)

			p.setPen(QPen(track_border2, 1))
			p.setBrush(Qt.NoBrush)
			p.drawRoundedRect(trackBorderRect2, trackRadius-1, trackRadius-1)

			p.setPen(Qt.NoPen)
			p.setBrush(thumb_brush)
			p.setOpacity(thumb_opacity)
			p.drawRoundedRect(thumbRect, trackRadius, trackRadius)

			p.setPen(QPen(thumb_border1, 1))
			p.setBrush(Qt.NoBrush)
			p.drawRoundedRect(thumbRect, trackRadius, trackRadius)

			p.setPen(QPen(thumb_border2, 1))
			p.drawRoundedRect(thumbRect2, trackRadius-1, trackRadius-1)

			p.setPen(QPen(text_color, 1))
			p.setOpacity(text_opacity)
			font = p.font()
			p.setFont(font)
			p.drawText(
				QRectF(
					self.xOffset - self.thumbWidth / 2,
					self.yOffset - self.thumbRadius,
					self.thumbDiameter,
					self.thumbDiameter,
				),
				Qt.AlignCenter,
				thumb_text,
			)

	def moveKnobTo(self, checkedPos: bool):
		anim = QPropertyAnimation(self, b'offsetState', self)
		anim.setDuration(90)
		anim.setStartValue(self.offsetState)
		anim.setEndValue(1.0 if checkedPos else 0.0)
		anim.start()

	@CrashReportWrapped
	def checkStateSet(self) -> None:
		super(Switch, self).checkStateSet()
		self.moveKnobTo(self.isChecked())

	@CrashReportWrapped
	def nextCheckState(self) -> None:
		super(Switch, self).nextCheckState()
		self.moveKnobTo(self.isChecked())

	@CrashReportWrapped
	def mouseReleaseEvent(self, event):
		super().mouseReleaseEvent(event)
		if event.button() == Qt.LeftButton:
			pass

	@CrashReportWrapped
	def enterEvent(self, event):
		self.setCursor(Qt.PointingHandCursor)
		super().enterEvent(event)


# class CatCheckBox(CatFocusableMixin, ShortcutMixin, QCheckBox, CatSizePolicyMixin, CatFramedWidgetMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
class CatCheckBox(CatFocusableMixin, ShortcutMixin, QCheckBox, CatSizePolicyMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None):
		super(CatCheckBox, self).__init__(parent=parent)
		self.setCheckable(True)
		self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
		self.setMargins(self.smallDefaultMargins)
		self._elideMode: Qt.TextElideMode = Qt.ElideNone
		self._staticText: QStaticText = QStaticText()
		self._normalColorPalette: ColorPalette = palettes.buttonColorPalette
		self._partiallyColorPalette: ColorPalette = palettes.defaultButtonColorPalette
		self._checkedColorPalette: ColorPalette = palettes.defaultButtonColorPalette
		self._colorPalette = palettes.buttonColorPalette
		self._cornerRadius: int = 2
		self._highlightOnHover = True
		self._highlightOnFocus = True
		self._layoutContents()

	# @property
	# def overlapCharacteristics(self) -> OverlapCharacteristics:
	# 	return CANT_AND_NO_OVERLAP

	@property
	def _baseIconHeight(self) -> int:
		return 14

	def elideMode(self) -> Qt.TextElideMode:
		return self._elideMode

	def setElideMode(self, mode: Qt.TextElideMode) -> None:
		self._elideMode = mode
		self.update()

	@property
	def _useStaticText(self) -> bool:
		return self._elideMode == Qt.ElideNone

	def getCheckMarkSize(self) -> QSize:
		checkMarkWidth = int(self._baseIconHeight * self._scale)
		return QSize(checkMarkWidth, checkMarkWidth)

	def getCheckMarkRect(self, rect: QRect) -> QRect:
		contentRect = rect.marginsRemoved(self.qMargins)
		checkMarkSize = self.getCheckMarkSize()
		checkMarkTop = ceil(contentRect.y() + contentRect.height() / 2 - checkMarkSize.height() / 2)
		checkMarkRect = QRect(
			contentRect.left(),
			checkMarkTop,
			checkMarkSize.width(),
			checkMarkSize.height()
		)
		return checkMarkRect

	def getElidedText(self) -> str:
		iconCount = 0
		textCount = 0 if not self.text() else 1
		gapsCount = max(0, iconCount + textCount - 1)
		widthAvailable = self.widthAvailableForText(self.size(), iconCount, gapsCount) - self.getCheckMarkSize().width()
		fm = self.fontMetrics()
		return fm.elidedText(self.text(), self.elideMode(), widthAvailable, Qt.TextShowMnemonic)

	@CrashReportWrapped
	def setText(self, text: str) -> None:
		if self.text() != text:
			super(CatCheckBox, self).setText(text)
			self._staticText.setText(text)
			self.refresh()

	def refresh(self) -> None:
		self._layoutContents()
		self.update()

	def _layoutContents(self) -> None:
		if self.text():
			sdm = self.smallDefaultMargins
			self._margins = (0, sdm[1], sdm[2], sdm[3])
		else:
			self._margins = (0, 0, 0, 0)

		rect = self.rect()

		text = self._staticText if self._useStaticText else self.getElidedText()
		hasIcon = not self.icon().isNull()
		font = self.font()

		checkMarkSize = self.getCheckMarkSize()
		checkMarkRect = self.getCheckMarkRect(rect)

		textSize = self.getTextSize(text, font)
		textRect = QRect(
			checkMarkRect.right()+1 + self.getDefaultIconPadding(),
			self.getTextTop(rect, font),
			textSize.width(),
			textSize.height()
		)

		cornerRadius = self._cornerRadius * self._scale
		borderPath = getBorderPath(checkMarkRect, cornerRadius, CORNERS.ALL)
		borderPath2 = getBorderPath(checkMarkRect.adjusted(1, 1, -1, -1), max(0., cornerRadius - 1), CORNERS.ALL)

		scale = self._scale
		p1 = QPointF( 3.75 * scale,  7.75 * scale) + checkMarkRect.topLeft()
		p2 = QPointF( 6 * scale, 10.333 * scale) + checkMarkRect.topLeft()
		p3 = QPointF(10 * scale,  4 * scale) + checkMarkRect.topLeft()
		checkMark = QPolygonF((p1, p2, p3))

		p1 = QPointF(3.5 * scale,  checkMarkRect.height() / 2) + checkMarkRect.topLeft()
		p2 = QPointF(checkMarkRect.width() - 3.5 * scale, checkMarkRect.height() / 2) + checkMarkRect.topLeft()
		partiallyMark = QPolygonF((p1, p2))

		self._checkMarkRect: QRect = checkMarkRect
		self._textRect: QRect = textRect
		self._borderPath: QPainterPath = borderPath
		self._borderPath2: QPainterPath = borderPath2
		self._checkMark: QPolygonF = checkMark
		self._partiallyMark: QPolygonF = partiallyMark

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		iconCount = 0
		textCount = 0 if not self.text() else 1
		gapsCount = max(0, iconCount + textCount - 1 + 1)
		if self._useStaticText:
			text = self._staticText
			text.prepare(font=self.font())
		else:
			text = self.text()

		ds = self.getDefaultSize(text, iconCount, gapsCount)
		if not self.text():
			ds.setHeight(self.minimumSizeHint().height())
		ds.setWidth(ds.width() + self.getCheckMarkSize().width())
		return ds

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		mg = self.qMargins
		minSize = self.getCheckMarkSize().grownBy(mg)
		return minSize
		# return self.getDefaultMinimumSize()

	@CrashReportWrapped
	def resizeEvent(self, event: QResizeEvent) -> None:
		super(CatCheckBox, self).resizeEvent(event)
		self.refresh()

	@CrashReportWrapped
	def hitButton(self, pos: QPoint) -> bool:
		return self.rect().contains(pos)

	def _updateColorPalette(self) -> None:
		checkState = self.checkState()
		if checkState == Qt.Checked:
			colorPalette = self._checkedColorPalette
		elif checkState == Qt.Unchecked:
			colorPalette = self._normalColorPalette
		else:  # checkState == Qt.PartiallyChecked:
			colorPalette = self._partiallyColorPalette
		self._colorPalette = colorPalette

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		self._updateColorPalette()
		drawLayoutBorders = False

		self.updateScaleFromFontMetrics()
		rect = self.rect()
		borderWidth = 1.
		font = self.font()
		bkgBrush = self.getPressedBackgroundBrush(rect) if self.isDown() else self.getBackgroundBrush(rect)
		textColor = self._fromCS(self._normalColorPalette.textColor)
		checkMarkColor = self.getTextBrush()
		borderBrush = self.getBorderBrush()
		borderBrush2 = self.getBorderBrush2()
		borderPen = QPen(borderBrush, borderWidth)
		borderPen2 = QPen(borderBrush2, borderWidth)
		if drawLayoutBorders:
			layoutBorderPen = getLayoutBorderPen(self)
		else:
			layoutBorderPen = None

		# do drawing:
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.setPen(borderPen)
			p.setBrush(bkgBrush)
			p.drawPath(self._borderPath)

			p.setPen(borderPen2)
			p.setBrush(Qt.NoBrush)
			p.drawPath(self._borderPath2)

			checkState = self.checkState()
			if checkState == Qt.Checked:
				scale = self._scale
				p.setPen(QPen(checkMarkColor, 1.5 * scale, cap=Qt.RoundCap))
				p.drawPolyline(self._checkMark)
			elif checkState == Qt.PartiallyChecked:
				scale = self._scale
				p.setPen(QPen(checkMarkColor, 1.75 * scale, cap=Qt.RoundCap))
				p.drawPolyline(self._partiallyMark)
			else:  # checkState == Qt.PartiallyChecked:
				pass

			if self.text():
				p.setPen(QPen(textColor, 1))
				p.setFont(font)
				if self._useStaticText:
					text = self._staticText
					p.drawStaticText(self._textRect.topLeft(), text)
				else:
					text = self.getElidedText()
					p.drawText(self._textRect, Qt.TextShowMnemonic, text)

				if drawLayoutBorders:
					p.setPen(layoutBorderPen)
					p.setBrush(Qt.NoBrush)
					p.drawRect(QRectF(self._textRect).adjusted(0.5, 0.5, -0.5, -0.5))

			if drawLayoutBorders:
				p.setPen(layoutBorderPen)
				p.setBrush(Qt.NoBrush)
				p.drawRect(QRectF(rect.marginsRemoved(self.qMargins)).adjusted(0.5, 0.5, -0.5, -0.5))


class CatRadioButton(CatFocusableMixin, ShortcutMixin, QRadioButton, CatSizePolicyMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None):
		super(QRadioButton, self).__init__(parent=parent)
		self.setCheckable(True)
		self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
		self.setMargins(self.smallDefaultMargins)
		self._elideMode: Qt.TextElideMode = Qt.ElideNone
		self._staticText: QStaticText = QStaticText()
		self._normalColorPalette: ColorPalette = palettes.buttonColorPalette
		#self._partiallyColorPalette: ColorPalette = palettes.defaultButtonColorPalette
		self._checkedColorPalette: ColorPalette = palettes.defaultButtonColorPalette
		self._colorPalette = palettes.buttonColorPalette
		self._cornerRadius: int = 2
		self._highlightOnHover = True
		self._highlightOnFocus = True
		self._layoutContents()

	# @property
	# def overlapCharacteristics(self) -> OverlapCharacteristics:
	# 	return CANT_AND_NO_OVERLAP

	@property
	def _baseIconHeight(self) -> int:
		return 14

	def elideMode(self) -> Qt.TextElideMode:
		return self._elideMode

	def setElideMode(self, mode: Qt.TextElideMode) -> None:
		self._elideMode = mode
		self.update()

	@property
	def _useStaticText(self) -> bool:
		return self._elideMode == Qt.ElideNone

	def getCheckMarkSize(self) -> QSize:
		checkMarkWidth = int(self._baseIconHeight * self._scale)
		return QSize(checkMarkWidth, checkMarkWidth)

	def getCheckMarkRect(self, rect: QRect) -> QRect:
		contentRect = rect.marginsRemoved(self.qMargins)
		checkMarkSize = self.getCheckMarkSize()
		checkMarkTop = ceil(contentRect.y() + contentRect.height() / 2 - checkMarkSize.height() / 2)
		checkMarkRect = QRect(
			contentRect.left(),
			checkMarkTop,
			checkMarkSize.width(),
			checkMarkSize.height()
		)
		return checkMarkRect

	def getElidedText(self) -> str:
		iconCount = 0
		textCount = 0 if not self.text() else 1
		gapsCount = max(0, iconCount + textCount - 1)
		widthAvailable = self.widthAvailableForText(self.size(), iconCount, gapsCount) - self.getCheckMarkSize().width()
		fm = self.fontMetrics()
		return fm.elidedText(self.text(), self.elideMode(), widthAvailable, Qt.TextShowMnemonic)

	@CrashReportWrapped
	def setText(self, text: str) -> None:
		if self.text() != text:
			super(CatRadioButton, self).setText(text)
			self._staticText.setText(text)
			self.refresh()

	def refresh(self) -> None:
		self._layoutContents()
		self.update()

	def _layoutContents(self) -> None:
		if self.text():
			sdm = self.smallDefaultMargins
			self._margins = (0, sdm[1], sdm[2], sdm[3])
		else:
			self._margins = (0, 0, 0, 0)

		rect = self.rect()

		text = self._staticText if self._useStaticText else self.getElidedText()
		hasIcon = not self.icon().isNull()
		font = self.font()

		checkMarkSize = self.getCheckMarkSize()
		checkMarkRect = self.getCheckMarkRect(rect)

		textSize = self.getTextSize(text, font)
		textRect = QRect(
			checkMarkRect.right()+1 + self.getDefaultIconPadding(),
			self.getTextTop(rect, font),
			textSize.width(),
			textSize.height()
		)

		cornerRadius = checkMarkSize.height() / 2
		borderPath = getBorderPath(checkMarkRect, cornerRadius, CORNERS.ALL)
		borderPath2 = getBorderPath(checkMarkRect.adjusted(1, 1, -1, -1), max(0., cornerRadius - 1), CORNERS.ALL)

		checkMark = QRectF(checkMarkRect).adjusted(
			checkMarkSize.width() / 3, checkMarkSize.height() / 3,
			-checkMarkSize.width() / 3, -checkMarkSize.height() / 3
		)

		self._checkMarkRect: QRect = checkMarkRect
		self._textRect: QRect = textRect
		self._borderPath: QPainterPath = borderPath
		self._borderPath2: QPainterPath = borderPath2
		self._checkMark: QRectF = checkMark

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		iconCount = 0
		textCount = 0 if not self.text() else 1
		gapsCount = max(0, iconCount + textCount - 1 + 1)
		if self._useStaticText:
			text = self._staticText
			text.prepare(font=self.font())
		else:
			text = self.text()

		ds = self.getDefaultSize(text, iconCount, gapsCount)
		if not self.text():
			ds.setHeight(self.minimumSizeHint().height())
		ds.setWidth(ds.width() + self.getCheckMarkSize().width())
		return ds

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		mg = self.qMargins
		minSize = self.getCheckMarkSize().grownBy(mg)
		return minSize
		# return self.getDefaultMinimumSize()

	@CrashReportWrapped
	def resizeEvent(self, event: QResizeEvent) -> None:
		super(CatRadioButton, self).resizeEvent(event)
		self.refresh()

	@CrashReportWrapped
	def hitButton(self, pos: QPoint) -> bool:
		return self.rect().contains(pos)

	def _updateColorPalette(self) -> None:
		if self.isChecked():
			colorPalette = self._checkedColorPalette
		else:
			colorPalette = self._normalColorPalette
		self._colorPalette = colorPalette

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		self._updateColorPalette()
		drawLayoutBorders = False

		self.updateScaleFromFontMetrics()
		rect = self.rect()
		borderWidth = 1.
		font = self.font()
		bkgBrush = self.getPressedBackgroundBrush(rect) if self.isDown() else self.getBackgroundBrush(rect)
		textColor = self._fromCS(self._normalColorPalette.textColor)
		checkMarkColor = self.getTextBrush()
		borderBrush = self.getBorderBrush()
		borderBrush2 = self.getBorderBrush2()
		borderPen = QPen(borderBrush, borderWidth)
		borderPen2 = QPen(borderBrush2, borderWidth)
		if drawLayoutBorders:
			layoutBorderPen = getLayoutBorderPen(self)
		else:
			layoutBorderPen = None


		# do drawing:
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.setPen(borderPen)
			p.setBrush(bkgBrush)
			p.drawPath(self._borderPath)

			p.setPen(borderPen2)
			p.setBrush(Qt.NoBrush)
			p.drawPath(self._borderPath2)

			if self.isChecked():
				scale = self._scale
				p.setPen(Qt.NoPen)
				p.setBrush(checkMarkColor)
				p.drawEllipse(self._checkMark)

			if self.text():
				p.setPen(QPen(textColor, 1))
				p.setFont(font)
				if self._useStaticText:
					text = self._staticText
					p.drawStaticText(self._textRect.topLeft(), text)
				else:
					text = self.getElidedText()
					p.drawText(self._textRect, Qt.TextShowMnemonic, text)

				if drawLayoutBorders:
					p.setPen(layoutBorderPen)
					p.setBrush(Qt.NoBrush)
					p.drawRect(QRectF(self._textRect).adjusted(0.5, 0.5, -0.5, -0.5))

			if drawLayoutBorders:
				p.setPen(layoutBorderPen)
				p.setBrush(Qt.NoBrush)
				p.drawRect(QRectF(rect.marginsRemoved(self.qMargins)).adjusted(0.5, 0.5, -0.5, -0.5))


class CatProgressBar(QWidget, CatSizePolicyMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

		self._maximum: int = 100
		self._minimum: int = 0
		self._value: int = -1
		self._format: str = ''
		self._textVisible: bool = True
		self._orientation: Qt.Orientation = Qt.Horizontal
		self.setColorPalette(palettes.progressBarColorPalette)

	def maximum(self) -> int:
		return self._maximum

	def setMaximum(self, maximum: int) -> None:
		self.setRange(min(self._minimum, maximum), maximum)

	def minimum(self) -> int:
		return self._minimum

	def setMinimum(self, minimum: int) -> None:
		self.setRange(minimum, max(self._maximum, minimum))

	def setRange(self, minimum: int, maximum: int) -> None:
		if self._minimum != minimum or self._maximum != maximum:
			self._minimum = minimum
			self._maximum = maximum
			self._refresh()

	valueChanged = pyqtSignal(int)

	def value(self) -> int:
		return self._value

	def setValue(self, value: int) -> None:
		if self._value != value and value in range(self._minimum, self._maximum+1):
			self._value = value
			safeEmit(self, self.valueChanged, value)
			self._refresh()

	def reset(self) -> None:
		self._value = self._minimum - 1
		self._refresh()

	def _progress(self) -> float:
		stepCount = self._maximum - self._minimum
		if stepCount != 0:
			percentage = (self._value - self._minimum) / stepCount
		else:
			percentage = 1.
		return percentage

	def text(self) -> str:
		stepCount = self._maximum - self._minimum
		if stepCount != 0:
			percentage = int(round(self._progress() * 100))
		else:
			percentage = 100

		text = self._format\
			.replace('%m', str(stepCount))\
			.replace('%v', str(self._value))\
			.replace('%p', str(percentage))
		return text

	def format(self) -> str:
		return self._format

	def setFormat(self, format: str) -> None:
		if self._format != format:
			self._format = format
			self._refresh()

	def resetFormat(self) -> None:
		self.setFormat('%p%')

	def isTextVisible(self) -> bool:
		return self._textVisible

	def setTextVisible(self, visible: bool) -> None:
		if self._textVisible != visible:
			self._textVisible = visible
			self._refresh()

	def orientation(self) -> Qt.Orientation:
		return self._orientation

	def setOrientation(self, orientation: Qt.Orientation) -> None:
		if self._orientation != orientation:
			self._orientation = orientation
			self._refresh()

	def _refresh(self) -> None:
		self.update()

	@CrashReportWrapped
	def sizeHint(self):
		return self.getDefaultSize(self.text())

	@CrashReportWrapped
	def resizeEvent(self, event):
		super().resizeEvent(event)
		self.updateScaleFromFontMetrics()

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event):
		rect = self.rect()
		# get Colors:
		bkgBrush = self.getBackgroundBrush(rect)
		borderPen = QPen(self.getBorderBrush(), 1)

		progressBrush = self.getIndicatorBrush(rect)
		progressBorderPen = QPen(self.getIndicatorBorderBrush(), 1)

		textPen1 =  QPen(self.getTextBrush(), 1)
		textPen2 =  QPen(self.getTextBrush(), 1)

		text = self.text()

		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			rect = self.rect()
			barHeight = 4 * self._scale

			borderRect = QRectF(
				rect.left(),
				rect.top() + (rect.height() - barHeight) / 2,
				rect.width(),
				barHeight
			)
			radius = 0. * self._scale + borderRect.height() * 0.5

			p.setPen(borderPen)
			p.setBrush(bkgBrush)
			p.drawRoundedRect(borderRect, radius, radius)

			p.setPen(textPen1)
			textRect = QRectF(
				borderRect.left(),
				self.getTextTop(rect),
				borderRect.width(),
				self.getTextSize(text).height()
			)
			textRect = QRectF(p.boundingRect(textRect, Qt.AlignVCenter | Qt.AlignCenter, text))

			p.setPen(textPen1)
			p.drawText(textRect, text)

			progress = self._progress()
			progressRect = QRectF(borderRect)
			progressRect.setWidth(progressRect.width() * progress)
			p.setPen(progressBorderPen)
			p.setBrush(progressBrush)
			p.drawRoundedRect(progressRect, radius, radius)

			textRect2 = textRect.intersected(progressRect)
			textRect2.setTop(textRect.top())
			textRect2.setHeight(textRect.height())
			p.setPen(textPen2)
			p.drawText(textRect2, text)


class Spoiler(CatFocusableMixin, ShortcutMixin, CatClickableMixin, QWidget, CatScalableWidgetMixin, CatStyledWidgetMixin):

	def __init__(self, parent=None, title=''):

		super(Spoiler, self).__init__(parent=parent)

		self._title: str = title
		self._open: bool = False
		self._drawDisabled: bool = False
		mgs = self.smallDefaultMargins
		self.setMargins((0, mgs[1], mgs[2], mgs[3]))
		sp = self.sizePolicy()
		sp.setVerticalPolicy(QSizePolicy.Fixed)
		self.setSizePolicy(sp)
		self.setColorPalette(palettes.framelessButtonColorPalette)

	def title(self):
		return self._title

	def setTitle(self, title: str):
		self._title = title

	def isOpen(self):
		return self._open

	def setOpen(self, isOpen):
		self._open = isOpen
		self.update()

	def isDrawDisabled(self):
		return self._drawDisabled

	def setDrawDisabled(self, isDrawDisabled):
		self._drawDisabled = isDrawDisabled
		self.update()

	@CrashReportWrapped
	def mouseReleaseEvent(self, event: QMouseEvent):
		if not sip.isdeleted(self):
			self.setOpen(not self.isOpen())
			event.accept()
			super(Spoiler, self).mouseReleaseEvent(event)

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		iconCount = 1
		gapsCount = 1 if self.title() else 0
		ds = self.getDefaultSize(self.title(), iconCount, gapsCount, self.font())
		return ds

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		return self.getDefaultMinimumSize(self.font())

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, paintEvent: QPaintEvent):
		drawLayoutBorders = False
		self.updateScaleFromFontMetrics()

		if self._drawDisabled and not drawLayoutBorders:
			return

		if drawLayoutBorders:
			layoutBorderPen = getLayoutBorderPen(self)
		else:
			layoutBorderPen = None

		rect = self.rect()
		font = self.font()

		# layout elements:
		text = self.title()

		translation = 0*self.qMargins.left()

		iconSize = self.getDefaultIconSize()
		iconRect = QRectF(
			translation,
			self.getIconTop(rect)+0,
			iconSize.width(),
			iconSize.height()
		)

		textSize = self.getTextSize(text, font)
		textRect = QRectF(
			iconRect.right() + 1 + self.getDefaultIconPadding(),
			self.getTextTop(rect, font),
			textSize.width(),
			textSize.height()
		)

		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing)
			w = iconRect.width()
			h = iconRect.height()
			t = int(iconRect.top() + h * 0.25) + 0.5
			b = int(iconRect.bottom() - h * 0.25) - 0.5
			l = int(iconRect.left() + w * 0.25) + 0.5
			r = int(iconRect.right() - w * 0.25) - 0.5
			if self.isOpen():
				points = (QPointF(l, t), QPointF(r, t), QPointF((l+r)/2.0, b))
			else:
				points = (QPointF(l, b), QPointF(l, t), QPointF(r, (t+b)/2))
			if not self._drawDisabled:
				brush = self.getIconBrush()
				pen = QPen(brush.color())
				pen.setJoinStyle(Qt.SvgMiterJoin)
				pen.setMiterLimit(5)
				p.setPen(pen)
				p.setBrush(brush)
				p.drawPolygon(*points)

				p.setPen(QPen(self.getTextBrush().color(), 1))
				p.drawText(textRect, Qt.TextShowMnemonic, self._title)

			if drawLayoutBorders:
				p.setPen(layoutBorderPen)
				p.setBrush(Qt.NoBrush)
				p.drawRect(iconRect)
				p.drawRect(textRect)

				p.setPen(Pens.red)
				p.drawRect(self.rect())


class CatBox(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self._radius: float = 10.

	def radius(self) -> float:
		return self._radius

	def setRadius(self, radius: float):
		self._radius = radius

	@PaintEventDebug
	def paintEvent(self, event):
		# get Colors:
		palette = self.palette()
		if self.isEnabled():
			palette.setCurrentColorGroup(QPalette.Normal)
		else:
			palette.setCurrentColorGroup(QPalette.Disabled)

		bkg_opacity = 1.0
		text_opacity = 1.0
		bkg_brush = palette.window()
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.setPen(Qt.NoPen)

			p.setBrush(bkg_brush)
			p.setOpacity(bkg_opacity)
			p.drawRoundedRect(
				0,
				0,
				self.width(),
				self.height(),
				self.radius(),
				self.radius(),
			)


class DataTableModel(QAbstractTableModel):
	def __init__(self, parent, headers = ()):
		QAbstractTableModel.__init__(self, parent)
		self.tableData = []
		self.headers = headers

	def _numRows(self):
		"""
		:return: number of rows with data
		"""
		return len(self.tableData)

	def _getRow(self, row):
		"""
		:param row: int of the row to get 
		:return: data of the row
		"""
		return self.tableData[row] if row < self._numRows() else [""] * self.columnCount()

	def _isRowEmpty(self, row):
		"""
		checks if the row is empty
		:param row: int of the row to check
		:return: true if row is empty
		"""
		return all(not str(v).strip() for v in self._getRow(row))

	def _removeTrailingEmptyRows(self):
		"""
		remove all rows at the end of the table that are empty
		"""
		for row in reversed(range(self._numRows())):
			if self._isRowEmpty(row):
				del self.tableData[row]
			else:
				break

	def _removeEmptyRows(self):
		"""
		remove all empty rows 
		"""
		for row in reversed(range(self._numRows())):
			if self._isRowEmpty(row):
				del self.tableData[row]

	def _ensureHasRows(self, numRows):
		"""
		ensure the table has numRows
		:param numRows:  number of rows that should exist
		"""
		while self._numRows() < numRows:
			self.tableData.append([""] * self.columnCount())

	def _setCellText(self, row, col, text):
		"""
		set the text of a cell
		:param row: row of the cell
		:param col: column of the cell
		:param text: text for the cell
		"""
		self._ensureHasRows(row + 1)
		self.tableData[row][col] = str(text).strip()

	def _getCellText(self, row, col):
		"""
		get the text of a cell
		:param row: row of the cell
		:param col: column of the cell
		:return: text of the cell
		"""
		return str(self._getRow(row)[col]).strip()

	# reimplemented QAbstractTableModel methods

	selectCell = pyqtSignal(QModelIndex)

	def emptyCells(self, indexes):
		"""
		empty the cells with the indexes
		:param indexes: indexes of the cells to be emptied
		"""
		for index in indexes:
			row = index.row()
			col = index.column()

			self._setCellText(row, col, "")

		self._removeEmptyRows()
		self.beginResetModel()
		self.endResetModel()
		# indexes is never empty
		safeEmit(self, self.selectCell, indexes[0])

	@CrashReportWrapped
	def rowCount(self, _=QModelIndex()):
		"""
		number of rows
		:return: returns the number of rows
		"""
		# one additional row for new data
		return self._numRows() + 1

	@CrashReportWrapped
	def columnCount(self, _=QModelIndex()):
		"""
		number of columns
		:return: number of columns
		"""
		return len(self.headers)

	@CrashReportWrapped
	def headerData(self, selection, orientation, role):
		"""
		header of the selection
		:param selection: selected cells
		:param orientation: orientation of selection
		:param role: role of the selection
		:return: header of the selection
		"""
		if Qt.Horizontal == orientation and Qt.DisplayRole == role:
			return self.headers[selection]
		return None

	@CrashReportWrapped
	def data(self, index, role):
		"""
		data of the cell
		:param index: index of the cell
		:param role: role of the cell
		:return: data of the cell
		"""
		if Qt.DisplayRole == role or Qt.EditRole == role:
			return self._getCellText(index.row(), index.column())
		return None

	@CrashReportWrapped
	def setData(self, index, text, _):
		"""
		set text in the cell
		:param index: index of the cell
		:param text: text for the cell
		:return: true if data is set
		"""
		row = index.row()
		col = index.column()

		self._setCellText(row, col, text)
		self._removeTrailingEmptyRows()

		self.beginResetModel()
		self.endResetModel()

		# move selection to the next column or row
		col = col + 1

		if col >= self.columnCount():
			row = row + 1
			col = 0

		row = min(row, self.rowCount() - 1)
		safeEmit(self, self.selectCell, self.index(row, col))

		return True

	@CrashReportWrapped
	def flags(self, _):
		"""
		flags for the table
		:return: flags
		"""
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable


class DataTableView(CatFocusableMixin, ShortcutMixin, QTableView):
	"""
	View of the tables
	"""

	@CrashReportWrapped
	def keyPressEvent(self, QKeyEvent):
		"""
		reimplemented keyPressEvent for deleting cells and arrows in editing cells 
		:param QKeyEvent: 
		:return: 
		"""
		if self.state() == QAbstractItemView.EditingState:
			index = self.currentIndex()
			if QKeyEvent.key() in [Qt.Key_Down, Qt.Key_Up]:
				self.setFocus(Qt.ShortcutFocusReason)
				self.setCurrentIndex(self.model().index(index.row(), index.column()))
			else:
				QTableView.keyPressEvent(self, QKeyEvent)
		if QKeyEvent.key() in [Qt.Key_Delete, Qt.Key_Backspace]:
			self.model().emptyCells(self.selectedIndexes())
		else:
			QTableView.keyPressEvent(self, QKeyEvent)


class HTMLDelegate2(QStyledItemDelegate):

	def _makeDoc(self, options: QStyleOptionViewItem) -> QTextDocument:
		doc = QTextDocument()
		doc.setDocumentMargin(2)
		doc.setDefaultFont(options.font)
		doc.setHtml(options.text)
		return doc

	@CrashReportWrapped
	def paint(self, painter: QPainter, opt: QStyleOptionViewItem, index: QModelIndex) -> None:
		options = QStyleOptionViewItem(opt)
		self.initStyleOption(options, index)
		doc = self._makeDoc(options)

		style = QApplication.style() if options.widget is None else options.widget.style()

		options.text = ""
		style.drawControl(QStyle.CE_ItemViewItem, options, painter)

		ctx = QAbstractTextDocumentLayout.PaintContext()

		# Highlighting text if item is selected
		if options.state & QStyle.State_Selected and options.state & QStyle.State_Active:
			ctx.palette.setColor(QPalette.Text, options.palette.color(QPalette.Active, QPalette.HighlightedText))

		textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options)
		textRect.setRight(textRect.right() - 2)

		docHeight = int(doc.size().height())
		if docHeight < textRect.height():
			textRect.setY(textRect.y() + (textRect.height() - docHeight) // 2)

		painter.save()
		painter.translate(textRect.topLeft())
		painter.setClipRect(textRect.translated(-textRect.topLeft()))
		doc.documentLayout().draw(painter, ctx)

		painter.restore()

	@CrashReportWrapped
	def sizeHint(self, opt: QStyleOptionViewItem, index: QModelIndex):
		options = QStyleOptionViewItem(opt)
		self.initStyleOption(options, index)
		doc = self._makeDoc(options)
		width = int(doc.idealWidth())
		height = int(doc.size().height())

		if options.features & QStyleOptionViewItem.HasDecoration:
			iconSize = options.decorationSize
			height = max(height, iconSize.height())
			width += iconSize.width() + CatScalableWidgetMixin._baseIconPadding.__get__(self, None)

		return QSize(width, height)


class HTMLDelegate(QStyledItemDelegate):

	def __init__(self):
		super(HTMLDelegate, self).__init__()

	def _makeDoc(self, options: QStyleOptionViewItem) -> QTextDocument:
		doc = QTextDocument()
		doc.setDocumentMargin(2)
		doc.setDefaultFont(options.font)
		doc.setHtml(options.text)
		return doc

	@classmethod
	def _getStaticText(cls, index: QModelIndex) -> QStaticText:
		treeItem = index.internalPointer()

		if hasattr(treeItem, 'displayCache'):
			displayCache = treeItem.displayCache
			if not isinstance(displayCache, list):
				treeItem.displayCache = displayCache = []

			col = index.column()
			if len(displayCache) < col + 1:
				for i in range(len(displayCache), col + 1):
					displayCache.append(None)

			if isinstance(displayCache[col], QStaticText):
				displayColCache = displayCache[col]
				# TODO: check for changes in text, icon, etc...
				pass
			else:
				displayColCache = displayCache[col] = QStaticText()
				cls._updateStaticText(displayColCache, treeItem, col)

		else:
			displayColCache = QStaticText()

		return displayColCache

	@staticmethod
	def _updateStaticText(staticText: QStaticText, treeItem: TreeItemBase, col: int) -> None:
		staticText.setText(treeItem.label(col))
		staticText.setTextFormat(Qt.RichText)
		txtOption = QTextOption()
		shouldWrap = False  # option.features & QStyleOptionViewItem.WrapText == QStyleOptionViewItem.WrapText
		wrapMode = QTextOption.WrapAtWordBoundaryOrAnywhere if shouldWrap else QTextOption.NoWrap
		txtOption.setWrapMode(wrapMode)
		staticText.setTextOption(txtOption)

	@CrashReportWrapped
	def paint(self, painter: QPainter, opt: QStyleOptionViewItem, index: QModelIndex) -> None:
		options = QStyleOptionViewItem(opt)
		staticText = self._getStaticText(index)

		isHighlighted = options.state & QStyle.State_Selected
		# Highlighting text if item is selected
		if isHighlighted:
			txtColor = options.palette.highlightedText().color()
			bkgBrush = options.palette.highlight()
		else:
			txtColor = options.palette.text().color()
			bkgBrush = options.palette.base()

		painter.setBrush(bkgBrush)
		painter.setPen(Qt.NoPen)
		painter.drawRect(options.rect)

		rectRemaining = QRectF(options.rect)
		rectRemaining.adjust(+2, +1, -2, -1)

		painter.setPen(txtColor)
		icon: QIcon = index.internalPointer().icon(index.column())
		hasIcon = icon is not None and not icon.isNull()
		if hasIcon:
			mode = QIcon.Active if isHighlighted else QIcon.Normal
			mode = QIcon.Selected if isHighlighted else mode
			mode = mode if options.state & QStyle.State_Enabled else QIcon.Disabled

			iconSize = QSizeF(options.decorationSize)
			iconTopLeft = QPointF(
				rectRemaining.left(),
				rectRemaining.top() + max(0, (rectRemaining.height() - iconSize.height()) / 2)
			)
			iconRect = QRectF(iconTopLeft, iconSize)
			iconPadding = CatScalableWidgetMixin._baseIconPadding.__get__(self, None)
			rectRemaining.setLeft(iconRect.right() + iconPadding)

			pixmap = icon.pixmap(
				iconSize.toSize(),
				mode=mode,
				state=QIcon.Off  # QIcon.On if options.checkState == Qt.Checked else QIcon.Off
			)
			painter.drawPixmap(iconRect.toRect(), pixmap)

		txtClipRect = QRectF(rectRemaining)

		docHeight = staticText.size().height()
		if docHeight < txtClipRect.height():
			txtClipRect.setY(txtClipRect.y() + (txtClipRect.height() - docHeight) // 2)

		painter.save()
		painter.setClipRect(txtClipRect)
		painter.drawStaticText(txtClipRect.topLeft(), staticText)
		painter.restore()

	@CrashReportWrapped
	def sizeHint(self, opt: QStyleOptionViewItem, index: QModelIndex):
		options = QStyleOptionViewItem(opt)
		staticText = self._getStaticText(index)
		options.text = staticText.text()
		doc = self._makeDoc(options)

		width = int(doc.idealWidth())
		height = int(doc.size().height())

		icon = index.internalPointer().icon(index.column())
		hasIcon = icon is not None and not icon.isNull()
		if hasIcon:
			iconSize = options.decorationSize
			height = max(height, iconSize.height())
			width += iconSize.width() + CatScalableWidgetMixin._baseIconPadding.__get__(self, None)

		return QSize(width + 4, height + 2)


class BuilderTreeView(CatFocusableMixin, ShortcutMixin, CatFramedAbstractScrollAreaMixin, QTreeView, CatStyledWidgetMixin):
	def __init__(self, parent: Optional[QObject] = None):
		super().__init__(parent)
		self._roundedCorners = CORNERS.NONE
		self._colorPalette = palettes.inputColorPalette
		self.setLineWidth(1)
		treeModel = self._makeTreeModel()
		treeModel._loadDeferred: bool = True
		self.setModel(treeModel)
		self.setMinimumWidth(150)
		self.setContextMenuPolicy(Qt.CustomContextMenu)
		self.setIndentation(self.indentation() * 2 // 3)
		connectSafe(self.customContextMenuRequested, lambda pos, s=self: s.onContextMenu(pos))
		QShortcut(QKeySequence.Copy,  self, lambda s=self: s.onCopy(), lambda: None, Qt.WidgetShortcut)
		QShortcut(QKeySequence.Paste, self, lambda s=self: s.onPaste(), lambda: None, Qt.WidgetShortcut)
		QShortcut(QKeySequence.Cut,   self, lambda s=self: s.onCut(), lambda: None, Qt.WidgetShortcut)
		QShortcut(QKeySequence.Delete,   self, lambda s=self: s.onDelete(), lambda: None, Qt.WidgetShortcut)
		# QShortcut(Qt.Key_Return,      self, lambda s=self: s.onDoubleClick(self.currentIndex()), lambda: None, Qt.WidgetShortcut)
		# QShortcut(Qt.Key_Enter,       self, lambda s=self: s.onDoubleClick(self.currentIndex()), lambda: None, Qt.WidgetShortcut)
		self._pressedIndex: Optional[QModelIndex] = None

	dataChanged = pyqtSignal()

	def _makeTreeModel(self) -> TreeModel:
		return TreeModel(self.selectionModel(), self)

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		super(BuilderTreeView, self).paintEvent(event)
		self.paintFrameOnWidget(event, self.viewport())

	def getBorderBrushes(self, rect: QRect) -> tuple[QBrush, QBrush, QBrush]:
		return self.getBorderBrush(), QBrush(Qt.NoBrush), QBrush(Qt.NoBrush)

	def loadDeferred(self) -> bool:
		return self.model()._loadDeferred

	def setLoadDeferred(self, v: bool):
		self.model()._loadDeferred = v

	def onDoubleClick(self, index: QModelIndex) -> bool:
		if index.isValid():
			return index.internalPointer().onDoubleClick()
		else:
			return False

	@CrashReportWrapped
	def onCopy(self):
		index = self.selectionModel().currentIndex()
		if index.isValid():
			data = index.internalPointer().onCopy()
			if data is not None:
				QApplication.clipboard().setText(data)

	@CrashReportWrapped
	def onCut(self):
		index = self.selectionModel().currentIndex()
		if index.isValid():
			data = index.internalPointer().onCut()
			if data is not None:
				QApplication.clipboard().setText(data)
				safeEmit(self, self.dataChanged, )

	@CrashReportWrapped
	def onPaste(self):
		treeItem: Optional[TreeItemBase] = None

		sm: QItemSelectionModel = self.selectionModel()
		index = sm.currentIndex()

		if index.isValid():
			treeItem = index.internalPointer()

		if not sm.hasSelection():
			treeItem = self.model().rootItem

		if treeItem is not None:
			data = QApplication.clipboard().text()
			treeItem.onPaste(data)
			safeEmit(self, self.dataChanged, )
			sm.emitSelectionChanged(sm.selection(), QItemSelection())

	@CrashReportWrapped
	def onDelete(self):
		index = self.selectionModel().currentIndex()
		if index.isValid():
			index.internalPointer().onDelete()

	@CrashReportWrapped
	def onContextMenu(self, pos: QPoint):
		accurateGlobalPos = QCursor.pos()
		accuratePos = self.viewport().mapFromGlobal(accurateGlobalPos)
		index: QModelIndex = self.indexAt(accuratePos)
		if index.isValid():
			index.internalPointer().onContextMenu(index.column(), self.viewport().mapToGlobal(pos))

	def _getIndexLevel(self, index: QModelIndex) -> int:
		depth = 0
		while index.parent().isValid():
			index = index.parent()
			depth += 1
		return depth

	def _expandOrCollapseItemAtPos(self, pos: QPoint, index: QModelIndex) -> bool:
		# we want to handle mousePress in EditingState (persistent editors)
		if self.state() not in (QAbstractItemView.NoState, QAbstractItemView.EditingState) \
				or not self.viewport().rect().contains(pos):
			return True

		level = self._getIndexLevel(index)
		if self.rootIsDecorated():
			level += 1
		indent = level * self.indentation()

		position = self.header().sectionViewportPosition(self.header().logicalIndex(0))
		indent += position

		isInDecoration = (indent - self.indentation()) <= pos.x() < indent

		if isInDecoration and self.model().hasChildren(index) and self.itemsExpandable():
			if self.isExpanded(index):
				self.collapse(index)
			else:
				self.expand(index)
			return True
		return False

	@CrashReportWrapped
	def event(self, event: QEvent) -> bool:
		if event.type() == QEvent.ShortcutOverride:
			event: QKeyEvent = cast(QKeyEvent, event)
			if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() == Qt.NoModifier:
				if self.onDoubleClick(self.currentIndex()):
					event.accept()
					return True
		return super(BuilderTreeView, self).event(event)

	@CrashReportWrapped
	def mousePressEvent(self, event: QMouseEvent):
		oldSelection: QItemSelection = self.selectionModel().selection()
		index: QModelIndex = self.indexAt(event.pos())

		self._pressedIndex = index
		handled = False
		handled = self._expandOrCollapseItemAtPos(event.pos(), index)
		if not handled:
			if index.row() == -1 and index.column() == -1:
				self.clearSelection()
				self.selectionModel().setCurrentIndex(QModelIndex(), QItemSelectionModel.Select)
				self.selectionModel().emitSelectionChanged(QItemSelection(), oldSelection)
			else:
				self.selectionModel().setCurrentIndex(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

	@CrashReportWrapped
	def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
		index: QModelIndex = self.indexAt(event.pos())
		self.onDoubleClick(index)
		super(BuilderTreeView, self).mouseDoubleClickEvent(event)


class DataBuilderTreeView(BuilderTreeView):
	def _makeTreeModel(self) -> TreeModel:
		return DataTreeModel(self.selectionModel(), self)


def distanceToRectSquared(pos: QPoint, rect: QRect) -> int:
	center: QPoint = centerOfRect(rect)
	nearestOnRect = QPoint(
		rect.right() if pos.x() > center.x() else rect.left(),
		rect.bottom() if pos.y() > center.y() else rect.top()
	)
	vector: QPoint = nearestOnRect - pos
	return QPoint.dotProduct(vector, vector)


def findClosestScreen(pos: QPoint, screens: List[QScreen]) -> Optional[QScreen]:
	nearestScreen: Optional[QScreen] = None
	nearestScreenDistanceSqr = +inf

	for screen in screens:
		rect: QRect = screen.availableGeometry()
		screen.virtualGeometry()
		if rect.contains(pos):
			return screen
		distanceSquared = distanceToRectSquared(pos, rect)
		if distanceSquared < nearestScreenDistanceSqr:
			nearestScreenDistanceSqr = distanceSquared
			nearestScreen = screen
	return nearestScreen


def fitToScreen(x: int, y: int, nWidth: int, nHeight: int) -> QRect:
	center = QPoint(x + nWidth // 2, y + nHeight // 2)
	parentsScreen: QScreen = QApplication.screenAt(center)
	if parentsScreen is None:
		parentsScreen = findClosestScreen(center, QApplication.screens())
	screenGeometry: QRect = parentsScreen.availableGeometry()
	maxX = screenGeometry.right() - nWidth
	maxY = screenGeometry.bottom() - nHeight
	minX = screenGeometry.left()
	minY = screenGeometry.top()

	return QRect(
		min(maxX, max(minX, x)),
		max(minY, min(maxY, y)),
		nWidth,
		nHeight
	)


class CatWindowMixin:
	def __init__(self, *args, x: Optional[int] = None, y: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None, **kwargs):
		super().__init__(*args, **kwargs)

		self.setInitialGeometry(x, y, width, height)

	if TYPE_CHECKING:
		def x(self) -> int: ...
		def y(self) -> int: ...
		def height(self) -> int: ...
		def width(self) -> int: ...
		@overload
		def setGeometry(self, a0: QRect) -> None: ...
		@overload
		def setGeometry(self, ax: int, ay: int, aw: int, ah: int) -> None: ...
		def setGeometry(self, *args): ...
		@overload
		def resize(self, a0: QSize) -> None: ...
		@overload
		def resize(self, w: int, h: int) -> None: ...
		def resize(self, *args): ...
		def parentWidget(self) -> QWidget: ...

	def setInitialGeometry(self, x: Optional[int] = None, y: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None):
		# size:
		nWidth = self.width() if width is None else width
		nHeight = self.height() if height is None else height
		# position:
		parent = self.parentWidget()
		if parent is not None:
			parentPos: QPoint = parent.mapToGlobal(QPoint(0, 0))
			centerX = parentPos.x() + parent.width() // 2
			centerY = parentPos.y() + parent.height() // 2
		else:
			centerX = self.x() + nWidth // 2
			centerY = self.y() + nHeight // 2

		centerX = x if x is not None else centerX
		centerY = y if y is not None else centerY

		if parent is None:
			self.resize(nWidth, nHeight)
		else:
			geometry = fitToScreen(centerX - nWidth // 2, centerY - nHeight // 2, nWidth, nHeight)
			self.setGeometry(geometry)


__all__ = [
	'getLayoutBorderPen',
	'CatToolbarSpacer',
	'CatPanel',
	'CatSeparator',
	'CatOverlay',
	'CatLabel',
	'CatElidedLabel',
	'CatTextField',
	'CatMultiLineTextField',
	'CatComboBox',
	'CatScrollArea',
	'Int64SpinBox',
	'CatButton',
	'CatToolButton',
	'CatGradiantButton',
	'CatFramelessButton',
	'Switch',
	'CatCheckBox',
	'CatRadioButton',
	'CatProgressBar',
	'Spoiler',
	'CatBox',
	'DataTableModel',
	'DataTableView',
	'HTMLDelegate',
	'BuilderTreeView',
	'DataBuilderTreeView',
	'distanceToRectSquared',
	'findClosestScreen',
	'fitToScreen',
	'CatWindowMixin',
]
