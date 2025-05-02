from __future__ import annotations

from abc import abstractmethod
from dataclasses import replace
from typing import Callable, Generic, Optional, TYPE_CHECKING, Type, TypeVar, Union

from PyQt5 import QtWidgets, sip
from PyQt5.QtCore import QEvent, QRectF, Qt, pyqtSignal, pyqtSlot, QObject, QPointF
from PyQt5.QtGui import QColor, QHideEvent, QIcon, QPaintEvent, QPainter, QPixmap, QShowEvent, QWindow, qGray, QFont, \
	QFontMetrics, QRadialGradient
from PyQt5.QtWidgets import QLayout, QWidget, qApp

from . import framelessWindowsManager
from .utilities import getDefaultAppIcon
from .._styles import applyStyle, getStyles
from ..utilities import connectSafe
from ...GUI.components.Widgets import CatButton, CatFramelessButton, CatWindowMixin
from ...GUI.components.catWidgetMixins import CLEAR_COLOR_COLOR_SET, CORNERS, ColorSet, DEFAULT_WINDOW_CORNER_RADIUS, INNER_CORNERS, InnerCorners, Margins, NO_MARGINS, Overlap, \
	RoundedCorners, adjustOverlap, joinCorners, joinInnerCorners, joinOverlap, maskCorners, palettes, selectInnerCorners
from ...GUI.enums import SizePolicy
from ...GUI.icons import icons
from ...utils.utils import CrashReportWrapped, runLaterSafe

_SHADOW_MARGINS = 13
_BORDER_SIZE = 9


# PythonGUIWidget:      onGUI, GuiCls, parent
# PythonGUIWindow:      parent, flags, GuiCls, *, x, y, ...
# PythonGUIMainWindow:  GuiCls, flags
# PythonGUIDialog:      parent, flags, GuiCls, *, x, y, ...
# PythonGUIPopupWindow: initVal, guiFunc, GUICls, parent, *, x, y, ...
#
# PythonGUIWidget:               onGUI, GUICls, parent, flags
# PythonGUIWindow:                      GUICls, parent, flags, *, x, y, ...
# PythonGUIMainWindow:                  GUICls, parent, flags, *, x, y, ...
# PythonGUIDialog:                      GUICls, parent, flags, *, x, y, ...
# PythonGUIPopupWindow: initVal, onGUI, GUICls, parent, flags, *, x, y, ...
#
# PythonGUIWindow:      onGUI, GuiCls, parent, flags, *, x, y, ...
# PythonGUIMainWindow:  onGUI, GuiCls, parent, flags

def changeHue(c1: QColor, hue: int) -> QColor:
	c2 = QColor.fromHsvF(hue / 360, c1.hsvSaturationF(), c1.valueF(), c1.alphaF())
	br1 = qGray(c1.rgb())
	br2 = qGray(c2.rgb())
	val3 = c1.valueF() * br1 / br2 if br2 != 0 else c1.valueF()
	val3 = min(1., val3)
	c3 = QColor.fromHsvF(hue / 360, c1.hsvSaturationF(), val3, c1.alphaF())

	return c3


def changeHue2(c1: ColorSet, hue: int) -> ColorSet:
	return ColorSet(
		getNormal=lambda: changeHue(c1.getNormal(), hue),
		getDisabled=lambda: changeHue(c1.getDisabled(), hue),
		getInactive=lambda: changeHue(c1.getInactive(), hue),
		getSelected=lambda: changeHue(c1.getSelected(), hue),
	)


CLEAR_COLOR = QColor(0, 0, 0, 0)


def setNewBorderHue(btn: CatButton, hue: int, useDefault: bool):

	btnDefColorPalette = replace(
		palettes.defaultButtonColorPalette,
		borderColor=changeHue2(palettes.defaultButtonColorPalette.borderColor, hue),
		borderColor2=changeHue2(palettes.defaultButtonColorPalette.borderColor2, hue),
		backgroundColor=changeHue2(palettes.defaultButtonColorPalette.backgroundColor, hue),
		backgroundColor2=changeHue2(palettes.defaultButtonColorPalette.backgroundColor2, hue)
	)

	btnColorPalette = replace(
		palettes.buttonColorPalette,
		borderColor=changeHue2(palettes.buttonColorPalette.borderColor, hue),
		borderColor2=replace(
			changeHue2(palettes.buttonColorPalette.borderColor2, hue),
			getSelected=btnDefColorPalette.borderColor2.getSelected
		),
		backgroundColor=replace(
			CLEAR_COLOR_COLOR_SET,
			getSelected=btnDefColorPalette.backgroundColor.getSelected
		),
		backgroundColor2=replace(
			CLEAR_COLOR_COLOR_SET,
			getSelected=btnDefColorPalette.backgroundColor2.getSelected
		),
	)

	btn._normalColorPalette = btnColorPalette
	btn._defaultColorPalette = btnDefColorPalette


def createShadowPixmap() -> QPixmap:
	pixmap = QPixmap(64, 64)
	pixmap.fill(Qt.transparent)
	with QPainter(pixmap) as p:
		gradient = QRadialGradient(QPointF(32, 32), 32)
		gradient.setColorAt(0., QColor(0, 0, 0, 92))
		gradient.setColorAt(0.25, QColor(0, 0, 0, 90))
		gradient.setColorAt(0.375, QColor(0, 0, 0, 80))
		gradient.setColorAt(0.5, QColor(0, 0, 0, 62))
		gradient.setColorAt(0.75, QColor(0, 0, 0, 13))
		gradient.setColorAt(0.875, QColor(0, 0, 0, 2))
		gradient.setColorAt(1., QColor(0, 0, 0, 0))
		p.fillRect(QRectF(0, 0, 64, 64), gradient)
	return pixmap


if TYPE_CHECKING:
	from ...GUI import PythonGUI
	_TPythonGUI = TypeVar('_TPythonGUI', bound=PythonGUI)
else:
	_TPythonGUI = TypeVar('_TPythonGUI', bound='PythonGUI')


class CatFramelessWindowMixin(CatWindowMixin, Generic[_TPythonGUI]):  # , QDialog):
	def __init__(
			self,
			GUICls: Type[_TPythonGUI] = ...,
			parent: Optional[QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags(),
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = None,
			height: Optional[int] = None
	):
		if GUICls is ...:
			from ...GUI import PythonGUI
			GUICls = PythonGUI
		super(CatFramelessWindowMixin, self).__init__(parent, flags | Qt.FramelessWindowHint, x=x, y=y, width=width, height=height)
		self._initGeometry = (x, y, width, height)
		self.setAttribute(Qt.WA_TranslucentBackground)
		self._isInited: bool = False
		self._isTitlebarVisible: bool = True
		self._isToolbarInTitleBar: bool = False
		self._drawTitleToolbarBorder: bool = True
		self._drawStatusbarBorder: bool = True
		self._statusbarIsWindowPanel: bool = False
		self._disableContentMargins: bool = False
		self._disableSidebarMargins: bool = False
		self._disableBottombarMargins: bool = False
		self._disableStatusbarMargins: bool = False
		self.roundedCorners: RoundedCorners = CORNERS.ALL

		self._shadowData: QPixmap = createShadowPixmap()

		self._minimizeBtn: CatButton = CatFramelessButton()
		self._maximizeBtn: CatButton = CatFramelessButton()
		self._closeBtn: CatButton = CatFramelessButton()
		self._ignoredTitleBarObjects: list[QWidget] = [
			self._minimizeBtn,
			self._maximizeBtn,
			self._closeBtn,
		]

		setNewBorderHue(self._closeBtn, 3, True)

		self._minimizeBtn._neverInactive = True
		self._maximizeBtn._neverInactive = True
		self._closeBtn._neverInactive = True

		self._minimizeBtn.setCheckable(False)
		self._maximizeBtn.setCheckable(False)
		self._closeBtn.setCheckable(False)
		self._titleBar: Optional[QWidget] = None
		self._toolbarInTitleBar: Optional[QWidget] = None
		self._ignoredToolbarObjects: list[QWidget] = []
		connectSafe(self._minimizeBtn.clicked, self._onMinimizeBtnClicked)
		connectSafe(self._maximizeBtn.clicked, self._onMaximizeBtnClicked)
		connectSafe(self._closeBtn.clicked, self._onCloseBtnClicked)

		self.borderSize: int = 0  # define the fields
		self._shadowMargins: tuple[int, int, int, int] = (0, 0, 0, 0)  # define the fields
		self._updateMarginsAndBorderSizes()  # set the fields correctly

		if hasattr(self, 'setCentralWidget'):
			centerWidget = QWidget()
			self.setCentralWidget(centerWidget)
		else:
			centerWidget = QWidget()
			if self.layout() is None:
				self.setLayout(QtWidgets.QVBoxLayout())
			self.layout().addWidget(centerWidget)

		self._centralWidget: QWidget = centerWidget
		self._gui: _TPythonGUI = GUICls(centerWidget, self._windowGUI)

		self.layout().setContentsMargins(*NO_MARGINS)

		# runLaterSafe(5, self.redraw)

		connectSafe(self.windowIconChanged, self._onWindowIconChanged)
		connectSafe(self.windowTitleChanged, self._onWindowTitleChanged)
		connectSafe(self.windowStateChanged, self._onWindowStateChanged)

	# connect(self.titleBarWidget.iconButton, &QPushButton.clicked, self, &MainWindow.displaySystemMenu)

	if TYPE_CHECKING:
		windowIconChanged: pyqtSignal
		windowTitleChanged: pyqtSignal
		windowIconTextChanged: pyqtSignal

		def setAttribute(self, attribute: Qt.WidgetAttribute, on: bool = True) -> None: ...  # raise NotImplementedError()
		def centralWidget(self) -> QWidget: ...  # raise NotImplementedError()
		def layout(self) -> QLayout: ...  # raise NotImplementedError()
		def windowIcon(self) -> QIcon: ...  # raise NotImplementedError()
		def windowTitle(self) -> str: ...  # raise NotImplementedError()
		def isFullScreen(self) -> bool: ...  # raise NotImplementedError()
		def isMaximized(self) -> bool: ...  # raise NotImplementedError()
		def isMinimized(self) -> bool: ...  # raise NotImplementedError()
		def close(self) -> bool: ...  # raise NotImplementedError()
		def showMinimized(self) -> None: ...  # raise NotImplementedError()
		def windowHandle(self) -> QWindow: ...  # raise NotImplementedError()
		def update(self) -> None: ...  # raise NotImplementedError()

	# Q_SIGNALS:
	windowStateChanged = pyqtSignal()

	# Slots:

	@pyqtSlot()
	@CrashReportWrapped
	def _onMinimizeBtnClicked(self) -> None:
		self.showMinimized()

	@pyqtSlot()
	@CrashReportWrapped
	def _onMaximizeBtnClicked(self) -> None:
		self.showNormal() if self.isMaximized() or self.isFullScreen() else self.showMaximized()

	@pyqtSlot()
	@CrashReportWrapped
	def _onCloseBtnClicked(self) -> None:
		self.close()


	@pyqtSlot()
	@CrashReportWrapped
	def _onWindowIconChanged(self) -> None:
		self.redrawLater('windowIconChanged')

	@pyqtSlot()
	@CrashReportWrapped
	def _onWindowTitleChanged(self) -> None:
		self.redrawLater('windowTitleChanged')

	@pyqtSlot()
	@CrashReportWrapped
	def _onWindowStateChanged(self) -> None:
		self._updateContentsMargins()

	@CrashReportWrapped
	def _updateContentsMargins(self) -> None:
		if self.isMaximized() or self.isFullScreen():
			self.setContentsMargins(0, 0, 0, 0)  # type: ignore
		elif not self.isMinimized():
			self.setContentsMargins(*self._shadowMargins)  # type: ignore

		self._gui.host.repaint()
		self.update()
		# self._gui.redrawGUI()
		self.redrawLater("updateShadowMargins")

	def _estimateScreenScaling(self) -> float:
		baseDPI = 96.0  # 72 | 96 | 120 | 150
		baseFontSize = 10.0
		baseScale = 1.0
		font: QFont = self.font()  # type: ignore

		fontSizeFactor = font.pointSizeF() / baseFontSize
		dpiFactor = QFontMetrics(font).fontDpi() / baseDPI
		newScale = dpiFactor * fontSizeFactor * baseScale
		return newScale

	def _applyShadowScaling(self, scale: float) -> tuple[float, float, float, float]:
		""":return: (T, R, B, L)"""
		rc = self.roundedCorners
		return (
			scale * (1.25 if rc[0] or rc[1] else 1.0),
			scale * (1.25 if rc[1] or rc[3] else 1.0),
			scale * (1.25 if rc[3] or rc[2] else 1.0),
			scale * (1.25 if rc[2] or rc[0] else 1.0),
		)

	@property
	def borderMargin(self) -> tuple[int, int, int, int]:
		return tuple(sm - self.borderSize for sm in self._shadowMargins)  # type: ignore

	def _updateMarginsAndBorderSizes(self) -> None:
		scale = self._estimateScreenScaling()
		borderSize = int(round(_BORDER_SIZE * scale))
		shadowScaling = self._applyShadowScaling(_SHADOW_MARGINS * scale)
		_shadowMargins: tuple[int, int, int, int] = tuple(int(round(ssc)) for ssc in shadowScaling)  # type: ignore

		needsUpdate = self.borderSize != borderSize or self._shadowMargins != _shadowMargins
		if needsUpdate:
			self.borderSize = borderSize
			self._shadowMargins = _shadowMargins
			if self._isInited and (win := self.windowHandle()):
				framelessWindowsManager.updateBorder(win, borderSize=self.borderSize, borderMargin=self.borderMargin)

			runLaterSafe(1, lambda: (self._updateContentsMargins() if not (isinstance(self, QObject) and sip.isdeleted(self)) else None))
	# Methids

	@abstractmethod
	def OnToolbarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnSidebarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnBottombarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnStatusbarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnGUI(self, gui: _TPythonGUI):
		pass

	OnToolbarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None
	OnSidebarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None
	OnBottombarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None
	OnStatusbarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None

	@property
	def disableContentMargins(self) -> bool:
		return self._disableContentMargins

	@disableContentMargins.setter
	def disableContentMargins(self, value: bool) -> None:
		self._disableContentMargins = value

	@property
	def disableSidebarMargins(self) -> bool:
		return self._disableSidebarMargins

	@disableSidebarMargins.setter
	def disableSidebarMargins(self, value: bool) -> None:
		self._disableSidebarMargins = value

	@property
	def disableBottombarMargins(self) -> bool:
		return self._disableBottombarMargins

	@disableBottombarMargins.setter
	def disableBottombarMargins(self, value: bool) -> None:
		self._disableBottombarMargins = value

	@property
	def disableStatusbarMargins(self) -> bool:
		return self._disableStatusbarMargins

	@disableStatusbarMargins.setter
	def disableStatusbarMargins(self, value: bool) -> None:
		self._disableStatusbarMargins = value

	@property
	def isToolbarInTitleBar(self) -> bool:
		return self._isToolbarInTitleBar

	@isToolbarInTitleBar.setter
	def isToolbarInTitleBar(self, value: bool):
		self._isToolbarInTitleBar = value

	@property
	def drawTitleToolbarBorder(self) -> bool:
		return self._drawTitleToolbarBorder

	@drawTitleToolbarBorder.setter
	def drawTitleToolbarBorder(self, value: bool):
		self._drawTitleToolbarBorder = value

	@property
	def isTitlebarVisible(self) -> bool:
		return self._isTitlebarVisible

	@isTitlebarVisible.setter
	def isTitlebarVisible(self, value: bool):
		self._isTitlebarVisible = value

	@property
	def isToolbarVisible(self) -> bool:
		return self.OnToolbarGUI is not None

	@property
	def isSidebarVisible(self) -> bool:
		return self.OnSidebarGUI is not None

	@property
	def isBottombarVisible(self) -> bool:
		return self.OnBottombarGUI is not None

	@property
	def drawStatusbarBorder(self) -> bool:
		return self._drawStatusbarBorder

	@drawStatusbarBorder.setter
	def drawStatusbarBorder(self, value: bool):
		self._drawStatusbarBorder = value

	@property
	def statusbarIsWindowPanel(self) -> bool:
		return self._statusbarIsWindowPanel

	@statusbarIsWindowPanel.setter
	def statusbarIsWindowPanel(self, value: bool):
		self._statusbarIsWindowPanel = value

	@property
	def isStatusbarVisible(self) -> bool:
		return self.OnStatusbarGUI is not None

	def setIgnoredToolbarObjects(self, ignoredToolbarObjects: list[QWidget]):
		if ignoredToolbarObjects != self._ignoredToolbarObjects:
			self._ignoredToolbarObjects = ignoredToolbarObjects
			if self._isInited:
				win = self.windowHandle()
				if win:
					ignoredObjects = self._ignoredTitleBarObjects + self._ignoredToolbarObjects
					framelessWindowsManager.updateIgnoredObjects(win, ignoredObjects)

	@property
	def windowSpacing(self) -> int:
		return self._gui.spacing

	@property
	def _sidebarMargins(self) -> Margins:
		if self.disableSidebarMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, margin, margin, margin

	@property
	def _bottombarMargins(self) -> Margins:
		if self.disableBottombarMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, margin, margin, margin

	@property
	def _statusbarMargins(self) -> Margins:
		if self.disableStatusbarMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, margin, margin, margin

	@property
	def _contentMargins(self) -> Margins:
		if self.disableContentMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, margin, margin, margin

	@property
	def windowRoundedCorners(self) -> RoundedCorners:
		return self.roundedCorners
		if self.isMaximized() or self.isFullScreen():
			return CORNERS.NONE
		else:
			return self.roundedCorners

	@property
	def windowCornerRadius(self) -> float:
		return DEFAULT_WINDOW_CORNER_RADIUS

	def _windowGUI(self, gui: _TPythonGUI):
		applyStyle(self, getStyles().hostWidgetStyle)
		gui.currentLayout._qLayout.setContentsMargins(*NO_MARGINS)
		gui.currentLayout._qLayout.setVerticalSpacing(0)
		leftOverCorners = self.windowRoundedCorners

		with gui.vPanel(roundedCorners=leftOverCorners, cornerRadius=self.windowCornerRadius, verticalSpacing=0, windowPanel=False, contentsMargins=NO_MARGINS):

			hasSeparateToolbar = self.isToolbarVisible and not self.isToolbarInTitleBar
			isTitleOrToolbarVisible = self.isTitlebarVisible or hasSeparateToolbar

			if self.isTitlebarVisible:
				titleBarCorners = maskCorners(leftOverCorners, CORNERS.TOP)
				leftOverCorners = maskCorners(leftOverCorners, CORNERS.BOTTOM)
				titleBarOverlap = (0, 0, 0, 1)  # if hasSeparateToolbar else (0, 0, 0, 0 if self.drawTitleToolbarBorder else 1)
				with gui.hPanel(
						overlap=titleBarOverlap,
						roundedCorners=titleBarCorners,
						cornerRadius=self.windowCornerRadius,
						windowPanel=False,
						contentsMargins=NO_MARGINS,
						sizePolicy=(SizePolicy.Expanding.value, SizePolicy.Fixed.value)
				):
					self._titleBar = gui.lastWidget
					self._titleBarGUI(gui, roundedCorners=titleBarCorners, cornerRadius=self.windowCornerRadius, overlap=titleBarOverlap)
				del titleBarOverlap
				del titleBarCorners
			else:
				self._titleBar = None
				self._toolbarInTitleBar = None
				self.setIgnoredToolbarObjects([])

			if hasSeparateToolbar:
				toolbarCorners = maskCorners(leftOverCorners, CORNERS.TOP)
				leftOverCorners = maskCorners(leftOverCorners, CORNERS.BOTTOM)
				toolbarOverlap = (0, 1, 0, 1)  # (0, 1, 0, 0 if self.drawTitleToolbarBorder else 1)
				mg = gui.panelMargins
				smg = gui.smallSpacing
				toolBarMargins = (mg, mg if not self.isTitlebarVisible else smg, mg, smg)
				with gui.hPanel(
						overlap=toolbarOverlap,
						roundedCorners=toolbarCorners,
						cornerRadius=self.windowCornerRadius,
						windowPanel=False,
						contentsMargins=toolBarMargins,
						sizePolicy=(SizePolicy.Expanding.value, SizePolicy.Fixed.value)
				):
					self.OnToolbarGUI(gui)
				del toolbarOverlap
				del toolbarCorners

			if self.isStatusbarVisible:
				statusbarCorners = maskCorners(leftOverCorners, CORNERS.BOTTOM)
				leftOverCorners = maskCorners(leftOverCorners, CORNERS.TOP)
			else:
				statusbarCorners = CORNERS.NONE

			innerCorners = InnerCorners(
				False,
				isTitleOrToolbarVisible and self.drawTitleToolbarBorder,
				False,
				self.isStatusbarVisible and self.drawStatusbarBorder
			)
			topOverlap = 1 if isTitleOrToolbarVisible and not self.drawTitleToolbarBorder else 0  # find better name
			bottomOverlap = 1 if self.isStatusbarVisible and not self.drawStatusbarBorder else 0  # find better name
			if self.isSidebarVisible:
				# innerCorners = joinCorners(
				# 	CORNERS.TOP if isTitleOrToolbarVisible and not self.drawTitleToolbarBorder else CORNERS.NONE,
				# 	CORNERS.BOTTOM if self.isStatusbarVisible else CORNERS.NONE
				# )
				with gui.hSplitter(handleWidth=self.windowSpacing, childrenCollapsible=True) as splitter:
					with splitter.addArea(id_='&!sidebar', stretchFactor=0, contentsMargins=NO_MARGINS):
						sidebarCorners = joinCorners(
							maskCorners(leftOverCorners, CORNERS.LEFT),
							selectInnerCorners(innerCorners, INNER_CORNERS.RIGHT)
						)
						sidebarOverlap = (0, topOverlap, 0, bottomOverlap)
						sidebarMargins = self._sidebarMargins
						with gui.vPanel(overlap=sidebarOverlap, roundedCorners=sidebarCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableSidebarMargins, contentsMargins=sidebarMargins):
							self.OnSidebarGUI(gui)

					with splitter.addArea(id_='&!mainArea', stretchFactor=2, verticalSpacing=0, contentsMargins=NO_MARGINS):
						mainAreaInnerCorners = INNER_CORNERS.LEFT if self.isSidebarVisible else INNER_CORNERS.NONE
						mainAreaCorners = joinCorners(
							maskCorners(leftOverCorners, CORNERS.RIGHT),
							selectInnerCorners(innerCorners, mainAreaInnerCorners)
						)
						mainAreaOverlap = (0, topOverlap, 0, bottomOverlap)
						self._mainAreaGUI(gui, overlap=mainAreaOverlap, roundedCorners=mainAreaCorners, innerCorners=joinInnerCorners(innerCorners, mainAreaInnerCorners))
				leftOverCorners = CORNERS.NONE
			else:
				mainAreaCorners = leftOverCorners
				leftOverCorners = CORNERS.NONE
				mainAreaOverlap = (0, topOverlap, 0, bottomOverlap)
				self._mainAreaGUI(gui, overlap=mainAreaOverlap, roundedCorners=mainAreaCorners, innerCorners=innerCorners)

			if self.isStatusbarVisible:
				statusbarMargins = self._statusbarMargins
				with gui.hPanel(overlap=(0, 1), roundedCorners=statusbarCorners, cornerRadius=self.windowCornerRadius, windowPanel=self.statusbarIsWindowPanel, seamless=self.disableStatusbarMargins, contentsMargins=statusbarMargins, vSizePolicy=SizePolicy.Fixed.value):
					self.OnStatusbarGUI(gui)

	def _titleBarGUI(self, gui: _TPythonGUI, roundedCorners: RoundedCorners, cornerRadius: float, overlap: Overlap) -> None:
		lSpacing = gui.spacing
		tSpacing = gui.smallSpacing - 1
		with gui.hLayout(contentsMargins=(lSpacing, tSpacing*0, 0, 0),):
			gui.label(self._getWindowIcon(), iconScale=1.0)
		with gui.hLayout(horizontalSpacing=0):
			self._titleOrToolbarGUI(gui, overlap)
			self._titleBarButtonsGUI(gui, overlap=joinOverlap(overlap, (1, 0, 0, 0)), roundedCorners=maskCorners(roundedCorners, CORNERS.RIGHT), cornerRadius=cornerRadius)

	def _titleOrToolbarGUI(self, gui: _TPythonGUI, overlap: Overlap) -> None:
		if self.isToolbarVisible and self.isToolbarInTitleBar:
			mg = gui.panelMargins
			with gui.hPanel(
					overlap=joinOverlap(overlap, (1, 0, 1, 0)),
					roundedCorners=CORNERS.NONE,
					cornerRadius=self.windowCornerRadius,
					windowPanel=False,
					contentsMargins=(mg, 0, mg, 0),
					sizePolicy=(SizePolicy.Expanding.value, SizePolicy.Fixed.value)):
				self._toolbarInTitleBar = gui.lastWidget
				self.OnToolbarGUI(gui)

			newIgnoredToolbarObject = [ c for c in self._toolbarInTitleBar.children() if isinstance(c, QWidget)]
			self.setIgnoredToolbarObjects(newIgnoredToolbarObject)

		else:
			self._toolbarInTitleBar = None
			self.setIgnoredToolbarObjects([])

			gui.elidedLabel(self.windowTitle() or qApp.applicationDisplayName())
			gui.addHSpacer(0, SizePolicy.Expanding)

	def _getWindowIcon(self) -> QIcon:
		windowIcon: QIcon = self.windowIcon()
		if windowIcon.isNull():
			windowIcon: QIcon = qApp.windowIcon()
		if windowIcon.isNull():
			windowIcon: QIcon = getDefaultAppIcon()
		return windowIcon

	def _titleBarButtonsGUI(self, gui: _TPythonGUI, overlap: Overlap, roundedCorners: RoundedCorners, cornerRadius: float) -> None:
		maximizeTip = 'Restore' if self.isMaximized() else 'Maximize'
		maximizeIcon = icons.btnRestore if self.isMaximized() else icons.btnMaximize

		with gui.hLayout(horizontalSpacing=0):
			gui.customWidget(self._minimizeBtn, icon=icons.btnMinimize, tip='Minimize', roundedCorners=maskCorners(roundedCorners, CORNERS.LEFT), cornerRadius=cornerRadius,
							overlap=adjustOverlap(overlap, (None, None, 1, None)), focusPolicy=Qt.NoFocus)

			gui.customWidget(self._maximizeBtn, icon=maximizeIcon, tip=maximizeTip, roundedCorners=CORNERS.NONE,
							overlap=adjustOverlap(overlap, (1, None, 1, None)), focusPolicy=Qt.NoFocus)

			gui.customWidget(self._closeBtn, icon=icons.btnClose, tip='Close', roundedCorners=maskCorners(roundedCorners, CORNERS.RIGHT), cornerRadius=cornerRadius,
							overlap=adjustOverlap(overlap, (1, None, None, None)), focusPolicy=Qt.NoFocus)

	def _mainAreaGUI(self, gui: _TPythonGUI, overlap: Overlap, roundedCorners: RoundedCorners, innerCorners: InnerCorners):
		if self.OnBottombarGUI is not None:
			with gui.vSplitter(handleWidth=self.windowSpacing, childrenCollapsible=True) as splitter:
				with splitter.addArea(stretchFactor=2, id_='&!contents', verticalSpacing=0, seamless=False):
					contentsOverlap = adjustOverlap(overlap, (None, None, None, 0))
					contentsRoundedCorners = joinCorners(roundedCorners, selectInnerCorners(innerCorners, INNER_CORNERS.BOTTOM))
					contentsMargins = self._contentMargins
					with gui.vPanel(overlap=contentsOverlap, roundedCorners=contentsRoundedCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableContentMargins, contentsMargins=contentsMargins):
						self.OnGUI(gui)

				with splitter.addArea(stretchFactor=0, id_='&!bottombar', verticalSpacing=0, seamless=False):
					bottomOverlap = adjustOverlap(overlap, (None, 0, None, None))
					bottomRoundedCorners = joinCorners(roundedCorners, selectInnerCorners(innerCorners, INNER_CORNERS.TOP))
					bottomMargins = self._bottombarMargins
					with gui.vPanel(overlap=bottomOverlap, roundedCorners=bottomRoundedCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableBottombarMargins, contentsMargins=bottomMargins):
						self.OnBottombarGUI(gui)
		else:
			contentsMargins = self._contentMargins
			with gui.vPanel(overlap=overlap, roundedCorners=roundedCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableContentMargins, contentsMargins=contentsMargins):
				self.OnGUI(gui)

	def redraw(self):
		self._gui.redrawGUI()

	def redrawLater(self, cause: Optional[str] = None):
		self._gui.redrawLater(cause)

	@CrashReportWrapped
	def paintEvent(self, event: QPaintEvent) -> None:
		self._updateMarginsAndBorderSizes()
		scale = self._estimateScreenScaling()
		# 25.6 == 32. / 1.25
		shadowScale = self._applyShadowScaling(25.6 * scale)
		_t,  _r, _b, _l = shadowScale
		w_r = self.width() - _r
		h_b = self.height() - _b

		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)
			if self.isMaximized() or self.isFullScreen():
				p.fillRect(self.rect(), QColor('black'))
			else:
				p.drawPixmap(QRectF(0.,  0.,  _l,       _t),       self._shadowData, QRectF( 0.,  0., 32., 32.))
				p.drawPixmap(QRectF(_l,  0.,  w_r - _l, _t),       self._shadowData, QRectF(31.,  0.,  2., 32.))
				p.drawPixmap(QRectF(w_r, 0.,  _r,       _t),       self._shadowData, QRectF(32.,  0., 32., 32.))
				p.drawPixmap(QRectF(w_r, _t,  _r,       h_b - _t), self._shadowData, QRectF(32., 31., 32.,  2.))
				p.drawPixmap(QRectF(w_r, h_b, _r,       _b),       self._shadowData, QRectF(32., 32., 32., 32.))
				p.drawPixmap(QRectF(_l,  h_b, w_r - _l, _b),       self._shadowData, QRectF(31., 32.,  2., 32.))
				p.drawPixmap(QRectF(0.,  h_b, _l,       _b),       self._shadowData, QRectF( 0., 32., 32., 32.))
				p.drawPixmap(QRectF(0.,  _t,  _l,       h_b - _t), self._shadowData, QRectF( 0., 31., 32.,  2.))

	@CrashReportWrapped
	def showEvent(self, event: QShowEvent) -> None:
		super(CatFramelessWindowMixin, self).showEvent(event)
		self.redraw()
		if not self._isInited and (win := self.windowHandle()):
			titleBar = [self._titleBar] if self._titleBar is not None else []
			ignoredObjects = self._ignoredTitleBarObjects + self._ignoredToolbarObjects
			framelessWindowsManager.registerWindow(win, titleBar=titleBar, ignoredObjects=ignoredObjects, borderSize=self.borderSize, borderMargin=self.borderMargin)
			self._isInited = True
		self.redraw()
		if self._initGeometry is not None:
			runLaterSafe(1, lambda geo=self._initGeometry: self.setInitialGeometry(*geo))
			self._initGeometry = None

	@CrashReportWrapped
	def hideEvent(self, event: QHideEvent) -> None:
		super(CatFramelessWindowMixin, self).hideEvent(event)
		if self._isInited:
			win = self.windowHandle()
			if win:
				framelessWindowsManager.deregisterWindow(win)
				self._isInited = False

	@CrashReportWrapped
	def changeEvent(self:QWidget, event: QEvent) -> None:
		super(CatFramelessWindowMixin, self).changeEvent(event)
		shouldUpdate: bool = False
		if event.type() == QEvent.WindowStateChange:
			shouldUpdate = True
			self.windowStateChanged.emit()
		elif event.type() == QEvent.ActivationChange:
			shouldUpdate = True

		if shouldUpdate:
			self.update()
