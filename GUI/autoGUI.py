from dataclasses import Field, is_dataclass, fields
from typing import Callable, Optional, TypeVar, Type

from . import Style
from .pythonGUI import PythonGUI
from PyQt5 import QtWidgets, QtCore

from ..Serializable.serializableDataclasses import getDecorator, getKwargs, getType, isReadOnly, SerializableDataclass
from ..Serializable.utils import getValueOrValueOfProp, PropertyDecorator
from ..utils import first

_TT = TypeVar('_TT')
_TS = TypeVar('_TS')


if not hasattr(QtCore, 'Signal'):
	QtCore.Signal = QtCore.pyqtSignal


class AutoGUI(PythonGUI):
	def __init__(self: _TS, host: QtWidgets.QWidget, OnGUI: Callable[[_TS], None], *, seamless: bool = False, deferBorderFinalization: bool = False, suppressRedrawLogging: bool = False, style: Style = None):
		super(AutoGUI, self).__init__(host, OnGUI, seamless=seamless, deferBorderFinalization=deferBorderFinalization, suppressRedrawLogging=suppressRedrawLogging, style=style)

	def simpleSerializableDataclassArea(self, container: SerializableDataclass, hasLabel: bool = True, label: Optional[str] = None, enabled: bool = True, **kwargs):
		if container == None:
			self.label('<None>')
			return container
		props = fields(container)
		for prop in props:
			self.propertyField(container, prop, hasLabel, enabled=enabled, **kwargs)
		return container

	def serializableContainerArea(self, container: SerializableDataclass, hasLabel: bool = True, label: Optional[str] = None, enabled: bool = True, **kwargs):
		if self.spoiler(label=label, enabled=enabled, **kwargs):
			with self.indentation():
				return self.simpleSerializableDataclassArea(container, enabled=enabled, **kwargs)
		return container

	def drawDecoratedField(self, value_: _TT, type_: Optional[Type[_TT]], decorator_: PropertyDecorator, owner_: SerializableDataclass, **kwargs) -> _TT:
		from . import decoratorDrawers
		decoratorDrawer = decoratorDrawers.getDecoratorDrawer(type(decorator_))
		if decoratorDrawer is None:
			raise Exception("Unknown decorator type '{}'. Cannot draw decorator for value '{}', kwargs '{}'".format(decorator_, value_, kwargs))
		return decoratorDrawer(self, value_, type_, decorator_, self.drawDecoratedField, owner_, **kwargs)

	def propertyField(self, owner: SerializableDataclass, field: Field | str, hasLabel=True, **kwargs):
		if is_dataclass(owner) and isinstance(field, str):
			field = first((f for f in fields(owner) if f.name == field), field)
		value = getattr(owner, field.name)
		type_ = getType(field)
		kwargs_ = getKwargs(field)
		decorator = getDecorator(field)
		propName = field.name
		readonly = isReadOnly(field)

		kwargs_ = { name : getValueOrValueOfProp(owner, value) for name, value in kwargs_.items() }
		kwargs_.update(kwargs)
		if 'label' in kwargs_ and not hasLabel:
			del kwargs_['label']
		elif 'label' not in kwargs_ and hasLabel:
			kwargs_['label'] = propName

		newValue = self.drawDecoratedField(value, type_, decorator, owner, **kwargs_)

		if not readonly:
			setattr(owner, field.name, newValue)


from . import addWidgetDrawer
addWidgetDrawer(SerializableDataclass, lambda gui, v, **kwargs: gui.simpleSerializableDataclassArea(v, **kwargs))
