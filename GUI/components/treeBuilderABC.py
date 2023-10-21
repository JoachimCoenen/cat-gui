from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, TypeVar, Union, Generic

from PyQt5.QtGui import QColor, QIcon, QPixmap

_TT = TypeVar('_TT')


DecorationRole = Union[QColor, QIcon, QPixmap]


class TreeBuilderABC(ABC, Generic[_TT]):

	def updateDeferred(self):
		"""
		gets galled only if needsUpdate() returns True or when there's no oldTreeBuilder (a new tree/ branch gets build). It gets called just before children() and childCount()
		:return: Nothing.
		"""
		pass

	@abstractmethod
	def needsUpdate(self, oldTreeBuilder: Optional[TreeBuilderABC[_TT]]) -> bool:
		return id(self) != id(oldTreeBuilder)

	@property
	@abstractmethod
	def id_(self) -> Any:
		pass

	@abstractmethod
	def children(self) -> Iterator[TreeBuilderABC[_TT]]:
		pass

	@property
	@abstractmethod
	def childCount(self) -> int:
		pass

	def isSelected(self) -> Optional[bool]:
		return None

	@abstractmethod
	def getData(self) -> _TT:
		pass

	@property
	@abstractmethod
	def columnCount(self):
		return 1

	@abstractmethod
	def getLabel(self, column: int) -> str:
		pass

	def getIcon(self, column: int) -> Optional[DecorationRole]:
		"""returns the icon for this item"""
		return None

	@abstractmethod
	def getTip(self, column: int) -> Optional[str]:
		"""returns the toolTip for this item"""
		pass

	def onDoubleClick(self):
		pass

	def onCopy(self) -> Optional[str]:
		return None

	def onCut(self) -> Optional[str]:
		return None

	def onPaste(self, data: str) -> None:
		pass

	def onDelete(self) -> None:
		pass

	def onContextMenu(self, column: int):
		pass
