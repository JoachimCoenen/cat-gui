from __future__ import annotations

import sys
from dataclasses import dataclass, field

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import qApp

from cat.GUI import getStyles, SizePolicy
from cat.GUI.components.catWidgetMixins import getGUIColors
from cat.GUI.components.treeBuilders import DataListBuilder
from cat.GUI.icons import iconGetter
from cat.GUI.pythonGUI import PythonGUI, PythonGUIDialog
from cat.utils.utils import runLaterSafe

from cat.examples.calculator.core import *


@dataclass
class OperatorDef:
	display: str
	shortcut: str | None
	operator: Curryable


OPERATOR_ADD = OperatorDef("+", '+', BinaryOperator("+", OperationType.SUM, lambda lhs, rhs: lhs + rhs))
OPERATOR_SUB = OperatorDef("-", '-', BinaryOperator("-", OperationType.SUM, lambda lhs, rhs: lhs - rhs))
OPERATOR_MUL = OperatorDef("×", '*', BinaryOperator("×", OperationType.MULTIPLICATIVE, lambda lhs, rhs: lhs * rhs))
OPERATOR_DIV = OperatorDef("÷", '/', BinaryOperator("÷", OperationType.MULTIPLICATIVE, lambda lhs, rhs: lhs / rhs if rhs != 0.0 else None))

OPERATOR_SQRT = OperatorDef("sqrt", None, UnaryOperator("sqrt", OperationType.FUNCTION, OperationKind.FUNCTION, lambda lhs: lhs**0.5 if lhs >= 0.0 else None))
OPERATOR_SQR = OperatorDef("x²", None, UnaryOperator("²", OperationType.POWER, OperationKind.POSTFIX, lambda lhs: lhs * lhs))
OPERATOR_INV = OperatorDef("1/x", None, UnaryOperator("1 /", OperationType.MULTIPLICATIVE, OperationKind.INFIX, lambda lhs: 1. / lhs if lhs != 0.0 else None))


class Calculator(PythonGUIDialog[PythonGUI]):  # must be a dialog for default buttons to work
	historyIcon = iconGetter('fa5s.history')
	trashIcon = iconGetter('fa5.trash-alt')
	appIcon = iconGetter('fa5s.calculator', options=[dict(color=getGUIColors().Highlight)])

	def __init__(self):
		super().__init__(PythonGUI)
		self.isToolbarInTitleBar = True
		self._showHistory: bool = False
		self.core = CalculatorCore()

	def OnToolbarGUI(self, gui: PythonGUI):
		gui.elidedLabel(self.windowTitle() or qApp.applicationDisplayName())
		gui.addHSpacer(0, SizePolicy.Expanding)
		self._showHistory = gui.toggleSwitch(self._showHistory, icon=self.historyIcon, tip="show History")

	def OnGUI(self, gui: PythonGUI):
		with gui.hLayout():
			with gui.vLayout(preventVStretch=True):
				self.displayGUI(gui)
				self.buttonsGUI(gui)
			if self._showHistory:
				with gui.vLayout():
					self.memoryGUI(gui)
					self.historyGUI(gui)

	def displayGUI(self, gui: PythonGUI):
		with gui.vPanel(seamless=True):
			with gui.hLayout(seamless=True):
				gui.addHSpacer(0, SizePolicy.Expanding)  # right align
				gui.label(self.core.lastOperationStr)
			gui.textField(self.core.display, fullSize=True, readOnly=True, alignment=Qt.AlignRight, maxLength=15, style=getStyles().title)

	def buttonsGUI(self, gui: PythonGUI):
		with gui.tableLayout(seamless=True) as tableLayout:
			tableLayout.setNextItemSpan(2)
			if gui.button("Clear All", shortcut="ESC"):
				self.core.clearAll()
			tableLayout.setNextItemSpan(2)
			if gui.button("Clear"):
				self.core.clear()
			tableLayout.setNextItemSpan(2)
			if gui.button("Backspace", shortcut="BACKSPACE"):
				self.core.backspace()

			tableLayout.advanceRow()
			if gui.button("MC"):
				self.core.clearMemory()
			self._addDigitButton(gui, "7")
			self._addDigitButton(gui, "8")
			self._addDigitButton(gui, "9")
			self._addOperatorButton(gui, OPERATOR_DIV)
			self._addOperatorButton(gui, OPERATOR_SQRT)

			tableLayout.advanceRow()
			if gui.button("MR"):
				self.core.readMemory()
			self._addDigitButton(gui, "4")
			self._addDigitButton(gui, "5")
			self._addDigitButton(gui, "6")
			self._addOperatorButton(gui, OPERATOR_MUL)
			self._addOperatorButton(gui, OPERATOR_SQR)

			tableLayout.advanceRow()
			if gui.button("MS"):
				self.core.setMemory()
			self._addDigitButton(gui, "1")
			self._addDigitButton(gui, "2")
			self._addDigitButton(gui, "3")
			self._addOperatorButton(gui, OPERATOR_SUB)
			self._addOperatorButton(gui, OPERATOR_INV)

			tableLayout.advanceRow()
			if gui.button("M+"):
				self.core.addToMemory()
			if gui.button("±"):
				self.core.changeSign()
			self._addDigitButton(gui, "0")
			if gui.button(".", shortcut="."):
				self.core.decimalSeparator()
			self._addOperatorButton(gui, OPERATOR_ADD)
			if gui.button("=", default=True):
				self.core.equals()

	def _addDigitButton(self, gui: PythonGUI, digit: str):
		if gui.button(digit, shortcut=digit):
			self.core.addDigit(digit)

	def _addOperatorButton(self, gui: PythonGUI, operator: OperatorDef):
		if gui.button(operator.display, shortcut=operator.shortcut or QKeySequence()):
			self.core.operator(operator.operator)

	def memoryGUI(self, gui: PythonGUI):
		with gui.vPanel(seamless=True):
			gui.title("Memory")
			gui.vSeparator()
			gui.label(str(self.core.sumInMemory), selectable=True)

	def historyGUI(self, gui: PythonGUI):
		with gui.vPanel(seamless=True):
			with gui.hLayout(seamless=True):
				gui.title("History")
				if gui.toolButton(icon=self.trashIcon, tip="Clears the history."):
					self.core.history.clear()

			gui.tree(
				DataListBuilder(
					self.core.history,
					labelMaker=lambda opRes, c: (opRes.display, f"= {opRes.value}")[c],
					iconMaker=None,
					toolTipMaker=lambda opRes, c: str(opRes.display),
					columnCount=2,
					onDoubleClick=lambda opRes: self.core.setValue(opRes.value) or self.redraw(),
					onCopy=lambda opRes: str(opRes.value),
					getId=id
				),
			)


def start(argv):
	app = QtWidgets.QApplication(argv)
	QtWidgets.QApplication.setStyle("Fusion")
	window = Calculator()

	app.setApplicationName("Cat Calculator")
	app.setWindowIcon(window.appIcon)

	window.show()
	runLaterSafe(0, lambda: window.resize(0, 0))  # reduce window size
	app.exec_()


if __name__ == '__main__':
	start(argv=sys.argv)
