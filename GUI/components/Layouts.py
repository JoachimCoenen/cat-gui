from __future__ import absolute_import, annotations, print_function

import enum
import functools as ft
import traceback
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, List, Optional, Type, TYPE_CHECKING, TypeVar, Union, NamedTuple, cast

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QGridLayout, QLayout, QLayoutItem, QSpacerItem, QWidget, QSizePolicy

from ...GUI.components.catWidgetMixins import CatFramedWidgetMixin, Overlap, OverlapCharacteristics, RoundedCorners, OverlapCharTpl
from ...GUI.utilities import disconnectAndDeleteLater
from ...utils import format_full_exc

if TYPE_CHECKING:
	from ...GUI.pythonGUI import PythonGUI


_TS = TypeVar('_TS')
_TWidget = TypeVar('_TWidget', bound=Union[QWidget, QLayout, QSpacerItem])
_TItemType = TypeVar('_TItemType', bound=Union[Type[Union[QWidget, QLayout, QSpacerItem]], QWidget])
_TQWidget = TypeVar('_TQWidget', bound=QWidget)
TWidgetOrType = Union[Type[_TWidget], _TWidget]
DictOrTuple = Union[tuple, dict[str, Any]]
LayoutItemOrWidget = Union[QLayoutItem, QtWidgets.QWidget]


CAT_DONT_DELETE_MARKER = '__catDontDelete__'


@dataclass
class Marker(object):
	count: int
	innerMarkers: list[Marker]


class WithBlock(object):
	"""docstring for WithBlock"""

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, tracebacks):
		if tracebacks:
			print("----", )
			print("--> ", exc_type)
			print("--> ", exc_value)
			print("-->!", ''.join(traceback.format_exception(exc_type, exc_value, tracebacks)))
		return False

	def surroundWithBlock(self, outer):
		return self.surroundWith(outer.__enter__, outer.__exit__)

	def surroundWith(self, enter, exit=None):
		class BoundBlock(WithBlock):
			"""docstring for BoundBlock"""
			def __init__(self, inner, outer__enter, outer__exit=None):
				super(BoundBlock, self).__init__()
				self.inner = inner
				self.outer__enter = outer__enter
				self.outer__exit = outer__exit
			
			def __enter__(self):
				if self.outer__enter is not None:
					result = self.outer__enter()
					self.inner.__enter__()
				else:
					result = self.inner.__enter__()
				return result

			def __exit__(self, exc_type, exc_value, traceback):
				hasHandeledException = self.inner.__exit__(exc_type, exc_value, traceback)
				if self.outer__exit is not None:
					if hasHandeledException:
						self.outer__exit(None, None, None)
						return True
					else:
						return self.outer__exit(exc_type, exc_value, traceback)
				else:
					return hasHandeledException
		
		return BoundBlock(self, enter, exit)


def deleteWidget(widget: QWidget) -> None:
	dontDelete = getattr(widget, CAT_DONT_DELETE_MARKER, False)
	if dontDelete:
		widget.hide()  # TODO: Test!! (2021-11-11)
		widget.setParent(None)
	else:
		widget.hide()
		widget.setParent(None)  # TODO: Test!! (2021-11-11)
		disconnectAndDeleteLater(widget)
	# widget.setParent(None)


def deleteLayout(layout: QLayout) -> None:
	removeItemsFromLayout(layout, 0)
	disconnectAndDeleteLater(layout)
	# layout.setParent(None)


def deleteItemFromLayout(item: QLayoutItem, qLayout: QLayout):
	if item is None:
		return
	qLayout.removeItem(item)
	if item.widget() is not None:
		deleteWidget(item.widget())
	elif item.layout() is not None:
		deleteLayout(item.layout())
	else:
		pass
		# item.spacerItem().setParent(None)


def _adjustToPos(totalCount: int, toPos: int):
	toPos = totalCount + toPos if toPos < 0 else toPos
	toPos = min(toPos, totalCount - 1)
	return toPos


def removeItemsFromLayout(qLayout: QLayout, fromPos: int = 0, toPos: int = -1):
	"""removes widgets from fromPos to toPos (inclusive)"""
	toPos = _adjustToPos(qLayout.count(), toPos)
	for i in range(toPos, fromPos-1, -1):
		child = qLayout.takeAt(i)
		deleteItemFromLayout(child, qLayout)


def _getItem(item: QLayoutItem):
	if item is None:
		return
	elif item.widget() is not None:
		return item.widget()
	elif item.layout() is not None:
		return item.layout()
	elif item.spacerItem() is not None:
		return item.spacerItem()
	return None


class LayoutBase(WithBlock, Generic[_TWidget], ABC):
	def __init__(self, gui: PythonGUI, qLayout: _TWidget, *, forWidget: Optional[QWidget]):
		super(LayoutBase, self).__init__()
		self._gui: PythonGUI = gui
		self._qLayout: _TWidget = qLayout
		self._forWidget: QWidget = forWidget

		self._indentLevel = 0
		self._index = 0
		self._newItems: List[LayoutItemOrWidget] = []
		self._oldItems: List[LayoutItemOrWidget] = []

	@abstractmethod
	def addItem(self, ItemType: TWidgetOrType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False) -> _TWidget:
		pass

	@abstractmethod
	def canIndentItem(self, isPrefix: bool) -> bool:
		pass

	def resetIndex(self):
		self._index = 0
		self._indentLevel = 0

	@property
	def indentLevel(self) -> int:
		return self._indentLevel

	@indentLevel.setter
	def indentLevel(self, value: int):
		self._indentLevel = value

	def __enter__(self: _TS) -> _TS:
		super().__enter__()
		self._gui.pushLayout(self)
		self._oldItems = self._collectAllOldItems()
		self._newItems = []
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		try:
			for item in self._oldItems:
				self._removeOldItem(item)
		finally:
			self._gui.popLayout(self)
		if not getattr(self, '_deferBorderFinalization', False):
			parent = self._gui.currentLayout
			if not hasattr(parent._qLayout, 'finalizeBorders') or parent is self:
				if hasattr(self._qLayout, 'finalizeBorders'):
					self._qLayout.finalizeBorders()

			if self._forWidget is not None:
				if hasattr(self._qLayout, 'updateSizePolicyForWidget'):
					self._qLayout.updateSizePolicyForWidget(self._forWidget)
		else:  # if getattr(self, '_deferBorderFinalization', False):
			# if _deferBorderFinalization was true, set it to false, so the border will be initialized eventually.
			self._deferBorderFinalization = False
		return super().__exit__(exc_type, exc_value, traceback)

	@abstractmethod
	def _collectAllOldItems(self) -> list[LayoutItemOrWidget]:
		pass

	@abstractmethod
	def _removeOldItem(self, item: LayoutItemOrWidget) -> None:
		pass

	def getOldItem(self) -> Optional[LayoutItemOrWidget]:
		return (self._oldItems[0]) if self._oldItems else None

	def takeOldItem(self) -> Optional[LayoutItemOrWidget]:
		return (self._oldItems.pop(0)) if self._oldItems else None

	def getLastItem(self) -> Optional[LayoutItemOrWidget]:
		return (self._newItems[-1]) if self._newItems else None


class Layout(LayoutBase[QLayout], ABC):
	def __init__(self, gui: PythonGUI, qLayout: QLayout, *, forWidget: Optional[QWidget] = None):
		super(Layout, self).__init__(gui, qLayout, forWidget=forWidget)

		self._newMarker: Marker = Marker(0, [])
		self._oldMarker: Marker = Marker(0, [])

	def __enter__(self: _TS) -> _TS:
		super().__enter__()
		if hasattr(self._qLayout, '_Layout__markers'):
			self._oldMarker = deepcopy(self._qLayout.__markers)
			del self._qLayout.__markers
			# printIndented(formatVal(self._oldMarker))
		# for item in self._oldItems:
		# 	item.setParent(None)
		self._newMarker = Marker(0, [])

		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self._qLayout.__markers = self._newMarker
		return super().__exit__(exc_type, exc_value, traceback)

	def _collectAllOldItems(self) -> list[LayoutItemOrWidget]:
		return [self._qLayout.itemAt(i) for i in range(0, self._qLayout.count())]

	def _removeOldItem(self, item: LayoutItemOrWidget) -> None:
		deleteItemFromLayout(item, self._qLayout)

	def _addItem(self, ItemType: TWidgetOrType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, args: tuple = ()) -> _TWidget:
		item_ = self.takeOldItem()
		item = _getItem(item_)

		hasToAddItem: bool = True  # evaluation only! original value was False
		mustCallOnInit: bool = False
		markAsDontDelete: bool = False
		if isinstance(ItemType, QWidget) and ItemType is not QWidget:
			markAsDontDelete = True
			if item is not ItemType:
				deleteItemFromLayout(item_, self._qLayout)
				item = ItemType
				hasToAddItem = True
		else:
			if type(item) is not ItemType:
				deleteItemFromLayout(item_, self._qLayout)
				if isinstance(initArgs, dict):
					item = ItemType(**initArgs)
				else:
					item = ItemType(*initArgs)
				if onInit is not None:
					mustCallOnInit = True
				hasToAddItem = True

		if hasToAddItem:
			if isinstance(item, QWidget):
				# print("adding Widget, args={}".format(type(item)))
				if markAsDontDelete:
					setattr(item, CAT_DONT_DELETE_MARKER, True)
				self._qLayout.removeWidget(item)
				self._qLayout.addWidget(item, *args)
				if item.isHidden():
					item.show()
			elif isinstance(item, QLayout):
				# print("adding Layout, args={}".format(args))
				self._qLayout.removeItem(item)
				self._qLayout.addLayout(item, *args)
			elif isinstance(item, QSpacerItem):
				self._qLayout.removeItem(item)
				self._qLayout.addItem(item, *args)
			else:
				raise Exception(f'cannot add item {item}')
		if mustCallOnInit:
			onInit(item)  # make sure that item has a parent when onInit is called!
		self._newItems.append(item)
		self._index += 1
		return item


class DirectionalLayout(Layout, ABC):
	QLayoutType = QGridLayout

	def __init__(self, gui: PythonGUI, qLayout: QGridLayout, preventVStretch: bool, preventHStretch: bool, deferBorderFinalization: bool, *, forWidget: Optional[QWidget] = None):
		super(DirectionalLayout, self).__init__(gui, qLayout, forWidget=forWidget)
		self._qLayout: QGridLayout = qLayout  # just for the typeChecker
		self._preventVStretch: bool = preventVStretch
		self._preventHStretch: bool = preventHStretch
		self._deferBorderFinalization: bool = deferBorderFinalization
		self._row: int = 0
		self._column: int = 0
		self._rowCount: int = 0
		self._columnCount: int = 0
		self.resetIndex()

		# fix a Qt bug:
		style: QtWidgets.QStyle = QtWidgets.QApplication.style()
		if qLayout.horizontalSpacing() == -1:
			hSpace = style.pixelMetric(style.PM_LayoutHorizontalSpacing, None, None)
			qLayout.setHorizontalSpacing(hSpace)
		if qLayout.verticalSpacing() == -1:
			vSpace = style.pixelMetric(style.PM_LayoutVerticalSpacing, None, None)
			qLayout.setVerticalSpacing(vSpace)
		# self._qLayout.setVerticalSpacing(1) # TODO: Investigate

	def __exit__(self, exc_type, exc_value, traceback):
		try:
			if self._preventHStretch:
				# add spacer to the right:
				self._addPositionedItem(QSpacerItem, 0, self._columnCount, initArgs=(0, 0))
				self._column += 1
				self._qLayout.setColumnStretch(self._columnCount, 1)

			if self._preventVStretch:
				# add spacer at the end, so widgets are aligned at the top:
				self._addPositionedItem(QSpacerItem, self._rowCount, 0, initArgs=(0, 0))
				self._qLayout.setRowStretch(self._row, 1)
				self._row += 1
		finally:
			hasHandeledException = super().__exit__(exc_type, exc_value, traceback)
		return hasHandeledException

	def resetIndex(self):
		super(DirectionalLayout, self).resetIndex()
		self._row = 0
		self._column = 0
		self._rowCount = 0
		self._columnCount = 0

	def _updateRowColumnCounts(self):
		self._rowCount = max(self._rowCount, self._row + 1)
		self._columnCount = max(self._columnCount, self._column + 1)

	def _addPositionedItem(self, ItemType: TWidgetOrType, row: int, column: int, rowSpan: int = 1, columnSpan: int = 1, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None) -> _TWidget:
		return self._addItem(ItemType, args=(row, column, rowSpan, columnSpan), initArgs=initArgs, onInit=onInit)

	def columnStretch(self, column: int) -> int:
		return self._qLayout.columnStretch(column)

	def setColumnStretch(self, column: int, stretch: int) -> None:
		self._qLayout.setColumnStretch(column, stretch)

	def rowStretch(self, row: int) -> int:
		return self._qLayout.rowStretch(row)

	def setRowStretch(self, row: int, stretch: int) -> None:
		self._qLayout.setRowStretch(row, stretch)

	@property
	def currentColumnStretch(self) -> int:
		return self._qLayout.columnStretch(self._column)

	@currentColumnStretch.setter
	def currentColumnStretch(self, stretch: int):
		self._qLayout.setColumnStretch(self._column, stretch)

	@property
	def nextColumnStretch(self) -> int:
		return self._qLayout.columnStretch(self._column+1)

	@nextColumnStretch.setter
	def nextColumnStretch(self, stretch: int):
		self._qLayout.setColumnStretch(self._column+1, stretch)

	@property
	def currentRowStretch(self) -> int:
		return self._qLayout.rowStretch(self._row)

	@currentRowStretch.setter
	def currentRowStretch(self, stretch: int):
		self._qLayout.setRowStretch(self._row, stretch)

	@property
	def nextRowStretch(self) -> int:
		return self._qLayout.rowStretch(self._row+1)

	@nextRowStretch.setter
	def nextRowStretch(self, stretch: int):
		self._qLayout.setRowStretch(self._row+1, stretch)


class QSingleColumnLayout(QGridLayout):
	pass


class QDoubleColumnLayout(QGridLayout):
	def setVerticalSpacing(self, spacing: int) -> None:
		super(QDoubleColumnLayout, self).setVerticalSpacing(spacing)


class QTableLayout(QGridLayout):
	pass


class QSingleRowLayout(QGridLayout):
	def setHorizontalSpacing(self, spacing: int) -> None:
		super(QSingleRowLayout, self).setHorizontalSpacing(spacing)


class QDoubleRowLayout(QGridLayout):
	pass


class SingleColumnLayout(DirectionalLayout):
	QLayoutType = QSingleColumnLayout

	def __init__(self, gui: PythonGUI, qLayout: QGridLayout, preventVStretch: bool, preventHStretch: bool, *, deferBorderFinalization: bool = False, forWidget: Optional[QWidget] = None):
		super(SingleColumnLayout, self).__init__(gui, qLayout, preventVStretch, preventHStretch, deferBorderFinalization, forWidget=forWidget)

	def addItem(self, ItemType: TWidgetOrType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False) -> _TWidget:
		item = self._addPositionedItem(ItemType, self._row, self._column, 1, 1, initArgs, onInit=onInit)
		self._row += 1
		self._updateRowColumnCounts()
		return item

	def canIndentItem(self, isPrefix: bool):
		return True


class DoubleColumnLayout(DirectionalLayout):
	QLayoutType = QDoubleColumnLayout

	def __init__(self, gui: PythonGUI, qLayout: QGridLayout, preventVStretch: bool, preventHStretch: bool, *, deferBorderFinalization: bool = False, forWidget: Optional[QWidget] = None):
		super().__init__(gui, qLayout, preventVStretch, preventHStretch, deferBorderFinalization, forWidget=forWidget)

	def __exit__(self, exc_type, exc_value, traceback):
		try:
			# always set column stretch, so that labels are not unnecessarily large:
			self._qLayout.setColumnStretch(0, 0)
			self._qLayout.setColumnStretch(self._qLayout.columnCount()-1, 1)
		finally:
			return super().__exit__(exc_type, exc_value, traceback)

	def addItem(self, ItemType: TWidgetOrType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False) -> _TWidget:
		hasPrefix = self._hasPrefix()
		columnSpan = 1 if isPrefix or hasPrefix else 2
		if isPrefix and hasPrefix:
			self.carriageReturn()

		item = self._addPositionedItem(ItemType, self._row, self._column, 1, columnSpan, initArgs, onInit=onInit)

		if self._preventVStretch:
			self._qLayout.setRowStretch(self._row, 0)

		self._column += columnSpan
		if self._column > 1:
			self.carriageReturn()
		else:
			self._updateRowColumnCounts()
		return item

	def canIndentItem(self, isPrefix: bool):
		return isPrefix or not self._hasPrefix()

	def carriageReturn(self):
		self._row += 1
		self._column = 0
		self._updateRowColumnCounts()

	def _hasPrefix(self):
		return self._column == 1


class PrefixMode(enum.Enum):
	none = 0
	first = 1
	all = 2


class TableLayoutRowManager(object):
	def __init__(self, layout: TableLayout):
		super().__init__()
		self._layout: TableLayout = layout

	def advanceRow(self):
		self._layout.carriageReturn()

	def advanceColumn(self):
		self._layout.carriageAdvance()

	def setNextItemSpan(self, span: int):
		"""
		actual span =
			| isPrefix == True: 1
			| hasPrefix == True: span
			| hasPrefix == False: span + 1
		if isPrefix == True: nextItemSpan won't be reset.
		:param span:
		:return:
		"""
		self._layout.setNextItemColumnSpan(span)

	def columnStretch(self, column: int) -> int:
		return self._layout.columnStretch(column)

	def setColumnStretch(self, column: int, stretch: int) -> None:
		self._layout.setColumnStretch(column, stretch)

	def rowStretch(self, row: int) -> int:
		return self._layout.rowStretch(row)

	def setRowStretch(self, row: int, stretch: int) -> None:
		self._layout.setRowStretch(row, stretch)

	@property
	def currentColumnStretch(self) -> int:
		return self._layout.currentColumnStretch

	@currentColumnStretch.setter
	def currentColumnStretch(self, stretch: int):
		self._layout.currentColumnStretch = stretch

	@property
	def nextColumnStretch(self) -> int:
		return self._layout.nextColumnStretch

	@nextColumnStretch.setter
	def nextColumnStretch(self, stretch: int):
		self._layout.nextColumnStretch = stretch

	@property
	def currentRowStretch(self) -> int:
		return self._layout.currentRowStretch

	@currentRowStretch.setter
	def currentRowStretch(self, stretch: int):
		self._layout.currentRowStretch = stretch

	@property
	def nextRowStretch(self) -> int:
		return self._layout.nextRowStretch

	@nextRowStretch.setter
	def nextRowStretch(self, stretch: int):
		self._layout.nextRowStretch = stretch


class TableLayout(DirectionalLayout):
	# conceptually somewhat like a hypothetical MultiColumnLayout
	QLayoutType = QTableLayout

	def __init__(self, gui: PythonGUI, qLayout: QGridLayout, preventVStretch: bool, preventHStretch: bool, prefixMode: PrefixMode, *, deferBorderFinalization: bool = False, forWidget: Optional[QWidget] = None):
		self._qLayout: QGridLayout = qLayout
		super().__init__(gui, qLayout, preventVStretch, preventHStretch, deferBorderFinalization, forWidget=forWidget)
		self._defaultColumnSpan = 1  # of course! ;-)
		self._nextColumnSpan = 1
		self._prefixMode: PrefixMode = prefixMode

	def __enter__(self):
		super().__enter__()
		return TableLayoutRowManager(self)

	def __exit__(self, exc_type, exc_value, traceback):
		# # always set column stretch, so that labels are not unnecessarily large:
		# for col in range(1, self._qLayout.columnCount()):
		# 	self._qLayout.setColumnStretch(col, 1)
		return super().__exit__(exc_type, exc_value, traceback)

	def addItem(self, ItemType: TWidgetOrType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False) -> _TWidget:
		if isPrefix:
			columnSpan = 1
			if self._hasPrefix:
				self.carriageAdvance()
		else:
			columnSpan = self._nextColumnSpan
			if self.prefixExpected:
				columnSpan += 1
			self._nextColumnSpan = self._defaultColumnSpan

		item = self._addPositionedItem(ItemType, self._row, self._column, 1, columnSpan, initArgs, onInit=onInit)

		if self._preventVStretch and self._column == 0:
			self._qLayout.setRowStretch(self._row, 0)

		self._column += columnSpan
		self._updateRowColumnCounts()
		return item

	def setNextItemColumnSpan(self, span: int) -> None:
		self._nextColumnSpan = span

	def canIndentItem(self, isPrefix: bool):
		return self._column == 0  # and (isPrefix or not self._hasPrefix)

	def carriageAdvance(self):
		"""
		advances the column count to the next prefix position.
		"""
		self._row += 0
		self._column += 2 if self.prefixExpected else 1
		self._updateRowColumnCounts()

	def carriageReturn(self):
		self._row += 1
		self._column = 0
		self._updateRowColumnCounts()

	@property
	def prefixExpected(self) -> bool:
		if self._prefixMode is PrefixMode.none:
			return False
		elif self._prefixMode is PrefixMode.first:
			return self._column == 0
		else:
			return self._column % 2 == 0

	@property
	def _hasPrefix(self) -> bool:
		return self._column % 2 == 1


class SingleRowLayout(DirectionalLayout):
	QLayoutType = QSingleRowLayout

	def __init__(self, gui: PythonGUI, qLayout: QGridLayout, preventVStretch: bool, preventHStretch: bool, *, deferBorderFinalization: bool = False, forWidget: Optional[QWidget] = None):
		super(SingleRowLayout, self).__init__(gui, qLayout, preventVStretch, preventHStretch, deferBorderFinalization, forWidget=forWidget)

	def addItem(self, ItemType: TWidgetOrType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False) -> _TWidget:
		item = self._addPositionedItem(ItemType, self._row, self._column, 1, 1, initArgs, onInit=onInit)
		self._column += 1
		self._updateRowColumnCounts()
		return item

	def canIndentItem(self, isPrefix: bool):
		return True


class DoubleRowLayout(DirectionalLayout):
	QLayoutType = QDoubleRowLayout

	def __init__(self, gui: PythonGUI, qLayout: QGridLayout, preventVStretch: bool, preventHStretch: bool, *, deferBorderFinalization: bool = False, forWidget: Optional[QWidget] = None):
		super(DoubleRowLayout, self).__init__(gui, qLayout, preventVStretch, preventHStretch, deferBorderFinalization, forWidget=forWidget)
		self.resetIndex()

	def addItem(self, ItemType: TWidgetOrType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False) -> _TWidget:
		hasPrefix = self._hasPrefix()
		rowSpan = 1 if isPrefix or hasPrefix else 2
		if isPrefix and hasPrefix:
			self.carriageReturn()

		item = self._addPositionedItem(ItemType, self._row, self._column, rowSpan, 1, initArgs, onInit=onInit)

		if self._preventHStretch:
			self._qLayout.setColumnStretch(self._column, 0)

		self._row += rowSpan
		if self._row > 1:
			self.carriageReturn()
		else:
			self._updateRowColumnCounts()
		return item

	def canIndentItem(self, isPrefix: bool):
		return False

	def carriageReturn(self):
		self._row = 0
		self._column += 1
		self._updateRowColumnCounts()

	def _hasPrefix(self):
		return self._row == 1


class SizePolicyTuple(NamedTuple):
	hPolicy: QSizePolicy.Policy
	vPolicy: QSizePolicy.Policy


_NONE_SIZE_POLICY_TUPLE = SizePolicyTuple(cast(QSizePolicy.Policy, None), cast(QSizePolicy.Policy, None))
_EMPTY_TUPLE = ()


class SeamlessQGridLayout(QGridLayout, CatFramedWidgetMixin):
	def __init__(self, parent: QWidget = None):
		super().__init__(parent)
		self.setContentsMargins(0, 0, 0, 0)
		self.setVerticalSpacing(0)
		self.setHorizontalSpacing(0)
		self._overlapCharacteristics: Optional[OverlapCharacteristics] = None

	def addWidget(self, w: QWidget, *args) -> None:
		super(SeamlessQGridLayout, self).addWidget(w, *args)
		self._overlapCharacteristics = None

	def addLayout(self, a0: QLayout, *args) -> None:
		super(SeamlessQGridLayout, self).addLayout(a0, *args)
		self._overlapCharacteristics = None

	def addItem(self, item: QLayoutItem, *args) -> None:
		super(SeamlessQGridLayout, self).addItem(item, *args)
		self._overlapCharacteristics = None

	@property
	def overlapCharacteristics(self) -> OverlapCharacteristics:
		try:
			if self._overlapCharacteristics is None:
				colCount = self.columnCount() # todo use actual columnCount and columnStart
				rowCount = self.rowCount() # todo use actual rowCount and rowStart
				lastCol = colCount - 1
				lastRow = rowCount - 1
				contentMargins: tuple[int, int, int, int] = self.getContentsMargins()
				canReqL = (True, True, True) if contentMargins[0] > 0 else getOverlapCharacteristics([self.itemAtPosition(i, 0) for i in range(rowCount)], 0)
				canReqT = (True, True, True) if contentMargins[1] > 0 else getOverlapCharacteristics([self.itemAtPosition(0, i) for i in range(colCount)], 1)
				canReqR = (True, True, True) if contentMargins[2] > 0 else getOverlapCharacteristics([self.itemAtPosition(i, lastCol) for i in range(rowCount)], 2)
				canReqB = (True, True, True) if contentMargins[3] > 0 else getOverlapCharacteristics([self.itemAtPosition(lastRow, i) for i in range(colCount)], 3)
				# if contentMargins != NO_MARGINS:
				# 	characteristics = OverlapCharacteristics(
				# 		(True, True) if contentMargins[0] > 0 else canReqL,
				# 		(True, True) if contentMargins[1] > 0 else canReqT,
				# 		(True, True) if contentMargins[2] > 0 else canReqR,
				# 		(True, True) if contentMargins[3] > 0 else canReqB,
				# 	)
				self._overlapCharacteristics = OverlapCharacteristics(canReqL, canReqT, canReqR, canReqB)
			return self._overlapCharacteristics
		except Exception as e:
			print(format_full_exc(e))
			raise

	def finalizeBorders(self):
		self.finalizeBorders2New()

	def finalizeBorders1Old(self):
		self.setVerticalSpacing(0)
		self.setHorizontalSpacing(0)
		olp = self.overlap()
		crn = self.roundedCorners()
		lastCol = self.columnCount() - 1
		lastRow = self.rowCount() - 1
		for i in range(self.count()):
			framed = _framedForItem(self.itemAt(i))
			if framed is None:
				continue

			row, col, rowSpan, colSpan = self.getItemPosition(i)
			isL = col == 0
			isR = col + colSpan - 1 == lastCol
			isT = row == 0
			isB = row + rowSpan - 1 == lastRow

			itemL = _framedForItem(self.itemAtPosition(row, col - 1))
			itemT = _framedForItem(self.itemAtPosition(row - 1, col))
			itemR = _framedForItem(self.itemAtPosition(row, col + colSpan))
			itemB = _framedForItem(self.itemAtPosition(row + rowSpan, col))

			otherOlpL = (False, False, False) if itemL is None else itemL.overlapCharacteristics.right
			otherOlpT = (False, False, False) if itemT is None else itemT.overlapCharacteristics.bottom
			otherOlpR = (False, False, False) if itemR is None else itemR.overlapCharacteristics.left
			otherOlpB = (False, False, False) if itemB is None else itemB.overlapCharacteristics.top

			overlap, corners = calculateBorderInfo(framed.overlapCharacteristics, otherOlpL, otherOlpT, otherOlpR, otherOlpB, isL, isT, isR, isB, olp, crn, (1, 1))
			finalizeBorders(framed, overlap, corners)

	def finalizeBorders2New(self):
		self.setVerticalSpacing(0)
		self.setHorizontalSpacing(0)
		olp = self.overlap()
		crn = self.roundedCorners()
		cCnt = self.columnCount()
		rCnt = self.rowCount()

		# rowCount() and columnCount() does not return the number of actually used rows / columns, but rather the number of allocated rows / columns.
		# see also: https://stackoverflow.com/questions/13405997/delete-a-row-from-qgridlayout
		actualRCnt = 0
		actualCCnt = 0
		actualRStart = 999999
		actualCStart = 999999

		_framedItemsAtPos = []
		for col in range(cCnt):
			for row in range(rCnt):
				item = self.itemAtPosition(row, col)
				_framedItemsAtPos.append(_framedForItem(item))
				if item is not None:
					actualCCnt = max(actualCCnt, col + 1)
					actualRCnt = max(actualRCnt, row + 1)
					actualCStart = min(actualCStart, col)
					actualRStart = min(actualRStart, row)

		actualCStart = min(actualCStart, actualCCnt)
		actualRStart = min(actualRStart, actualRCnt)

		def framedItemsAtCol(row: slice, col: int) -> list[Optional[CatFramedWidgetMixin]]:
			sel = slice(row.start + col * rCnt, row.stop + col * rCnt)
			selItems = _framedItemsAtPos[sel]
			return list(filter(None, selItems))

		def framedItemsAtRow(row: int, col: slice) -> list[Optional[CatFramedWidgetMixin]]:
			sel = slice(row + col.start * rCnt, row + col.stop * rCnt, rCnt)
			selItems = _framedItemsAtPos[sel]
			return list(filter(None, selItems))

		for i in range(self.count()):
			framed = _framedForItem(self.itemAt(i))
			if framed is None:
				continue

			row, col, rowSpan, colSpan = self.getItemPosition(i)
			isL = col <= actualCStart
			isR = col + colSpan == actualCCnt
			isT = row <= actualRStart
			isB = row + rowSpan == actualRCnt

			itemsL = framedItemsAtCol(slice(row, row+rowSpan),       col - 1) if not isL else _EMPTY_TUPLE
			itemsT = framedItemsAtRow(      row - 1,           slice(col, col+colSpan)) if not isT else _EMPTY_TUPLE
			itemsR = framedItemsAtCol(slice(row, row+rowSpan),       col + colSpan) if not isR else _EMPTY_TUPLE
			itemsB = framedItemsAtRow(      row + rowSpan,     slice(col, col+colSpan)) if not isB else _EMPTY_TUPLE

			otherOlpL = (False, False, False) if not itemsL else getOverlapCharacteristics2(itemsL, 2)  # =^ itemL.overlapCharacteristics.right
			otherOlpT = (False, False, False) if not itemsT else getOverlapCharacteristics2(itemsT, 3)  # =^ itemT.overlapCharacteristics.bottom
			otherOlpR = (False, False, False) if not itemsR else getOverlapCharacteristics2(itemsR, 0)  # =^ itemR.overlapCharacteristics.left
			otherOlpB = (False, False, False) if not itemsB else getOverlapCharacteristics2(itemsB, 1)  # =^ itemB.overlapCharacteristics.top

			overlap, corners = calculateBorderInfo(framed.overlapCharacteristics, otherOlpL, otherOlpT, otherOlpR, otherOlpB, isL, isT, isR, isB, olp, crn, (1, 1))
			finalizeBorders(framed, overlap, corners)

	def updateSizePolicyForWidget(self, wd: QWidget):
		spt = self._recalculateSizePolicy()
		if spt is not None:
			sp = wd.sizePolicy()
			sp.setHorizontalPolicy(spt.hPolicy)
			sp.setVerticalPolicy(spt.vPolicy)
			wd.setSizePolicy(sp)

	def _recalculateSizePolicy(self) -> Optional[SizePolicyTuple]:
		"""
		:return: tuple[horizontalPolicy, verticalPolicy]
		"""
		cCnt = self.columnCount()
		rCnt = self.rowCount()

		policyForItem: dict[int, tuple[SizePolicyTuple, Any]] = {}

		items = [self.itemAt(i) for i in range(self.count())]

		for item in items:
			spt: SizePolicyTuple
			if (layout := item.layout()) is not None:
				spt = layout._recalculateSizePolicy() if hasattr(layout, '_recalculateSizePolicy') else None
				if spt is None:
					# not seamless
					return None
			else:
				sp = (item.spacerItem() or item.widget()).sizePolicy()
				spt = SizePolicyTuple(sp.horizontalPolicy(), sp.verticalPolicy())
			policyForItem[id(item)] = spt, (item.layout() or item.spacerItem() or item.widget())

		colsPolicies: list[list[QSizePolicy.Policy]] = [[] for _ in range(cCnt)]
		rowsPolicies: list[list[QSizePolicy.Policy]] = [[] for _ in range(rCnt)]

		for row in range(rCnt):
			for col in range(cCnt):
				item = self.itemAtPosition(row, col)
				if item is not None:
					spt = policyForItem[id(item)][0]
					rowsPolicies[row].append(spt.hPolicy)
					colsPolicies[col].append(spt.vPolicy)

		colPolicies = [_mergePoliciesSerial(cPols) for cPols in colsPolicies]
		rowPolicies = [_mergePoliciesSerial(rPols) for rPols in rowsPolicies]
		vPolicy = QSizePolicy.Policy(_mergePoliciesParallel(colPolicies))
		hPolicy = QSizePolicy.Policy(_mergePoliciesParallel(rowPolicies))
		return SizePolicyTuple(hPolicy, vPolicy)


def _mergePoliciesSerial(policies: list[QSizePolicy.Policy]) -> QSizePolicy.Policy:
	return ft.reduce(_mergePoliciesSerial2, policies) if policies else QSizePolicy.IgnoreFlag


def _mergePoliciesParallel(policies: list[QSizePolicy.Policy]) -> QSizePolicy.Policy:
	return ft.reduce(_mergePoliciesParallel2, policies) if policies else QSizePolicy.IgnoreFlag


def _mergePoliciesSerial2(p1: QSizePolicy.Policy, p2: QSizePolicy.Policy) -> QSizePolicy.Policy:
	# QSizePolicy::Fixed		0	The QWidget::sizeHint() is the only acceptable alternative, so the widget can never grow or shrink (e.g. the vertical direction of a push button).
	# ------------------------------------------------------------------------------------
	# QSizePolicy::GrowFlag		1	The widget can grow beyond its size hint if necessary.
	# QSizePolicy::ExpandFlag	2	The widget should get as much space as possible.
	# QSizePolicy::ShrinkFlag	4	The widget can shrink below its size hint if necessary.
	# QSizePolicy::IgnoreFlag	8	The widget's size hint is ignored. The widget will get as much space as possible.
	if p1 & QSizePolicy.IgnoreFlag and p2 & QSizePolicy.IgnoreFlag:
		return QSizePolicy.IgnoreFlag
	merged = p1 | p2
	return (merged | QSizePolicy.IgnoreFlag) ^ QSizePolicy.IgnoreFlag  # remove the IgnoreFlag
	# QSizePolicy.Policy.Preferred
	# QSizePolicy.Policy.Maximum
	# PolicyFlag = QSizePolicy.PolicyFlag
	# gf = p1 & PolicyFlag.GrowFlag or p2 & PolicyFlag.GrowFlag
	# ef = p1 & PolicyFlag.ExpandFlag or p2 & PolicyFlag.ExpandFlag


def _mergePoliciesParallel2(p1: QSizePolicy.Policy, p2: QSizePolicy.Policy) -> QSizePolicy.Policy:
	if p1 & QSizePolicy.IgnoreFlag:
		return p2
	elif p2 & QSizePolicy.IgnoreFlag:
		return p1
	return p1 & p2


def _framedForItem(item: QLayoutItem) -> Optional[CatFramedWidgetMixin]:
	if item is None:
		return None
	widget = item.widget()
	if widget is not None:
		item = widget
		if isinstance(widget, CatFramedWidgetMixin):
			return widget
	if isinstance(item.layout(), CatFramedWidgetMixin):
		return item.layout()
	return None


def getOverlapCharacteristics(items: Iterable[QLayoutItem], directionSel: int) -> OverlapCharTpl:
	"""
	:param items:
	:param directionSel: 0 = left, 1 = top, 2 = right, 3 = bottom, see also :type:`OverlapCharacteristics`
	:return: tuple[can, req, has]
	"""
	canO = True
	reqO = False
	hasB = True
	anyIsFramed = False
	for item in items:
		if item is None:
			continue
		isFramedWidget = isinstance(item.widget(), CatFramedWidgetMixin)
		if not isFramedWidget:
			item = item.layout()
			isFramedWidget = isinstance(item, CatFramedWidgetMixin)
		else:
			item = item.widget()
		if isFramedWidget:
			anyIsFramed = True
			char: OverlapCharTpl = item.overlapCharacteristics[directionSel]
			canO = canO and char[0]
			reqO = reqO or char[1]
			hasB = hasB and char[2]
		else:
			hasB = False

	# why was this different from getOverlapCharacteristics2(...)???:
	# return canO, reqO  # and anyIsFramed, reqO
	return canO or not anyIsFramed, reqO, hasB and anyIsFramed


def getOverlapCharacteristics2(items: Iterable[QLayout | QWidget], directionSel: int) -> OverlapCharTpl:
	"""
	:param items:
	:param directionSel: 0 = left, 1 = top, 2 = right, 3 = bottom, see also :type:`OverlapCharacteristics`
	:return: tuple[can, req, has]
	"""
	canO = True
	reqO = False
	hasB = True
	anyIsFramed = False
	for item in items:
		if isinstance(item, CatFramedWidgetMixin):
			anyIsFramed = True
			char: OverlapCharTpl = item.overlapCharacteristics[directionSel]
			canO = canO and char[0]
			reqO = reqO or char[1]
			hasB = hasB and char[2]
		else:
			hasB = False
	return canO and anyIsFramed, reqO, hasB and anyIsFramed


def calculateBorderInfoSimple(isL: bool, isR: bool, isT: bool, isB: bool, olp: Overlap, crn: RoundedCorners, internalOverlap: tuple[int, int]) -> tuple[Overlap, RoundedCorners]:
	overlap = (
		olp[0] if isL else internalOverlap[0],
		olp[1] if isT else internalOverlap[1],
		olp[2] if isR else 0,
		olp[3] if isB else 0,
	)
	corners = (
		isL and isT and crn[0],  # LT
		isR and isT and crn[1],  # RT
		isL and isB and crn[2],  # LB
		isR and isB and crn[3],  # RB
	)
	return overlap, corners


def calculateBorderInfo(center: OverlapCharacteristics, oL: OverlapCharTpl, oT: OverlapCharTpl, oR: OverlapCharTpl, oB: OverlapCharTpl, isL: bool, isT: bool, isR: bool, isB: bool, olp: Overlap, crn: RoundedCorners, internalOverlap: tuple[int, int]):
	# oL, oT, oR, oB = otherLeft, other, Top, otherRight, otherBottom
	# OverlapCharTpl = (can, req, has) aka. (can overlap, requires overlap, has border over full length
	c = center
	overlap = (
		#                                         (i can)     ( we need overlap )         (prefer r / b border & other can)
		olp[0] if isL else (internalOverlap[0] if c[0][0] and (c[0][1] and oL[1]) and not (c[0][2] and not oL[2] and oL[0]) else 0),
		olp[1] if isT else (internalOverlap[1] if c[1][0] and (c[1][1] and oT[1]) and not (c[1][2] and not oT[2] and oT[0]) else 0),
		#                                         (i can)     ( we need overlap )     (other can't) ( prefer r / b border  )
		olp[2] if isR else (internalOverlap[0] if c[2][0] and (c[2][1] and oR[1]) and (not oR[0] or (oR[2] and not c[2][2])) else 0),
		olp[3] if isB else (internalOverlap[1] if c[3][0] and (c[3][1] and oB[1]) and (not oB[0] or (oB[2] and not c[3][2])) else 0),
	)
	corners = (
		isL and isT and crn[0],  # LT
		isR and isT and crn[1],  # RT
		isL and isB and crn[2],  # LB
		isR and isB and crn[3],  # RB
	)
	return overlap, corners


def finalizeBorders(item: QLayout | QWidget, overlap: Overlap, corners: RoundedCorners) -> None:
	layout: QLayout = item.layout()
	if isinstance(item, CatFramedWidgetMixin):
		item.setOverlap(overlap)
		item.setRoundedCorners(corners)
	elif isinstance(layout, CatFramedWidgetMixin):
		layout.setOverlap(overlap)
		layout.setRoundedCorners(corners)

	if hasattr(item, 'finalizeBorders'):
		item.finalizeBorders()
	elif hasattr(layout, 'finalizeBorders'):
		layout.finalizeBorders()


class SeamlessSingleColumnLayout(SingleColumnLayout):
	QLayoutType = SeamlessQGridLayout


class SeamlessDoubleColumnLayout(DoubleColumnLayout):
	QLayoutType = SeamlessQGridLayout


class SeamlessSingleRowLayout(SingleRowLayout):
	QLayoutType = SeamlessQGridLayout


class SeamlessDoubleRowLayout(DoubleRowLayout):
	QLayoutType = SeamlessQGridLayout


def getSingleColumnLayout(seamless: bool) -> Type[SingleColumnLayout | SeamlessSingleColumnLayout]:
	return SeamlessSingleColumnLayout if seamless else SingleColumnLayout


def getDoubleColumnLayout(seamless: bool) -> Type[DoubleColumnLayout | SeamlessDoubleColumnLayout]:
	return SeamlessDoubleColumnLayout if seamless else DoubleColumnLayout


def getSingleRowLayout(seamless: bool) -> Type[SingleRowLayout | SeamlessSingleRowLayout]:
	return SeamlessSingleRowLayout if seamless else SingleRowLayout


def getDoubleRowLayout(seamless: bool) -> Type[DoubleRowLayout | SeamlessDoubleRowLayout]:
	return SeamlessDoubleRowLayout if seamless else DoubleRowLayout


__all__ = [
	'DictOrTuple',
	# 'AddItemToLayoutFunc',
	'Marker',
	'deleteWidget',
	'deleteLayout',
	'deleteItemFromLayout',
	'removeItemsFromLayout',
	'WithBlock',
	'LayoutBase',
	'Layout',
	'DirectionalLayout',
	'SingleColumnLayout',
	'DoubleColumnLayout',
	'PrefixMode',
	'TableLayoutRowManager',
	'TableLayout',
	'SingleRowLayout',
	'DoubleRowLayout',
	'getOverlapCharacteristics',
	'getOverlapCharacteristics2',
	'calculateBorderInfoSimple',
	'calculateBorderInfo',
	'finalizeBorders',
	'SeamlessSingleColumnLayout',
	'SeamlessDoubleColumnLayout',
	'SeamlessSingleRowLayout',
	'SeamlessDoubleRowLayout',
	'getSingleColumnLayout',
	'getDoubleColumnLayout',
	'getSingleRowLayout',
	'getDoubleRowLayout',
]
