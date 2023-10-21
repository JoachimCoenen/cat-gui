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

from typing import Optional

from PyQt5.QtGui import QWindow
from PyQt5.QtWidgets import QWidget

from Cat.GUI.framelessWindow.framelesshelper import BorderSize, FramelessHelper

framelessHelper = FramelessHelper()


def registerWindow(window: QWindow, *, titleBar: list[QWidget], ignoredObjects: list[QWidget], borderSize: Optional[BorderSize] = None, borderMargin: Optional[BorderSize] = None, fixedSize: bool = False) -> None:
	assert window
	if not window:
		return
	framelessHelper.registerWindow(window, titleBar=titleBar, ignoredObjects=ignoredObjects, borderSize=borderSize, borderMargin=borderMargin, fixedSize=fixedSize)


def deregisterWindow(window: QWindow) -> None:
	assert window
	if not window:
		return
	framelessHelper.deregisterWindow(window)


def updateIgnoredObjects(window: QWindow, ignoredObjects: list[QWidget]):
	assert window
	if not window:
		return
	framelessHelper.updateIgnoredObjects(window, ignoredObjects)