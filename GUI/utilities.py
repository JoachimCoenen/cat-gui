from collections import defaultdict
from functools import wraps
from typing import Callable, DefaultDict, Dict, Optional, Union

from PyQt5 import sip
from PyQt5.QtCore import pyqtBoundSignal, pyqtSignal, QObject, QTimer

from Cat.utils import Decorator, format_full_exc
from Cat.utils.profiling import logError, ProfiledAction


def __onCrash__(exception):
	pass

onCrash = __onCrash__


def connect(signal, slot):
	def wrappedSlot(*args, slot__=slot, **kwargs):
		try:
			slot__(*args, **kwargs)
		except Exception as e:
			#slot(1)
			print(format_full_exc())
			logError(format_full_exc())
			onCrash(e)
			raise
	return signal.connect(wrappedSlot)


def disconnect(obj: QObject):
	try:
		obj.disconnect()
	except TypeError as e:
		print(f"  {e}")
		pass


def disconnectAndDeleteLater(obj: QObject):
	#print(f"disconnectAndDeleteLater()")
	#print(f"  {type(obj)}")
	try:
		obj.disconnect()
	except TypeError as e:
		print(f"  {e}")
		pass
	#print(f"  disconnected")
	# obj.setParent(None)
	# print(f"  parent is None")
	#QTimer.singleShot(0, lambda ob=obj: ob.deleteLater())
	#obj.deleteLater()
	# QApplication.processEvents(QEventLoop.ProcessEventsFlag(0), 30)
	# QApplication.sendPostedEvents()
	# QApplication.processEvents(QEventLoop.ProcessEventsFlag(0), 30)
	# print(f"  eventsProcessed")

	QTimer.singleShot(10, lambda obj=obj: obj.deleteLater() if not sip.isdeleted(obj) else None)  # bad practice, but necessary in order to reasonably make sure that all signals have been handled :'(
	#print(f"  deletedLater scheduled")


QTSlot = Callable
QTSlotID = str


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
		connect(signal, slot)


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


class CrashReportWrappedProfiledAction(ProfiledAction):
	def __init__(self, name: str, threshold_percent: float = 1., report_interval: float = 5., colourNodesBySelftime: bool = False , enabled: bool = True):
		super(CrashReportWrappedProfiledAction, self).__init__(name, threshold_percent, report_interval, colourNodesBySelftime, enabled)
		#self.__isProfiling: bool = False
		self.__callDepth: int = 0

	def __enter__(self):
		#return
		self.__callDepth += 1
		if self.__callDepth == 1:
			super(CrashReportWrappedProfiledAction, self).__enter__()

	def __exit__(self, exc_type, exc_val, exc_tb):
		#return
		self.__callDepth -= 1
		if self.__callDepth == 0:
			super(CrashReportWrappedProfiledAction, self).__exit__(exc_type, exc_val, exc_tb)


_crashReportWrappedProfiledAction = CrashReportWrappedProfiledAction('CrashReportWrapped')
_lableStr = None
@Decorator
def CrashReportWrapped(func=None, *, lable=None, labelle=None):
	global _lableStr
	if func is None:
		_lableStr = lable
		labelle = lable
		return lambda f: CrashReportWrapped(f, labelle=labelle)

	#func = MethodCallCounter(enabled=True, minPrintCount=5000)(func)
	@wraps(func)
	def call(*args, labelle=labelle, **kwargs):
		# if labelle==_lableStr:
		# 	with _crashReportWrappedProfiledAction:
		# 		try:
		# 			return func(*args, **kwargs)
		# 		except Exception as e:
		# 			#slot(1)
		# 			print(format_full_exc())
		# 			logError(format_full_exc())
		# 			onCrash(e)
		# 			raise
		# else:
		try:
			return func(*args, **kwargs)
		except Exception as e:
			# slot(1)
			print(format_full_exc())
			logError(format_full_exc())
			onCrash(e)
			raise
	call.__CrashReportWrapped__ = True
	return call


