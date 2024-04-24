from collections import defaultdict
from typing import Callable, DefaultDict, Dict, Optional, Union

from PyQt5 import sip
from PyQt5.QtCore import QObject, pyqtBoundSignal, pyqtSignal, pyqtSlot

from ..utils.logging_ import logDebug, logError
from ..utils.utils import CrashReportWrapped, isCrashReportWrapped, runLaterSafe


QTSlot = Callable
QTSlotID = str


def connectUnsafe(signal, slot: QTSlot):
	if isCrashReportWrapped(slot):
		raise TypeError(f"expected a CrashReportWrapped callable, but got {slot}")
	return signal.connect(slot)


def connectSafe(signal: pyqtBoundSignal | pyqtSignal, slot: QTSlot):
	return signal.connect(CrashReportWrapped(slot))


def disconnect(obj: QObject | pyqtSignal):
	try:
		obj.disconnect()
	except TypeError as e:
		print(f"  {e} for type {type(obj)}")
		logDebug(f"  {e} for type {type(obj)}")
		pass


def disconnectAndDeleteLater(obj: QObject):
	try:
		obj.disconnect()
	except TypeError as e:
		print(f"  {e} for type {type(obj)}")
		logDebug(f"  {e} for type {type(obj)}")
		pass

	runLaterSafe(10, lambda: obj.deleteLater() if not sip.isdeleted(obj) else None)  # bad practice, but necessary in order to reasonably make sure that all signals have been handled :'(


def disconnectAndDeleteImmediately(obj: QObject):
	"""
	Potentially DANGEROUS!
	"""
	try:
		obj.disconnect()
	except TypeError as e:
		print(f"  {e}")
		logError(e)
		pass
	if not sip.isdeleted(obj):
		sip.delete(obj)
		#obj.deleteLater()


def connectOnlyOnce(obj: QObject, signal: pyqtBoundSignal | pyqtSignal, slot: QTSlot, slotID: QTSlotID):
	# pyqtSignal is in the type signature, only to make pycharms typechecker happy.
	assert slotID is not None, "slotID must NOT be None!"
	assert not isinstance(signal, pyqtSignal), "expected a bound signal (pyqtBoundSignal), but got pyqtSignal."
	connectedSlotsAttrName = '__catConnectedSlots__'
	connectedSlots: Optional[DefaultDict[str, Dict[QTSlotID, QTSlot]]] = getattr(obj, connectedSlotsAttrName, None)

	if connectedSlots is None:
		connectedSlots = defaultdict(dict)
		setattr(obj, connectedSlotsAttrName, connectedSlots)

	slotsForSignal = connectedSlots[signal.signal]
	if slotID not in slotsForSignal:
		slotsForSignal[slotID] = slot
		connectSafe(signal, slot)


def saveDisconnect(obj: QObject, signal: pyqtBoundSignal, slotID: QTSlotID):
	assert slotID is not None, "slotID must NOT be None!"
	assert not isinstance(signal, pyqtSignal), "expected a bound signal (pyqtBoundSignal), but got pyqtSignal."
	connectedSlotsAttrName = '__catConnectedSlots__'
	connectedSlots: Optional[DefaultDict[str, Dict[QTSlotID, QTSlot]]] = getattr(obj, connectedSlotsAttrName, None)

	if connectedSlots is None:
		return

	if signal.signal in connectedSlots:
		slotsForSignal = connectedSlots[signal.signal]
		if slotID in slotsForSignal:
			slot = slotsForSignal[slotID]
			signal.disconnect(slot)
			del slotsForSignal[slotID]


def safeEmit(self: QObject, signal: Union[pyqtBoundSignal, pyqtSignal], *args) -> None:
	if not sip.isdeleted(self):
		signal.emit(*args)

