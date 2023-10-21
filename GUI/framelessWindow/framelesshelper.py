# MIT License
#
# Copyright (C) 2021 by Joachim Coenen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

from PyQt5 import QtCore
from PyQt5.QtCore import QEvent, QObject, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QTouchEvent, QWindow

from PyQt5.QtWidgets import QWidget

from Cat.GUI.framelessWindow.utilities import isMouseInSpecificObjects
from Cat.GUI.utilities import CrashReportWrapped


def getMousePositions(e: QMouseEvent) -> QPointF:
	if QtCore.QT_VERSION_STR.startswith('6.'):
		return e.globalPosition()
	else:
		return e.screenPos()

BorderSize = tuple[int, int, int, int]

@dataclass
class WindowFrameInfo:
	titleBar: list[QWidget]
	ignoredObjects: list[QWidget]
	borderSize: BorderSize
	borderMargin: BorderSize
	isFixedSize: bool = False
	totalBorderWidth: BorderSize = field(default=None, init=False)

	def __post_init__(self):
		self.totalBorderWidth = (
			self.borderSize[0] + self.borderMargin[0],
			self.borderSize[1] + self.borderMargin[1],
			self.borderSize[2] + self.borderMargin[2],
			self.borderSize[3] + self.borderMargin[3],
		)

class FramelessHelper(QObject):

	def __init__(self, parent: QObject = None):
		super(FramelessHelper, self).__init__(parent)
		self._defaultBrderSize = (8, 8, 8, 8)
		self._defaultBrderMargin = (0, 0, 0, 0)
		self._registeredWindows: dict[QWindow, WindowFrameInfo] = {}
		self._wasInFrame: bool = False

	def registerWindow(self, window: QWindow, *, titleBar: list[QWidget], ignoredObjects: list[QWidget], borderSize: Optional[BorderSize] = None, borderMargin: Optional[BorderSize] = None, fixedSize: bool = False) -> None:
		if borderSize is None:
			borderSize = self._defaultBrderSize
		if borderMargin is None:
			borderMargin = self._defaultBrderMargin
		if window in self._registeredWindows:
			logging.warning("Trying to register already registered window.")
			return

		# # TODO: check whether these flags are correct for Linux and macOS.
		# window.setFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint | Qt.WindowTitleHint)

		self._registeredWindows[window] = WindowFrameInfo(titleBar, ignoredObjects, borderSize, borderMargin, fixedSize)
		window.installEventFilter(self)

	def deregisterWindow(self, window: QWindow) -> None:
		if self._registeredWindows.pop(window, None) is None:
			logging.warning("Tried to deregister an unregistered window.")
		window.removeEventFilter(self)

	def updateIgnoredObjects(self, window: QWindow, ignoredObjects: list[QWidget]):
		frameInfo = self.getFrameInfo(window)
		if frameInfo is not None:
			frameInfo.ignoredObjects = ignoredObjects


	def getFrameInfo(self, window: QWindow) -> Optional[WindowFrameInfo]:
		frameInfo = self._registeredWindows.get(window, None)
		if frameInfo is None:
			logging.warning("Tried to get FrameInfo for an unregistered window.")
		return frameInfo

	# eventFilter:
	_bIsMRBPressed: bool = False
	_pOldMousePos: QPointF = QPointF()

	def getWindowResizeEdges(self, globalMousePos: QPointF, window: QWindow, frameInfo: WindowFrameInfo) -> Qt.Edges:
		if window.windowState() != Qt.WindowNoState:
			return Qt.Edges()
		if frameInfo.isFixedSize:
			return Qt.Edges()

		mousePos = window.mapFromGlobal(globalMousePos.toPoint())

		borderSize = frameInfo.totalBorderWidth
		borderMargin = frameInfo.borderMargin
		edges = Qt.Edges()
		if borderSize[0] >= mousePos.x() > borderMargin[0]:
			edges |= Qt.LeftEdge
		if borderSize[1] >= mousePos.y() > borderMargin[1]:
			edges |= Qt.TopEdge
		if borderSize[2] >= window.width() - mousePos.x() > borderMargin[2]:
			edges |= Qt.RightEdge
		if borderSize[3] >= window.height() - mousePos.y() > borderMargin[3] :
			edges |= Qt.BottomEdge

		return edges

	def isInTitlebarArea(self, globalPoint: QPointF, frameInfo: WindowFrameInfo) -> bool:
		inTitleBarArea = isMouseInSpecificObjects(globalPoint, frameInfo.titleBar)
		if not inTitleBarArea:
			return False
		inIgnoredObject = isMouseInSpecificObjects(globalPoint, frameInfo.ignoredObjects)
		return inTitleBarArea and not inIgnoredObject

	def moveOrResize(self, globalMousePos: QPointF, window: QWindow) -> None:
		assert window
		frameInfo = self.getFrameInfo(window)
		if frameInfo is None:
			return
		# const QPointF deltaPoint = globalPoint - self._pOldMousePos;
		edges: Qt.Edges = self.getWindowResizeEdges(globalMousePos, window, frameInfo)
		if edges == Qt.Edges():
			if self.isInTitlebarArea(globalMousePos, frameInfo):
				supportedBySystem = window.startSystemMove()
				if not supportedBySystem:
					# ### FIXME: TO BE IMPLEMENTED!
					logging.warning("Current OS doesn't support QWindow::startSystemMove().")
		else:
			if not isMouseInSpecificObjects(globalMousePos, frameInfo.ignoredObjects):
				supportedBySystem = window.startSystemResize(edges)
				if not supportedBySystem:
					# ### FIXME: TO BE IMPLEMENTED!
					logging.warning("Current OS doesn't support QWindow::startSystemResize().")

	def mouseButtonDblClick(self, currentWindow: QWindow, mouseEvent: QMouseEvent) -> None:
		if not mouseEvent:
			return
		if mouseEvent.button() != Qt.LeftButton:
			return

		frameInfo = self.getFrameInfo(currentWindow)
		if frameInfo is None:
			return

		mPos = getMousePositions(mouseEvent)
		if self.isInTitlebarArea(mPos, frameInfo):
			if currentWindow.windowState() == Qt.WindowFullScreen:
				currentWindow.setWindowState(Qt.WindowNoState)
			elif currentWindow.windowState() == Qt.WindowMaximized:
				currentWindow.setWindowState(Qt.WindowNoState)
				#currentWindow.showMaximized()
				# currentWindow.showNormal()
			else:
				currentWindow.setWindowState(Qt.WindowMaximized)
				# currentWindow.hide()  # is needed on windows 10. possibly a bug?
				# currentWindow.showMaximized()
			currentWindow.setCursor(Qt.ArrowCursor)

	def mouseButtonPress(self, currentWindow: QWindow, mouseEvent: QMouseEvent) -> None:
		if not mouseEvent:
			return
		if mouseEvent.button() != Qt.LeftButton:
			return

		self._bIsMRBPressed = True
		mPos = getMousePositions(mouseEvent)
		self._pOldMousePos = mPos
		self.moveOrResize(mPos, currentWindow)

	def mouseMove(self, currentWindow: QWindow, mouseEvent: QMouseEvent) -> None:
		# def getCursorShape(edges: Qt.Edges) -> Qt.CursorShape:
		# 	if (Qt.TopEdge & edges and Qt.LeftEdge & edges) or (Qt.BottomEdge & edges and Qt.RightEdge & edges):
		# 		return Qt.SizeFDiagCursor
		# 	elif (Qt.TopEdge & edges and Qt.RightEdge & edges) or (Qt.BottomEdge & edges and Qt.LeftEdge & edges):
		# 		return Qt.SizeBDiagCursor
		# 	elif Qt.TopEdge & edges or Qt.BottomEdge & edges:
		# 		return Qt.SizeVerCursor
		# 	elif Qt.LeftEdge & edges or Qt.RightEdge & edges:
		# 		return Qt.SizeHorCursor
		# 	else:
		# 		return Qt.ArrowCursor
		if not mouseEvent:
			return
		frameInfo = self.getFrameInfo(currentWindow)
		if frameInfo is None:
			return

		if (currentWindow.windowState() == Qt.WindowNoState) and not frameInfo.isFixedSize:
			mPos = getMousePositions(mouseEvent)
			edges = self.getWindowResizeEdges(mPos, currentWindow, frameInfo)

			if edges:
				self._wasInFrame = True

			if Qt.TopEdge | Qt.LeftEdge == edges or Qt.BottomEdge | Qt.RightEdge == edges:
				cursorShape = Qt.SizeFDiagCursor
			elif Qt.TopEdge | Qt.RightEdge == edges or Qt.BottomEdge | Qt.LeftEdge == edges:
				cursorShape = Qt.SizeBDiagCursor
			elif Qt.TopEdge == edges or Qt.BottomEdge == edges:
				cursorShape = Qt.SizeVerCursor
			elif Qt.LeftEdge == edges or Qt.RightEdge == edges:
				cursorShape = Qt.SizeHorCursor
			elif self._wasInFrame:
				cursorShape = Qt.ArrowCursor
				self._wasInFrame = False
			else:
				return #cursorShape = Qt.ArrowCursor
			currentWindow.setCursor(cursorShape)

	def mouseButtonRelease(self, currentWindow: QWindow, mouseEvent: QMouseEvent) -> None:
		if mouseEvent:
			if mouseEvent.button() != Qt.LeftButton:
				return
			self._bIsMRBPressed = False
			self._pOldMousePos = QPointF()

	def touchBeginOrUpdate(self, currentWindow: QWindow, touchEvent: QTouchEvent) -> None:
		if QtCore.QT_VERSION_STR.startswith('6.'):
			point = touchEvent.points().first()
			self.moveOrResize(point.globalPosition(), currentWindow)
		else:
			point = touchEvent.touchPoints().first()
			self.moveOrResize(point.screenPos(), currentWindow)

	_eventHandlers: dict[QEvent.Type, Callable[[FramelessHelper, QWindow, QEvent], None]] = {
		QEvent.MouseButtonDblClick: mouseButtonDblClick,
		QEvent.MouseButtonPress   : mouseButtonPress,
		QEvent.MouseMove          : mouseMove,
		QEvent.MouseButtonRelease : mouseButtonRelease,
		QEvent.TouchBegin         : touchBeginOrUpdate,
		QEvent.TouchUpdate        : touchBeginOrUpdate,
	}

	@CrashReportWrapped
	def eventFilter(self, object: QObject, event: QEvent) -> bool:
		if not object or not event:
			return False
		if not object.isWindowType():
			return False
		# QWindow will always be a top level window. It can't
		# be anyone's child window.
		currentWindow: QWindow = object

		if isinstance(event, QMouseEvent):
			pass #return False
			#isMouseInSpecificObjects(globalMouse, self.getIgnoredObjects(window), dpr)


		handler: Callable[[FramelessHelper, QWindow, QEvent], None] = self._eventHandlers.get(event.type(),  None)
		if handler is not None:
			handler(self, currentWindow, event)
		
		return False
