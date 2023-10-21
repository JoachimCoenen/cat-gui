from PyQt5.QtGui import QIcon

from ...GUI.components.treeBuilderABC import DecorationRole
from ...GUI.components.treeModel import _DataListDefs
from typing import Callable, Any, Sequence, Optional, TypeVar, Union, Generic

from ...GUI.components.treeBuilderABC import TreeBuilderABC

_TT = TypeVar('_TT')
_TU = TypeVar('_TU')


class DataTreeBuilderNode(TreeBuilderABC[_TT], Generic[_TT]):
	def __init__(self, data: _TT, dataList: Sequence[_TT], dataListDefs: _DataListDefs):
		super(DataTreeBuilderNode, self).__init__()
		self._data = data
		self._dataListDefs: _DataListDefs = dataListDefs
		self._dataList: Sequence[_TT] = dataList

	def needsUpdate(self, oldTreeBuilder: Optional[TreeBuilderABC]) -> bool:
		return not self._dataListDefs.suppressUpdate and id(self) != id(oldTreeBuilder)

	@property
	def id_(self) -> Any:
		if self._dataListDefs.getId is None:
			return self._data
		else:
			return self._dataListDefs.getId(self._data)

	def children(self) -> Sequence[TreeBuilderABC]:
		dataListDefs = self._dataListDefs
		children = [
			DataTreeBuilderNode(childData, dataListDefs.childrenMaker(childData), dataListDefs)
			for childData in self._dataList
		]
		return children

	@property
	def childCount(self) -> int:
		return len(self._dataList)

	def getData(self) -> list[_TT]:
		return self._data

	@property
	def columnCount(self):
		return self._dataListDefs.columnCount

	def getLabel(self, column: int) -> str:
		return self._dataListDefs.labelMaker(self._data, column)

	def getIcon(self, column: int) -> Optional[DecorationRole]:
		"""returns the icon for this item"""
		if self._dataListDefs.iconMaker is not None:
			return self._dataListDefs.iconMaker(self._data, column)
		else:
			return None

	def getTip(self, column: int) -> Optional[str]:
		"""returns the toolTip for this item"""
		if self._dataListDefs.toolTipMaker is not None:
			return self._dataListDefs.toolTipMaker(self._data, column)
		else:
			return None

	def onDoubleClick(self):
		if self._dataListDefs.onDoubleClick is not None:
			self._dataListDefs.onDoubleClick(self._data)

	def onContextMenu(self, column: int):
		if self._dataListDefs.onContextMenu is not None:
			self._dataListDefs.onContextMenu(self._data, column)

	def onDelete(self):
		if self._dataListDefs.onDelete is not None:
			self._dataListDefs.onDelete(self._data)

	def onCopy(self) -> Optional[str]:
		return self._dataListDefs.onCopy(self._data)

	def onCut(self) -> Optional[str]:
		return self._dataListDefs.onCut(self._data)

	def onPaste(self, data: str) -> None:
		self._dataListDefs.onPaste(self._data, data)


class DataTreeBuilderRoot(DataTreeBuilderNode[_TT], Generic[_TT]):
	def __init__(self, data: _TT, dataListDefs: _DataListDefs, showRoot: bool):
		dataList = (data,) if showRoot else dataListDefs.childrenMaker(data)
		super(DataTreeBuilderRoot, self).__init__(data, dataList, dataListDefs)

	def needsUpdate(self, oldTreeBuilder: Optional[TreeBuilderABC]) -> bool:
		return super(DataTreeBuilderRoot, self).needsUpdate(oldTreeBuilder)

	def children(self) -> Sequence[TreeBuilderABC]:
		return super(DataTreeBuilderRoot, self).children()


class DataListBuilderNode(DataTreeBuilderNode[_TT], Generic[_TT]):

	def needsUpdate(self, oldTreeBuilder: Optional[TreeBuilderABC]) -> bool:
		return not self._dataListDefs.suppressUpdate and id(self) != id(oldTreeBuilder)

	def children(self) -> Sequence[TreeBuilderABC]:
		return []

	@property
	def childCount(self) -> int:
		return 0


class DataListBuilder(TreeBuilderABC[_TT], Generic[_TT]):
	def __init__(
			self,
			data: Sequence[_TT],
			labelMaker    : Callable[[_TT, int], str],
			iconMaker     : Optional[Callable[[_TT, int], Optional[QIcon]]],
			toolTipMaker  : Optional[Callable[[_TT, int], Optional[str]]],
			columnCount   : int,
			suppressUpdate: bool = False,
			onDoubleClick : Optional[Callable[[_TT], None]] = None,
			onContextMenu : Optional[Callable[[_TT, int], None]] = None,
			onCopy        : Optional[Callable[[_TT], Optional[str]]] = None,
			onCut         : Optional[Callable[[_TT], Optional[str]]] = None,
			onPaste       : Optional[Callable[[_TT, str], None]] = None,
			onDelete      : Optional[Callable[[_TT], None]] = None,
			isSelected    : Optional[Callable[[_TT], bool]] = None,
			getId         : Optional[Callable[[_TT], Any]] = None
	):
		super(DataListBuilder, self).__init__()
		self._data = None
		self._dataList: Sequence[_TT] = data
		self._dataListDefs = _DataListDefs(
			childrenMaker=lambda dataList: dataList,
			isTree=False,
			labelMaker=labelMaker,
			iconMaker=iconMaker,
			toolTipMaker=toolTipMaker,
			columnCount=columnCount,
			suppressUpdate=suppressUpdate,
			onDoubleClick=onDoubleClick,
			onContextMenu=onContextMenu,
			onCopy=onCopy,
			onCut=onCut,
			onPaste=onPaste,
			onDelete=onDelete,
			isSelected=isSelected,
			getId=getId,
		)

	def needsUpdate(self, oldTreeBuilder: Optional[TreeBuilderABC]) -> bool:
		return not self._dataListDefs.suppressUpdate

	@property
	def id_(self) -> Any:
		return '<ROOT>'

	def children(self) -> Sequence[TreeBuilderABC]:
		dataListDefs = self._dataListDefs
		children = [
			DataListBuilderNode(childData, (), dataListDefs)
			for childData in self._dataList
		]
		return children

	@property
	def childCount(self) -> int:
		return len(self._dataList)

	def getData(self) -> Sequence[_TT]:
		return self._dataList

	@property
	def columnCount(self):
		return self._dataListDefs.columnCount

	def getLabel(self, column: int) -> str:
		return '<ROOT>'

	def getIcon(self, column: int) -> Optional[DecorationRole]:
		"""returns the icon for this item"""
		return None

	def getTip(self, column: int) -> Optional[str]:
		"""returns the toolTip for this item"""
		return None

	def onDoubleClick(self):
		pass

	def onContextMenu(self, column: int):
		pass


def DataTreeBuilder(
		data: _TT,
		childrenMaker : Callable[[Union[_TT, _TU]], Sequence[Union[_TT, _TU]]],
		labelMaker    : Callable[[Union[_TT, _TU], int], str],
		iconMaker     : Optional[Callable[[Union[_TT, _TU], int], Optional[QIcon]]],
		toolTipMaker  : Optional[Callable[[Union[_TT, _TU], int], Optional[str]]],
		columnCount   : int,
		showRoot      : bool = True,
		suppressUpdate: bool = False,
		onDoubleClick : Optional[Callable[[Union[_TT, _TU]], None]] = None,
		onContextMenu : Optional[Callable[[Union[_TT, _TU], int], None]] = None,
		onCopy        : Optional[Callable[[Union[_TT, _TU]], Optional[str]]] = None,
		onCut         : Optional[Callable[[Union[_TT, _TU]], Optional[str]]] = None,
		onPaste       : Optional[Callable[[Union[_TT, _TU], str], None]] = None,
		onDelete      : Optional[Callable[[Union[_TT, _TU]], None]] = None,
		isSelected    : Optional[Callable[[Union[_TT, _TU]], bool]] = None,
		getId         : Optional[Callable[[Union[_TT, _TU]], Any]] = None
) -> DataTreeBuilderNode[Union[_TT, _TU]]:
	dataListDefs = _DataListDefs(
		childrenMaker=childrenMaker,
		isTree=True,
		labelMaker=labelMaker,
		iconMaker=iconMaker,
		toolTipMaker=toolTipMaker,
		columnCount=columnCount,
		suppressUpdate=suppressUpdate,
		onDoubleClick=onDoubleClick,
		onContextMenu=onContextMenu,
		onCopy=onCopy,
		onCut=onCut,
		onPaste=onPaste,
		onDelete=onDelete,
		isSelected=isSelected,
		getId=getId,
	)
	return DataTreeBuilderRoot(data, dataListDefs, showRoot)


class DataHeaderBuilder(TreeBuilderABC[_TT], Generic[_TT]):
	def __init__(
			self,
			data: _TT,
			labelMaker: Callable[[_TT, int], str],
			iconMaker: Optional[Callable[[_TT, int], Optional[QIcon]]] = None,
			toolTipMaker: Optional[Callable[[_TT, int], Optional[str]]] = None,
			onDoubleClick: Optional[Callable[[_TT], None]] = None
	):
		super(DataHeaderBuilder, self).__init__()
		self._data = data
		self._labelMaker = labelMaker
		self._iconMaker = iconMaker
		self._toolTipMaker = toolTipMaker
		self._columnCount: int = -1  # columnCount
		self._suppressUpdate = True
		self._onDoubleClick = onDoubleClick

	def needsUpdate(self, oldTreeBuilder: Optional[TreeBuilderABC]) -> bool:
		return not self._suppressUpdate

	@property
	def id_(self) -> Any:
		return self._data

	def children(self) -> Sequence[TreeBuilderABC]:
		return []

	@property
	def childCount(self) -> int:
		return 0

	def getData(self) -> _TT:
		return self._data

	@property
	def columnCount(self):
		return self._columnCount

	def getLabel(self, column: int) -> str:
		return self._labelMaker(self._data, column)

	def getIcon(self, column: int) -> Optional[DecorationRole]:
		"""returns the icon for this item"""
		if self._iconMaker:
			return self._iconMaker(self._data, column)
		else:
			return None

	def getTip(self, column: int) -> Optional[str]:
		"""returns the toolTip for this item"""
		if self._toolTipMaker:
			return self._toolTipMaker(self._data, column)
		else:
			return None

	def onDoubleClick(self):
		if self._onDoubleClick:
			self._onDoubleClick(self._data)

	def onCopy(self) -> Optional[str]:
		return None

	def onPaste(self, data: str):
		pass


def StringHeaderBuilder(
			data: tuple[str, ...],
			labelMaker: Callable[[_TT, int], str] = lambda data, c: data[c],
			iconMaker: Optional[Callable[[_TT, int], Optional[QIcon]]] = None,
			toolTipMaker: Optional[Callable[[_TT, int], Optional[str]]] = None,
			onDoubleClick: Optional[Callable[[_TT], None]] = None
) -> DataHeaderBuilder[tuple[str, ...]]:
	return DataHeaderBuilder(data, labelMaker, iconMaker, toolTipMaker, onDoubleClick)


__all__ = [
	'DataListBuilder',
	'DataTreeBuilder',
	'DataHeaderBuilder',
	'StringHeaderBuilder',
]