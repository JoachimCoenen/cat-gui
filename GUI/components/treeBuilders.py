from PyQt5.QtGui import QIcon

from ...GUI.components.treeModel import _DataListDefs
from typing import Callable, Any, Sequence


class DataTreeBuilderNode[TT]:
	def __init__(self, data: TT, dataListDefs: _DataListDefs, id_: Any) -> None:
		super().__init__()
		self._data = data
		self._dataListDefs: _DataListDefs = dataListDefs
		self._id: Any = id_

	@property
	def id_(self) -> Any:
		return self._id

	def getData(self) -> TT:
		return self._data


def DataListBuilder[TT](
		data: Sequence[TT],
		labelMaker    : Callable[[TT, int], str],
		iconMaker     : Callable[[TT, int], QIcon | None] | None,
		toolTipMaker  : Callable[[TT, int], str | None] | None,
		columnCount   : int,
		suppressUpdate: bool = False,
		onDoubleClick : Callable[[TT], None] | None = None,
		onContextMenu : Callable[[TT, int], None] | None = None,
		onCopy        : Callable[[TT], str | None] | None = None,
		onCut         : Callable[[TT], str | None] | None = None,
		onPaste       : Callable[[TT, str], None] | None = None,
		onDelete      : Callable[[TT], None] | None = None,
		isSelected    : Callable[[TT], bool] | None = None,
		getId         : Callable[[TT], Any] | None = None
) -> DataTreeBuilderNode[TT | Sequence[TT]]:
	dataListDefs = _DataListDefs(
		childrenMaker=lambda data_: data_,
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
	id_ = '<ROOT>'
	return DataTreeBuilderNode(data, dataListDefs, id_)


def DataTreeBuilder[TT, TU](
		data: TT,
		childrenMaker : Callable[[TT | TU], Sequence[TT | TU]],
		labelMaker    : Callable[[TT | TU, int], str],
		iconMaker     : Callable[[TT | TU, int], QIcon | None] | None,
		toolTipMaker  : Callable[[TT | TU, int], str | None] | None,
		columnCount   : int,
		showRoot      : bool = True,  # deprecated. has no effect
		suppressUpdate: bool = False,
		onDoubleClick : Callable[[TT | TU], None] | None = None,
		onContextMenu : Callable[[TT | TU, int], None] | None = None,
		onCopy        : Callable[[TT | TU], str | None] | None = None,
		onCut         : Callable[[TT | TU], str | None] | None = None,
		onPaste       : Callable[[TT | TU, str], None] | None = None,
		onDelete      : Callable[[TT | TU], None] | None = None,
		isSelected    : Callable[[TT | TU], bool] | None = None,
		getId         : Callable[[TT | TU], Any] | None = None
) -> DataTreeBuilderNode[TT | TU]:
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
	id_ = dataListDefs.getId(data)
	return DataTreeBuilderNode(data, dataListDefs, id_)


class DataHeaderBuilder[TT](DataTreeBuilderNode[TT]):
	def __init__(
			self,
			data: TT,
			labelMaker: Callable[[TT, int], str],
			iconMaker: Callable[[TT, int], QIcon | None] | None = None,
			toolTipMaker: Callable[[TT, int], str | None] | None = None,
			onDoubleClick: Callable[[TT], None] | None = None,
			onContextMenu : Callable[[TT, int], None] | None = None,
			onCopy        : Callable[[TT], str | None] | None = None,
			onCut         : Callable[[TT], str | None] | None = None,
			onPaste       : Callable[[TT, str], None] | None = None,
			onDelete      : Callable[[TT], None] | None = None,
			isSelected    : Callable[[TT], bool] | None = None,
			getId         : Callable[[TT], Any] | None = None
	) -> None:
		dataListDefs = _DataListDefs(
			childrenMaker=lambda _: (),
			isTree=False,
			labelMaker=labelMaker,
			iconMaker=iconMaker,
			toolTipMaker=toolTipMaker,
			columnCount=-1,
			suppressUpdate=True,
			onDoubleClick=onDoubleClick,
			onContextMenu=onContextMenu,
			onCopy=onCopy,
			onCut=onCut,
			onPaste=onPaste,
			onDelete=onDelete,
			isSelected=isSelected,
			getId=getId,
		)
		id_ = dataListDefs.getId(data)
		super().__init__(data, dataListDefs, id_)


def StringHeaderBuilder(
			data: tuple[str, ...],
			labelMaker: Callable[[tuple[str, ...], int], str] = lambda data, c: data[c],
			iconMaker: Callable[[tuple[str, ...], int], QIcon | None] | None = None,
			toolTipMaker: Callable[[tuple[str, ...], int], str | None] | None = None,
			onDoubleClick: Callable[[tuple[str, ...]], None] | None = None
) -> DataHeaderBuilder[tuple[str, ...]]:
	return DataHeaderBuilder(data, labelMaker, iconMaker, toolTipMaker, onDoubleClick)


__all__ = [
	'DataTreeBuilderNode',
	'DataListBuilder',
	'DataTreeBuilder',
	'DataHeaderBuilder',
	'StringHeaderBuilder',
]
