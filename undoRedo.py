from __future__ import annotations
import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar, Protocol, AnyStr

from PyQt5.QtGui import QColor, QPixmap

from .GUI import addWidgetDrawer, PythonGUI, SizePolicy
from .utils.collections_ import Stack

_TTarget = TypeVar("_TTarget")
_TDocument = TypeVar("_TDocument")


class MementoABC(Generic[_TTarget], ABC):

	@abstractmethod
	def restore(self, currentState: _TTarget, lastRecordedState: _TTarget, doDeepCopy: bool) -> tuple[MementoABC[_TTarget], _TTarget, _TTarget]:
		"""
		:param currentState:
		:param lastRecordedState:
		:param doDeepCopy:
		:return: (redoMemento, newState, lastRecordeState / newStateCopy)
		"""
		pass


class MakeMementoIfDiffFunc(Protocol[_TTarget]):
	def __call__(self, oldState: Optional[_TTarget], newState: _TTarget, doDeepCopy: bool) -> tuple[Optional[MementoABC[_TTarget]], _TTarget]:
		...


@dataclass
class SnapshotMemento(MementoABC[_TTarget]):
	_oldState: _TTarget

	def restore(self, currentState: _TTarget, lastRecordedState: _TTarget, doDeepCopy: bool) -> tuple[MementoABC[_TTarget], _TTarget, _TTarget]:
		lastRecordeState = copy.deepcopy(self._oldState) if doDeepCopy else copy.copy(self._oldState)
		# no deepcopy for currentState required here, because it will be replaced with oldState
		return SnapshotMemento(currentState), self._oldState, lastRecordeState


@dataclass
class AnyStrMemento(MementoABC[AnyStr]):
	_oldState: AnyStr

	def restore(self, currentState: AnyStr, lastRecordedState: AnyStr, doDeepCopy: bool) -> tuple[AnyStrMemento[AnyStr], AnyStr, AnyStr]:
		return AnyStrMemento(currentState), self._oldState, self._oldState


def makesSnapshotMementoIfDiff(oldState: Optional[_TTarget], newState: _TTarget, doDeepCopy: bool) -> tuple[Optional[SnapshotMemento[_TTarget]], _TTarget]:
	if oldState == newState:
		memento, newStateCopy = None, oldState
	else:
		memento = SnapshotMemento(copy.deepcopy(oldState)) if oldState is not None else None
		newStateCopy = copy.deepcopy(newState) if doDeepCopy else copy.copy(newState)
	return memento, newStateCopy


def makesAnyStrMementoIfDiff(oldState: Optional[AnyStr], newState: AnyStr, doDeepCopy: bool) -> tuple[Optional[AnyStrMemento[AnyStr]], AnyStr]:
	if oldState is None or oldState == newState:
		return None, newState
	else:
		return AnyStrMemento(oldState), newState


@dataclass
class UndoRedoStack2(Generic[_TDocument, _TTarget]):

	_document: _TDocument
	_dataProperty: str
	_makeMementoIfDiff: MakeMementoIfDiffFunc[_TTarget]
	doDeepCopy: bool = field(kw_only=True)

	_undoStack: Stack[MementoABC[_TTarget]] = field(default_factory=Stack, init=False)
	_redoStack: Stack[MementoABC[_TTarget]] = field(default_factory=Stack, init=False)
	_isUndoingOrRedoing: bool = field(default=False, init=False)

	lastRecordedState: Optional[_TTarget] = field(default=None, init=False)

	def takeSnapshot(self):
		currentState = self._getCurrentState()
		memento, newStateCopy = self._makeMementoIfDiff(self.lastRecordedState, currentState, self.doDeepCopy)
		if memento is not None:
			self._undoStack.push(memento)
			self.clearRedoStack()
		self.lastRecordedState = newStateCopy

	def takeSnapshotIfChanged(self):
		return self.takeSnapshot()

	@property
	def isUndoingOrRedoing(self) -> bool:
		return self._isUndoingOrRedoing

	@property
	def canUndo(self) -> bool:
		return bool(self._undoStack)

	@property
	def canRedo(self) -> bool:
		return bool(self._redoStack)

	def canUndoMultiple(self, n: int) -> bool:
		return len(self._undoStack) >= n

	def canRedoMultiple(self, n: int) -> bool:
		return len(self._redoStack) >= n

	@property
	def undoCount(self) -> int:
		return len(self._undoStack)

	@property
	def redoCount(self) -> int:
		return len(self._redoStack)

	@property
	def undoStack(self) -> Stack[MementoABC[_TTarget]]:
		return self._undoStack

	@property
	def redoStack(self) -> Stack[MementoABC[_TTarget]]:
		return self._redoStack

	def undoOnce(self):
		if not self.canUndo:
			return
		memento: MementoABC[_TTarget] = self._undoStack.pop()
		redoMemento, newState, self.lastRecordedState = memento.restore(self._getCurrentState(), self.lastRecordedState, self.doDeepCopy)
		self._redoStack.push(redoMemento)
		self._setCurrentState(newState)

	def redoOnce(self):
		if not self.canRedo:
			return
		memento: MementoABC[_TTarget] = self._redoStack.pop()
		undoMemento, newState, self.lastRecordedState = memento.restore(self._getCurrentState(), self.lastRecordedState, self.doDeepCopy)
		self._undoStack.push(undoMemento)
		self._setCurrentState(newState)

	def undoMultiple(self, n: int):
		n = min(self.undoCount, n)
		if n <= 0:
			return
		newState = self._getCurrentState()
		lastRecordedState = self.lastRecordedState
		doDeepCopy = self.doDeepCopy
		for i in range(n):
			memento: MementoABC[_TTarget] = self._undoStack.pop()
			redoMemento, newState, lastRecordedState = memento.restore(newState, lastRecordedState, doDeepCopy)
			self._redoStack.push(redoMemento)
		self.lastRecordedState = lastRecordedState
		self._setCurrentState(newState)

	def redoMultiple(self, n: int):
		n = min(self.redoCount, n)
		if n <= 0:
			return
		newState = self._getCurrentState()
		lastRecordedState = self.lastRecordedState
		doDeepCopy = self.doDeepCopy
		for i in range(n):
			memento: MementoABC[_TTarget] = self._redoStack.pop()
			undoMemento, newState, lastRecordedState = memento.restore(newState, lastRecordedState, doDeepCopy)
			self._undoStack.push(undoMemento)
		self.lastRecordedState = lastRecordedState
		self._setCurrentState(newState)

	def _getCurrentState(self) -> _TTarget:
		assert self._document is not None
		assert self._dataProperty is not None
		return getattr(self._document, self._dataProperty)

	def _setCurrentState(self, state: _TTarget):
		assert self._document is not None
		assert self._dataProperty is not None
		# self.lastRecordedState = state
		self._isUndoingOrRedoing = True
		try:
			setattr(self._document, self._dataProperty, state)
		finally:
			self._isUndoingOrRedoing = False

	def clearRedoStack(self):
		self._redoStack.clear()


def colorLabel(gui: PythonGUI, v: QColor):
	pixmap = QPixmap(16, 16)
	pixmap.fill(v)
	gui.label(pixmap)


def undoEntry(gui: PythonGUI, label: Optional[str], text: str, color: QColor):
	with gui.hLayout(label):
		if text:
			gui.textField('Bla')
		else:
			gui.textField('')
		colorLabel(gui, color)


def drawUndoRedoStack2(gui: PythonGUI, v: UndoRedoStack2, **kwargs) -> UndoRedoStack2:
	undoStack: Stack = v.undoStack
	redoStack: Stack = v.redoStack
	with gui.hLayout():
		if gui.button('Clear All'):
			undoStack.clear()
			redoStack.clear()
		if gui.button('Clear Undo'):
			undoStack.clear()
		if gui.button('Clear Redo'):
			redoStack.clear()
		gui.addHSpacer(50, SizePolicy.Expanding)

	with gui.scrollBox(preventVStretch=True):
		for i, u in enumerate(undoStack):
			if gui.button('o', isPrefix=True):
				undoCount = len(undoStack) - i
				v.undoMultiple(undoCount)
			undoEntry(gui, label=None, text=' ', color=QColor(64, 64, 192, 255))

		hasChanged = False  # v.lastRecordedState != snapShot
		color = QColor(192, 64, 64, 255) if hasChanged else QColor(64, 192, 64, 255)
		undoEntry(gui, label='-->', text=v.lastRecordedState, color=color)

		for i, u in enumerate(reversed(redoStack), 1):
			if gui.button('o', isPrefix=True):
				redoCount = i
				v.redoMultiple(redoCount)
			undoEntry(gui, label=None, text=' ', color=QColor(224, 192, 64, 255))
	return v


addWidgetDrawer(UndoRedoStack2,    drawUndoRedoStack2)
