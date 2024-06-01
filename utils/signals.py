from __future__ import annotations

from typing import Any, Callable, Literal, Type, Union, overload

from .collections_.weakUnhashableKeyDict import WeakUnhashableKeyDict
from ..utils.profiling import logDebug, logWarning

VERBOSE_LOGGING = False


class CatSignal[*_DArgs]:

	def __init__(self, name: str):
		self._name: str = name
		self._connectedSlots: WeakUnhashableKeyDict[Any, dict[Any, Callable[[*_DArgs], Any]]] = WeakUnhashableKeyDict()

	@property
	def name(self) -> str:
		return self._name

	@property
	def connectedSlots(self) -> WeakUnhashableKeyDict[Any, dict[Any, Callable[[*_DArgs], Any]]]:
		return self._connectedSlots

	def connect[_TInstance](self, instance: _TInstance, key: Any, slot: Callable[[*_DArgs], Any], *, warnIfAlreadyConnected: bool = True) -> None:
		slotsForInstance = self._connectedSlots.setdefault(instance, {})
		if key in slotsForInstance:
			if warnIfAlreadyConnected:
				logWarning(f"Slot '{key}' already connected to signal {self.name} for instance '{instance}'. The old connection won't be replaced.")
		else:
			if VERBOSE_LOGGING:
				logDebug(f"Connecting slot '{key}' to signal {self.name} for instance '{instance}'.")
			slotsForInstance[key] = slot

	def disconnect[_TInstance](self, instance: _TInstance, key: Any, *, warnIfNotConnected: bool = True) -> None:
		slotsForInstance = self._connectedSlots.get(instance, None)
		if slotsForInstance is None or key not in slotsForInstance:
			if warnIfNotConnected:
				logWarning(f"Slot '{key}' was not connected to signal {self.name} for instance '{instance}'.")
		else:
			if VERBOSE_LOGGING:
				logDebug(f"Disconnecting slot '{key}' from signal {self.name} for instance '{instance}'.")
			del slotsForInstance[key]

	def reconnect[_TInstance](self, instance: _TInstance, key: Any, slot: Callable[[*_DArgs], Any]) -> None:
		self.disconnect(instance, key, warnIfNotConnected=False)
		self.connect(instance, key, slot)

	def disconnectFromAllInstances(self, *, key: Any):
		if VERBOSE_LOGGING:
			logDebug(f"Disconnecting slot '{key}' from signal {self.name} for all instances.")
		for instance, slots in self._connectedSlots.items():
			if key in slots:
				del slots[key]

	def disconnectAll[_TInstance](self, instance: _TInstance) -> None:
		if instance not in self._connectedSlots:
			if VERBOSE_LOGGING:
				logDebug(f"No connections to signal {self.name} for '{instance}' found.")
		else:
			if VERBOSE_LOGGING:
				logDebug(f"Disconnecting all slots from signal {self.name} for instance '{instance}'.")
			del self._connectedSlots[instance]

	def emit[_TInstance](self, instance: _TInstance, args: tuple[*_DArgs]) -> None:
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
	def __get__[_TInstance](self, instance, owner: Type[_TInstance]) -> CatBoundSignal[*_DArgs]:
		...

	@overload
	def __get__(self, instance: Literal[None], owner: type) -> CatSignal[*_DArgs]:
		...

	def __get__[_TInstance](self, instance, owner: Type[_TInstance]) -> Union[CatBoundSignal[*_DArgs], CatSignal[*_DArgs]]:
		if instance is None:
			return self

		return CatBoundSignal(instance, self)


class CatBoundSignal[*_DArgs]:

	def __init__(self, instance, unboundSignal: CatSignal[*_DArgs]):
		self._instance = instance
		self.__unboundSignal: tuple[CatSignal[*_DArgs]] = (unboundSignal,)

	@property
	def _unboundSignal(self) -> CatSignal[*_DArgs]:
		return self.__unboundSignal[0]

	def connect(self, key: Any, slot: Callable[[*_DArgs], Any], *, warnIfAlreadyConnected: bool = True):
		self._unboundSignal.connect(self._instance, key, slot, warnIfAlreadyConnected=warnIfAlreadyConnected)

	def disconnect(self, key: Any, *, warnIfNotConnected: bool = True):
		self._unboundSignal.disconnect(self._instance, key, warnIfNotConnected=warnIfNotConnected)

	def reconnect(self, key: Any, slot: Callable[[*_DArgs], Any]):
		self._unboundSignal.reconnect(self._instance, key, slot)

	def disconnectAll(self) -> None:
		self._unboundSignal.disconnectAll(self._instance)

	def emit(self, *args: *_DArgs) -> None:
		self._unboundSignal.emit(self._instance, args)
