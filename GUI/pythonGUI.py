#  Copyright (c) 2018 Joachim Coenen. All Rights Reserved
from __future__ import annotations

import dataclasses
import functools as ft
import itertools
import math
import os
from abc import abstractmethod
from datetime import date
from enum import Enum
from types import EllipsisType
from typing import Any, Callable, ClassVar, ContextManager, Generic, Iterable, Iterator, Literal, Optional, Protocol, Sequence, Type, TypeVar, Union, cast, overload

from PyQt5 import QtCore, QtGui, QtWidgets, sip
from PyQt5.QtCore import QItemSelectionModel, QMargins, QObject, Qt, pyqtBoundSignal, pyqtSignal
from PyQt5.QtGui import QFont, QFontDatabase, QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QShortcut, QSizePolicy, QWidget

from ._styles import Style, applyStyle, getStyles
from .components import codeEditor
from .components.Layouts import *
from .components.Widgets import BuilderTreeView, CatBox, CatButton, CatCheckBox, CatComboBox, CatElidedLabel, CatFramelessButton, CatGradiantButton, CatLabel, \
	CatMultiLineTextField, CatOverlay, CatPanel, CatProgressBar, CatRadioButton, CatScrollArea, CatSeparator, CatTextField, CatToolButton, CatToolbarSpacer, DataBuilderTreeView, \
	DataTableModel, DataTableView, Int64SpinBox, Spoiler, Switch
from .components.catTabBar import CatTabBar, TabOptions
from .components.catWidgetMixins import CANT_AND_NO_OVERLAP, CORNERS, CatFramedWidgetMixin, CatScalableWidgetMixin, CatSizePolicyMixin, DEFAULT_PANEL_CORNER_RADIUS, \
	KeySequenceLike, Margins, NO_MARGINS, NO_OVERLAP, Overlap, OverlapCharacteristics, RoundedCorners, getShortcutParent, setQWidgetShortcutBase
from .components.renderArea import CatPainter, RenderArea, Vector
from .components.treeBuilderABC import TreeBuilderABC
from .components.treeBuilders import DataListBuilder, DataTreeBuilderNode
from .enums import *
from .framelessWindow.catFramelessWindowMixin import CatFramelessWindowMixin
from .utilities import connectOnlyOnce, connectSafe
from ..Serializable.utils import get_args
from ..utils import DeferredCallOnceMethod, Deprecated
from ..utils.collections_ import AddToDictDecorator, Stack, getIfKeyIssubclass, getIfKeyIssubclassOrEqual
from ..utils.profiling import ProfiledAction, TimedAction
from ..utils.utils import CrashReportWrapped

if not hasattr(QtCore, 'Signal'):
	QtCore.Signal = QtCore.pyqtSignal

# global variables for debugging:
ADD_LAYOUT_INFO_AS_TOOL_TIP: bool = False
PROFILING_ENABLED: bool = False


_TT = TypeVar('_TT')
_TS = TypeVar('_TS')
_T2 = TypeVar('_T2')
_TQWidget = TypeVar('_TQWidget', bound=QWidget)
_TDirectionalLayout = TypeVar('_TDirectionalLayout', bound=DirectionalLayout)


MenuItemValue = Union[None, Callable[[], None], Iterable['MenuItemData']]
MenuItemDataShort = tuple[str, MenuItemValue]
MenuItemDataLong = tuple[str, MenuItemValue, dict[str, Any]]
MenuItemData = Union[MenuItemDataShort, MenuItemDataLong]

BoolOrCheckState = Union[bool, ToggleCheckState]


class GuiDrawerFunc(Protocol[_TT]):
	def __call__(self, gui: PythonGUI, v: _TT, **kwargs) -> _TT:
		...


# useful:
qEmptyIcon = QtGui.QIcon()


__widgetDrawers = dict()
WidgetDrawer: AddToDictDecorator[Type[_TT], GuiDrawerFunc[_TT]] = AddToDictDecorator[Type[_TT], GuiDrawerFunc[_TT]](__widgetDrawers)


def addWidgetDrawer(cls: Type[_TT], widgetDrawer: GuiDrawerFunc[_TT]):
	WidgetDrawer(cls)(widgetDrawer)


def getWidgetDrawer(cls: Type[_TT], default: _T2 = None) -> Union[GuiDrawerFunc[_TT], _T2]:
	if issubclass(cls, Enum):
		enumWidgetDrawers = {type_: drawer for type_, drawer in __widgetDrawers.items() if issubclass(type_, Enum)}
		if (drawer := getIfKeyIssubclassOrEqual(enumWidgetDrawers, cls, default)) is not None:
			return drawer
	result = getIfKeyIssubclassOrEqual(__widgetDrawers, cls, None)
	if result is None and hasattr(cls, '__origin__'):
		result = getIfKeyIssubclassOrEqual(__widgetDrawers, cls.__origin__, None)
	if result is None:
		result = default
	return result


class Indentation(WithBlock):
	"""docstring for Indentation"""
	def __init__(self, gui: PythonGUI):
		super().__init__()
		self._gui: PythonGUI = gui
		if isinstance(gui.currentLayout, Layout):
			self._layout: Layout = gui.currentLayout
		else:
			raise ValueError(f"Indentation can only be applied to instances of Layout (and its subclasses). currentLayout was {type(gui.currentLayout)}")

	def __enter__(self):
		super().__enter__()
		self._layout.indentLevel += 1
		self._enterIndex = self._layout._index

		self._outer_oldMarker: Marker = self._layout._oldMarker
		self._oldMarker: Marker = self._outer_oldMarker.innerMarkers.pop(0) if self._outer_oldMarker.innerMarkers else Marker(0, [])
		self._layout._oldMarker = self._oldMarker

		self._newMarker: Marker = Marker(-1, [])
		self._outer_newMarker: Marker = self._layout._newMarker
		self._layout._newMarker = self._newMarker

		self._outer_newMarker.innerMarkers.append(self._newMarker)

	def __exit__(self, exc_type, exc_value, traceback):
		self._layout.indentLevel -= 1
		self._exitIndex = self._layout._index

		self._newMarker.count = self._exitIndex - self._enterIndex
		widgetsToRemove = self._oldMarker.count - self._newMarker.count
		widgetsToRemove = max(0, widgetsToRemove)

		for i in range(widgetsToRemove):
			deleteItemFromLayout(self._layout.takeOldItem(), self._layout._qLayout)
		self._outer_oldMarker.count -= widgetsToRemove

		# set marker list of layout to outer markes list:
		self._layout._newMarker = self._outer_newMarker
		self._layout._oldMarker = self._outer_oldMarker

		return super().__exit__(exc_type, exc_value, traceback)


class CenteredBlock(WithBlock):
	def __init__(self, spacerFunc: Callable[[int, SizePolicy], None]):
		self._spacerFunc: Callable[[int, SizePolicy], None] = spacerFunc

	def __enter__(self):
		super().__enter__()
		self._spacerFunc(0, SizePolicy.Expanding)
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self._spacerFunc(0, SizePolicy.Expanding)
		return super().__exit__(exc_type, exc_value, traceback)


class SeamlessQStackedWidget(QtWidgets.QStackedWidget, CatFramedWidgetMixin, CatSizePolicyMixin):

	def __init__(self, *args):
		super(SeamlessQStackedWidget, self).__init__(*args)
		self._overlapCharacteristics: Optional[OverlapCharacteristics] = None

	def addWidget(self, w: QWidget) -> int:
		self._overlapCharacteristics = None
		return super(SeamlessQStackedWidget, self).addWidget(w)

	def insertWidget(self, index: int, w: QWidget) -> int:
		self._overlapCharacteristics = None
		return super(SeamlessQStackedWidget, self).insertWidget(index, w)

	def removeWidget(self, w: QWidget) -> None:
		self._overlapCharacteristics = None
		return super(SeamlessQStackedWidget, self).removeWidget(w)

	@property
	def overlapCharacteristics(self) -> OverlapCharacteristics:
		if self._overlapCharacteristics is None:
			widget = self.currentWidget()
			if widget is not None:
				self._overlapCharacteristics = self.getOverlapCharacteristicsForLayout(widget.layout())
			else:
				self._overlapCharacteristics = self.getOverlapCharacteristicsForLayout(None)

		return self._overlapCharacteristics

	def finalizeBorders(self) -> None:
		lastIndex = self.count() - 1
		overlap = self.overlap()
		corners = self.roundedCorners()
		for i in range(lastIndex + 1):
			item = self.widget(i)
			finalizeBorders(item, overlap, corners)


class StackedControl(LayoutBase[SeamlessQStackedWidget]):
	def __init__(self, gui: PythonGUI, stackedWidget: SeamlessQStackedWidget, selectedView: Optional[str], *, forWidget: Optional[QWidget] = None):
		super().__init__(gui, stackedWidget, forWidget=forWidget)
		self._selectedViewId: str = self._getIdFromViewIndex(self._selectedIndexFromWidget())
		self._selectedViewRequest: Optional[str] = selectedView

	def _getIdFromViewIndex(self, index: int) -> str:
		currentSelectedView = self._qLayout.widget(index)
		selectedViewIdOrNone = getattr(currentSelectedView, '__id', None)
		return self._getWidget__id(selectedViewIdOrNone, index)

	def _getViewIndexFromId(self, id_: str) -> Optional[int]:
		stackedWidget = self._qLayout
		index = next((i for i in range(stackedWidget.count()) if getattr(stackedWidget.widget(i), '__id', None) == id_), None)
		return index

	def _getCurrentlyRequestedViewSelectionIndex(self):
		return self._getViewIndexFromId(self.selectedView)

	def __exit__(self, exc_type, exc_value, traceback):
		result = super().__exit__(exc_type, exc_value, traceback)
		index = self._getViewIndexFromId(self.selectedView)  # = currently requested selection index
		if index is not None:
			self._setSelectedIndexForWidget(index)
		return result

	def addItem(self, ItemType, initArgs: DictOrTuple = (), onInit: Callable = None, isPrefix: bool = False):
		raise NotImplementedError(f".addItem(...) not supported for {type(self).__name__}")

	def canIndentItem(self, isPrefix: bool) -> bool:
		return False

	def _collectAllOldItems(self) -> list[QWidget]:
		stackedWidget = self._qLayout
		return [stackedWidget.widget(i) for i in range(stackedWidget.count())]

	def _removeOldItem(self, item: QWidget) -> None:
		index = self._qLayout.indexOf(item)
		if index >= 0:
			self._removeWidget(index, item)
		# if item is not None:
		# 	deleteWidget(item)

	def addView(self, id_: Optional[str] = None, preventVStretch: bool = False, preventHStretch: bool = False, seamless: bool = False, *, contentsMargins: Margins = None, **kwargs):
		"""
		Adds a view to the stacked control.
		:param id_: the id that uniquely identfies the contents of this view within the stacked control.
				Can be used to reorder / delete views without rebuilding every single view.
		:param preventVStretch:
		:param preventHStretch:
		:param seamless:
		:param contentsMargins:
		:return:
		"""
		newIndex = self._index
		id_ = self._getWidget__id(id_, newIndex)
		# find view for id:
		widget = next((view for view in self._oldItems if getattr(view, '__id', None) == id_), None)
		# handle old view or create a new view
		if widget is not None:
			self._oldItems.remove(widget)
			oldIndex = self._qLayout.indexOf(widget)
			if oldIndex != newIndex:
				self._moveWidget(oldIndex, newIndex, widget)
			qLayout: Optional[QtWidgets.QGridLayout] = cast(QtWidgets.QGridLayout, widget.layout())
		else:
			widget = self._insertNewWidget(newIndex, id_, None)
			qLayout: Optional[QtWidgets.QGridLayout] = None
		self._gui.addkwArgsToItem(widget, kwargs)
		layoutCls = getDoubleColumnLayout(seamless)
		if type(qLayout) is not layoutCls.QLayoutType:
			qLayout = layoutCls.QLayoutType()
			if contentsMargins is not None:
				qLayout.setContentsMargins(*contentsMargins)
			widget.setLayout(qLayout)

		self._index += 1
		return layoutCls(self._gui, qLayout, preventVStretch, preventHStretch, deferBorderFinalization=True, forWidget=widget)

	def _insertNewWidget(self, newIndex: int, id_: str, widget: Optional[QWidget]) -> QWidget:
		widget = widget or QWidget()
		setattr(widget, '__id', id_)
		self._qLayout.insertWidget(newIndex, widget)
		return widget

	def _moveWidget(self, oldIndex: int, newIndex: int, widget: QWidget) -> None:
		self._qLayout.removeWidget(widget)
		self._qLayout.insertWidget(newIndex, widget)

	def _removeWidget(self, oldIndex: int, widget: QWidget) -> None:
		self._qLayout.removeWidget(widget)
		deleteWidget(widget)

	def _selectedIndexFromWidget(self) -> int:
		return self._qLayout.currentIndex()

	def _setSelectedIndexForWidget(self, index: int) -> None:
		self._qLayout.setCurrentIndex(index)

	@property
	def selectedView(self) -> str:
		if self._qLayout != self._gui.modifiedInput[0] and (request := self._selectedViewRequest) is not None:
			return request
		else:  # fallback, if _selectedViewRequest could not be found. TODO: maybe add a warning in this case?
			return self._selectedViewId

	def _getWidget__id(self, id_: Optional[str], index: int) -> str:
		return id_ if id_ is not None else f'${index}'


_DEFAULT_TAB_OPTIONS = TabOptions('label')


class TabControl(StackedControl):
	def __init__(self, gui: PythonGUI, tabBar: CatTabBar, stackedWidget: SeamlessQStackedWidget, selectedView: Optional[str], *, forWidget: Optional[QWidget] = None):
		self._tabBar: CatTabBar = tabBar
		super().__init__(gui, stackedWidget, selectedView, forWidget=forWidget)

	def __enter__(self) -> TabControl:
		result = super().__enter__()
		self._gui._connectOnInputModified(self._tabBar, self._tabBar.currentChanged)
		return cast(TabControl, result)

	def addTab(self, options: TabOptions, id_: Optional[str] = None, preventVStretch: bool = False, preventHStretch: bool = False, seamless: bool = False, *, contentsMargins: Margins = None, windowPanel: bool = False, **kwargs):
		"""
		Adds a Tab to the tab control.
		:param options: options for the tab (text, toolTip, icon, etc.).
		:param id_: the id that uniquely identifies the contents of this tab within the tab control.
				Can be used to reorder / delete tabs without rebuilding every single tab.
		:param preventVStretch:
		:param preventHStretch:
		:param seamless:
		:param contentsMargins:
		:return:
		"""
		newIndex = self._index
		layout = super(TabControl, self).addView(id_, preventVStretch, preventHStretch, seamless, contentsMargins=contentsMargins, windowPanel=windowPanel, **kwargs)
		self._tabBar.setTabOptions(newIndex, options)
		return layout

	addView = addTab

	def addItem(self, ItemType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False):
		return super(TabControl, self).addItem(ItemType, initArgs, onInit, isPrefix)

	def _insertNewWidget(self, newIndex: int, id_: str, widget: Optional[QWidget]) -> QWidget:
		widget = widget or CatPanel()
		widget = super(TabControl, self)._insertNewWidget(newIndex, id_, widget)
		self._tabBar.insertTab(newIndex, _DEFAULT_TAB_OPTIONS)
		return widget

	def _moveWidget(self, oldIndex: int, newIndex: int, widget: QWidget) -> None:
		self._tabBar.moveTab(oldIndex, newIndex)
		super(TabControl, self)._moveWidget(oldIndex, newIndex, widget)

	def _removeWidget(self, oldIndex: int, widget: QWidget) -> None:
		super(TabControl, self)._removeWidget(oldIndex, widget)
		self._tabBar.removeTab(oldIndex)

	def _selectedIndexFromWidget(self) -> int:
		return self._tabBar.currentIndex()

	def _setSelectedIndexForWidget(self, index: int) -> None:
		super(TabControl, self)._setSelectedIndexForWidget(index)
		self._tabBar.setCurrentIndex(index)


class SeamlessQSplitter(QtWidgets.QSplitter, CatFramedWidgetMixin, CatSizePolicyMixin):

	def __init__(self, *args):
		super(SeamlessQSplitter, self).__init__(*args)
		self._overlapCharacteristics: Optional[OverlapCharacteristics] = None

	def insertWidget(self, *args) -> None:
		super(SeamlessQSplitter, self).insertWidget(*args)
		self._overlapCharacteristics = None

	def addWidget(self, *args) -> None:
		super(SeamlessQSplitter, self).addWidget(*args)
		self._overlapCharacteristics = None

	def replaceWidget(self, *args) -> QWidget:
		self._overlapCharacteristics = None
		return super(SeamlessQSplitter, self).replaceWidget(*args)

	@property
	def overlapCharacteristics(self) -> OverlapCharacteristics:
		if self._overlapCharacteristics is None:
			count = self.count()
			if count == 0:
				self._overlapCharacteristics = CANT_AND_NO_OVERLAP
			else:
				if self.orientation() == Qt.Vertical:
					canReqL = getOverlapCharacteristics2([self.widget(i).layout() for i in range(count)], 0)
					canReqR = getOverlapCharacteristics2([self.widget(i).layout() for i in range(count)], 2)
					canReqT = getOverlapCharacteristics2([self.widget(0).layout()], 1)
					canReqB = getOverlapCharacteristics2([self.widget(count - 1).layout()], 3)
				else:
					canReqT = getOverlapCharacteristics2([self.widget(i).layout() for i in range(count)], 1)
					canReqB = getOverlapCharacteristics2([self.widget(i).layout() for i in range(count)], 3)
					canReqL = getOverlapCharacteristics2([self.widget(0).layout()], 0)
					canReqR = getOverlapCharacteristics2([self.widget(count - 1).layout()], 2)
				self._overlapCharacteristics = OverlapCharacteristics(canReqL, canReqT, canReqR, canReqB)
		return self._overlapCharacteristics

	def finalizeBorders(self) -> None:
		lastIndex = self.count() - 1
		orientation = self.orientation()
		olp = self.overlap()
		crn = self.roundedCorners()
		for i in range(lastIndex + 1):
			item = self.widget(i)
			if isinstance(item.layout(), CatFramedWidgetMixin):
				isL = i == 0 or orientation == Qt.Vertical
				isR = i == lastIndex or orientation == Qt.Vertical
				isT = i == 0 or orientation == Qt.Horizontal
				isB = i == lastIndex or orientation == Qt.Horizontal
				overlap, corners = calculateBorderInfoSimple(isL, isR, isT, isB, olp, crn, (0, 0))
				finalizeBorders(item, overlap, corners)


class SplitterControl(LayoutBase[SeamlessQSplitter]):
	def __init__(self, gui: PythonGUI, splitterWidget: SeamlessQSplitter, *, forWidget: Optional[QWidget] = None):
		super().__init__(gui, splitterWidget, forWidget=forWidget)

	def addItem(self, ItemType, initArgs: DictOrTuple = (), onInit: Callable[[_TQWidget], None] = None, isPrefix: bool = False):
		raise NotImplementedError("")

	def canIndentItem(self, isPrefix: bool) -> bool:
		return False

	def _collectAllOldItems(self) -> list[QWidget]:
		splitterWidget = self._qLayout
		return [splitterWidget.widget(i) for i in range(splitterWidget.count())]

	def _removeOldItem(self, item: QWidget) -> None:
		print("!!!! REMOVING Widget:", item)
		deleteWidget(item)

	def addArea(self, stretchFactor=1, id_: str = None, preventVStretch: bool = False, preventHStretch: bool = False, seamless: bool = False, **kwargs):
		splitterWidget = self._qLayout

		layoutCls = getDoubleColumnLayout(seamless)

		# find widget for id:
		widget: Optional[QWidget] = next((widget for widget in self._oldItems if getattr(widget, '__id', None) == id_), None)
		# handle old widget or create a new widget
		if widget is not None:
			self._oldItems.remove(widget)
			qLayout = widget.layout()
		else:
			widget = QWidget()
			qLayout = layoutCls.QLayoutType()
			widget.setLayout(qLayout)
			# stackWidget.layout().setStackingMode(QtWidgets.QStackedLayout.StackAll)

		kwargs.setdefault('contentsMargins', NO_MARGINS)
		self._gui.addkwArgsToItem(qLayout, kwargs)

		setattr(widget, '__id', id_)

		if (0 > self._index or self._index >= splitterWidget.count()) or splitterWidget.widget(self._index) is not widget:
			splitterWidget.insertWidget(self._index, widget)
		else:
			pass
		splitterWidget.setStretchFactor(self._index, stretchFactor)
		self._index += 1
		self._newItems.append(widget)
		return layoutCls(self._gui, qLayout, preventVStretch, preventHStretch, forWidget=widget)


class MenuControl(WithBlock):
	def __init__(self, menuWidget: QtWidgets.QMenu, gui, position: Optional[QtCore.QPoint] = None, execOnExit: bool = True):
		self._gui: PythonGUI = gui
		self._menuWidget: QtWidgets.QMenu = menuWidget
		self._position: Optional[QtCore.QPoint] = position
		self._execOnExit: bool = execOnExit

	def __enter__(self):
		super().__enter__()
		if not self._position and self._execOnExit:
			raise ValueError(f"Invalid popup menu position: {self._position}")
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if self._execOnExit:
			self._menuWidget.exec_(self._position)
		return super().__exit__(exc_type, exc_value, traceback)

	def addSeparator(self, label: str = '', **kwargs) -> None:
		action = self._addAction(label, kwargs)
		action.setSeparator(True)

	def addMenu(self, label: str, items: Iterable[MenuItemData] = (), **kwargs) -> MenuControl:
		action = self._addAction(label, kwargs)
		subMenuWidget = QtWidgets.QMenu(parent=self._menuWidget)
		action.setMenu(subMenuWidget)
		with MenuControl(subMenuWidget, self._gui, execOnExit=False) as subMenu:
			subMenu.addItems(items)
		return subMenu

	def addAction(self, label: str, value: Callable[[], None], **kwargs):
		def executeAction(checked):
			value()
			self._gui.redrawGUI()
		action = self._addAction(label, kwargs)
		connectSafe(action.triggered, executeAction)

	def addToggle(self, label: str, value: bool, setter: Callable[[bool], None], **kwargs):
		def executeAction(checked):
			setter(checked)
			self._gui.redrawGUI()
		kwargs.setdefault('checkable', True)
		kwargs.setdefault('checked', value)
		action = self._addAction(label, kwargs)
		connectSafe(action.triggered, executeAction)

	def addItems(self, items: Iterable[MenuItemData]):
		for item in items:
			if len(item) == 2:
				self.addItem(*item)
			else:
				item: MenuItemDataLong
				self.addItem(item[0], item[1], **item[2])

	def addItem(self, label: str, value: MenuItemValue, **kwargs):
		if value is None:  # value is separator
			return self.addSeparator(label, **kwargs)
		if callable(value):  # value is action
			return self.addAction(label, value, **kwargs)
		if isinstance(value, Iterable):  # value is menu:
			return self.addMenu(label, value, **kwargs)
		raise ValueError(f"Unknown value type for menu item. Expected a list, callable, or None, but got {type(value)}")

	def _addAction(self, label: str, kwargs: dict[str, Any]) -> QtWidgets.QAction:
		action = self._menuWidget.addAction(label)
		self._gui.addkwArgsToItem(action, kwargs)
		return action


@dataclasses.dataclass
class TreeResult(Generic[_TT]):
	selectedItem: Optional[_TT]
	value: _TT  # the root data

	selectionModel: Optional[QItemSelectionModel] = None
	treeView: Optional[QtWidgets.QTreeView] = None

	def __iter__(self) -> Iterator[_TT]:
		yield from self.unpack()

	def unpack(self) -> tuple[Optional[_TT], _TT]:
		return self.selectedItem, self.value


ModifiedInput = tuple[Optional[Union[QWidget, QtWidgets.QLayout]], Optional[Any]]


profiler = ProfiledAction('OnGUI', threshold_percent=1.0, colourNodesBySelftime=False)
# profiler2 = ProfiledAction('OnInputModified', threshold_percent=1.0, colourNodesBySelftime=False)


_redrawRecursionLvl: int = 0


def _connectEventListener(item: QObject, propName: str, value: Any):
	eventName = propName[2].lower() + propName[3:]
	event = getattr(item, eventName)
	receivers = QtCore.QObject.receivers(item, event)
	if receivers == 1:
		event.disconnect()
	elif receivers > 1:
		raise AttributeError('too many receivers connected to signal. only one (1) is allowed.')
	connectSafe(event, value)


_SHORTCUT_SETTERS: dict[str, Callable[[QObject, KeySequenceLike, dict[str, Any]], bool]] = {}
_shortcutSetter = AddToDictDecorator(_SHORTCUT_SETTERS)


def _setQObjectPropertySimple(item: QObject, propName: str, value: Any) -> None:
	name = propName[0].upper() + propName[1:len(propName)]
	getName = 'is' + name if (type(value) is bool and not hasattr(item, propName)) else propName
	if getattr(item, getName)() != value:
		setter = getattr(item, 'set' + name)
		if type(value) is tuple:
			try:
				setter(*value)
			except TypeError:
				setter(value)
		else:
			setter(value)


def _setQWidgetShortcut(item: QObject, key: KeySequenceLike, kwargs: dict[str, Any], *, defaultParentDepth: int, shortcutContext: Qt.ShortcutContext) -> bool:
	shortcutParent = getShortcutParent(item, kwargs.get('parentShortcutDepth', defaultParentDepth) + 1)
	shortcutEvent = getattr(item, 'shortcutEvent', None)
	if shortcutEvent is None:
		onShortcut = lambda shortcut, isAmbiguous: item.setFocus(Qt.ShortcutFocusReason)
	else:
		onShortcut = lambda shortcut, isAmbiguous: shortcutEvent(QtGui.QShortcutEvent(key, shortcut.id(), isAmbiguous))
	setQWidgetShortcutBase(item, shortcutParent, shortcutContext, key, onShortcut)
	return True


_shortcutSetter('parentShortcutDepth')(lambda item, key, kwargs: False)
_shortcutSetter('windowShortcut', kwargs=dict(defaultParentDepth=-1, shortcutContext=Qt.WindowShortcut))(_setQWidgetShortcut)
_shortcutSetter('selfShortcut', kwargs=dict(defaultParentDepth=-1, shortcutContext=Qt.WidgetWithChildrenShortcut))(_setQWidgetShortcut)
_shortcutSetter('shortcut', kwargs=dict(defaultParentDepth=0, shortcutContext=Qt.WidgetWithChildrenShortcut))(_setQWidgetShortcut)
_shortcutSetter('parentShortcut', kwargs=dict(defaultParentDepth=1, shortcutContext=Qt.WidgetWithChildrenShortcut))(_setQWidgetShortcut)


def _setQObjectProperty(item: QObject, propName: str, value: Any, kwargs: dict[str, Any]) -> bool:
	# value is just a plain value:
	try:
		_setQObjectPropertySimple(item, propName, value)
		hasShortcut = False
	except AttributeError:
		shortcutSetter = _SHORTCUT_SETTERS.get(propName)
		if shortcutSetter is None:
			raise
		hasShortcut = shortcutSetter(item, value, kwargs)
	return hasShortcut


@dataclasses.dataclass(init=False, repr=False, eq=False)
class PythonGUI(CatScalableWidgetMixin):
	"""docstring for PythonGUI

		kwArgs common to almost all widget creating functions:

		enabled: 	bool,   	enables/disables the widget (disabled = greyed out)
		value: 		<?>,    	the value of the field
		label: 		string, 	the label that is to the left or above widget
		tip: 		string, 	the tool tip
		someName:	<?>,		calls setSomeName(value) on the widget

		style:		<?>,		a function taking the widget and returning a Stylesheet, which is applied later.

		onCreate: 				function to perform on the created Widget. e.g.:
								gui.someWidget(label = 'theMessage',
									onCreate=lambda widget: (
										message := "Hello world",
										widget.setMessage(message, style=myStyle)
									)[-1]
								)
		onValueChanged: 		function to perform when the Value has changed. e.g.:
								gui.someWidget(label = 'theMessage',
									onValueChanged=lambda widget: (
										message := "Hello world",
										widget.setMessage(message, style=myStyle)
									)[-1]
								)
	"""

	customData: dict[str, Any]  # for the user of this PythonGUI instance to store custom data
	host: QWidget
	OnGUI: Callable[[_TS], None]
	isCurrentlyDrawing: bool
	_widgetStack: Stack[LayoutBase]

	style: Style

	qLayout: QtWidgets.QLayout
	currentLayout: LayoutBase

	_overlay: CatOverlay

	suppressRedrawLogging: bool
	modifiedInput: ModifiedInput  # tuple (widget, data)
	_modifiedInputStack: Stack[ModifiedInput]  # for handling recursive OnInputModified calls, don't remove!
	_buttonGroups: dict[Union[str, int], QtWidgets.QButtonGroup]
	_forceSecondRedraw: bool
	_firstTabWidget: Optional[QWidget]
	_lastTabWidget: Optional[QWidget]
	_lastWidget: Optional[QWidget]

	_isFirstRedraw: bool
	_isLastRedraw: bool
	_name: str

	def __init__(self: _TS, host: QWidget, OnGUI: Callable[[_TS], None], *, seamless: bool = False, deferBorderFinalization: bool = False, suppressRedrawLogging: bool = False, style: Style = None):
		super(PythonGUI, self).__init__()
		self.customData = {}  # for the user of this PythonGUI instance to store custom data
		self.host = host
		self.OnGUI = OnGUI
		self.isCurrentlyDrawing = False
		self._widgetStack: Stack[LayoutBase] = Stack()

		if style is None:
			style = getStyles().hostWidgetStyle
		if style is not None:
			applyStyle(host, style)

		layoutCls = getDoubleColumnLayout(seamless)
		qLayout = layoutCls.QLayoutType()
		self.currentLayout: LayoutBase = layoutCls(self, qLayout, False, False, deferBorderFinalization=deferBorderFinalization, forWidget=host)

		if host.layout() is not None:
			host.layout().addItem(qLayout)
		else:
			host.setLayout(qLayout)

		self._overlay = CatOverlay(host)
		self._overlay.hide()

		self.suppressRedrawLogging = suppressRedrawLogging
		self.modifiedInput = (None, None)  # tuple (widget, data)
		self._modifiedInputStack = Stack()  # for handling recursive OnInputModified calls, don't remove!
		self._buttonGroups = {}
		self._forceSecondRedraw = False
		self._firstTabWidget = None
		self._lastTabWidget = None
		self._lastWidget = None

		self._isFirstRedraw = True
		self._isLastRedraw = True
		self._name = ''

	@property
	def name(self) -> str:
		return self._name

	@name.setter
	def name(self, name: str):
		self._name = name

	@property
	def loggingIdentifier(self) -> str:
		loggingIdentifier = self._name or type(self.host).__name__
		if hostWindowTitle := self.host.windowTitle():
			loggingIdentifier = f"{loggingIdentifier}, {hostWindowTitle}"
		return loggingIdentifier

	def _logNPrint(self, msg: str, *, forceLog: bool = True) -> None:
		TimedAction.logNPrint(msg, doPrint=not self.suppressRedrawLogging, doLog=forceLog or not self.suppressRedrawLogging)

	def timedAction(self, msg: str, *, details: str = '', forceLog: bool = True) -> TimedAction:
		return TimedAction(msg, details=details, doPrint=not self.suppressRedrawLogging, doLog=forceLog or not self.suppressRedrawLogging)

	def font(self) -> QtGui.QFont:
		return self.host.font()

	def fontMetrics(self) -> QtGui.QFontMetrics:
		return self.host.fontMetrics()

	def parentWidget(self) -> None:
		return None

	def updateGeometry(self):
		if not sip.isdeleted(self.host):
			self.host.updateGeometry()

	@property
	def scale(self) -> float:
		return self._scale

	@property
	def panelMargins(self) -> int:
		return self.margin

	@property
	def margin(self) -> int:
		return int(9 * self._scale)

	@property
	def smallPanelMargin(self) -> int:
		return int(4 * self._scale)

	@property
	def spacing(self) -> int:
		return int(9 * self._scale)

	@property
	def smallSpacing(self) -> int:
		return int(6 * self._scale)

	@property
	def qBoxMargins(self) -> QMargins:
		mg = 6
		mg = int(round(mg * self._scale))
		return QMargins(
			mg,
			mg,
			mg,
			mg,
		)

	@property
	def isFirstRedraw(self) -> bool:
		return self._isFirstRedraw

	@property
	def isLastRedraw(self) -> bool:
		return self._isLastRedraw

	@property
	def firstTabWidget(self) -> Optional[QWidget]:
		return self._firstTabWidget

	@property
	def lastTabWidget(self) -> Optional[QWidget]:
		return self._lastTabWidget

	@property
	def lastWidget(self) -> Optional[QWidget]:
		return self._lastWidget

	def updatesDisabled(self) -> ContextManager[None]:
		gui = self

		class UpdatesManager:
			def __enter__(self):
				self._wasEnabled = gui.host.updatesEnabled()
				if self._wasEnabled:
					gui.host.setUpdatesEnabled(False)

			def __exit__(self, exc_type, exc_val, exc_tb):
				if self._wasEnabled:  # re-enable updates:
					gui.host.setUpdatesEnabled(True)
		return UpdatesManager()

	def _redrawRecursionDepth(self) -> ContextManager[None]:
		# TODO: find better name for PythonGUI._redrawRecursionDepth(...)
		gui = self

		class RedrawRecursionManager:
			def __enter__(self):
				self._wasDrawing = gui.isCurrentlyDrawing
				gui.isCurrentlyDrawing = True
				global _redrawRecursionLvl
				_redrawRecursionLvl += 1

			def __exit__(self, exc_type, exc_val, exc_tb):
				global _redrawRecursionLvl
				_redrawRecursionLvl -= 1
				gui.isCurrentlyDrawing = self._wasDrawing
		return RedrawRecursionManager()

	def waitCursor(self) -> ContextManager[None]:
		gui = self

		class WaitCursorManager:
			def __enter__(self):
				if gui.host.testAttribute(Qt.WA_SetCursor):
					self._lastCursor = gui.host.cursor()
				else:
					self._lastCursor = None
				gui.host.setCursor(Qt.WaitCursor)

			def __exit__(self, exc_type, exc_val, exc_tb):
				if self._lastCursor is not None:
					gui.host.setCursor(self._lastCursor)
				else:
					gui.host.unsetCursor()
		return WaitCursorManager()

	def overlay(self) -> ContextManager[None]:
		gui = self

		class OverlayManager:
			def __enter__(self):
				self._wasHidden = gui._overlay.isHidden()
				if self._wasHidden:
					window = gui.host.window()
					gui._overlay.setParent(window)
					gui._overlay.setGeometry(window.contentsRect())
					gui._overlay.raise_()
					gui._overlay.show()
					gui.host.setUpdatesEnabled(True)

			def __exit__(self, exc_type, exc_val, exc_tb):
				if self._wasHidden:
					gui._overlay.hide()
		return OverlayManager()

	def _redrawGUI(self) -> None:
		applyStyle(self.host, getStyles().hostWidgetStyle)  # + styles.layoutingBorder)
		global PROFILING_ENABLED
		global profiler
		if self.isCurrentlyDrawing:
			return

		with self.timedAction('redrawing GUI', details=self.loggingIdentifier):
			# prepare _widgetStack:
			assert len(self._widgetStack) == 0, f"len(self._widgetStack) = {len(self._widgetStack)}"
			self.currentLayout.resetIndex()
			self._firstTabWidget = None
			self._lastTabWidget = None
			self._lastWidget = None

			profiler.enabled = PROFILING_ENABLED
			if profiler.enabled:
				self._logNPrint(f"Profiling...")
			self.updateScaleFromFontMetrics()
			# draw GUI:
			with profiler, self.waitCursor(), self.updatesDisabled(), self._redrawRecursionDepth():
				with self.currentLayout:
					self.OnGUI(self)
				assert len(self._widgetStack) == 0

	@CrashReportWrapped
	def redraw(self, cause: Optional[str] = None) -> None:
		if self.host is None or sip.isdeleted(self.host):
			return
		if self.isCurrentlyDrawing:
			return
		if cause is not None:
			logMessage = f"redraw caused by: {cause}"
			self._logNPrint(logMessage)
		self._redrawGUI()

	def redrawGUI(self) -> None:
		return self.redraw()

	redrawGUI = redraw

	def redrawLater(self, cause: Optional[str] = None) -> None:
		logMessage = f"scheduling redrawLater for {self.loggingIdentifier}"
		if cause is not None:
			logMessage = f"{logMessage}; cause = {cause}"
		self._logNPrint(logMessage)
		self._redrawLater(cause)

	@DeferredCallOnceMethod(delay=0)
	def _redrawLater(self, cause: Optional[str] = None) -> None:
		if self.host is None or sip.isdeleted(self.host):
			return
		if cause is not None:
			logMessage = f"redrawLater caused by: {cause}"
			self._logNPrint(logMessage)
		self.redraw()

	@Deprecated
	def redrawGUILater(self) -> None:
		self.redrawLater()

	redrawGUILater = Deprecated(redrawLater)

	def OnInputModified(self, modifiedWidget: QWidget | QtWidgets.QLayout, data: Any = None):
		self._forceSecondRedraw = True
		try:
			self._modifiedInputStack.push(self.modifiedInput)
			self.modifiedInput = (modifiedWidget, data)
			if not self.isCurrentlyDrawing:
				self._logNPrint(f'modifiedInput = {self.modifiedInput}')
				self._isFirstRedraw = True
				self._isLastRedraw = False
				self._redrawGUI()
		finally:
			self.modifiedInput = self._modifiedInputStack.pop()
		if not self._modifiedInputStack and self._forceSecondRedraw:
			self._forceSecondRedraw = False
			self._isFirstRedraw = False
			self._isLastRedraw = True
			self._redrawGUI()  # redraw again!
		self._isFirstRedraw = True
		self._isLastRedraw = True

	def _connectOnInputModified(self, widget: QWidget | QtWidgets.QLayout, signal: pyqtBoundSignal | pyqtSignal):
		# pyqtSignal is in the type signature, only to make pycharms typechecker happy.
		connectOnlyOnce(widget, signal, lambda _=None: self.OnInputModified(widget), '_OnInputModified_')

	def handleKWArgsCache(self, item, kwargs):
		if not kwargs:
			return True
		kwargsTuple = tuple(kwargs.items())
		allKwArgs = getattr(item, '_PythonGUI__allKwArgs', ())
		if allKwArgs == kwargsTuple:
			return True
		else:
			setattr(item, '_PythonGUI__allKwArgs', kwargsTuple)
		return False

	def handleBasicKwArgs(self, item, kwargs):
		enabled = kwargs.pop('enabled', None)
		if enabled is not None and item.isEnabled() != enabled:
			item.setEnabled(enabled)

		toolTip = kwargs.pop('tip', '')
		try:
			if item.toolTip() != toolTip:
				item.setToolTip(toolTip)
		except AttributeError:
			pass

	def addLayoutInfoAsToolTip(self, item: QWidget, kwargs: dict[str, Any]) -> dict[str, Any]:
		infos: list[str] = []
		try:
			typeName = type(item).__name__
			infos.append(f'type = {typeName}')
		except AttributeError:
			pass
		try:
			gm = item.geometry()
			tl = item.mapToParent(gm.topLeft())
			gm = (tl.x(), tl.y(), gm.width(), gm.height())
			infos.append(f'geometryP = {gm}')
		except AttributeError:
			pass
		try:
			ms = item.minimumSize()
			ms = (ms.width(), ms.height())
			infos.append(f'minSize = {ms if ms != (0, 0) else tuple()}')
		except AttributeError:
			pass
		try:
			msh = item.minimumSizeHint()
			msh = (msh.width(), msh.height())
			infos.append(f'minSizeHint = {msh if msh != (0, 0) else tuple()}')
		except AttributeError:
			pass
		try:
			sh = item.sizeHint()
			sh = (sh.width(), sh.height())
			infos.append(f'sizeHint = {sh if sh != (0, 0) else tuple()}')
		except AttributeError:
			pass
		try:
			sp = item.sizePolicy()
			sp = (
				SizePolicy(sp.horizontalPolicy()).name, sp.horizontalStretch(),
				SizePolicy(sp.verticalPolicy()).name, sp.verticalStretch())
			infos.append(f'sizePolicy = {sp}')
		except AttributeError:
			pass
		try:
			cm = item.layout().contentsMargins()
			cm = (cm.left(), cm.top(), cm.right(), cm.bottom())
			infos.append(f'layoutContentsMargins = {cm}')
		except AttributeError:
			pass
		try:
			cm = item.contentsMargins()
			cm = (cm.left(), cm.top(), cm.right(), cm.bottom())
			infos.append(f'contentsMargins = {cm}')
		except AttributeError:
			pass
		try:
			cm = item.viewportMargins()
			cm = (cm.left(), cm.top(), cm.right(), cm.bottom())
			infos.append(f'viewportMargins = {cm}')
		except AttributeError:
			pass
		try:
			hs = item.layout().horizontalSpacing()
			vs = item.layout().verticalSpacing()
			spacing = (hs, vs)
			infos.append(f'spacing = {spacing}')
		except AttributeError:
			pass
		try:
			cr = item.contentsRect()
			cr = (cr.x(), cr.y(), cr.width(), cr.height())
			infos.append(f'contentsRect = {cr}')
		except AttributeError:
			pass
		try:
			ol = getattr(item, 'overlap')()
			infos.append(f'overlap = {ol}')
		except AttributeError:
			pass
		try:
			ol = getattr(item, 'overlapCharacteristics')
			infos.append(f'overlapCharacteristics (can, req, has) = \\')
			infos.append(f'{ol}')
		except AttributeError:
			pass
		try:
			rc = getattr(item, 'roundedCorners')
			if callable(rc):
				rc = rc()
			infos.append(f'roundedCorners = {rc}')
		except AttributeError:
			pass
		except TypeError:
			pass
		try:
			ps = item.fontInfo().pointSize()
			infos.append(f'fontInfo.pointSize = {ps}')
		except AttributeError:
			pass

		try:
			qLayout = item.layout()
			try:
				qLayout = qLayout or getattr(item, 'widget')().layout()
			except (AttributeError, TypeError):
				pass

			if isinstance(qLayout, QtWidgets.QGridLayout):
				infos.append(f'-------- -------- -------- ')
				for c in range(qLayout.columnCount()):
					ci = (qLayout.columnStretch(c), qLayout.columnMinimumWidth(c))
					infos.append(f'    columns[{c}] = {ci}')
		except AttributeError:
			pass

		try:
			qLayout = getattr(self.currentLayout, '_qLayout')
			if isinstance(qLayout, QtWidgets.QGridLayout):
				infos.append(f'======== ======== ======== ')
				for c in range(qLayout.columnCount()):
					ci = (qLayout.columnStretch(c), qLayout.columnMinimumWidth(c))
					infos.append(f'    columns[{c}] = {ci}')
		except AttributeError:
			pass

		try:
			if self._widgetStack:
				qLayout = getattr(self._widgetStack.peek(), '_qLayout')
				if isinstance(qLayout, QtWidgets.QGridLayout):
					infos.append(f'======== ======== ======== ')
					infos.append(f'-------- -------- -------- ')
					for c in range(qLayout.columnCount()):
						ci = (qLayout.columnStretch(c), qLayout.columnMinimumWidth(c))
						infos.append(f'    columns[{c}] = {ci}')
		except AttributeError:
			pass

		toolTip: str = '\n'.join(infos)
		kwargsCpy = kwargs.copy()
		kwargsCpy['tip'] = toolTip
		return kwargsCpy

	def addFontInfoToToolTip(self, item: QWidget, kwargs: dict[str, Any]) -> dict[str, Any]:
		infos: list[str] = []
		try:
			typeName = type(item).__name__
			infos.append(f'type = {typeName}')
		except AttributeError:
			pass
		try:
			f = item.font()
			fontAttrs = ('family', 'pointSizeF', 'pixelSize', 'styleHint', 'weight', 'style', 'underline', 'strikeOut', 'fixedPitch')
			infos.append('font = \n' + '\n'.join(f'    {a}: {getattr(f, a)()}'for a in fontAttrs))
		except AttributeError:
			pass

		toolTip: str = '\n'.join(infos)
		kwargsCpy = kwargs.copy()
		if oldTip := kwargsCpy.get('tip', None):
			toolTip = f'{toolTip}\n{oldTip}'
		kwargsCpy['tip'] = toolTip
		return kwargsCpy

	def addkwArgsToItem(self, item: QObject, kwargs: dict[str, Any]):
		if ADD_LAYOUT_INFO_AS_TOOL_TIP:
			kwargs = self.addLayoutInfoAsToolTip(item, kwargs)
		# kwargs = self.addFontInfoToToolTip(item, kwargs)
		self.handleBasicKwArgs(item, kwargs)

		if self.handleKWArgsCache(item, kwargs):
			return

		hasShortcut: bool = False
		for propName, value in kwargs.items():
			# value is a style:
			if propName == 'style':
				if value is not None:
					applyStyle(item, value)
			elif propName.startswith('on') and len(propName) > 2 and propName[2].isupper():
				# value is an eventListener (a function), so connect it:
				_connectEventListener(item, propName, value)
			else:
				hasShortcut |= _setQObjectProperty(item, propName, value, kwargs)
		if not hasShortcut:
			currentShortcut: QShortcut = getattr(item, '__currentShortcut', None)
			if currentShortcut is not None:
				currentShortcut.setEnabled(False)

	@overload
	def addItem(
			self,
			ItemType: _TQWidget,
			isPrefix: bool = False,
			fullSize=False,
			initArgs: DictOrTuple = (),
			onInit: Callable[[_TQWidget], None] = None,
			**kwargs
	) -> _TQWidget: ...

	@overload
	def addItem(
			self,
			ItemType: Type[_TQWidget],
			isPrefix: bool = False,
			fullSize=False,
			initArgs: DictOrTuple = (),
			onInit: Callable[[_TQWidget], None] = None,
			**kwargs
	) -> _TQWidget: ...

	def addItem(
			self,
			ItemType: Union[Type[_TQWidget], _TQWidget],
			isPrefix: bool = False,
			initArgs: DictOrTuple = (),
			onInit: Callable[[_TQWidget], None] = None,
			**kwargs
	) -> _TQWidget:
		indentLevel = self.currentLayout.indentLevel
		shouldIndent = indentLevel > 0 and self.currentLayout.canIndentItem(isPrefix)

		if shouldIndent:
			isSeamless = hasattr(self.currentLayout._qLayout, 'finalizeBorders')
			rowLayoutCls = getSingleRowLayout(isSeamless)
			qLayout = self.currentLayout.addItem(rowLayoutCls.QLayoutType, isPrefix=isPrefix)
			qLayout.setHorizontalSpacing(0)
			with rowLayoutCls(self, qLayout, preventVStretch=False, preventHStretch=False):
				self.addHSpacer(int(17 * indentLevel * self._scale), SizePolicy.Fixed)
				item = self.currentLayout.addItem(ItemType, initArgs=initArgs, onInit=onInit, isPrefix=isPrefix)
		else:
			item = self.currentLayout.addItem(ItemType, initArgs=initArgs, onInit=onInit, isPrefix=isPrefix)

		# extract onCreate and onValueChanged functions:
		onCreate = kwargs.pop('onCreate', None)
		onValueChanged = kwargs.pop('onValueChanged', None)

		# add kwArgs to Item
		self.addkwArgsToItem(item, kwargs)

		# retain correct tab order (for navigating using the TAB-key):
		if isinstance(item, QWidget):
			self._lastWidget = item
			if Qt.TabFocus & item.focusPolicy():
				if self._lastTabWidget is not None:
					QWidget.setTabOrder(self._lastTabWidget, item)
				else:
					self._firstTabWidget = item
				self._lastTabWidget = item

		# apply the onCreate function:
		if onCreate:
			onCreate(item)
		# apply the onValueChanged function:
		if onValueChanged and item == self.modifiedInput[0]:
			onValueChanged(item)

		return item

	@overload
	def addLabeledItem(self, ItemType: _TQWidget, label, fullSize=False, initArgs: Union[dict[str, Any], tuple[Any, ...]] = (), onInit=None, **kwargs) -> _TQWidget:
		pass

	@overload
	def addLabeledItem(self, ItemType: Type[_TT], label, fullSize=False, initArgs: Union[dict[str, Any], tuple[Any, ...]] = (), onInit=None, **kwargs) -> _TT:
		pass

	def addLabeledItem(self, ItemType, label, fullSize=False, initArgs: Union[dict[str, Any], tuple[Any, ...]] = (), onInit=None, **kwargs):
		if label is not None:
			if fullSize:
				self.label(label, enabled=kwargs.get('enabled', True), tip=kwargs.get('tip', ''))
			else:
				self.prefixLabel(label, enabled=kwargs.get('enabled', True), tip=kwargs.get('tip', ''))
		return self.addItem(ItemType, initArgs=initArgs, onInit=onInit, **kwargs)

	def pushLayout(self, layoutInstance: LayoutBase):
		assert self.currentLayout is not None
		self._widgetStack.push(self.currentLayout)
		self.currentLayout = layoutInstance

	def popLayout(self, layoutInstance: LayoutBase):
		assert self.currentLayout is layoutInstance, "self.currentLayout is not layoutInstance"
		self.currentLayout = self._widgetStack.pop()

	def indentation(self):
		"""
		Creates an indented block. has to be used in an ``with`` statement (``with gui.indentation():``).
		Everything within the with statement will be indented.
		"""
		return Indentation(self)

	def vLayout1C(self, label: Optional[str] = None, *, fullSize: bool = False, preventVStretch: bool = False, preventHStretch: bool = False, verticalSpacing: int = -1, horizontalSpacing: int = -1, seamless: bool = False, **kwargs) -> SingleColumnLayout | SeamlessSingleColumnLayout:
		"""
		Creates a vertical layout with the labels *above* the widgets (single column). has to be used in an ``with`` statement (``with gui.vLayout1C():``).
		Everything within the with statement will be inside the vertical layout.
		::
			with gui.vLayout1C():
				name = gui.textField(None, 'your name:')
				gui.prefixLabel('your greeting:')
				gui.label(f'Hello there, {name}!')

		"""
		layoutCls = getSingleColumnLayout(seamless)
		qLayout = self.addLabeledItem(layoutCls.QLayoutType, label, fullSize=fullSize, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing, **kwargs)
		return layoutCls(self, qLayout, preventVStretch, preventHStretch)

	def vLayout(self, label: Optional[str] = None, *, fullSize: bool = False, preventVStretch: bool = False, preventHStretch: bool = False, verticalSpacing: int = -1, horizontalSpacing: int = -1, seamless: bool = False, **kwargs) -> DoubleColumnLayout | SeamlessDoubleColumnLayout:
		"""
		Creates a vertical layout with the labels *next to* the widgets (typically on the left). has to be used in an ``with`` statement (``with gui.vLayout():``).
		Everything within the with statement will be inside the vertical layout.
		::
			with gui.vLayout():
				name = gui.textField(None, 'your name:')
				gui.prefixLabel('your greeting:')
				gui.label(f'Hello there, {name}!')
		"""
		layoutCls = getDoubleColumnLayout(seamless)
		qLayout = self.addLabeledItem(layoutCls.QLayoutType, label, fullSize=fullSize, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing, **kwargs)
		return layoutCls(self, qLayout, preventVStretch, preventHStretch)

	def hLayout(self, label: Optional[str] = None, *, fullSize: bool = False, preventVStretch: bool = False, preventHStretch: bool = False, verticalSpacing: int = -1, horizontalSpacing: int = -1, seamless: bool = False, **kwargs) -> SingleRowLayout | SeamlessSingleRowLayout:
		"""
		Creates a horizontal layout with the labels *next to* the widgets  (single row). has to be used in an ``with`` statement (``with gui.hLayout():``).
		Everything within the with statement will be inside the horizontal layout.
		::
			with gui.hLayout():
				name = gui.textField(None, 'your name:')
				gui.prefixLabel('your greeting:')
				gui.label(f'Hello there, {name}!')
		"""
		layoutCls = getSingleRowLayout(seamless)
		qLayout = self.addLabeledItem(layoutCls.QLayoutType, label, fullSize=fullSize, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing, **kwargs)
		return layoutCls(self, qLayout, preventVStretch, preventHStretch)

	def hLayout2R(self, label=None, *, fullSize: bool = False, preventVStretch: bool = False, preventHStretch: bool = False, verticalSpacing: int = -1, horizontalSpacing: int = -1, seamless: bool = False, **kwargs) -> DoubleRowLayout | SeamlessDoubleRowLayout:
		"""
		Creates a horizontal layout with the labels *above* the widgets. has to be used in an ``with`` statement (``with gui.hLayout2R():``).
		Everything within the with statement will be inside the horizontal layout.
		::
			with gui.hLayout2R():
				name = gui.textField(None, 'your name:')
				gui.prefixLabel('your greeting:')
				gui.label(f'Hello there, {name}!')
		"""
		layoutCls = getDoubleRowLayout(seamless)
		qLayout = self.addLabeledItem(layoutCls.QLayoutType, label, fullSize=fullSize, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing, **kwargs)
		return layoutCls(self, qLayout, preventVStretch, preventHStretch)

	def tableLayout(self, preventVStretch: bool = False, preventHStretch: bool = False, prefixMode: PrefixMode = PrefixMode.none, **kwargs) -> TableLayout:
		"""
		Creates a layout with multiple widgets per row. The widgets will be horizontally and vertically aligned. It has to be used in an ``with`` statement (``with gui.tableLayout() as table:``).
		Everything within the with statement will be inside the layout.
		::
			with gui.tableLayout() as table:
				gui.label('')  # just a filler
				gui.title('Name')
				gui.title('Phone')
				gui.title('Email')
				gui.title('Address')
				for contact in contacts:
					table.advanceRow()
					contact.isSelected = gui.checkbox(contact.isSelected)
					gui.label(contact.name)
					gui.label(contact.phone)
					gui.label(contact.email)
					gui.label(contact.address)

		:param preventVStretch:
		:param preventHStretch:
		:param prefixMode:
		:param kwargs:
		:return:
		"""
		qLayout = self.addItem(TableLayout.QLayoutType, **kwargs)
		return TableLayout(self, qLayout, preventVStretch, preventHStretch, prefixMode)

	def hCentered(self) -> WithBlock:
		"""
		Centers contained widgets horizontally.
		::
			with gui.hLayout(), gui.hCentered():
				gui.helpBox("To come in a future version.")
		or:
		::
			with gui.hCentered().surroundWithBlock(gui.hLayout()):
				gui.helpBox("To come in a future version.")
		"""
		return CenteredBlock(self.addHSpacer)

	def vCentered(self) -> WithBlock:
		"""
		Centers contained widgets vertically.
		::
			with gui.vLayout(), gui.vCentered():
				gui.label("Top half of the page")
				gui.vSeparator()
				gui.label("Bottom half of the page")
		or:
		::
			with gui.vCentered().surroundWithBlock(gui.collapsibleGroupBox("page center")) as isVisible:
				if isVisible:
					gui.label("Top half of the page")
					gui.vSeparator()
					gui.label("Bottom half of the page")
		"""
		return CenteredBlock(self.addVSpacer)

	def hCentered2(self, label: Optional[str] = None, *, fullSize: bool = False, preventVStretch: bool = False, preventHStretch: bool = False, verticalSpacing: int = -1, horizontalSpacing: int = -1, seamless: bool = False, **kwargs) -> SingleRowLayout | SeamlessSingleRowLayout:
		"""
		Centers contained widgets horizontally.
		::
			with gui.hCentered2():
				gui.helpBox("To come in a future version.")
		"""
		return self.hCentered().surroundWithBlock(self.hLayout(label, fullSize=fullSize, preventVStretch=preventVStretch, preventHStretch=preventHStretch, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing, seamless=seamless, **kwargs))

	def vCentered2(self, label: Optional[str] = None, *, fullSize: bool = False, preventVStretch: bool = False, preventHStretch: bool = False, verticalSpacing: int = -1, horizontalSpacing: int = -1, seamless: bool = False, **kwargs) -> DoubleColumnLayout | SeamlessDoubleColumnLayout:
		"""
		Centers contained widgets vertically.
		::
			with gui.vCentered2():
				gui.label("Top half of the page")
				gui.vSeparator()
				gui.label("Bottom half of the page")
		"""
		return self.vCentered().surroundWithBlock(self.vLayout(label, fullSize=fullSize, preventVStretch=preventVStretch, preventHStretch=preventHStretch, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing, seamless=seamless, **kwargs))

	def groupBox(self, title: str, *, selectable: bool = False, addSeparator: bool = False, **kwargs):
		"""
		Creates a vertical layout. has to be used in an ``with`` statement (``with gui.verticalLayout():``).
		Everything within the with statement will be inside the vertical layout.
		"""
		self.title(title, selectable=selectable, addSeparator=addSeparator, **kwargs)
		return self.indentation()

	def groupBoxChecked(self, isChecked: Optional[bool], title: Optional[str] = None, isCheckable: bool = True, **kwargs):
		"""
		Creates a vertical layout. has to be used in an ``with`` statement (``with gui.groupBoxChecked(isChecked) as isChecked:``).
		Everything within the with statement will be inside the groupBox.
		"""
		return self.indentation().surroundWith(lambda: self.toggleLeft(isChecked, title, style=getStyles().title, **kwargs))

	def scrollBox(self, preventVStretch: bool = False, preventHStretch: bool = False, contentsMargins: Margins = None, verticalSpacing: int = -1, horizontalSpacing: int = -1, **kwargs):
		"""
		Creates a vertical layout. has to be used in an ``with`` statement (``with gui.verticalLayout():``).
		Everything within the with statement will be inside the vertical layout.
		"""
		scrollBox = self.addItem(CatScrollArea, **kwargs)
		if not scrollBox.widgetResizable():
			scrollBox.setWidgetResizable(True)
		widget = scrollBox.widget()
		if widget is None:
			widget = QWidget()
			scrollBox.setWidget(widget)

		qLayout = widget.layout()
		if qLayout is None:
			qLayout = DoubleColumnLayout.QLayoutType()
			widget.setLayout(qLayout)

		if contentsMargins is None:
			qLayout.setContentsMargins(self.qBoxMargins)
		else:
			qLayout.setContentsMargins(*contentsMargins)
		layoutKwArgs = dict(verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing)
		self.addkwArgsToItem(qLayout, layoutKwArgs)
		return DoubleColumnLayout(self, qLayout, preventVStretch, preventHStretch)

	def frameBox(self, preventVStretch: bool = False, preventHStretch: bool = False, **kwargs):
		"""
		Creates a framed box. has to be used in an ``with`` statement (``with gui.frameBox():``).
		Everything within the with statement will be inside the frameBox.
		"""
		kwargs.setdefault('frameStyle', QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Plain)
		frame: QtWidgets.QFrame = self.addItem(QtWidgets.QFrame, **kwargs)

		qLayout = frame.layout()
		if qLayout is None:
			qLayout = DoubleColumnLayout.QLayoutType()
			qLayout.setContentsMargins(self.qBoxMargins)
			frame.setLayout(qLayout)

		return DoubleColumnLayout(self, qLayout, preventVStretch, preventHStretch)

	def frameBox2(self, preventVStretch: bool = False, preventHStretch: bool = False, **kwargs):
		"""
		Creates a framed box. has to be used in an ``with`` statement (``with gui.frameBox2():``).
		Everything within the with statement will be inside the frameBox.
		"""
		groupBox: QtWidgets.QGroupBox = self.addItem(QtWidgets.QGroupBox, **kwargs)

		qLayout = groupBox.layout()
		if qLayout is None:
			qLayout = DoubleColumnLayout.QLayoutType()
			qLayout.setContentsMargins(self.qBoxMargins)
			groupBox.setLayout(qLayout)

		return DoubleColumnLayout(self, qLayout, preventVStretch, preventHStretch)

	def _panel(self, preventVStretch: bool, preventHStretch: bool, verticalSpacing: int, horizontalSpacing: int, layoutCls: Type[_TDirectionalLayout], **kwargs) -> _TDirectionalLayout:
		"""
		Creates a framed box. has to be used in an ``with`` statement (``with gui.frameBox2():``).
		Everything within the with statement will be inside the frameBox.
		"""

		if kwargs.get('overlap') is ...:
			kwargs.pop('overlap')

		if kwargs.get('roundedCorners') is ...:
			kwargs.pop('roundedCorners')

		margin = self.panelMargins
		kwargs.setdefault('contentsMargins', (margin, margin, margin, margin))
		panel: CatPanel = self.addItem(CatPanel,  **kwargs)
		qLayout = panel.layout()
		if type(qLayout) is not layoutCls.QLayoutType:
			if qLayout is not None:
				deleteLayoutImmediately(qLayout)
			qLayout = layoutCls.QLayoutType()
			qLayout.setContentsMargins(*NO_MARGINS)
			panel.setLayout(qLayout)

			panel.setOverlap(kwargs.get('overlap', NO_OVERLAP))
			panel.setRoundedCorners(kwargs.get('roundedCorners', CORNERS.ALL))
			panel.setCornerRadius(kwargs.get('cornerRadius', DEFAULT_PANEL_CORNER_RADIUS))

		layoutKwArgs = dict(verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing)
		self.addkwArgsToItem(qLayout, layoutKwArgs)
		return layoutCls(self, qLayout, preventVStretch, preventHStretch, forWidget=panel)

	def vPanel(
			self,
			preventVStretch: bool = False,
			preventHStretch: bool = False,
			verticalSpacing: int = -1,
			horizontalSpacing: int = -1,
			overlap: Overlap = ...,
			roundedCorners: RoundedCorners = ...,
			windowPanel: bool = False,
			seamless: bool = False,
			**kwargs
	) -> DoubleColumnLayout:
		layoutCls = getDoubleColumnLayout(seamless)
		if seamless:
			kwargs.setdefault('contentsMargins', NO_MARGINS)
			kwargs.setdefault('margins', NO_MARGINS)
		return self._panel(
			preventVStretch=preventVStretch, preventHStretch=preventHStretch, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing,
			overlap=overlap, roundedCorners=roundedCorners, windowPanel=windowPanel, layoutCls=layoutCls, **kwargs
		)

	def hPanel(
			self,
			preventVStretch: bool = False,
			preventHStretch: bool = False,
			verticalSpacing: int = -1,
			horizontalSpacing: int = -1,
			overlap: Overlap = ...,
			roundedCorners: RoundedCorners = ...,
			windowPanel: bool = False,
			seamless: bool = False,
			**kwargs
	) -> SingleRowLayout:
		layoutCls = getSingleRowLayout(seamless)
		if seamless:
			kwargs.setdefault('contentsMargins', NO_MARGINS)
			kwargs.setdefault('margins', NO_MARGINS)
		return self._panel(
			preventVStretch=preventVStretch, preventHStretch=preventHStretch, verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing,
			overlap=overlap, roundedCorners=roundedCorners, windowPanel=windowPanel, layoutCls=layoutCls, **kwargs
		)

	def vSeparator(self):
		self.addItem(CatSeparator, orientation=Qt.Vertical)

	def hSeparator(self):
		self.addItem(CatSeparator, orientation=Qt.Horizontal)

	def spoiler(self, label: str = '', isOpen: bool = None, **kwargs) -> bool:
		spoiler = self.addItem(Spoiler, title=label, **kwargs)

		if spoiler != self.modifiedInput[0] and spoiler.isOpen() != isOpen and isOpen is not None:
			spoiler.setOpen(isOpen)

		self._connectOnInputModified(spoiler, spoiler.clicked)

		return spoiler.isOpen()

	def collapsibleGroupBox(self, label='', isOpen=None, **kwargs) -> bool:
		"""
		Creates a groupbox with a spoiler. has to be used in an ``with`` statement:
		::
			with gui.collapsibleGroupBox(isChecked) as isOpen:
				if isOpen()

		Everything within the with statement will be inside the groupBox.
		"""
		return self.indentation().surroundWith(lambda: self.spoiler(label, isOpen=isOpen, style=getStyles().title, **kwargs))

	def tabWidget(self, selectedTab: Optional[Any] = None, initialSelectedTab: Optional[Any] = None, drawBase: bool = True, overlap: Overlap = NO_OVERLAP, roundedCorners: RoundedCorners = CORNERS.NONE, cornerGUI: Callable[[], None] = None, **kwargs) -> TabControl:
		"""
		Creates a vertical layout. has to be used in an ``with`` statement:
		::
			with gui.tabWidget() as tabs:
				with tabs.addTab(TabOptions('Example tab')):
					gui.button('Press me!')
				with tabs.addTab(TabOptions('Another example tab', icon=icons.exampleIcon)):
					...

		Everything within the with statement will be inside the vertical layout.

		:param selectedTab:
		:param initialSelectedTab: if not None: overrides selectedTab on first drawing of this tab widget.
		:param kwargs:
		:return:
		"""

		# frameColorName = '#b9b9b9'  # self.host.palette().mid().color().name()
		stackWidgetKwArgs = dict(
			lineWidth=0,
			sizePolicy=QSizePolicy(SizePolicy.Preferred.value, SizePolicy.Preferred.value, QSizePolicy.TabWidget),
			# frameStyle=QtWidgets.QFrame.NoFrame | QtWidgets.QFrame.Plain,
			# style=Style({'#TabWidgetStack': Style({
			# 	'border-top': f'0px solid {frameColorName}',
			# 	'border-bottom': f'1px solid {frameColorName}',
			# 	'border-right': f'1px solid {frameColorName}',
			# 	'border-left': f'1px solid {frameColorName}',
			# }) }),
			objectName='TabWidgetStack',
		)

		vLayout = self.vLayout(seamless=True, overlap=overlap, roundedCorners=roundedCorners)
		vLayout.__enter__()
		try:
			with self.hLayout(seamless=True):
				tabBar: CatTabBar = self.addItem(
					CatTabBar,
					drawBase=drawBase,
					expanding=kwargs.pop('expanding', False),
					**kwargs
				)
				if cornerGUI is not None:
					cornerGUI()
			stackedWidget: SeamlessQStackedWidget = self.addItem(SeamlessQStackedWidget, **stackWidgetKwArgs)

			redrawnCount = getattr(tabBar, '__redrawnCount', 0)
			setattr(tabBar, '__redrawnCount', redrawnCount + 1)

			if redrawnCount == 0:
				selectedTab = initialSelectedTab
			return TabControl(
				self,
				tabBar,
				stackedWidget,
				selectedTab
			).surroundWith(None, vLayout.__exit__)
		except Exception as ex:
			vLayout.__exit__(type(ex), ex, ex.__traceback__)
			raise

	def tabBar(self, allTabs: list[TabOptions], *, selectedTab: Optional[int] = None, initialSelectedTab: Optional[Any] = None, closeIcon: Optional[QIcon] = None, **kwargs) -> int:
		"""
		Creates a tab bar
		:param allTabs:
		:param selectedTab:
		:param initialSelectedTab: if not None: overrides selectedTab on first drawing of this tab widget.
		:param closeIcon:
		:param kwargs:
		:return: index of currently selected tab
		"""

		if closeIcon is None:
			from . import icons
			closeIcon = icons.icons.closeTab
		tabBar: CatTabBar = self.addItem(CatTabBar, minimumHeight=0, closeIcon=closeIcon, **kwargs)
		redrawnCount = getattr(tabBar, '__redrawnCount', 0)
		setattr(tabBar, '__redrawnCount', redrawnCount + 1)

		previouslySelected: int = tabBar.currentIndex()

		for i, tab in enumerate(allTabs):
			assert isinstance(tab, TabOptions)
			if i < tabBar.count():
				tabBar.setTabOptions(i, tab)
			else:
				tabBar.addTab(tab)

		while tabBar.count() > len(allTabs):
			tabBar.removeTab(tabBar.count()-1)

		if redrawnCount == 0 and initialSelectedTab is not None:
			selectedTab = initialSelectedTab
		if tabBar != self.modifiedInput[0] and selectedTab is not None:
			tabBar.setCurrentIndex(selectedTab)
		else:
			tabBar.setCurrentIndex(previouslySelected)

		self._connectOnInputModified(tabBar, tabBar.currentChanged)

		return tabBar.currentIndex()

	def stackedWidget(self, selectedView: Optional[Any] = None, **kwargs) -> StackedControl:
		"""
		Creates a vertical layout. has to be used in an ``with`` statement:
		::
			with gui.stackedWidget() as stacked:
				with stacked.addView(label='Example view'):
					gui.button('Press me!')
				with stacked.addView(label='Another example view'):
					...

		Everything within the with statement will be inside the vertical layout.

		:param selectedView:
		:param kwargs:
		:return:
		"""
		stackedWidget: SeamlessQStackedWidget = self.addItem(SeamlessQStackedWidget, **kwargs)
		return StackedControl(self, stackedWidget, selectedView)

	def _splitter(self, **kwargs) -> SplitterControl:
		splitterWidget = self.addItem(SeamlessQSplitter, **kwargs)
		if 'handleWidth' not in kwargs:
			style = splitterWidget.style()
			splitterWidget.setHandleWidth(style.pixelMetric(QtWidgets.QStyle.PM_SplitterWidth, None, splitterWidget))
		return SplitterControl(self, splitterWidget)

	def vSplitter(self, handleWidth: int = -1, **kwargs):
		return self._splitter(orientation=Qt.Vertical, handleWidth=handleWidth, **kwargs)

	def hSplitter(self, handleWidth: int = -1, **kwargs):
		return self._splitter(orientation=Qt.Horizontal, handleWidth=handleWidth, **kwargs)

	def subGUI(self, guiCls: Type[_TPythonGUI], guiFunc: Callable[[_TPythonGUI], None], label=None, *, seamless: bool = False, suppressRedrawLogging: bool = False, **kwargs) -> PythonGUI:
		if 'onInit' in kwargs:
			kwargs['onInit'] = lambda w, onInit=kwargs['onInit']: onInit(w) or w._gui.redrawGUI()
		else:
			kwargs['onInit'] = lambda w:  w._gui.redrawGUI()

		deferBorderFinalization = False  # hasattr(self.currentLayout._qLayout, 'finalizeBorders')
		qwidget: PythonGUIWidget = self.addLabeledItem(PythonGUIWidget, label, initArgs=(guiFunc, guiCls, seamless, deferBorderFinalization), suppressRedrawLogging=suppressRedrawLogging, **kwargs)
		qwidget._guiFunc = guiFunc
		qwidget.layout().setContentsMargins(*NO_MARGINS)
		return qwidget._gui

	def editor(self, editor: Type[TEditor], model: _TT, *, seamless: bool = False, **kwargs) -> TEditor:
		# def editor(self, editor: Type[EditorBase[_TT]], model: _TT, *, seamless: bool = False, **kwargs) -> EditorBase[_TT]:
		deferBorderFinalization = False  # hasattr(self.currentLayout._qLayout, 'finalizeBorders')
		editor2 = self.customWidget(editor, initArgs=(model, type(self), seamless, deferBorderFinalization), **kwargs)
		editor2.setModel(model)
		return editor2

	def box(self, preventVStretch: bool = False, preventHStretch: bool = False, verticalSpacing: int = -1, horizontalSpacing: int = -1, **kwargs):
		widget = self.addItem(CatBox, **kwargs)

		qLayout = widget.layout()
		if type(qLayout) is not DoubleColumnLayout.QLayoutType:
			qLayout = DoubleColumnLayout.QLayoutType()
			# TODO: ? self.setContentMargins(qLayout)
			widget.setLayout(qLayout)
		layoutKwArgs = dict(verticalSpacing=verticalSpacing, horizontalSpacing=horizontalSpacing)
		self.addkwArgsToItem(qLayout, layoutKwArgs)
		return DoubleColumnLayout(self, qLayout, preventVStretch, preventHStretch)

	def addHSpacer(self, size: int, sizePolicy: SizePolicy):
		spacer = self.currentLayout.addItem(QtWidgets.QSpacerItem, initArgs=(0, 0))
		needsInvalidation = False

		needsInvalidation = needsInvalidation or spacer.sizeHint().width() != size
		needsInvalidation = needsInvalidation or spacer.sizePolicy().horizontalPolicy() != sizePolicy
		spacer.changeSize(size, 0, hPolicy=sizePolicy.value)
		if needsInvalidation:
			spacer.invalidate()

	def addVSpacer(self, size: int, sizePolicy: SizePolicy):
		spacer = self.currentLayout.addItem(QtWidgets.QSpacerItem, initArgs=(0, 0))
		needsInvalidation = False

		qLayout = getattr(self.currentLayout, '_qLayout', None)
		if hasattr(qLayout, 'setRowMinimumHeight') and hasattr(qLayout, 'getItemPosition'):
			index = getattr(self.currentLayout, '_index', None)
			if index is not None:
				row, _, _, _ = qLayout.getItemPosition(index-1)
				qLayout.setRowMinimumHeight(row, 0)

		needsInvalidation = needsInvalidation or spacer.sizeHint().height() != size
		needsInvalidation = needsInvalidation or spacer.sizePolicy().verticalPolicy() != sizePolicy
		spacer.changeSize(0, size, vPolicy=sizePolicy.value)
		if needsInvalidation:
			spacer.invalidate()

	def addToolbarSpacer(self, sizePolicy: SizePolicy, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.NONE):
		spacer: CatToolbarSpacer = self.addItem(CatToolbarSpacer, overlap=overlap, roundedCorners=roundedCorners)
		spacer.setSizePolicy(sizePolicy.value, QSizePolicy.Preferred)

	def popupMenu(self, atMousePosition: bool = False, **kwargs) -> MenuControl:
		"""
		Creates a popupMenu at the position of the last Widget. has to be used in an ``with`` statement:
		::
			with gui.popupMenu() as menu:
				menu.addAction()

		Everything within the with statement will be inside the vertical layout.
		"""
		lastitem = self.currentLayout.getLastItem()
		if atMousePosition:
			position: QtCore.QPoint = QtGui.QCursor.pos()
		else:
			position: QtCore.QPoint = lastitem.mapToGlobal(QtCore.QPoint(0, 0))

		menuWidget = QtWidgets.QMenu(parent=None)

		# add kwArgs to Item
		self.addkwArgsToItem(menuWidget, kwargs)
		return MenuControl(menuWidget, self, position)

	def popupWindow(
			self, initVal: _TT,
			guiFunc: Callable[[_TPythonGUI, _TT], _TT] = lambda gui, v, **kwargs: gui.valueField(v, **kwargs),
			*,
			width: Optional[int] = None,
			height: Optional[int] = None,
			atMousePosition: bool = False,
			**kwargs
	) -> tuple[_TT, bool]:
		lastItem = self.host

		geometry: dict[str, int] = {}

		if width is not None:
			geometry['width'] = width

		if height is not None:
			geometry['height'] = height

		if atMousePosition:
			position: QtCore.QPoint = QtGui.QCursor.pos()
			geometry['x'] = position.x()
			geometry['y'] = position.y()
		elif lastItem is not None:
			position: QtCore.QPoint = lastItem.mapToGlobal(lastItem.rect().center())
			geometry['x'] = position.x()
			geometry['y'] = position.y()

		with self.overlay():
			result = PythonGUIPopupWindow.getValue(type(self), initVal, guiFunc, parent=lastItem, **geometry)
		return result

	@staticmethod
	def getFieldWidth(widget, letterCount=6):
		fm = widget.fontMetrics()
		return fm.size(Qt.TextSingleLine, 'M'*letterCount).width()

	@classmethod
	def setMinimumFieldWidth(cls, widget: QWidget, letterCount=6):
		minWidth = cls.getFieldWidth(widget, letterCount)
		if widget.minimumWidth() != minWidth and widget.sizeHint().width() < minWidth:
			widget.setMinimumWidth(minWidth)

	@classmethod
	def setMaximumFieldWidth(cls, widget, letterCount=6):
		maxWidth = cls.getFieldWidth(widget, letterCount)
		if widget.maximumWidth() != maxWidth:
			widget.setMaximumWidth(maxWidth)

	@staticmethod
	def switchKwArg(value, mapping: dict[type, str], default: str, kwArgsIO: dict) -> None:
		argKey = getIfKeyIssubclass(mapping, type(value), default)
		kwArgsIO[argKey] = value

	_labelContentKwArgSwitchMap: ClassVar[dict[type, str]] = {
		str: 'text',
		QtGui.QPixmap: 'pixmap',
		QtGui.QPicture: 'picture',
		QtGui.QIcon: 'icon',
		QtGui.QMovie: 'movie',
		int: 'num',
		float: 'num'
	}

	@classmethod
	def switchLabelContent(cls, value, kwArgsIO: dict) -> None:
		if value is True:
			value = 'true'
		elif value is False:
			value = 'false'
		cls.switchKwArg(value, cls._labelContentKwArgSwitchMap, 'text',  kwArgsIO=kwArgsIO)

	def _button(self, ButtonCls: Type[CatButton], text='', icon: QtGui.QIcon = None, autoDefault: bool = False, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.ALL, **kwargs) -> bool:
		if icon is None:
			icon = qEmptyIcon
		kwargs.setdefault('checkable', False)
		checked = kwargs.pop('checked', None)
		# if 'onInit' in kwargs:  # TODO: add proper onInit handling to all widgets, that receive the setMinimumFieldWidth treatment.
		# 	kwargs['onInit'] = lambda x, onInit=kwargs['onInit']: self.setMinimumFieldWidth(x) or onInit(x)
		# else:
		# 	kwargs['onInit'] = self.setMinimumFieldWidth
		button: CatButton = self.addItem(ButtonCls, text=text, icon=icon, autoDefault=autoDefault, overlap=overlap, roundedCorners=roundedCorners, **kwargs)
		self._connectOnInputModified(button, button.clicked)

		if button is not self.modifiedInput[0] and button.isCheckable() and checked is not None:
			button.setChecked(checked)
		elif button is self.modifiedInput[0]:
			self._forceSecondRedraw = True
			if not button.isCheckable():
				return True
		return button.isChecked()

	def button(self, text='', icon: QtGui.QIcon = None, autoDefault: bool = False, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.ALL, **kwargs):
		return self._button(CatButton, text, icon, autoDefault, overlap, roundedCorners, **kwargs)

	def toolButton(self, text='', icon: QtGui.QIcon = None, autoDefault: bool = False, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.NONE, **kwargs):
		return self._button(CatToolButton, text, icon, autoDefault, overlap, roundedCorners, **kwargs)

	def gradiantButton(self, text='', icon: QtGui.QIcon = None, autoDefault: bool = False, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.ALL, **kwargs):
		return self._button(CatGradiantButton, text, icon, autoDefault, overlap, roundedCorners, **kwargs)

	def framelessButton(self, text='', icon: QtGui.QIcon = None, autoDefault: bool = False, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.ALL, **kwargs):
		return self._button(CatFramelessButton, text, icon, autoDefault, overlap, roundedCorners, **kwargs)

	_defaultButtonTranslations: ClassVar[dict[MessageBoxButton, Callable[[], str]]] = {
		MessageBoxButton.Ok             : lambda: QApplication.instance().translate("QPlatformTheme", "OK"),
		MessageBoxButton.Save           : lambda: QApplication.instance().translate("QPlatformTheme", "Save"),
		MessageBoxButton.SaveAll        : lambda: QApplication.instance().translate("QPlatformTheme", "Save All"),
		MessageBoxButton.Open           : lambda: QApplication.instance().translate("QPlatformTheme", "Open"),
		MessageBoxButton.Yes            : lambda: QApplication.instance().translate("QPlatformTheme", "&Yes"),
		MessageBoxButton.YesToAll       : lambda: QApplication.instance().translate("QPlatformTheme", "Yes to &All"),
		MessageBoxButton.No             : lambda: QApplication.instance().translate("QPlatformTheme", "&No"),
		MessageBoxButton.NoToAll        : lambda: QApplication.instance().translate("QPlatformTheme", "N&o to All"),
		MessageBoxButton.Abort          : lambda: QApplication.instance().translate("QPlatformTheme", "Abort"),
		MessageBoxButton.Retry          : lambda: QApplication.instance().translate("QPlatformTheme", "Retry"),
		MessageBoxButton.Ignore         : lambda: QApplication.instance().translate("QPlatformTheme", "Ignore"),
		MessageBoxButton.Close          : lambda: QApplication.instance().translate("QPlatformTheme", "Close"),
		MessageBoxButton.Cancel         : lambda: QApplication.instance().translate("QPlatformTheme", "Cancel"),
		MessageBoxButton.Discard        : lambda: QApplication.instance().translate("QPlatformTheme", "Discard"),
		MessageBoxButton.Help           : lambda: QApplication.instance().translate("QPlatformTheme", "Help"),
		MessageBoxButton.Apply          : lambda: QApplication.instance().translate("QPlatformTheme", "Apply"),
		MessageBoxButton.Reset          : lambda: QApplication.instance().translate("QPlatformTheme", "Reset"),
		MessageBoxButton.RestoreDefaults: lambda: QApplication.instance().translate("QPlatformTheme", "Restore Defaults"),
	}

	def getDefaultButtonText(self, btnId: MessageBoxButton) -> str:
		return self._defaultButtonTranslations.get(btnId, lambda: '')()

	def dialogButtons(self, buttons: dict[MessageBoxButton, Callable[[MessageBoxButton], None] | tuple[Callable[[MessageBoxButton], None], dict[str, Any]]], defaultBtn: MessageBoxButton = MessageBoxButton.Ok, **kwargs):
		leftButtonsOrder = [
			MessageBoxButton.Reset,
			MessageBoxButton.RestoreDefaults,
		]
		rightButtonsOrder = [
			MessageBoxButton.Help,
			MessageBoxButton.Yes,
			MessageBoxButton.YesToAll,
			MessageBoxButton.Ok,
			MessageBoxButton.Save,
			MessageBoxButton.SaveAll,
			MessageBoxButton.Open,
			MessageBoxButton.Retry,
			MessageBoxButton.Ignore,
			MessageBoxButton.Discard,
			MessageBoxButton.No,
			MessageBoxButton.NoToAll,
			MessageBoxButton.Abort,
			MessageBoxButton.Close,
			MessageBoxButton.Cancel,
			MessageBoxButton.Apply,
		]

		def addButton(btnId: MessageBoxButton, action: Callable[[MessageBoxButton], None] | tuple[Callable[[MessageBoxButton], None], dict[str, Any]], default: bool):
			btnText = self.getDefaultButtonText(btnId)
			minimumWidth = int(80 * self._scale)
			action, kwArgs = action if isinstance(action, tuple) else (action, {})
			if self.button(btnText, autoDefault=False, default=default, minimumWidth=minimumWidth, **kwArgs) and action is not None:
				action(btnId)

		with self.hLayout(fullSize=True, **kwargs):
			for btnId in leftButtonsOrder:
				if btnId in buttons:
					addButton(btnId, buttons[btnId], btnId == defaultBtn)

			self.addHSpacer(int(16 * self._scale), SizePolicy.MinimumExpanding)

			for btnId in rightButtonsOrder:
				if btnId in buttons:
					addButton(btnId, buttons[btnId], btnId == defaultBtn)

	def _label(self, LabelCls: Type[QtWidgets.QLabel], content: LabelContent, style: Style, selectable: bool, **kwargs) -> None:
		if style is None:
			style = getStyles().label
		if selectable:
			kwargs['textInteractionFlags'] = kwargs.get('textInteractionFlags', Qt.NoTextInteraction) | Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
		self.switchLabelContent(content, kwArgsIO=kwargs)
		label: QtWidgets.QLabel = self.addItem(LabelCls, style=style, **kwargs)

		sp = label.sizePolicy()
		if 'hSizePolicy' not in kwargs:
			if not isinstance(getattr(self.currentLayout, '_qLayout', None), QtWidgets.QGridLayout):
				sp.setHorizontalPolicy(SizePolicy.Minimum.value)
			else:
				sp.setHorizontalPolicy(SizePolicy.Preferred.value)
				sp.setHorizontalStretch(0)
		if 'vSizePolicy' not in kwargs:
			sp.setVerticalPolicy(SizePolicy.Fixed.value)
		label.setSizePolicy(sp)

	def label(self, text: LabelContent, style: Style = None, selectable: bool = False, **kwargs) -> None:
		self._label(CatLabel, text, style, selectable, **kwargs)

	def elidedLabel(self, text: str, style: Style = None, elideMode: Qt.TextElideMode = Qt.ElideRight, selectable: bool = False, **kwargs):
		self._label(CatElidedLabel, text, style, selectable, elideMode=elideMode, **kwargs)

	def prefixLabel(self, text: LabelContent, style: Style = None, selectable: bool = False, **kwargs):
		return self._label(CatLabel, text, style, selectable, isPrefix=True, **kwargs)

	def title(self, text: LabelContent, *, selectable: bool = False, addSeparator: bool = False, **kwargs):
		self._label(CatLabel, text, getStyles().title, selectable, **kwargs)
		if addSeparator:
			self.vSeparator()

	def elidedTitle(self, text: LabelContent, elideMode: Qt.TextElideMode = Qt.ElideRight, selectable: bool = False, **kwargs):
		self._label(CatElidedLabel, text, getStyles().title, selectable, elideMode=elideMode, **kwargs)

	def doubleClickLabel(self, text: LabelContent, style: Style = None, selectable: bool = False, **kwargs):
		if style is None:
			style = getStyles().label
		if selectable:
			kwargs['textInteractionFlags'] = kwargs.get('textInteractionFlags', Qt.NoTextInteraction) | Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
		self.switchLabelContent(text, kwArgsIO=kwargs)
		label: CatLabel = self.addItem(CatLabel, style=style, **kwargs)

		sp = label.sizePolicy()
		if not isinstance(getattr(self.currentLayout, '_qLayout', None), QtWidgets.QGridLayout):
			sp.setHorizontalPolicy(SizePolicy.Minimum.value)

		sp.setVerticalPolicy(SizePolicy.Fixed.value)
		label.setSizePolicy(sp)

		self._connectOnInputModified(label, label.doubleClicked)
		if label is self.modifiedInput[0]:
			self._forceSecondRedraw = True
			return True
		return False

	helpBoxStyles: ClassVar[dict[str, Style]] = {
		'hint': getStyles().hint,
		'info': getStyles().hint,
		'warning': getStyles().warning,
		'error': getStyles().error
	}

	def helpBox(self, text: str, style: str = 'hint', elided: bool = False, wordWrap: bool = True, hasLabel: bool = True, **kwargs):
		""" displays a full width Help Box"""
		assert style in self.helpBoxStyles
		style = Style({'QLabel': self.helpBoxStyles[style]})

		kwargs.setdefault('textInteractionFlags', Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
		if text:
			if hasLabel:
				self.label('', isPrefix=True)
			if elided:
				self.elidedLabel(text, style=style, selectable=True, wordWrap=wordWrap, **kwargs)
			else:
				self.label(text, style=style, selectable=True, wordWrap=wordWrap, **kwargs)

	def textField(self, text: Optional[str], label=None, placeholderText: str = "", isMultiline: bool = False, focusEndOfText: bool = False, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.NONE, **kwargs):
		kwargs['placeholderText'] = placeholderText

		if 'onInit' in kwargs:  # TODO: add proper onInit handling to all widgets, that receive the setMinimumFieldWidth treatment.
			kwargs['onInit'] = lambda x, onInit=kwargs['onInit']: self.setMinimumFieldWidth(x) or onInit(x)
		else:
			kwargs['onInit'] = self.setMinimumFieldWidth

		if isMultiline:
			textField: CatMultiLineTextField = self.addLabeledItem(CatMultiLineTextField, label, overlap=overlap, roundedCorners=roundedCorners, **kwargs)
		else:
			textField: CatTextField = self.addLabeledItem(CatTextField, label, overlap=overlap, roundedCorners=roundedCorners, **kwargs)
		
		prevCursorPosition = textField.cursorPosition()
		if isMultiline:
			textField.setTabStopWidth(textField.fontMetrics().averageCharWidth() * 4)

		if textField != self.modifiedInput[0] and textField.plainText() != text and text is not None:
			textField.setPlainText(text)
			if focusEndOfText:
				newCursorPosition = textField.plainText().rfind('\n')+1 if isMultiline else len(textField.plainText())
			else:
				newCursorPosition = min(len(text), prevCursorPosition)
			textField.setCursorPosition(newCursorPosition)

		self._connectOnInputModified(textField, textField.textChanged)
		return textField.plainText()

	def codeField(self, text: Optional[str], label: Optional[str] = None, isMultiline: bool = True, focusEndOfText: bool = False, overlap: Overlap = (0, 0), roundedCorners: RoundedCorners = CORNERS.NONE, **kwargs) -> str:
		kwargs['style'] = getStyles().fixedWidthChar + kwargs.get('style', getStyles().none)
		# kwargs.setdefault('isMultiline', True)
		if isMultiline:
			kwargs.setdefault('lineWrapMode', QtWidgets.QTextEdit.NoWrap)
		return self.textField(text, label=label, isMultiline=isMultiline, focusEndOfText=focusEndOfText, overlap=overlap, roundedCorners=roundedCorners, **kwargs)

	def advancedCodeField(
			self, code: Optional[str],
			label: Optional[str] = None,
			language: str = 'PlainText',
			isMultiline: bool = True,
			searchResults: Optional[list[codeEditor.IndexSpan]] = None,
			prev: bool = False,
			next: bool = False,
			searchOptions: Optional[codeEditor.SearchOptions] = None,
			**kwargs) -> str:
		return codeEditor.advancedCodeField(self, code, label=label, language=language, isMultiline=isMultiline, searchResults=searchResults, next=next, prev=prev, searchOptions=searchOptions, **kwargs)

	_defaultButtonsForMessageBox: ClassVar[dict[MessageBoxStyle, MessageBoxButtons]] = {
		MessageBoxStyle.Information : {MessageBoxButton.Ok},
		MessageBoxStyle.Question    : {MessageBoxButton.Yes, MessageBoxButton.No},
		MessageBoxStyle.Warning     : {MessageBoxButton.Ok},
		MessageBoxStyle.Critical    : {MessageBoxButton.Ok},
		MessageBoxStyle.About       : {MessageBoxButton.Ok},
		MessageBoxStyle.AboutQt     : {MessageBoxButton.Ok},
	}

	def showMessageDialog(
			self,
			title: str,
			message: str,
			style: Optional[MessageBoxStyle],
			buttons: Optional[MessageBoxButtons] = None,
			*,
			textFormat: Qt.TextFormat = Qt.AutoText
	) -> MessageBoxButton:
		# MessageBoxStyle Information = 1
		# Question    = 2
		# Warning     = 3
		# Critical    = 4
		buttons = buttons or self._defaultButtonsForMessageBox[style]
		with self.overlay():
			return MessageDialog.showMessageDialog(self.host.window(), title, message, style, buttons, type(self), textFormat=textFormat)

	def showInformationDialog(self, title: str, message: str, *, textFormat: Qt.TextFormat = Qt.AutoText) -> None:
		self.showMessageDialog(title, message, MessageBoxStyle.Information, textFormat=textFormat)

	def askUser(self, title: str, message: str, *, textFormat: Qt.TextFormat = Qt.AutoText, style: MessageBoxStyle = MessageBoxStyle.Question, buttons: MessageBoxButtons = ...) -> bool:
		buttons = self._defaultButtonsForMessageBox[MessageBoxStyle.Question] if buttons is ... else buttons
		return self.showMessageDialog(title, message, style, buttons, textFormat=textFormat) == MessageBoxButton.Yes

	def showWarningDialog(self, title: str, message: str, *, textFormat: Qt.TextFormat = Qt.AutoText) -> None:
		self.showMessageDialog(title, message, MessageBoxStyle.Warning, textFormat=textFormat)

	def showErrorDialog(self, title: str, message: str, *, textFormat: Qt.TextFormat = Qt.AutoText) -> None:
		self.showMessageDialog(title, message, MessageBoxStyle.Error, textFormat=textFormat)

	def showCriticalDialog(self, title: str, message: str, *, textFormat: Qt.TextFormat = Qt.AutoText) -> None:
		self.showMessageDialog(title, message, MessageBoxStyle.Critical, textFormat=textFormat)

	def showAboutDialog(self, title: str, message: str, *, textFormat: Qt.TextFormat = Qt.AutoText) -> None:
		self.showMessageDialog(title, message, MessageBoxStyle.About, textFormat=textFormat)

	def showAboutQtDialog(self, title: str = '') -> None:
		self.showMessageDialog(title, '', MessageBoxStyle.AboutQt, textFormat=Qt.AutoText)

	def askUserInput(
			self: _TS,
			title: str,
			initVal: _TT,
			guiFunc: Callable[[_TS, _TT], _TT] = lambda gui, v: gui.valueField(v),
			*,
			windowModality: Qt.WindowModality = Qt.WindowModal,
			width: Optional[int] = None, height: Optional[int] = None,
			**kwargs
	) -> tuple[_TT, bool]:
		kwargs['windowTitle'] = title
		kwargs['windowModality'] = windowModality
		with self.overlay():
			result = PythonGUIValueDialog.getValue(type(self), initVal, guiFunc, self.host, width=width, height=height, kwargs=kwargs)
		return result

	def showDialog(
			self: _TS,
			title: str,
			initVal: _TT,
			guiFunc: Callable[[_TS, _TT], _TT] = lambda gui, v: gui.valueField(v),
			*,
			width: Optional[int] = None, height: Optional[int] = None,
			**kwargs
	):
		kwargs['windowTitle'] = title
		return PythonGUIValueDialog.showNonModal(type(self), initVal, guiFunc, self.host, width=width, height=height, kwargs=kwargs)

	fileDialogStyles: ClassVar[set[str]] = {'open', 'save'}

	def showFileDialog(self, path, filters: Sequence[FileExtensionFilter] = (), selectedFilter: FileExtensionFilter = None, *, style: Literal['open', 'save'] = 'open', returnOldPathOnCancel: bool = False) -> Optional[str]:
		assert style in self.fileDialogStyles

		def toFilterStr(fileFilter: FileExtensionFilter):
			extensionList = fileFilter[1] if isinstance(fileFilter[1], str) else " *".join(fileFilter[1])
			return f"{fileFilter[0]}, (*{extensionList})"

		if style in {'save'}:
			for fileFilter in filters:
				assert len(fileFilter[1]) == 1 or isinstance(fileFilter[1], str), \
					f"The save file dialog doesn't support grouping of file extensions: '{toFilterStr(fileFilter)}'"

		if style == 'open':
			fileDialog = QtWidgets.QFileDialog.getOpenFileName
			title = 'Open File'
		else:
			fileDialog = QtWidgets.QFileDialog.getSaveFileName
			title = 'Save File'

		filterStrs = list(map(toFilterStr, filters))
		filtersStr = ";;".join(filterStrs)
		selectedFilterStr = toFilterStr(selectedFilter) if selectedFilter is not None else None

		with self.overlay():
			newPath, extDescr = fileDialog(self.host, title, path, filtersStr, selectedFilterStr)
		if newPath:
			# TODO: add extension to filePath on Linux!
			import platform
			if style in {'save'} and platform.system().lower() == "linux":
				# on Linux, QFileDialog.getSaveFileName doesn't add the file extension, so lets do that here:
				reqExt = filters[filterStrs.index(extDescr)][1]
				reqExt = reqExt[0] if not isinstance(reqExt, str) else reqExt

				# check if newPath already has an extension:
				fPath, fExt = os.path.splitext(newPath)
				if fExt.lower() != reqExt and reqExt.strip():
					# newPah doesn't have an extension yet:
					newPath = fPath + reqExt
					if os.path.isfile(newPath):
						# file already exists, but user hasn't been asked for overwrite permission,
						# because fileDialog didn't add the extension. So do that here:
						souldOverwrite = QtWidgets.QMessageBox.warning(
							self.host, 
							"Confirm Overwrite",
							f"{os.path.basename(newPath)} already exists.\nDo you want to replace it?",
							QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes
						if not souldOverwrite:
							newPath = ''

		return newPath if newPath else (path if returnOldPathOnCancel else None)

	def showFolderDialog(self, path: str, *, returnOldPathOnCancel: bool = False) -> Optional[str]:
		with self.overlay():
			newPath = str(QtWidgets.QFileDialog.getExistingDirectory(self.host, "Select Directory", path))
		return newPath if newPath else (path if returnOldPathOnCancel else None)

	def folderPathField(self, path, label=None, **kwargs):
		with self.hLayout(label=label, seamless=True, **kwargs):
			path = self.textField(path, **kwargs)
			if self.button('Browse', overlap=(1, 0), roundedCorners=(False, True, False, True), **kwargs):
				path = self.showFolderDialog(path, returnOldPathOnCancel=True)

		return path

	@Deprecated
	def openFolderPathEdit(self, path, label=None, **kwargs):
		"""
		WARNING:: This function is deprecated please use ``folderPathField`` instead.
		"""
		path = self.folderPathField(path, label, **kwargs)

		if not os.path.lexists(path):
			self.helpBox('folder not found', style='error', hasLabel=label)

		return path

	@Deprecated
	def saveFolderPathEdit(self, path, label=None, **kwargs):
		"""
		WARNING:: This function is deprecated please use ``folderPathField`` instead.
		"""
		path = self.folderPathField(path, label, **kwargs)

		if not os.path.lexists(path):
			self.helpBox('folder not found', style='error', hasLabel=label)
		elif not os.access(path, os.W_OK):
			self.helpBox("cannot write in directory", style='error', hasLabel=label)

		return path

	def filePathField(self, path: Optional[str], filters: Sequence[tuple[str, Union[str, Sequence[str]]]] = (), style: Literal['open', 'save'] = 'open', label: Optional[str] = None, **kwargs):
		with self.hLayout(label=label, seamless=True, **kwargs):
			path = self.textField(path)
			if self.button('Browse', overlap=(1, 0), roundedCorners=(False, True, False, True)):
				path = self.showFileDialog(path, filters, style=style, returnOldPathOnCancel=True)
		return path

	def qintField(self, value: Optional[int], min: int = 0, max: int = +99, step: int = 1, label: Optional[str] = None, **kwargs):
		intField = self.addLabeledItem(QtWidgets.QSpinBox, label, minimum=min, maximum=max, singleStep=step, onInit=self.setMinimumFieldWidth, **kwargs)

		if value is not None and intField != self.modifiedInput[0] and intField.value() != value:
			intField.setValue(value)

		self._connectOnInputModified(intField, intField.valueChanged)
		return intField.value()

	def intField(self, value: Optional[int], min: int = 0, max: int = +99, step: int = 1, label: Optional[str] = None, **kwargs):
		intField = self.addLabeledItem(Int64SpinBox, label, minimum=min, maximum=max, singleStep=step, onInit=self.setMinimumFieldWidth, **kwargs)

		if value is not None and intField != self.modifiedInput[0] and intField.value() != value:
			intField.setValue(value)

		self._connectOnInputModified(intField, intField.valueChanged)
		return intField.value()

	def floatField(self, value: Optional[float], min: float = -math.inf, max: float = +math.inf, step: float = 0.01, decimals: int = 3, label: Optional[str] = None, **kwargs):
		floatField = self.addLabeledItem(QtWidgets.QDoubleSpinBox, label, minimum=min, maximum=max, singleStep=step, decimals=decimals, onInit=self.setMinimumFieldWidth, **kwargs)
		if value is not None and floatField != self.modifiedInput[0] and floatField.value() != value:
			floatField.setValue(value)
		self._connectOnInputModified(floatField, floatField.valueChanged)
		return floatField.value()

	def comboBox(self, value: Union[str, int], choices: Iterable[str], label: str = None, *, editable: bool = False, **kwargs):
		"""
			params:
			- editable: True/False* whether text can be freely edited by the user
		"""
		if 'onInit' in kwargs:
			kwargs['onInit'] = lambda x, onInit=kwargs['onInit']: self.setMinimumFieldWidth(x) or onInit(x)
		kwargs.setdefault('hSizePolicy', QSizePolicy.Expanding)
		comboBox: CatComboBox = self.addLabeledItem(CatComboBox, label, editable=editable, **kwargs)

		allCurrentItems = [comboBox.itemText(i) for i in range(comboBox.count())]
		choices = list(choices)
		if allCurrentItems != choices:
			comboBox.clear()
			comboBox.addItems(choices)
		if (completer := comboBox.completer()) is not None:
			completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)

		valueIsStr = isinstance(value, str)
		setCurrentValue: Callable[[Union[str, int]], None] = comboBox.setCurrentText if valueIsStr else comboBox.setCurrentIndex
		getCurrentValue = comboBox.currentText if valueIsStr else comboBox.currentIndex

		if comboBox != self.modifiedInput[0] and getCurrentValue() != value:
			setCurrentValue(value)

		self._connectOnInputModified(comboBox, comboBox.currentTextChanged[str])

		return getCurrentValue()

	def autoCompletionTreeComboBox(self, value: str, autoCompletionTree: codeEditor.AutoCompletionTree, label=None, prefix: str = None, **kwargs) -> str:
		rest = value
		if prefix:
			rest = rest.removeprefix(prefix)

		currentTree = autoCompletionTree
		lastTree = autoCompletionTree
		while rest and currentTree is not None:
			separators = currentTree.nextSeparators
			if not separators:
				break
			for separator in separators:
				l, sep, rest = rest.partition(separator)
				currentTree = lastTree.get(l)
				if currentTree is not None:
					if sep:
						lastTree = currentTree
					break
		if prefix:
			choices = [prefix + member.qName + member.separator[:-1] for member in lastTree.members()]
		else:
			choices = [member.qName + member.separator[:-1] for member in lastTree.members()]

		return self.comboBox(value, choices, label, editable=True, **kwargs)

	def fontComboBox(self, value: QFont, label: str = None, *, editable: bool = True, **kwargs) -> QFont:
		"""
			params:
			- editable: True/False* whether text can be freely edited by the user
		"""
		if 'onInit' in kwargs:
			kwargs['onInit'] = lambda x, onInit=kwargs['onInit']: self.setMinimumFieldWidth(x) or onInit(x)
		comboBox: QtWidgets.QFontComboBox = self.addLabeledItem(QtWidgets.QFontComboBox, label, editable=editable, **kwargs)

		valueIsStr = isinstance(value, str)

		if comboBox != self.modifiedInput[0] and comboBox.currentFont().family() != value.family():
			comboBox.setCurrentFont(value)

		self._connectOnInputModified(comboBox, comboBox.currentFontChanged)

		return comboBox.currentFont()

	def fontFamilyComboBox(self, value: str, label: str = None, *, editable: bool = False, writingSystem: QFontDatabase.WritingSystem = None, predicate: Callable[[QFontDatabase, str], bool] = None, **kwargs) -> str:
		"""
			params:
			- editable: True/False* whether text can be freely edited by the user
			- writingSystem: the writingSystem the font must support
			- predicate: a function for further filtering the font families or None.
		"""
		fontDB = QFontDatabase()
		choices = fontDB.families(QFontDatabase.Any if writingSystem is None else writingSystem)
		if predicate is not None:
			choices = filter(ft.partial(predicate, fontDB), choices)
		return self.comboBox(value, choices, label, editable=editable, **kwargs)

	def dateField(self, value: Optional[date], label: Optional[str] = None, **kwargs) -> date:
		dateField = self.addLabeledItem(QtWidgets.QDateEdit, label, onInit=self.setMinimumFieldWidth, **kwargs)
		if value is not None and dateField != self.modifiedInput[0] and dateField.date().toPyDate() != value:
			dateField.setDate(_toQDate(value))

		self._connectOnInputModified(dateField, dateField.dateChanged)
		return dateField.date().toPyDate()

	def slider(self, value: int, min: int, max: int, label: Optional[str] = None, orientation=QtCore.Qt.Horizontal, **kwargs):
		slider = self.addLabeledItem(QtWidgets.QSlider, label, minimum=min, maximum=max, orientation=orientation, **kwargs)

		if value is not None and slider != self.modifiedInput[0] and slider.value() != value:
			slider.setValue(value)

		self._connectOnInputModified(slider, slider.valueChanged)
		return slider.value()

	def scrollBar(self, value: Optional[int], docSize: int, pageStep: int, orientation=QtCore.Qt.Horizontal, **kwargs):
		slider: QtWidgets.QScrollBar = self.addItem(QtWidgets.QScrollBar, minimum=0, maximum=docSize + 0 - pageStep, pageStep=pageStep, orientation=orientation, **kwargs)

		if value is not None and slider != self.modifiedInput[0] and slider.value() != value:
			slider.setValue(value)

		self._connectOnInputModified(slider, slider.valueChanged)
		return slider.value()

	def checkbox(self, isChecked: Optional[BoolOrCheckState], label: Optional[str] = None, returnTristate: bool = False, **kwargs) -> BoolOrCheckState:
		tristate = kwargs.pop('tristate', False)
		checkbox = self.addLabeledItem(CatCheckBox, label, **kwargs)
		checkbox.setTristate(tristate)

		sp = checkbox.sizePolicy()
		sp.setHorizontalPolicy(SizePolicy.Fixed.value)
		checkbox.setSizePolicy(sp)

		l, t, r, b = checkbox.getContentsMargins()
		checkbox.setContentsMargins(15, t, 15, b)

		if isChecked is not None and checkbox != self.modifiedInput[0]:
			if type(isChecked) is bool:
				if checkbox.isChecked() != isChecked:
					checkbox.setChecked(isChecked)
			else:
				if checkbox.checkState() != isChecked.value:
					checkbox.setCheckState(cast(Qt.CheckState, isChecked.value))

		self._connectOnInputModified(checkbox, checkbox.stateChanged)
		return checkbox.isChecked() if not returnTristate else ToggleCheckState(checkbox.checkState())

	def checkboxLeft(self, isChecked: Optional[BoolOrCheckState], label: Optional[str] = None, returnTristate: bool = False, **kwargs) -> BoolOrCheckState:
		# kwargs['style'] = kwargs.get('style', getStyles().none) + getStyles().toggleLeft
		tristate = kwargs.pop('tristate', False)
		checkbox = self.addItem(CatCheckBox, text=label, **kwargs)
		checkbox.setTristate(tristate)

		if not isinstance(getattr(self.currentLayout, '_qLayout', None), QtWidgets.QGridLayout):
			sp = checkbox.sizePolicy()
			sp.setHorizontalPolicy(SizePolicy.Fixed.value)
			checkbox.setSizePolicy(sp)

		if isChecked is not None and checkbox != self.modifiedInput[0]:
			if type(isChecked) is bool:
				if checkbox.isChecked() != isChecked:
					checkbox.setChecked(isChecked)
			else:
				if checkbox.checkState() != isChecked.value:
					checkbox.setCheckState(cast(Qt.CheckState, isChecked.value))

		self._connectOnInputModified(checkbox, checkbox.stateChanged)
		return checkbox.isChecked() if not returnTristate else ToggleCheckState(checkbox.checkState())

	def prefixCheckbox(self, isChecked: Optional[BoolOrCheckState], label: Optional[str] = None, returnTristate: bool = False, **kwargs) -> BoolOrCheckState:
		return self.checkboxLeft(isChecked, label=label, returnTristate=returnTristate, isPrefix=True, **kwargs)

	# @Deprecated(msg="use ``gui.checkbox(...)`` instead")
	def toggle(self, isChecked: Optional[BoolOrCheckState], label=None, returnTristate=False, **kwargs) -> BoolOrCheckState:
		return self.checkbox(isChecked, label, returnTristate, **kwargs)

	# @Deprecated(msg="use ``gui.checkboxLeft(...)`` instead")
	def toggleLeft(self, isChecked: Optional[BoolOrCheckState], label=None, returnTristate=False, **kwargs) -> BoolOrCheckState:
		return self.checkboxLeft(isChecked, label, returnTristate, **kwargs)

	# @Deprecated(msg="use ``gui.prefixCheckbox(...)`` instead")
	def prefixToggle(self, isChecked: Optional[BoolOrCheckState], label=None, **kwargs) -> BoolOrCheckState:
		return self.prefixCheckbox(isChecked, label=label, **kwargs)

	def toggleSwitch(self, isChecked: Optional[bool], label=None, **kwargs) -> bool:

		toggle: Switch = self.addLabeledItem(Switch, label, **kwargs)

		if isChecked is not None and toggle != self.modifiedInput[0] and toggle.isChecked() != isChecked:
			toggle.setChecked(isChecked)

		self._connectOnInputModified(toggle, toggle.toggled)

		return toggle.isChecked()

	def radioButton(self, isChecked, label="", group: Optional[str] = None, id: Optional[int] = None, **kwargs):
		radioButton: CatRadioButton = self.addItem(CatRadioButton, **kwargs)
		radioButton.setText(label)

		if group is None:
			if radioButton.group() is not None:
				radioButton.group().removeButton(radioButton)
		else:
			if group not in self._buttonGroups:
				self._buttonGroups[group] = QtWidgets.QButtonGroup()
			btnGroup: QtWidgets.QButtonGroup = self._buttonGroups[group]
			if radioButton.group() != btnGroup:
				btnGroup.addButton(radioButton, id)
			else:
				btnGroup.setId(radioButton, id)

		radioButton.setAutoExclusive(group is None)
		if isChecked is not None and radioButton != self.modifiedInput[0] and radioButton.isChecked() != isChecked:
			radioButton.setChecked(isChecked)

		self._connectOnInputModified(radioButton, radioButton.toggled)

		return radioButton.isChecked()

	def radioButtonGroup(self, value: Optional[int], radioButtons: Sequence[str], label: Optional[str] = None, preventHStretch: bool = True, **kwargs):
		with self.hLayout(label, preventHStretch=preventHStretch, **kwargs) as layout:
			btnGrpLayout = layout._qLayout  # used later for identifying, whether btnGroup has been changed by user
			buttonGroup = getattr(btnGrpLayout, '_buttonGroup', None)
			if buttonGroup is None:
				buttonGroup = QtWidgets.QButtonGroup(layout._qLayout)
				setattr(layout._qLayout, '_buttonGroup', buttonGroup)

			currentValue = buttonGroup.checkedId()
			for i in range(0, len(radioButtons)):
				btn: CatRadioButton = self.addItem(CatRadioButton, **kwargs)
				btn.setText(radioButtons[i])
				if btn.group() != buttonGroup:
					buttonGroup.addButton(btn, i)
				else:
					buttonGroup.setId(btn, i)

		buttonGroup.setExclusive(True)
		if btnGrpLayout != self.modifiedInput[0] and buttonGroup.checkedId() != value:
			if value is not None:
				buttonGroup.buttons()[value].setChecked(True)
			elif buttonGroup.button(currentValue) is not None:
				buttonGroup.button(currentValue).setChecked(True)

		# event gets fired twice (1x for button that turned on and 1x for button that turned off).
		# make sure only one event triggers a redrawing:
		connectOnlyOnce(buttonGroup, buttonGroup.buttonToggled[int, bool], lambda _, switchedOn: self.OnInputModified(btnGrpLayout, data=buttonGroup) if switchedOn else 0, '_OnInputModified_')
		return buttonGroup.checkedId()

	def listField(self, index, values, label=None, valuesHaveChanged=True, **kwargs):
		listBox = self.addLabeledItem(QtWidgets.QListView,   label, **kwargs)
		if listBox.model() is None:
			listBox.setModel(QtCore.QStringListModel(listBox))
			connectSafe(listBox.model().modelReset, lambda: self.OnInputModified(listBox.model()))

		selection = listBox.selectionModel()
		if listBox != self.modifiedInput[0]:  # and listBox.currentIndex().row() != index:
			if valuesHaveChanged:
				if index is None:
					index = listBox.currentIndex().row()
				listBox.model().setStringList(values)
			if index is not None:
				indexOfTheCellIWant = listBox.model().index(index, 0)
				selection.setCurrentIndex(indexOfTheCellIWant, QtCore.QItemSelectionModel.ClearAndSelect)

		# connectOnlyOnce does not work here, because sometimes the __dict__ attribute doesn't get persisted properly:
		if QtCore.QObject.receivers(selection, selection.selectionChanged) == 1:  # '1' required here, because the QListView also connects to that signal
			# connectOnlyOnce does not work here, because sometimes the __dict__ attribute doesn't get persisted properly
			connectSafe(selection.selectionChanged, lambda x, y: self.OnInputModified(listBox))

		return listBox.currentIndex().row()

	def stringTable(self, data: list[Sequence[str]], headers: Sequence[str] = (), label: Optional[str] = None, fullSize: bool = False, **kwargs):
		assert len(headers) > 0
		needsReset = False

		table = self.addLabeledItem(DataTableView, label, fullSize=fullSize, **kwargs)
		if table.model() is None:
			table.setModel(DataTableModel(table, headers))
			connectSafe(table.model().modelReset, lambda: self.OnInputModified(table.model()))

		table.verticalHeader().setVisible(False)
		table.horizontalHeader().setStretchLastSection(True)
		table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
		table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

		if table.model().headers != headers:
			table.model().headers = headers
			needsReset = True
		if table.model() != self.modifiedInput[0] and table.model().tableData != data:
			table.model().tableData = data
			needsReset = True

		if needsReset:
			table.model().beginResetModel()
			table.model().endResetModel()

		tableHeight = sum(table.rowHeight(i) for i in range(min(table.model().rowCount(), 5)))
		table.setMinimumHeight(tableHeight + table.horizontalHeader().height() + 2 + 9)

		return table.model().tableData

	def tree(
			self,
			treeBuilder: TreeBuilderABC[_TT],
			headerBuilder: Optional[TreeBuilderABC[_T2]] = None,
			*,
			headerVisible: bool | EllipsisType = ...,
			loadDeferred: bool = True,
			columnResizeModes: Optional[Iterable[ResizeMode]] = None,
			stretchLastColumn: bool | EllipsisType = ...,
			**kwargs
	) -> TreeResult[_TT]:
		if 'itemDelegate' not in kwargs:
			kwargs['itemDelegate'] = QtWidgets.QStyledItemDelegate()

		kwargs.setdefault('indentation', int(13 * self._scale))

		if headerVisible is ...:
			headerVisible = headerBuilder is not None

		if isinstance(treeBuilder, (DataTreeBuilderNode, DataListBuilder)):
			treeWidget: DataBuilderTreeView = self.customWidget(DataBuilderTreeView, headerHidden=not headerVisible, loadDeferred=loadDeferred, **kwargs)
		else:
			treeWidget: BuilderTreeView = self.customWidget(BuilderTreeView, headerHidden=not headerVisible, loadDeferred=loadDeferred, **kwargs)

		selectionModel = treeWidget.selectionModel()

		if treeWidget is not self.modifiedInput[0] and selectionModel is not self.modifiedInput[0]:
			treeWidget.model().updateTree(treeBuilder, headerBuilder, selectionModel)

		header = treeWidget.header()

		if columnResizeModes is not None:
			header.setStretchLastSection(stretchLastColumn if stretchLastColumn is not ... else False)
			for i, srm in enumerate(columnResizeModes):
				header.setSectionResizeMode(i, srm.value)
		elif headerVisible:
			header.setStretchLastSection(stretchLastColumn if stretchLastColumn is not ... else True)
			header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
		else:
			header.setStretchLastSection(stretchLastColumn if stretchLastColumn is not ... else False)
			header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

		# connectOnlyOnce does not work here, because sometimes the __dict__ attribute doesn't get persisted properly:
		if QtCore.QObject.receivers(selectionModel, selectionModel.selectionChanged) == 2:
			# connectOnlyOnce does not work here, because sometimes the __dict__ attribute doesn't get persisted properly
			connectSafe(selectionModel.selectionChanged, lambda new, old: self.OnInputModified(selectionModel))

		self._connectOnInputModified(treeWidget, treeWidget.dataChanged)

		index = selectionModel.currentIndex()
		selectedItem: Optional[_TT] = index.internalPointer().getData(0) if index.isValid() else None
		return TreeResult(selectedItem, treeWidget.model().rootItem.getData(0), selectionModel, treeWidget)

	def progressBar(self, progressSignal: Optional[pyqtBoundSignal], min: int = 0, max: int = 100, label: Optional[str] = None, fullSize: bool = False, **kwargs):
		if min is not None:
			kwargs['minimum'] = min
		if max is not None:
			kwargs['maximum'] = max
		value = kwargs.pop('value', None)
		progressBar = self.addLabeledItem(CatProgressBar, label, fullSize=fullSize, orientation=QtCore.Qt.Horizontal, **kwargs)
		if value is not None:
			progressBar.setValue(value)

		if progressSignal is not None:
			try:
				progressSignal.disconnect(progressBar.setValue)
			except Exception as e:
				if str(e)[0:19] != "disconnect() failed" and str(e)[9:32] != "object is not connected":
					raise e
			connectSafe(progressSignal, progressBar.setValue)

	@overload
	def customWidget(self, widgetInstance: _TQWidget, label: Optional[str] = None, **kwargs) -> _TQWidget:
		pass

	@overload
	def customWidget(self, widgetInstance: Type[_TT], label: Optional[str] = None, **kwargs) -> _TT:
		pass

	def customWidget(self, widgetInstance, label=None, **kwargs):
		return self.addLabeledItem(widgetInstance, label, **kwargs)

	def renderArea(self, label=None, boundingSize: Vector = None, **kwargs) -> CatPainter:
		renderArea = self.addLabeledItem(RenderArea, label, **kwargs)
		cp = CatPainter(renderArea)
		if boundingSize is None:
			cp.setBoundingSize(renderArea.width(), renderArea.height())
		else:
			cp.setBoundingSize(boundingSize.x, boundingSize.y)
		return cp

	def enumField(self, value: Enum, label: Optional[str] = None, **kwargs):
		names = []
		members = []
		for name, member in type(value).__members__.items():
			names.append(name)
			members.append(member)
		index = members.index(value)

		index = self.comboBox(index, names, label, **kwargs)

		return members[index]

	def vectorField(self, values, label=None, labels=(), decorators=(), tips=(), tip='', kwargs: tuple[dict[str, Any], ...] = (), **commonKWargs):
		def addSpacers(widgetPainters):
			try:
				yield next(widgetPainters)()
				while True:
					wp = next(widgetPainters)
					self.addHSpacer(5, SizePolicy.Minimum)
					yield wp()
			except StopIteration as e:
				return

		def getPainter(type_, decorator):
			propertyPainter = decorator or getWidgetDrawer(type_)
			if propertyPainter is None:
				raise Exception("Unknown property type '{}'.\nCannot draw property".format(type_))
			return propertyPainter

		allLabels = itertools.chain(labels, itertools.repeat(None))
		allTips = itertools.chain(tips, itertools.repeat(tip))
		allDecorators = itertools.chain(decorators, itertools.repeat(None))
		allKWargs = itertools.chain(kwargs, itertools.repeat({}))
		widgetPainters = (lambda: getPainter(type(v), d)(self, v, label=l, tip=t, **commonKWargs, **kwa) for v, l, t, d, kwa in zip(values, allLabels, allTips, allDecorators, allKWargs))

		with self.hLayout(label=label, tip=tip, **commonKWargs):
			result = tuple(map(lambda v: v, addSpacers(widgetPainters)))
			self.addHSpacer(0, SizePolicy.Minimum)
			return result

	def valueField(self, value, type_=None, **kwargs):
		widgetDrawer = None
		try:
			typeHint = type_
			if typeHint.__origin__._name == 'Union':
				for arg in get_args(typeHint):
					widgetDrawer = getWidgetDrawer(arg)
					if widgetDrawer is not None:
						break
		except AttributeError:
			pass

		if widgetDrawer is None:
			widgetDrawer = getWidgetDrawer(type_ or type(value))
		if widgetDrawer is None:
			raise Exception(f"Unknown property type '{type_ or type(value)}'.\nCannot draw property")
		newValue = widgetDrawer(self, value, **kwargs)
		return newValue


_TPythonGUI = TypeVar('_TPythonGUI', bound=PythonGUI)


addWidgetDrawer(str, lambda gui, v, **kwargs: gui.textField(v, **kwargs))
addWidgetDrawer(int, lambda gui, v, **kwargs: gui.intField(v, **kwargs))
addWidgetDrawer(float, lambda gui, v, **kwargs: gui.floatField(v, **kwargs))
addWidgetDrawer(bool, lambda gui, v, **kwargs: gui.checkbox(v, **kwargs))
addWidgetDrawer(ToggleCheckState, lambda gui, v, **kwargs: gui.checkbox(v, returnTristate=True, **kwargs))
addWidgetDrawer(Enum, lambda gui, v, **kwargs: gui.enumField(v, **kwargs))
addWidgetDrawer(list, lambda gui, v, **kwargs: gui.stringTable(v, **kwargs))
addWidgetDrawer(set, lambda gui, v, **kwargs: set(gui.stringTable(list(v), **kwargs)))
addWidgetDrawer(tuple, lambda gui, v, **kwargs: gui.vectorField(v, **kwargs))
addWidgetDrawer(QFont, lambda gui, v, **kwargs: gui.fontComboBox(v, **kwargs))


class PythonGUIWidget(QWidget, CatSizePolicyMixin, CatFramedWidgetMixin, Generic[_TPythonGUI]):
	def __init__(
			self,
			guiFunc: Callable[[_TPythonGUI], None],
			GuiCls: Type[_TPythonGUI] = PythonGUI,
			seamless: bool = False,
			deferBorderFinalization: bool = False,
			parent: Optional[QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags()
	):
		super(PythonGUIWidget, self).__init__(parent, flags)
		# GUI
		self._guiFunc: Callable[[_TPythonGUI], None] = guiFunc
		self._gui: _TPythonGUI = GuiCls(self, self.OnGUI, seamless=seamless, deferBorderFinalization=deferBorderFinalization)

	def OnGUI(self, gui: _TPythonGUI):
		self._guiFunc(gui)

	def suppressRedrawLogging(self) -> bool:
		return self._gui.suppressRedrawLogging

	def setSuppressRedrawLogging(self, value: bool):
		self._gui.suppressRedrawLogging = value

	def redraw(self, cause: Optional[str] = None) -> None:
		self._gui.redraw(cause)

	def redrawLater(self, cause: Optional[str] = None) -> None:
		self._gui.redrawLater(cause)


class EditorBase(PythonGUIWidget, Generic[_TT]):

	def __init__(
			self,
			model: _TT,
			GuiCls: Type[_TPythonGUI],
			seamless: bool = False,
			deferBorderFinalization: bool = False,
			parent: Optional[QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags()
	):
		super(EditorBase, self).__init__(self.OnGUI, GuiCls, seamless, deferBorderFinalization, parent, flags)
		self._gui._name = f"'{self}'"
		self._model: _TT = model
		self.onSetModel(model, None)
		self.layout().setContentsMargins(0, 0, 0, 0)
		self.postInit()

		# self.redraw('EditorBase.__init__(...)')
		self.redrawLater('EditorBase.__init__(...)')

	def postInit(self) -> None:
		pass

	@abstractmethod
	def OnGUI(self, gui: _TPythonGUI) -> None:
		raise NotImplementedError()

	def model(self) -> _TT:
		return self._model

	def setModel(self, model: _TT):
		# self._gui._name = f"'<{type(model).__name__} at 0x{id(model):x}>'"
		if model is not self._model:
			old = self._model
			self._model = model
			self.onSetModel(model, old)
			self.redraw('EditorBase.setModel(...)')

	def onSetModel(self, new: _TT, old: Optional[_TT]) -> None:
		return None


TEditor = TypeVar('TEditor', bound=EditorBase)


class PythonGUIWindow(CatFramelessWindowMixin[_TPythonGUI], QWidget, Generic[_TPythonGUI]):
	def suppressRedrawLogging(self) -> bool:
		return self._gui.suppressRedrawLogging

	def setSuppressRedrawLogging(self, value: bool):
		self._gui.suppressRedrawLogging = value


class PythonGUIMainWindow(CatFramelessWindowMixin[_TPythonGUI], QtWidgets.QMainWindow, Generic[_TPythonGUI]):
	def __init__(
			self,
			GUICls: Type[_TPythonGUI] = PythonGUI,
			parent: Optional[QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags(),
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = None,
			height: Optional[int] = None
	):
		super(PythonGUIMainWindow, self).__init__(GUICls, parent, flags, x=x, y=y, width=width, height=height)
		self._disableContentMargins = True
		self._disableSidebarMargins = True
		self._isToolbarInTitleBar = False
		self.roundedCorners = CORNERS.ALL
		self.setAcceptDrops(True)

	def suppressRedrawLogging(self) -> bool:
		return self._gui.suppressRedrawLogging

	def setSuppressRedrawLogging(self, value: bool):
		self._gui.suppressRedrawLogging = value


class PythonGUIDialog(CatFramelessWindowMixin[_TPythonGUI], QDialog, Generic[_TPythonGUI]):
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
		super(PythonGUIDialog, self).__init__(GUICls, parent, flags, x=x, y=y, width=width, height=height)

	def suppressRedrawLogging(self) -> bool:
		return self._gui.suppressRedrawLogging

	def setSuppressRedrawLogging(self, value: bool):
		self._gui.suppressRedrawLogging = value

	@abstractmethod
	def OnGUI(self, gui: _TPythonGUI):
		raise NotImplementedError('PythonGUIDialog.OnGUI(self, gui)')

	def exec_(self) -> int:
		return self.exec()

	@CrashReportWrapped
	def exec(self) -> int:
		self._gui.redrawGUI()
		if self._gui.firstTabWidget:
			self._gui.firstTabWidget.setFocus(Qt.ActiveWindowFocusReason)
		return super().exec()


class PythonGUIValueDialog(PythonGUIDialog, Generic[_TPythonGUI]):
	def __init__(
			self,
			GUICls: Type[_TPythonGUI],
			initVal: _TT,
			guiFunc: Callable[[_TPythonGUI, _TT], _TT],
			parent: Optional[QtWidgets.QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags(),
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = None,
			height: Optional[int] = None
	):
		self._value: _TT = initVal
		self._guiFunc: Callable[[_TPythonGUI, _TT], _TT] = guiFunc
		super(PythonGUIValueDialog, self).__init__(GUICls, parent, flags, x=x, y=y, width=width, height=height)
		self._autoWidth: bool = False and width is None
		self._autoHeight: bool = height is None
		self._disableContentMargins = True

	def OnGUI(self, gui: _TPythonGUI):
		self._value = self._guiFunc(gui, self._value)
		self.updateSizeDeferred()

	@DeferredCallOnceMethod(delay=0)
	def updateSizeDeferred(self):
		oldSize = self.size()
		self.adjustSize()
		width = self.width() if self._autoWidth else oldSize.width()
		height = self.height() if self._autoHeight else oldSize.height()
		self.resize(width, height)

	def OnStatusbarGUI(self, gui: _TPythonGUI):
		with gui.vLayout():
			gui.dialogButtons({
				MessageBoxButton.Ok    : lambda b: self.accept(),
				MessageBoxButton.Cancel: lambda b: self.reject(),
			})

	# static method to create the dialog and return (value, accepted)
	@classmethod
	def getValue(
			cls,
			GUICls: Type[_TPythonGUI],
			initVal: _TT,
			guiFunc: Callable[[_TPythonGUI, _TT], _TT],
			parent: Optional[QWidget] = None,
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = None,
			height: Optional[int] = None,
			kwargs: dict[str, Any] = None,
	) -> tuple[_TT, bool]:
		if kwargs is None:
			kwargs = {}
		dialog = cls(GUICls, initVal, guiFunc, parent, x=x, y=y, width=width, height=height)
		# add kwArgs to dialog
		dialog._gui.addkwArgsToItem(dialog, kwargs)
		result = dialog.exec()

		isOk = result == QDialog.Accepted
		value = dialog._value if isOk else initVal
		return value, isOk

	@classmethod
	def showNonModal(
			cls,
			GUICls: Type[_TPythonGUI],
			initVal: _TT,
			guiFunc: Callable[[_TPythonGUI, _TT], _TT],
			parent: Optional[QWidget] = None,
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = None,
			height: Optional[int] = None,
			kwargs: dict[str, Any] = None,
	) -> PythonGUIValueDialog:
		if kwargs is None:
			kwargs = {}
		dialog = cls(GUICls, initVal, guiFunc, parent, x=x, y=y, width=width, height=height)
		# add kwArgs to dialog
		dialog._gui.addkwArgsToItem(dialog, kwargs)
		dialog.show()
		return dialog


class PythonGUIPopupWindow(PythonGUIValueDialog, Generic[_TPythonGUI]):
	def __init__(
			self,
			GUICls: Type[_TPythonGUI],
			initVal: _TT,
			guiFunc: Callable[[_TPythonGUI, _TT], _TT],
			parent: Optional[QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Popup,  # Qt.WindowFlags(),
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = None,
			height: Optional[int] = None
	):
		super(PythonGUIPopupWindow, self).__init__(GUICls, initVal, guiFunc, parent, flags | Qt.NoDropShadowWindowHint, x=x, y=y, width=width, height=height)
		self._isTitlebarVisible = False
		self._disableContentMargins = True
		self.roundedCorners = CORNERS.NONE
		QShortcut(Qt.Key_Return, self, lambda s=self: s.accept(), lambda s=self: s.accept(), Qt.WindowShortcut)
		QShortcut(Qt.Key_Enter, self, lambda s=self: s.accept(), lambda s=self: s.accept(), Qt.WindowShortcut)

	OnStatusbarGUI = None


class MessageDialog(CatFramelessWindowMixin[_TPythonGUI], QDialog, Generic[_TPythonGUI]):
	def __init__(
			self,
			title: str,
			message: str,
			buttons: MessageBoxButtons,
			style: MessageBoxStyle,
			GUICls: Type[_TPythonGUI] = ...,
			parent: Optional[QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags(),
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = 450,
			height: Optional[int] = None,
			textFormat: Qt.TextFormat = Qt.AutoText,
	):
		self._title: str = title
		self._message: str = message
		self._textFormat: Qt.TextFormat = textFormat
		self._buttons: MessageBoxButtons = buttons
		self._style: MessageBoxStyle = style
		self._icon: QIcon = QIcon()
		super(MessageDialog, self).__init__(GUICls, parent, flags, x=x, y=y, width=width, height=height)
		self.drawTitleToolbarBorder = False
		# self.setWindowTitle(self._title)
		if self._style == MessageBoxStyle.About:
			self._icon = self.windowIcon()
		else:
			self._icon = self.style().standardIcon(self.iconsForStyle[self._style])

	iconsForStyle = {
		MessageBoxStyle.Information: QtWidgets.QStyle.SP_MessageBoxInformation,
		MessageBoxStyle.Question: QtWidgets.QStyle.SP_MessageBoxQuestion,
		MessageBoxStyle.Warning: QtWidgets.QStyle.SP_MessageBoxWarning,
		MessageBoxStyle.Critical: QtWidgets.QStyle.SP_MessageBoxCritical,
	}

	def OnGUI(self, gui: _TPythonGUI):
		with gui.vLayout():
			with gui.vLayout(preventVStretch=True, isPrefix=True):
				gui.addVSpacer(gui.margin, SizePolicy.Fixed)
				gui.label(self._icon, iconScale=2, hSizePolicy=SizePolicy.Fixed.value)
			with gui.vLayout(preventVStretch=True):
				gui.title(self._title, selectable=False, textFormat=self._textFormat)
				gui.label(self._message, selectable=True, wordWrap=True, textFormat=self._textFormat)
		gui.addVSpacer(gui.spacing, SizePolicy.Fixed)
		gui.dialogButtons({
			msgBtn: lambda btnId: setattr(self, '_pressedButton', btnId) or self.done(btnId.value)
			for msgBtn in self._buttons
		})

	@classmethod
	def showMessageDialog(
			cls,
			host: Optional[QWidget],
			title: str,
			message: str,
			style: MessageBoxStyle,
			buttons: MessageBoxButtons,
			GUICls: Type[_TPythonGUI] = ...,
			*,
			textFormat: Qt.TextFormat = Qt.AutoText,
	) -> MessageBoxButton:
		if style == MessageBoxStyle.AboutQt:
			QtWidgets.QMessageBox.aboutQt(host, title)
			return MessageBoxButton.Ok
		dialog = cls(title, message, buttons, style, GUICls, host, Qt.Dialog, textFormat=textFormat)
		result = dialog.exec()
		return MessageBoxButton(result)


def _toQDate(pyDate: date) -> QtCore.QDate:
	return QtCore.QDate.fromString(str(pyDate), 'yyyy-MM-dd')
