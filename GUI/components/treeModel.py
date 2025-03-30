from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Sequence, TYPE_CHECKING, ClassVar, cast, TypeAlias

from PyQt5.QtCore import QAbstractItemModel, QItemSelectionModel, QModelIndex, QPoint, Qt
from PyQt5.QtGui import QIcon, QColor, QPixmap
from better_orderedmultidict import OrderedMultiDict as DeOrderedMultiDict

from cat.utils.utils import CrashReportWrapped
from ...utils.formatters import formatVal

if TYPE_CHECKING:
	from .treeBuilders import DataTreeBuilderNode, DataHeaderBuilder


DecorationRole: TypeAlias = QColor | QIcon | QPixmap


@dataclass(init=False)
class _DataListDefs[TT]:
	childrenMaker  : Callable[[TT], Sequence[TT]]
	isTree         : bool
	labelMaker     : Callable[[TT, int], str]
	iconMaker      : Callable[[TT, int], QIcon | None]
	toolTipMaker   : Callable[[TT, int], str | None]
	columnCount    : int
	suppressUpdate : bool
	onDoubleClick  : Callable[[TT], None] | None  # this stays an optional intentionally.
	onContextMenu  : Callable[[TT, int], None]
	onCopy         : Callable[[TT], str | None]
	onCut          : Callable[[TT], str | None]
	onPaste        : Callable[[TT, str], None]
	onDelete       : Callable[[TT], None]
	isSelected     : Callable[[TT], bool]
	getId          : Callable[[TT], Any]

	def __init__(self,
		childrenMaker  : Callable[[TT], Sequence[TT]],
		isTree         : bool,
		labelMaker     : Callable[[TT, int], str],
		iconMaker      : Callable[[TT, int], QIcon | None] | None,
		toolTipMaker   : Callable[[TT, int], str | None] | None,
		columnCount    : int,
		suppressUpdate : bool,
		onDoubleClick  : Callable[[TT], None] | None,  # this stays an optional intentionally.
		onContextMenu  : Callable[[TT, int], None] | None,
		onCopy         : Callable[[TT], str | None] | None,
		onCut          : Callable[[TT], str | None] | None,
		onPaste        : Callable[[TT, str], None] | None,
		onDelete       : Callable[[TT], None] | None,
		isSelected     : Callable[[TT], bool] | None,
		getId          : Callable[[TT], Any] | None,
	):
		self.childrenMaker  = childrenMaker
		self.isTree         = isTree
		self.labelMaker     = labelMaker
		self.iconMaker      = iconMaker if iconMaker is not None else lambda x, i: None
		self.toolTipMaker   = toolTipMaker if toolTipMaker is not None else lambda x, i: None
		self.columnCount    = columnCount
		self.suppressUpdate = suppressUpdate
		self.onDoubleClick  = onDoubleClick  # See comment on 'onDoubleClick' attrinute above
		self.onContextMenu  = onContextMenu if onContextMenu is not None else lambda x, i: None
		self.onCopy         = onCopy if onCopy is not None else lambda x: None
		self.onCut          = onCut if onCut is not None else lambda x: None
		self.onPaste        = onPaste if onPaste is not None else lambda x, v: None
		self.onDelete       = onDelete if onDelete is not None else lambda x: None
		self.isSelected     = isSelected if isSelected is not None else lambda x: False
		self.getId          = getId if getId is not None else lambda x: x


@dataclass
class Operation:
	type: ClassVar[int]

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


class ListUpdater[TT]:

	def __init__(self, oldList: list[TT], newList: list[TT]):
		super(ListUpdater, self).__init__()

		self.intList: list[TT] = oldList.copy()  # intermediateList
		self.newList: list[TT] = newList

		self.operations: list[Operation] = []

	def _getIndexDict(self, aList: list[TT]) -> DeOrderedMultiDict[TT, int]:
		aDict: DeOrderedMultiDict[TT, int] = DeOrderedMultiDict[TT, int]()
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
			iOld = intDict.popfirst(vNew, None)

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
				# 	intDict.setall(valAti, allNewIndexes)
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
						if iOld == intDict.getfirst(vNew, None):
							intDict.popfirst(vNew)
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
							intDict.setall(valAti, allNewIndexes)
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

	def findAllDeleteOperations(self) -> None:
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
				if newDictCpy.popfirst(vOld, None) is not None:
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


def getUpdateOperations[TT](oldList: list[TT], newList: list[TT]) -> list[Operation]:
	if not oldList and not newList:
		return []
	lu = ListUpdater(oldList, newList)
	lu.calculatOperations()
	return lu.operations


class DataTreeItem:
	def __init__(self, data: Any, treeBuilder: _DataListDefs | None, treeModelRoot: DataTreeModel) -> None:
		super(DataTreeItem, self).__init__()
		self._parentItem: DataTreeItem | None = None
		self.childItems: list[DataTreeItem] = []
		self._treeModelRoot: DataTreeModel = treeModelRoot

		self.displayCache: Any | None = None
		self.isLoaded: bool = False
		self.isUpdating: bool = False

		self._data: Any = data
		self.treeBuilder: _DataListDefs | None = treeBuilder
		self._id: Any = treeBuilder.getId(data) if treeBuilder is not None else None

	@classmethod
	def createEmpty(cls, treeModelRoot: DataTreeModel) -> DataTreeItem:
		return DataTreeItem(None, None, treeModelRoot=treeModelRoot)

	def child(self, row: int) -> DataTreeItem:
		return self.childItems[row]

	def childCount(self) -> int:
		return len(self.childItems)

	def hasChildren(self) -> bool:
		return len(self.childItems) > 0

	def parent(self) -> DataTreeItem | None:
		return self._parentItem

	def index(self, other: DataTreeItem) -> int:
		return self.childItems.index(other)

	def _getModelIndexOfSelf(self) -> QModelIndex:
		if self._parentItem is None:
			return QModelIndex()
		i = self._parentItem.index(self)
		return self._treeModelRoot.index(i, 0, self._parentItem._getModelIndexOfSelf())

	def row(self) -> int:
		if (parent := self.parent()) is not None:
			try:
				return parent.index(self)
			except ValueError as e:
				print(e)
				raise
		return 0

	def columnCount(self) -> int:
		if self.treeBuilder is None:
			return 1
		return self.treeBuilder.columnCount

	def label(self, column: int) -> str | None:
		if self.treeBuilder is None:
			return None
		try:
			label = self.treeBuilder.labelMaker(self._data, column)
			return label
		except IndexError as e:
			print(e)
			raise  # TODO: remove try:... except IndexError as e:... clause
			return None

	def icon(self, column: int) -> DecorationRole | None:
		if self.treeBuilder is None:
			return None
		try:
			icon = self.treeBuilder.iconMaker(self._data, column)
			return icon
		except IndexError as e:
			print(e)
			raise  # TODO: remove try:... except IndexError as e:... clause
			return None

	def toolTip(self, column: int) -> str | None:
		if self.treeBuilder is None:
			return None
		try:
			tip = self.treeBuilder.toolTipMaker(self._data, column)
			return tip
		except IndexError as e:
			print(e)
			raise  # TODO: remove try:... except IndexError as e:... clause
			return None

	def getData(self, column: int) -> Any | None:
		data = self._data
		return data

	def onCopy(self) -> str | None:
		if self.treeBuilder is None:
			return None
		return self.treeBuilder.onCopy(self._data)

	def onCut(self) -> str | None:
		if self.treeBuilder is None:
			return None
		return self.treeBuilder.onCut(self._data)

	def onPaste(self, data: str) -> None:
		if self.treeBuilder is None:
			return
		self.treeBuilder.onPaste(self._data, data)

	def onDelete(self) -> None:
		if self.treeBuilder is None:
			return
		self.treeBuilder.onDelete(self._data)

	def onDoubleClick(self) -> bool:
		"""
		:return: True if a Action was taken, else False
		"""
		if self.treeBuilder is None or self.treeBuilder.onDoubleClick is None:
			return False
		self.treeBuilder.onDoubleClick(self._data)
		return True

	def onContextMenu(self, column: int, pos: QPoint) -> None:
		if self.treeBuilder is None:
			return
		self.treeBuilder.onContextMenu(self._data, column)

	def loadSubTree(self, selectionModel: QItemSelectionModel):
		if self.treeBuilder is not None:
			if self.treeBuilder.isTree:
				for child in self.childItems:
					child.updateTree(selectionModel)
			self.isLoaded = True

	def updateTree(self, selectionModel: QItemSelectionModel) -> None:
		if self.isUpdating or self.treeBuilder is None:
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

			if operations:
				self._applyOperationsToTree(children, operations, treeBuilder)

			isSelected = treeBuilder.isSelected
			for child, childItem in zip(children, self.childItems):
				childId = getId(child)
				if childItem._id != childId:
					childItem.isLoaded = False
				childItem._data = child
				childItem.treeBuilder = treeBuilder
				childItem._id = childId
				if isSelected(child):
					selectionModel.setCurrentIndex(childItem._getModelIndexOfSelf(),QItemSelectionModel.ClearAndSelect,)

			if children:
				if not self._treeModelRoot._loadDeferred or self.isLoaded:
					self.loadSubTree(selectionModel)

		finally:
			self.isUpdating = False

	def _applyOperationsToTree(self, children: Any, operations: list[Operation], treeBuilder: _DataListDefs) -> None:
		treeModelRoot = self._treeModelRoot

		selfIndex = self._getModelIndexOfSelf()
		for operation in operations:
			if operation.type == 0:  # DeleteOperation
				operation = cast(DeleteOperation, operation)
				try:
					treeModelRoot.beginRemoveRows(selfIndex, operation.first, operation.last)
					for i in range(operation.first, operation.last + 1):
						self.childItems[operation.first]._parentItem = None
						del self.childItems[operation.first]
				finally:
					treeModelRoot.endRemoveRows()

			elif operation.type == 1:  # InsertOperation
				operation = cast(InsertOperation, operation)
				try:
					treeModelRoot.beginInsertRows(selfIndex, operation.first, operation.last)
					for i in range(operation.first, operation.last + 1):
						child = DataTreeItem(children[i], treeBuilder, treeModelRoot=treeModelRoot)
						self.childItems.insert(i, child)
						child._parentItem = self
				finally:
					treeModelRoot.endInsertRows()

			elif operation.type == 2:  # MoveOperation
				operation = cast(MoveOperation, operation)
				try:
					treeModelRoot.beginMoveRows(selfIndex, operation.first, operation.last, selfIndex, operation.dest,)
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

	def setTreeBuilderForRoot(self, treeBuilder: DataTreeBuilderNode) -> None:
		self.treeBuilder = treeBuilder._dataListDefs
		self._data = treeBuilder.getData()
		self._id = treeBuilder.id_  # avoids possible exceptions with DataListBuilder


_IGNORED_ROLES: set[int] = {2, 4, 5, 6, 7, 8, 9, 10, 13}
# Qt::DisplayRole	0	The key data to be rendered in the form of text. (QString)
# Qt::DecorationRole	1	The data to be rendered as a decoration in the form of an icon. (QColor, QIcon or QPixmap)
# Qt::EditRole	2	The data in a form suitable for editing in an editor. (QString)
# Qt::ToolTipRole	3	The data displayed in the item's tooltip. (QString)
# Qt::StatusTipRole	4	The data displayed in the status bar. (QString)
# Qt::WhatsThisRole	5	The data displayed for the item in "What's This?" mode. (QString)
# Qt::SizeHintRole	13	The size hint for the item that will be supplied to views. (QSize)

_ACCESSORS: dict[int, str] = {
	Qt.DisplayRole   : 'label',
	Qt.DecorationRole: 'icon',
	Qt.ToolTipRole   : 'toolTip',
	Qt.UserRole      : 'getData',

	# Qt.EditRole: item.getData,
	# Qt.StatusTipRole: item.getData,
	# Qt.WhatsThisRole: item.getData,
	# Qt.SizeHintRole: item.getData,
}


class DataTreeModel(QAbstractItemModel):
	def __init__(self, selectionModel: QItemSelectionModel, parent=None):
		super(DataTreeModel, self).__init__(parent)
		self.rootItem: DataTreeItem = DataTreeItem.createEmpty(treeModelRoot=self)

		self.headerItem: DataTreeItem = DataTreeItem.createEmpty(treeModelRoot=self)
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
	def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any | None:
		if not index.isValid():
			return None

		if role in _IGNORED_ROLES:
			return None

		item: DataTreeItem = index.internalPointer()

		accessor = _ACCESSORS.get(role)
		if accessor is not None:
			return getattr(item, accessor)(index.column())
		else:
			return None

	@CrashReportWrapped
	def canFetchMore(self, index: QModelIndex) -> bool:
		if not index.isValid():
			return False
		item: DataTreeItem = index.internalPointer()

		return not item.isLoaded
		# return not (self._loadDeferred and item.isLoaded)
		# return (not item.isLoaded) or (not self._loadDeferred)

	@CrashReportWrapped
	def fetchMore(self, index: QModelIndex):
		item: DataTreeItem = index.internalPointer()
		item.loadSubTree(self._lastSelectionModel)

	# @CrashReportWrapped
	def flags(self, index: QModelIndex) -> Qt.ItemFlags:
		if not index.isValid():
			return Qt.NoItemFlags  # type: ignore
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable

	@CrashReportWrapped
	def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any | None:
		if orientation == Qt.Vertical:  # and role == Qt.DisplayRole:
			return None
		if self.headerItem.treeBuilder is None:
			return None

		item: DataTreeItem = self.headerItem
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

	def updateTree(self, treeBuilder: DataTreeBuilderNode, headerBuilder: DataHeaderBuilder | None, selectionModel: QItemSelectionModel):
		needsModelReset = False
		if self.rootItem.treeBuilder is None:
			needsModelReset = True
		else:
			if self.rootItem.treeBuilder.columnCount != treeBuilder._dataListDefs.columnCount:
				needsModelReset = True

		if needsModelReset:
			self.beginResetModel()
		self.rootItem.setTreeBuilderForRoot(treeBuilder)
		if headerBuilder is not None:
			self.headerItem.setTreeBuilderForRoot(headerBuilder)

		self.rootItem.updateTree(selectionModel)
		if not self.rootItem.isLoaded:
			self.rootItem.loadSubTree(selectionModel)
		self._lastSelectionModel = selectionModel

		if needsModelReset:
			csi = selectionModel.currentIndex()
			self.endResetModel()
			selectionModel.setCurrentIndex(csi, QItemSelectionModel.ClearAndSelect)


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

	def performOperations[TT](oldList: list[TT], operations: list[Operation]) -> list[TT]:
		newList = oldList.copy()
		for i, operation in enumerate(operations):
			operation.apply(newList)
		return newList

	def _checkListUpdater[TT](oldList: list[TT], newList: list[TT], title: str):
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