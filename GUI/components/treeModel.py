from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, List, Optional, Sequence, TYPE_CHECKING, TypeVar, Union

from PyQt5.QtCore import QAbstractItemModel, QItemSelectionModel, QModelIndex, QPoint, Qt
from PyQt5.QtGui import QIcon

from ...GUI.components.treeBuilderABC import DecorationRole, TreeBuilderABC
from ...GUI.utilities import CrashReportWrapped
from ...utils.collections_ import OrderedMultiDict
from ...utils.formatters import formatVal

if TYPE_CHECKING:
	from .treeBuilders import DataListBuilder, DataTreeBuilderNode
else:
	DataListBuilder = Any
	DataTreeBuilderNode = Any


_TT = TypeVar('_TT')


@dataclass
class _DataListDefs:
	childrenMaker  : Callable[[_TT], Sequence[_TT]]
	isTree         : bool
	labelMaker     : Callable[[_TT, int], str]
	iconMaker      : Optional[Callable[[_TT, int], Optional[QIcon]]]
	toolTipMaker   : Optional[Callable[[_TT, int], Optional[str]]]
	columnCount    : int
	suppressUpdate : bool
	onDoubleClick  : Optional[Callable[[_TT], None]]  # this stays an optional intentionally.
	onContextMenu  : Optional[Callable[[_TT, int], None]]
	onCopy         : Optional[Callable[[_TT], Optional[str]]]
	onCut          : Optional[Callable[[_TT], Optional[str]]]
	onPaste        : Optional[Callable[[_TT, str], None]]
	onDelete       : Optional[Callable[[_TT], None]]
	isSelected     : Optional[Callable[[_TT], bool]]
	getId          : Optional[Callable[[_TT], Any]]

	def __post_init__(self):
		# funcNames = [
		# 	'childrenMaker',
		# 	'labelMaker',
		# 	'iconMaker',
		# 	'toolTipMaker',
		# 	'onDoubleClick',
		# 	'onContextMenu',
		# 	'onDelete',
		# 	'getId',
		# ]
		# for funcName in funcNames:
		# 	func = getattr(self, funcName)
		# 	if func is not None:
		# 		if not hasattr(func, '__CrashReportWrapped__'):
		# 			setattr(self, funcName, CrashReportWrapped(func))

		if self.iconMaker is None:
			self.iconMaker = lambda x, i: None

		if self.toolTipMaker is None:
			self.toolTipMaker = lambda x, i: None

		# if self.onDoubleClick is None:  See comment on 'onDoubleClick' attrinute above
		# 	self.onDoubleClick = lambda x: None

		if self.onContextMenu is None:
			self.onContextMenu = lambda x, i: None

		if self.onCopy is None:
			self.onCopy = lambda x: None

		if self.onCut is None:
			self.onCut = lambda x: None

		if self.onPaste is None:
			self.onPaste = lambda x, v: None

		if self.onDelete is None:
			self.onDelete = lambda x: None

		if self.isSelected is None:
			self.isSelected = lambda x: False

		if self.getId is None:
			self.getId = lambda x: x

@dataclass
class Operation:
	pass

	@abstractmethod
	def apply(self, aList: list):
		pass


@dataclass
class DeleteOperation(Operation):
	type = 0
	first: int
	last: int

	def apply(self, aList: list):
		for i in range(self.first, self.last+1):
			del aList[self.first]


@dataclass
class InsertOperation(Operation):
	type = 1
	first: int
	last: int
	values: list

	def apply(self, aList: list):
		for i in range(self.first, self.last+1):
			val = self.values[i - self.first]
			aList.insert(i, val)


@dataclass
class MoveOperation(Operation):
	type = 2
	first: int
	last: int
	dest: int  # destination

	def apply(self, aList: list):
		pocketSize = (self.last + 1) - self.first
		if self.first > self.dest:
			for i in range(pocketSize):
				val = aList.pop(self.first + i)
				aList.insert(self.dest + i, val)
		else:
			for i in range(pocketSize):
				val = aList.pop(self.first)
				aList.insert(self.dest-1, val)
		return aList


class ListUpdater(Generic[_TT]):

	def __init__(self, oldList: list[_TT], newList: list[_TT]):
		super(ListUpdater, self).__init__()

		self.intList: list[_TT] = oldList.copy()  # intermediateList
		self.newList: list[_TT] = newList

		self.operations: list[Operation] = []

	def _getIndexDict(self, aList: list[_TT]) -> OrderedMultiDict[_TT, int]:
		aDict: OrderedMultiDict[_TT, int] = OrderedMultiDict[_TT, int]()
		for i, v in enumerate(aList):
			aDict.add(v, i)
		return aDict

	def calculatOperations(self) -> list[Operation]:
		self.operations.clear()
		if self.intList == self.newList:
			return self.operations

		self.findAllDeleteOperations()
		self.findInsertAndMoveOperations()
		return self.operations

	def findInsertAndMoveOperations(self):
		intList = self.intList
		intDict = self._getIndexDict(self.intList)
		newList = self.newList

		newListLen = len(newList)
		intListLen = len(intList)
		currentIndexDelta = 0

		iNew = 0
		while iNew < newListLen:
			vNew = newList[iNew]
			iOld = intDict.popFirst(vNew, None)

			if iOld is None:  # we have a new Item!
				# InsertOperation:
				iFirst = iNew
				iNew += 1
				while iNew < newListLen:
					vNew = newList[iNew]
					if vNew in intDict:
						break
					iNew += 1
				iLast = iNew - 1
				pocketSize = (iLast + 1) - iFirst

				self.operations.append(InsertOperation(iFirst, iLast, newList[iFirst : iLast + 1]))
				# update intermediate list:
				for i in range(iFirst, iLast + 1):
					intList.insert(i, newList[i])
				intListLen = len(intList)
				# update intermediate index dict:
				currentIndexDelta += pocketSize
				# alreadyVisited = set()
				# for i in range(iLast + 1, intListLen):
				# 	valAti = intList[i]
				# 	if valAti in alreadyVisited:
				# 		continue
				# 	alreadyVisited.add(valAti)
				# 	allIndexes = intDict.getall(valAti)
				# 	allNewIndexes = [oi + (pocketSize * int(oi >= iFirst)) for oi in allIndexes]
				# 	intDict.setAll(valAti, allNewIndexes)
				# del alreadyVisited

			else:
				iOld += currentIndexDelta
				if iOld == iNew:  # everything is fine!
					# go ahead
					iNew += 1
					continue

				else:  # we have an old Item!
					# MoveOperation
					dest = iNew
					iFirst = iOld
					iOld += 1
					iNew += 1
					while iOld < intListLen:
						vNew = newList[iNew]
						if vNew != intList[iOld]:
							break
						if iOld == intDict.getFirst(vNew, None):
							intDict.popFirst(vNew)
						else:
							break
						iNew += 1
						iOld += 1
					iLast = iOld - 1
					pocketSize = (iLast + 1) - iFirst

					if iFirst > dest:
						self.operations.append(MoveOperation(iFirst, iLast, dest))
						# update intermediate list:
						range1 = intList[ : dest]
						range2 = intList[dest:iFirst]
						range3 = intList[iFirst : iLast+1]
						range4 = intList[iLast+1 : ]
						intList = range1 + range3 + range2 + range4
						# update intermediate index dict:
						# items that are moved directly:
						delta = dest - iFirst
						# for v in range3:
						# 	intDict[v] += delta
						alreadyVisited = set()
						for i in range(dest + pocketSize, iLast+1):
							valAti = intList[i]
							if valAti in alreadyVisited:
								continue
							alreadyVisited.add(valAti)
							allIndexes = intDict.getall(valAti)
							# allNewIndexes = [oi + ( delta if (iFirst <= oi <= iLast) else (pocketSize if oi < iFirst else 0) ) for oi in allIndexes]
							allNewIndexes = [oi + ( pocketSize if iFirst > oi+currentIndexDelta else 0 ) for oi in allIndexes]
							intDict.setAll(valAti, allNewIndexes)
						del alreadyVisited

						# # items that are pushed away by the moved items:
						# # AZ-JCO: actually, this is not necessary here, because, we'll never want to get the index of one of these items anyways
						# delta = pocketSize
						# for v in range2:
						# 	intDict[v] += delta


					else:
						assert False
						# dest += pocketSize
						# self.operations.append(MoveOperation(iFirst, iLast, dest))
						# # update intermediate list:
						# range1 = intList[ : iFirst]
						# range2 = intList[iFirst : iLast+1]
						# range3 = intList[iLast+1 : dest]
						# range4 = intList[dest : ]
						# intList = range1 + range3 + range2 + range4
						# # update intermediate index dict:
						# # items that are moved directly:
						# delta = dest - (iLast + 1)
						# for v in range2:
						# 	intDict[v] += delta
						# # items that are pushed away by the moved items:
						# # AZ-JCO: actually, this is not necessary here, because, we'll never want to get the index of one of these items anyways
						# delta = -pocketSize
						# for v in range3:
						# 	intDict[v] += delta

		self.intList = intList

	def findAllDeleteOperations(self):
		intList = self.intList
		newDictCpy = self._getIndexDict(self.newList)
		newIntList: list = []
		i1: int = 0
		i2: int = 0
		currentIndexDelta = 0

		iOld = 0
		intListLen = len(intList)
		while iOld < intListLen:
			# skip items that don't get removed:
			while iOld < intListLen:
				vOld = intList[iOld]
				if newDictCpy.popFirst(vOld, None) is not None:
					newIntList.append(vOld)
					iOld += 1
					continue
				else:
					break
			else:
				break  # no more items in intList!

			i1 = iOld
			iOld += 1
			# find continuous sequence of items that get removed:
			while iOld < intListLen:
				vOld = intList[iOld]
				if vOld not in newDictCpy:
					iOld += 1
					continue
				else:
					break
			i2 = iOld

			self.operations.append(DeleteOperation(i1 + currentIndexDelta, i2 - 1 + currentIndexDelta))
			currentIndexDelta += i1 - i2

		self.intList = newIntList


def getUpdateOperations(oldList: list[_TT], newList: list[_TT]) -> list[Operation]:
	if not oldList and not newList:
		return []
	lu = ListUpdater(oldList, newList)
	lu.calculatOperations()
	return lu.operations


_TTreeItem = TypeVar('_TTreeItem', bound='TreeItemBase')


class TreeItemBase(Generic[_TTreeItem]):
	def __init__(self, treeModelRoot: TreeModel):
		super(TreeItemBase, self).__init__()
		self._parentItem: Optional[_TTreeItem] = None
		self.childItems: List[_TTreeItem] = []
		self._treeModelRoot: TreeModel = treeModelRoot

		self.displayCache: Optional[Any] = None
		self.isLoaded: bool = False
		self.isUpdating: bool = False

	@classmethod
	@abstractmethod
	def createEmpty(cls, treeModelRoot: TreeModel) -> _TTreeItem:
		pass

	def __insertChild(self, item: _TTreeItem, row: int, index: QModelIndex):
		self._treeModelRoot.beginInsertRows(index, row, row)
		self.childItems.insert(row, item)
		self._treeModelRoot.endInsertRows()
		item._parentItem = self

	def __removeChild(self, childItemIndex: int, index: QModelIndex):
		row = childItemIndex  # item.row()
		self._treeModelRoot.beginRemoveRows(index, row, row)

		item = self.childItems[childItemIndex]
		del self.childItems[childItemIndex]
		item._parentItem = None

		self._treeModelRoot.endRemoveRows()

	def child(self, row: int) -> _TTreeItem:
		return self.childItems[row]

	def childCount(self) -> int:
		return len(self.childItems)

	def hasChildren(self) -> bool:
		return len(self.childItems) > 0

	def parent(self) -> Optional[_TTreeItem]:
		return self._parentItem

	def index(self, other: _TTreeItem) -> int:
		return self.childItems.index(other)

	def _getModelIndexOfSelf(self) -> QModelIndex:
		if self._parentItem is None:
			return QModelIndex()
		i = self._parentItem.index(self)
		return self._treeModelRoot.index(i, 0, self._parentItem._getModelIndexOfSelf())

	def row(self) -> int:
		if self.parent():
			try:
				return self.parent().index(self)
			except ValueError as e:
				print(e)
				raise
		return 0

	@abstractmethod
	def columnCount(self) -> int:
		pass

	@abstractmethod
	def label(self, column: int) -> Optional[str]:
		pass

	@abstractmethod
	def icon(self, column: int) -> Optional[DecorationRole]:
		pass

	@abstractmethod
	def toolTip(self, column: int) -> Optional[str]:
		pass

	@abstractmethod
	def getData(self, column: int) -> Optional[Any]:
		pass

	@abstractmethod
	def onCopy(self) -> Optional[str]:
		pass

	@abstractmethod
	def onCut(self) -> Optional[str]:
		pass

	@abstractmethod
	def onPaste(self, data: str):
		pass

	@abstractmethod
	def onDelete(self) -> None:
		pass

	@abstractmethod
	def onDoubleClick(self) -> bool:
		"""
		:return: True if a Action was taken, else False
		"""
		pass

	@abstractmethod
	def onContextMenu(self, column: int, pos: QPoint):
		pass

	def loadSubTree(self, selectionModel: QItemSelectionModel):
		for child in self.childItems:
			child.updateTree(selectionModel)
		self.isLoaded = True

	@abstractmethod
	def updateTree(self, selectionModel: QItemSelectionModel):
		pass

	@abstractmethod
	def setTreeBuilderForRoot(self, treeBuilder: TreeBuilderABC) -> None:
		pass


class DataTreeItem(TreeItemBase['DataTreeItem']):
	def __init__(self, data: Any, treeBuilder: Optional[_DataListDefs], treeModelRoot: TreeModel):
		super(DataTreeItem, self).__init__(treeModelRoot)
		self._data: Any = data
		self.treeBuilder: Optional[_DataListDefs] = treeBuilder
		self._id: Any = treeBuilder.getId(data) if treeBuilder is not None else None

	@classmethod
	def createEmpty(cls, treeModelRoot: TreeModel) -> DataTreeItem:
		return DataTreeItem(None, None, treeModelRoot=treeModelRoot)

	def columnCount(self) -> int:
		if self.treeBuilder is None:
			return 1
		return self.treeBuilder.columnCount

	def label(self, column: int) -> Optional[str]:
		try:
			label = self.treeBuilder.labelMaker(self._data, column)
			return label
		except IndexError as e:
			print(e)
			raise  # TODO: remove try:... except IndexError as e:... clause
			return None

	def icon(self, column: int) -> Optional[DecorationRole]:
		try:
			icon = self.treeBuilder.iconMaker(self._data, column)
			return icon
		except IndexError as e:
			print(e)
			raise  # TODO: remove try:... except IndexError as e:... clause
			return None

	def toolTip(self, column: int) -> Optional[str]:
		try:
			tip = self.treeBuilder.toolTipMaker(self._data, column)
			return tip
		except IndexError as e:
			print(e)
			raise  # TODO: remove try:... except IndexError as e:... clause
			return None

	def getData(self, column: int) -> Optional[Any]:
		data = self._data
		return data

	def onCopy(self) -> Optional[str]:
		return self.treeBuilder.onCopy(self._data)

	def onCut(self) -> Optional[str]:
		return self.treeBuilder.onCut(self._data)

	def onPaste(self, data: str):
		return self.treeBuilder.onPaste(self._data, data)

	def onDelete(self) -> None:
		self.treeBuilder.onDelete(self._data)

	def onDoubleClick(self) -> bool:
		"""
		:return: True if a Action was taken, else False
		"""
		if self.treeBuilder.onDoubleClick is None:
			return False
		self.treeBuilder.onDoubleClick(self._data)
		return True

	def onContextMenu(self, column: int, pos: QPoint):
		if self.treeBuilder.onContextMenu is None:
			return
		self.treeBuilder.onContextMenu(self._data, column)

	def loadSubTree(self, selectionModel: QItemSelectionModel):
		if self.treeBuilder is not None:
			if self.treeBuilder.isTree:
				for child in self.childItems:
					child.updateTree(selectionModel)
			self.isLoaded = True

	def updateTree(self, selectionModel: QItemSelectionModel):
		if self.isUpdating:
			return
		self.isUpdating = True
		try:
			treeBuilder = self.treeBuilder
			children: Any = treeBuilder.childrenMaker(self._data)
			if len(children) == 0 and len(self.childItems) == 0:
				return
			getId = treeBuilder.getId
			if getId is None:
				getId = lambda x: x
			childIds = [getId(ch) for ch in children]
			oldChildIds = [ci._id for ci in self.childItems]
			operations = getUpdateOperations(oldChildIds, childIds)

			selfIndex: Optional[QModelIndex] = None
			if operations:
				selfIndex = self._getModelIndexOfSelf()

			for operation in operations:
				if operation.type == 0:  # DeleteOperation
					operation: DeleteOperation
					try:
						self._treeModelRoot.beginRemoveRows(selfIndex, operation.first, operation.last)
						for i in range(operation.first, operation.last + 1):
							self.childItems[operation.first]._parentItem = None
							del self.childItems[operation.first]
					finally:
						self._treeModelRoot.endRemoveRows()

				elif operation.type == 1:  # InsertOperation
					operation: InsertOperation
					try:
						self._treeModelRoot.beginInsertRows(selfIndex, operation.first, operation.last)
						for i in range(operation.first, operation.last + 1):
							child = DataTreeItem(children[i], treeBuilder, treeModelRoot=self._treeModelRoot)
							self.childItems.insert(i, child)
							child._parentItem = self
					finally:
						self._treeModelRoot.endInsertRows()

				elif operation.type == 2:  # MoveOperation
					operation: MoveOperation
					try:
						self._treeModelRoot.beginMoveRows(selfIndex, operation.first, operation.last, selfIndex, operation.dest)
						pocketSize = (operation.last + 1) - operation.first
						if operation.first > operation.dest:
							for i in range(pocketSize):
								val = self.childItems.pop(operation.first + i)
								self.childItems.insert(operation.dest + i, val)
						else:
							for i in range(pocketSize):
								val = self.childItems.pop(operation.first)
								self.childItems.insert(operation.dest - 1, val)
					finally:
						self._treeModelRoot.endMoveRows()

			isSelected = treeBuilder.isSelected
			for child, childItem in zip(children, self.childItems):
				childId = getId(child)
				if childItem._id != childId:
					childItem.isLoaded = False
				childItem._data = child
				childItem.treeBuilder = treeBuilder
				childItem._id = childId
				if isSelected(child):
					selectionModel.setCurrentIndex(childItem._getModelIndexOfSelf(), QItemSelectionModel.ClearAndSelect)

			if children:
				if not self._treeModelRoot._loadDeferred or self.isLoaded:
					self.loadSubTree(selectionModel)

		finally:
			self.isUpdating = False

	def setTreeBuilderForRoot(self, treeBuilder: Union[DataTreeBuilderNode, DataListBuilder]) -> None:
		self.treeBuilder = treeBuilder._dataListDefs
		self._data = treeBuilder.getData()
		self._id = treeBuilder.id_  # avoids possible exceptions with DataListBuilder


class TreeItem(TreeItemBase['TreeItem']):
	def __init__(self, treeBuilder: Optional[TreeBuilderABC], treeModelRoot: TreeModel):
		super(TreeItem, self).__init__(treeModelRoot)
		self.treeBuilder: Optional[TreeBuilderABC] = treeBuilder

	@classmethod
	def createEmpty(cls, treeModelRoot: TreeModel) -> TreeItem:
		return TreeItem(None, treeModelRoot=treeModelRoot)

	def columnCount(self) -> int:
		if self.treeBuilder is None:
			return 1
		return self.treeBuilder.columnCount

	def label(self, column: int) -> Optional[str]:
		return self.treeBuilder.getLabel(column)

	def icon(self, column: int) -> Optional[DecorationRole]:
		return self.treeBuilder.getIcon(column)

	def toolTip(self, column: int) -> Optional[str]:
		return self.treeBuilder.getTip(column)

	def getData(self, column: int) -> Optional[Any]:
		try:
			data = self.treeBuilder.getData()
			return data
		except IndexError as e:
			print(e)
			return None

	def onCopy(self) -> Optional[str]:
		return self.treeBuilder.onCopy()

	def onCut(self) -> Optional[str]:
		return self.treeBuilder.onCut()

	def onPaste(self, data: str):
		self.treeBuilder.onPaste(data)

	def onDelete(self) -> None:
		self.treeBuilder.onDelete()

	def onDoubleClick(self) -> bool:
		"""
		:return: True if a Action was taken, else False
		"""
		self.treeBuilder.onDoubleClick()
		return True  # TODO: return a meaningful value

	def onContextMenu(self, column: int, pos: QPoint):
		self.treeBuilder.onContextMenu(column)

	def loadSubTree(self, selectionModel: QItemSelectionModel):
		for child in self.childItems:
			# forceUpdate = True
			# if forceUpdate or childTreeBuilder.needsUpdate(child.treeBuilder):
			child.updateTree(selectionModel)
		self.isLoaded = True

	def updateTree(self, selectionModel: QItemSelectionModel):
		if self.isUpdating:
			return
		self.isUpdating = True
		try:
			treeBuilder = self.treeBuilder
			i = -1
			selfIndex: Optional[QModelIndex] = None
			childrenBuilders = self.treeBuilder.children()
			childrenBuildersIds = [tb.id_ for tb in childrenBuilders ]
			oldChildBuildersIds = [ci.treeBuilder.id_ for ci in self.childItems ]
			operations = getUpdateOperations(oldChildBuildersIds, childrenBuildersIds)

			if operations:
				selfIndex = self._getModelIndexOfSelf()

			for operation in operations:
				if isinstance(operation, DeleteOperation):
					try:
						self._treeModelRoot.beginRemoveRows(selfIndex, operation.first, operation.last)
						for i in range(operation.first, operation.last + 1):
							self.childItems[operation.first]._parentItem = None
							del self.childItems[operation.first]
					finally:
						self._treeModelRoot.endRemoveRows()

				elif isinstance(operation, InsertOperation):
					try:
						self._treeModelRoot.beginInsertRows(selfIndex, operation.first, operation.last)
						for i in range(operation.first, operation.last + 1):
							child = TreeItem(childrenBuilders[i], treeModelRoot=self._treeModelRoot)
							self.childItems.insert(i, child)
							child._parentItem = self
							# child.treeBuilder.updateDeferred()
					finally:
						self._treeModelRoot.endInsertRows()

				elif isinstance(operation, MoveOperation):
					try:
						self._treeModelRoot.beginMoveRows(selfIndex, operation.first, operation.last, selfIndex, operation.dest)
						pocketSize = (operation.last + 1) - operation.first
						if operation.first > operation.dest:
							for i in range(pocketSize):
								val = self.childItems.pop(operation.first + i)
								self.childItems.insert(operation.dest + i, val)
						else:
							for i in range(pocketSize):
								val = self.childItems.pop(operation.first)
								self.childItems.insert(operation.dest - 1, val)
					finally:
						self._treeModelRoot.endMoveRows()

			for childTreeBuilder, child in zip(childrenBuilders, self.childItems):
				if childTreeBuilder.needsUpdate(child.treeBuilder):
					child.treeBuilder = childTreeBuilder
					# childTreeBuilder.updateDeferred()
				if childTreeBuilder.isSelected():
					selectionModel.setCurrentIndex(child._getModelIndexOfSelf(), QItemSelectionModel.ClearAndSelect)


			# for childTreeBuilder in childrenBuilders:
			# 	i += 1
			#
			# 	child: Optional[TreeItem] = None
			# 	if i < len(self.childItems) and self.childItems[i].treeBuilder.id_ == childTreeBuilder.id_:
			# 		child = self.childItems[i]
			# 		childTreeBuilder.initDeferred(treeBuilder, child.treeBuilder)
			# 		forceUpdate = False
			# 	else:
			# 		childTreeBuilder.initDeferred(treeBuilder, None)
			# 		child = TreeItem(childTreeBuilder, treeModelRoot=self._treeModelRoot)
			# 		if selfIndex is None:
			# 			selfIndex = self._getModelIndexOfSelf()
			# 		self.__insertChild(child, i, selfIndex)
			# 		forceUpdate = True
			# 	if forceUpdate or childTreeBuilder.needsUpdate(child.treeBuilder):
			# 		child.treeBuilder = childTreeBuilder
			# 		childTreeBuilder.updateDeferred()
			#
			# 	if childTreeBuilder.isSelected():
			# 		selectionModel.setCurrentIndex(child._getModelIndexOfSelf(), QItemSelectionModel.ClearAndSelect)
			#
			# while i + 1 < len(self.childItems):
			# 	if selfIndex is None:
			# 		selfIndex = self._getModelIndexOfSelf()
			# 	self.__removeChild(i + 1, selfIndex)

			if not self._treeModelRoot._loadDeferred or self.isLoaded:
				self.loadSubTree(selectionModel)

		finally:
			self.isUpdating = False

	def setTreeBuilderForRoot(self, treeBuilder: TreeBuilderABC) -> None:
		self.treeBuilder = treeBuilder


_IGNORED_ROLES: set[Qt.EditRole] = {2, 4, 5, 6, 7, 8, 9, 10, 13}
# Qt::DisplayRole	0	The key data to be rendered in the form of text. (QString)
# Qt::DecorationRole	1	The data to be rendered as a decoration in the form of an icon. (QColor, QIcon or QPixmap)
# Qt::EditRole	2	The data in a form suitable for editing in an editor. (QString)
# Qt::ToolTipRole	3	The data displayed in the item's tooltip. (QString)
# Qt::StatusTipRole	4	The data displayed in the status bar. (QString)
# Qt::WhatsThisRole	5	The data displayed for the item in "What's This?" mode. (QString)
# Qt::SizeHintRole	13	The size hint for the item that will be supplied to views. (QSize)

_ACCESSORS: dict[Qt.EditRole, str] = {
	Qt.DisplayRole   : 'label',
	Qt.DecorationRole: 'icon',
	Qt.ToolTipRole   : 'toolTip',
	Qt.UserRole      : 'getData',

	# Qt.EditRole: item.getData,
	# Qt.StatusTipRole: item.getData,
	# Qt.WhatsThisRole: item.getData,
	# Qt.SizeHintRole: item.getData,
}


class TreeModel(QAbstractItemModel):
	def __init__(self, selectionModel: QItemSelectionModel, parent=None):
		super().__init__(parent)
		self.rootItem = TreeItem.createEmpty(treeModelRoot=self)

		self.headerItem: TreeItem = TreeItem.createEmpty(treeModelRoot=self)
		self._loadDeferred: bool = True
		self._lastSelectionModel: QItemSelectionModel = selectionModel
	# self.updateTree(xmlData, treeBuilder)

	@CrashReportWrapped
	def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
		if parent.isValid():
			parentItem = parent.internalPointer()
		else:
			parentItem = self.rootItem
		return parentItem.columnCount()

	@CrashReportWrapped
	def data(self, index: QModelIndex, role: Qt.EditRole = Qt.DisplayRole) -> Optional[Any]:
		if not index.isValid():
			return None

		if role in _IGNORED_ROLES:
			return None

		item: TreeItem = index.internalPointer()

		accessor = _ACCESSORS.get(role)
		if accessor is not None:
			return getattr(item, accessor)(index.column())
		else:
			return None

	@CrashReportWrapped
	def canFetchMore(self, index: QModelIndex) -> bool:
		if not index.isValid():
			return False
		item: TreeItem = index.internalPointer()

		return not item.isLoaded
		return not (self._loadDeferred and item.isLoaded)
		return (not item.isLoaded) or (not self._loadDeferred)
		#return not self._loadDeferred

	@CrashReportWrapped
	def fetchMore(self, index: QModelIndex):
		item: TreeItem = index.internalPointer()
		item.loadSubTree(self._lastSelectionModel)

	# @CrashReportWrapped
	def flags(self, index: QModelIndex) -> Qt.ItemFlags:
		if not index.isValid():
			return Qt.NoItemFlags
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable

	@CrashReportWrapped
	def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.EditRole = Qt.DisplayRole) -> Optional[Any]:
		if orientation == Qt.Vertical:  # and role == Qt.DisplayRole:
			return None
		if self.headerItem.treeBuilder is None:
			return None

		item: TreeItem = self.headerItem
		# Qt::DisplayRole	0	The key data to be rendered in the form of text. (QString)
		# Qt::DecorationRole	1	The data to be rendered as a decoration in the form of an icon. (QColor, QIcon or QPixmap)
		# Qt::EditRole	2	The data in a form suitable for editing in an editor. (QString)
		# Qt::ToolTipRole	3	The data displayed in the item's tooltip. (QString)
		# Qt::StatusTipRole	4	The data displayed in the status bar. (QString)
		# Qt::WhatsThisRole	5	The data displayed for the item in "What's This?" mode. (QString)
		# Qt::SizeHintRole	13	The size hint for the item that will be supplied to views. (QSize)
		if role == Qt.DisplayRole:
			return item.label(section)
		elif role == Qt.DecorationRole:
			return item.icon(section)
		elif role == Qt.EditRole:
			return None  # item.data(section)
		elif role == Qt.ToolTipRole:
			return item.toolTip(section)
		elif role == Qt.StatusTipRole:
			return None  # item.data(section)
		elif role == Qt.WhatsThisRole:
			return None  # item.data(section)
		elif role == Qt.SizeHintRole:
			return None  # item.data(section)
		else:
			return None

	@CrashReportWrapped
	def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
		# if not self.hasIndex(row, column, parent):
		# 	return QModelIndex()
		if parent.isValid():
			parentItem = parent.internalPointer()
		else:
			parentItem = self.rootItem

		# if row not in range(childCount()) or column not in range(columnCount()):
		if not (0 <= row < parentItem.childCount()) or not (0 <= column < parentItem.columnCount()):
			return QModelIndex()

		try:
			childItem = parentItem.child(row)
			return self.createIndex(row, column, childItem)
		except IndexError:
			return QModelIndex()

	@CrashReportWrapped
	def parent(self, index: QModelIndex):
		if not index.isValid() or index.internalPointer() == None:
			return QModelIndex()

		childItem = index.internalPointer()
		parentItem = self.rootItem
		try:
			parentItem = childItem.parent()
		except Exception as e:
			print(e)

		if parentItem == self.rootItem or not parentItem:
			return QModelIndex()

		return self.createIndex(parentItem.row(), 0, parentItem)

	@CrashReportWrapped
	def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
		if parent.column() > 0:
			return 0

		if parent.isValid():
			parentItem = parent.internalPointer()
		else:
			parentItem = self.rootItem

		return parentItem.childCount()

	# @CrashReportWrapped
	def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
		if parent.column() > 0:
			return False

		if parent.isValid():
			parentItem = parent.internalPointer()
		else:
			parentItem = self.rootItem

		return parentItem.hasChildren()

	def updateTree(self, treeBuilder: TreeBuilderABC, headerBuilder: Optional[TreeBuilderABC], selectionModel: QItemSelectionModel):
		needsModelReset = False
		if self.rootItem.treeBuilder is None:
			needsModelReset = True
		else:
			if self.rootItem.treeBuilder.columnCount != treeBuilder.columnCount:
				needsModelReset = True

		if needsModelReset:
			self.beginResetModel()
		self.rootItem.setTreeBuilderForRoot(treeBuilder)
		self.headerItem.treeBuilder = headerBuilder

		self.rootItem.updateTree(selectionModel)
		if not self.rootItem.isLoaded:
			self.rootItem.loadSubTree(selectionModel)
		self._lastSelectionModel = selectionModel

		if needsModelReset:
			csi = selectionModel.currentIndex()
			self.endResetModel()
			selectionModel.setCurrentIndex(csi, QItemSelectionModel.ClearAndSelect)


class DataTreeModel(TreeModel):
	def __init__(self, selectionModel: QItemSelectionModel, parent=None):
		super(TreeModel, self).__init__(parent)
		self.rootItem = DataTreeItem.createEmpty(treeModelRoot=self)

		self.headerItem: TreeItem = TreeItem.createEmpty(treeModelRoot=self)
		self._loadDeferred: bool = True
		self._lastSelectionModel: QItemSelectionModel = selectionModel

	# def updateTree(self, treeBuilder: DataTreeBuilderRoot, headerBuilder: Optional[TreeBuilderABC], selectionModel: QItemSelectionModel):
	# 	needsModelReset = False
	# 	if self.rootItem.treeBuilder is None:
	# 		needsModelReset = True
	# 	else:
	# 		if self.rootItem.treeBuilder.columnCount != treeBuilder.columnCount:
	# 			needsModelReset = True
	#
	# 	if needsModelReset:
	# 		self.beginResetModel()
	# 	self.rootItem.setTreeBuilderForRoot(treeBuilder)
	# 	self.headerItem.treeBuilder = headerBuilder
	#
	# 	self.rootItem.updateTree(selectionModel)
	# 	if not self.rootItem.isLoaded:
	# 		self.rootItem.loadSubTree(selectionModel)
	# 	self._lastSelectionModel = selectionModel
	#
	# 	if needsModelReset:
	# 		csi = selectionModel.currentIndex()
	# 		self.endResetModel()
	# 		selectionModel.setCurrentIndex(csi, QItemSelectionModel.ClearAndSelect)


if __name__ == '__main__':

	# app = QApplication(sys.argv)
	#
	# f = QFile(':/default.txt')
	# f.open(QIODevice.ReadOnly)
	# model = TreeModel(f.readAll())
	# f.close()
	#
	# view = QTreeView()
	# view.setModel(model)
	# view.setWindowTitle("Simple Tree Model")
	# view.show()
	# sys.exit(app.exec_())

	def performOperations(oldList: list[_TT], operations: list[Operation]) -> list[_TT]:
		newList = oldList.copy()
		for i, operation in enumerate(operations):
			operation.apply(newList)
		return newList

	def _checkListUpdater(oldList: list[_TT], newList: list[_TT], title: str):
		print()
		print(f"======== BEGIN: {title} ==========")
		lu = ListUpdater(oldList, newList)
		operations = lu.calculatOperations()

		print(f"  len(operations) = {len(operations)}")
		print(formatVal(operations, tab = 1))
		print(f"  len(operations) = {len(operations)}")

		print(f"  oldList = {oldList}")
		print(f"  newList = {newList}")
		print(f"   luList = {lu.intList}")
		chkList = performOperations(oldList, operations)
		print(f"  chkList = {chkList}")
		print(f"========== END: {title} ==========")

		assert newList == lu.intList
		assert newList == chkList
		return operations

	lists = [
		# 0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16   17   18   19   20   21   22   23   24   25
		['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],
		# list 1:
		['b', 'c','h', 'i', 'l', 'o', 's', 'l', 'l', 'v', 'w', 'y'],
		# list 2:
		['A', 'a', 'b', 'c', 'D', 'E', 'F', 'G', 'd', 'e', 'f', 'g', 'h', 'i', 'J', 'K', 'j', 'k', 'l', 'M', 'N', 'm', 'n', 'o', 'P', 'Q', 'R', 'p', 'q', 'r', 's', 'T', 'U', 't', 'u', 'v', 'w', 'X', 'x', 'y', 'Z', 'z'],
		# list 3:
		['A', 'b', 'c', 'D', 'E', 'F', 'G', 'h', 'i', 'J', 'K', 'l', 'M', 'N', 'o', 'P', 'Q', 'R', 's', 'T', 'U', 'v', 'w', 'X', 'y', 'Z'],
		# list 4:
		['a', 'k', 's', 'd', 'r', 'o', 'x', 'n', 'i', 'u', 'c', 'b', 'y', 'e', 'w', 'p', 'h', 'q', 'f', 'm', 'v', 'z', 'l', 't', 'j', 'g'],
		# list 5:
		['A', 'K', 's', 'D', 'R', 'o', 'X', 'N', 'i', 'U', 'c', 'b', 'y', 'E', 'w', 'P', 'h', 'Q', 'F', 'M', 'v', 'Z', 'l', 'T', 'J', 'G'],
		# list 6:
		['w', 'b', 'o', 'M', 'N', 'F', 'Q', 'c', 'D', 'J', 'h', 'X', 'E', 'Z', 'i', 'A', 'R', 'y', 'U', 'l', 's', 'K', 'v', 'P', 'T', 'G'],
	]


	def checkAllListUpdaters():
		allOpLens = []
		for oldI, oldList in enumerate(lists):
			for newI, newList in enumerate(lists):
				if oldI == newI:
					continue
				title = f"list{oldI} -> list{newI}"
				opLen = len(_checkListUpdater(oldList, newList, title))
				allOpLens.append(opLen)
			# break;

		avgOpsLen = sum(allOpLens) / len(allOpLens)
		print(f"avgOpsLen = {avgOpsLen:.2f}")

	checkAllListUpdaters()
	# print()
	# print(f"======== list0 -> list0 ========")
	# lu = ListUpdater(list0, list0)
	# lu.calculatOperations()
	# print(formatVal(lu.operations))
	# assert
	# print()
	# print(f"======== list0 -> list0 ========")
	# lu = ListUpdater(list0, list1)
	# lu.findUpdateTransformations()
	# print(formatVal(lu.operations))
	# print()
	# print(f"======== list0 -> list2 ========")
	# lu = ListUpdater(list0, list2)
	# lu.findUpdateTransformations()
	# print(formatVal(lu.operations))
	# print()
	# print(f"======== list0 -> list3 ========")
	# lu = ListUpdater(list0, list3)
	# lu.findUpdateTransformations()
	# print(formatVal(lu.operations))
	# print()
	# print(f"======== list0 -> list4 ========")
	# lu = ListUpdater(list0, list4)
	# lu.findUpdateTransformations()
	# print(formatVal(lu.operations))