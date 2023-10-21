from __future__ import annotations

from typing import Any, Callable, Generic, Literal, overload, Type, TypeVar, Union
from weakref import WeakKeyDictionary

from Cat.utils.profiling import logDebug, logWarning


VERBOSE_LOGGING = False

_TSlot = TypeVar("_TSlot", bound=Callable)
_TInstance = TypeVar('_TInstance')


class CatSignal(Generic[_TSlot]):

	def __init__(self, name: str):
		self._name: str = name
		self._connectedSlots: WeakKeyDictionary[Any, dict[Any, _TSlot]] = WeakKeyDictionary()

	@property
	def name(self) -> str:
		return self._name

	@property
	def connectedSlots(self) -> WeakKeyDictionary[Any, dict[Any, _TSlot]]:
		return self._connectedSlots

	def connect(self, instance: _TInstance, key: Any, slot: _TSlot, *, warnIfAlreadyConnected: bool = True):
		slotsForInstance = self._connectedSlots.setdefault(instance, {})
		if key in slotsForInstance:
			if warnIfAlreadyConnected:
				logWarning(f"Slot '{key}' already connected to signal {self.name} for instance '{instance}'. The old connection won't be replaced.")
		else:
			if VERBOSE_LOGGING:
				logDebug(f"Connecting slot '{key}' to signal {self.name} for instance '{instance}'.")
			slotsForInstance[key] = slot

	def disconnect(self, instance: _TInstance, key: Any, *, warnIfNotConnected: bool = True):
		slotsForInstance = self._connectedSlots.get(instance, None)
		if slotsForInstance is None or key not in slotsForInstance:
			if warnIfNotConnected:
				logWarning(f"Slot '{key}' was not connected to signal {self.name} for instance '{instance}'.")
		else:
			if VERBOSE_LOGGING:
				logDebug(f"Disconnecting slot '{key}' from signal {self.name} for instance '{instance}'.")
			del slotsForInstance[key]

	def reconnect(self, instance: _TInstance, key: Any, slot: _TSlot):
		self.disconnect(instance, key, warnIfNotConnected=False)
		self.connect(instance, key, slot)

	def disconnectFromAllInstances(self, *, key: Any):
		if VERBOSE_LOGGING:
			logDebug(f"Disconnecting slot '{key}' from signal {self.name} for all instances.")
		for instance, slots in self._connectedSlots.items():
			if key in slots:
				del slots[key]

	def disconnectAll(self, instance: _TInstance):
		if instance not in self._connectedSlots:
			if VERBOSE_LOGGING:
				logDebug(f"No connections to signal {self.name} for '{instance}' found.")
		else:
			if VERBOSE_LOGGING:
				logDebug(f"Disconnecting all slots from signal {self.name} for instance '{instance}'.")
			del self._connectedSlots[instance]

	def emit(self, instance: _TInstance, args: list[Any]):
		slotsForInstance = self._connectedSlots.get(instance, None)
		if not slotsForInstance:
			if VERBOSE_LOGGING:
				logDebug(f"No connections to signal {self.name} for '{instance}' found.")
		else:
			if VERBOSE_LOGGING:
				logDebug(f"emitting signal {self.name} for instance '{instance}'.")
			for key, slot in slotsForInstance.copy().items():
				slot(*args)

	@overload
	def __get__(self, instance: Literal[None], owner: type) -> CatSignal[_TSlot]:
		...

	@overload
	def __get__(self, instance: _TInstance, owner: Type[_TInstance]) -> CatBoundSignal[_TInstance, _TSlot]:
		...

	def __get__(self, instance: _TInstance, owner: Type[_TInstance]) -> Union[CatBoundSignal[_TInstance, _TSlot], CatSignal[_TSlot]]:
		if instance is None:
			return self

		return CatBoundSignal[owner, _TSlot](instance, self)


class CatBoundSignal(Generic[_TInstance, _TSlot]):

	def __init__(self, instance: _TInstance, unboundSignal: CatSignal[_TSlot]):
		self._instance: _TInstance = instance
		self.__unboundSignal: tuple[CatSignal[_TSlot]] = (unboundSignal,)

	@property
	def _unboundSignal(self) -> CatSignal[_TSlot]:
		return self.__unboundSignal[0]

	def connect(self, key: Any, slot: _TSlot, *, warnIfAlreadyConnected: bool = True):
		self._unboundSignal.connect(self._instance, key, slot, warnIfAlreadyConnected=warnIfAlreadyConnected)

	def disconnect(self, key: Any, *, warnIfNotConnected: bool = True):
		self._unboundSignal.disconnect(self._instance, key, warnIfNotConnected=warnIfNotConnected)

	def reconnect(self, key: Any, slot: _TSlot):
		self._unboundSignal.reconnect(self._instance, key, slot)

	def disconnectAll(self):
		self._unboundSignal.disconnectAll(self._instance)

	def emit(self, *args):
		self._unboundSignal.emit(self._instance, args)
