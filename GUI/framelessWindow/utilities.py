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
import logging
import platform

from PyQt5.QtCore import QPoint, QPointF, QRectF, QSizeF
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

_isWindows: bool = platform.system() == 'Windows'


def isMouseInSpecificObjects(mousePos: QPointF, objects: list[QWidget], dpr: float = 1.0) -> bool:
	if mousePos.isNull():
		logging.warning("Mouse position is null.")
		return False
	if not objects:
		# logging.warning("Object list is empty.")
		return False

	for object in objects:
		if object is None:
			logging.warning("Object pointer is null.")
			continue
		try:
			if not object.isWidgetType() and not object.inherits("QQuickItem"):
				logging.warning(f"{object} is not a QWidget or QQuickItem!")
				continue
		except RuntimeError as e:
			if str(e).endswith('has been deleted'):
				continue
			else:
				raise

		if not object.property("visible"):
			logging.debug(f"Skipping invisible object {object}")
			continue

		originPoint: QPointF = QPointF(object.mapToGlobal(QPoint()))
		originPoint = originPoint * dpr
		size: QSizeF = QSizeF(object.size()) * dpr
		rect: QRectF = QRectF(originPoint, size)
		if rect.contains(mousePos):
			return True
	return False


def getDefaultAppIcon() -> QIcon:
	if _isWindows:
		import ctypes
		from PyQt5.QtWinExtras import QtWin
		user32 = ctypes.windll.user32
		IDI_APPLICATION = 32512
		windowIcon: QIcon = QIcon(QtWin.fromHICON(user32.LoadIconA(None, IDI_APPLICATION)))
	else:
		# TODO: getDefaultAppIcon() for other operating systems.
		windowIcon: QIcon = QIcon()
	return windowIcon
