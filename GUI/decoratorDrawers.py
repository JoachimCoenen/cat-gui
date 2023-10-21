from typing import Any, Optional, TypeVar, Type, Protocol, Collection, Mapping

from PyQt5.QtGui import QFontDatabase

from .autoGUI import AutoGUI
from .propertyDecorators import *
from . import CORNERS, PythonGUI
from .components.Layouts import SingleColumnLayout

from ..Serializable.serializableDataclasses import SerializableDataclass
from ..Serializable.utils import get_args, typeHintMatchesType, getValueOrValueOfProp


_TT = TypeVar('_TT')


class InnerDrawPropertyFunc(Protocol[_TT]):
	def __call__(self, value_: _TT, type_: Optional[Type[_TT]], decorator_: PropertyDecorator, _owner: SerializableDataclass, **kwargs) -> _TT:
		...


class DecoratorDrawer(Protocol[_TT]):
	def __call__(self, gui_, value_: _TT, type_: Optional[Type[_TT]], decorator_: Optional[PropertyDecorator], drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
		...


__decoratorDrawers = dict()


def addDecoratorDrawer(DecoratorType: Type[PropertyDecorator], decoratorDrawer: DecoratorDrawer):
	__decoratorDrawers[DecoratorType] = decoratorDrawer


def getDecoratorDrawer(DecoratorType: Type[PropertyDecorator]) -> Optional[DecoratorDrawer]:
	for subType in DecoratorType.__mro__:
		decoratorDrawer = __decoratorDrawers.get(subType, None)
		if decoratorDrawer is not None:
			return decoratorDrawer

	return None


def registerDecoratorDrawer(cls: Type[PropertyDecorator]):
	"""Draws a decorator. for more information on propertyDecorators and customizing the GUI see <TODO, TBD>"""
	def makeDecoratorDrawer(decoratorDrawer):
		addDecoratorDrawer(cls, decoratorDrawer)
		return decoratorDrawer
	return makeDecoratorDrawer
		

@registerDecoratorDrawer(type(None))
def drawValue(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: None, drawProperty_: InnerDrawPropertyFunc[_TT], owner_, **kwargs) -> _TT:
	return gui_.valueField(value_, type_, **kwargs)


def drawSerializableDataclassList(gui_: AutoGUI, values_, type_, labels_=None, **kwargs):
	if labels_ == None:
		labels_ = [ "({})".format(i) for i in range(len(values_)) ]
	assert len(values_) == len(labels_)

	with gui_.hSplitter() as splitter:
		with splitter.addArea():
			index = gui_.listField(None, labels_, **kwargs)
		with splitter.addArea():
			with gui_.vLayout():
				if index >= 0:
					values_[index] = gui_.valueField(values_[index], type_, **kwargs)
	return values_


def drawSimpleList(gui_: AutoGUI, values_: Collection[_TT], **kwargs) -> Collection[_TT]:
	index = gui_.listField(None, [str(v) for v in values_], **kwargs)
	return values_


@registerDecoratorDrawer(List)
def drawList(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: List, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	innerType_ = get_args(type_)[0]
	if typeHintMatchesType(innerType_, SerializableDataclass):
		return drawSerializableDataclassList(gui_, value_, innerType_, **kwargs)
	else:
		return drawSimpleList(gui_, value_, **kwargs)


def drawSimpleDict(gui_: AutoGUI, values_: Mapping[str, _TT], **kwargs) -> Mapping[str, _TT]:
	kwargs.setdefault('headers', ('key', 'val'))
	gui_.stringTable(list(values_.items()), **kwargs)
	return values_


@registerDecoratorDrawer(Dict)
def drawDict(gui_: AutoGUI, values_: Mapping[str, _TT], type_: Optional[Type[_TT]], decorator_: Dict, drawProperty_: InnerDrawPropertyFunc[Mapping[str, _TT]], owner_: SerializableDataclass, **kwargs) -> Mapping[str, _TT]:
	innerType_ = get_args(type_)[1]
	if typeHintMatchesType(innerType_, SerializableDataclass):
		drawSerializableDataclassList(gui_, list(values_.values()), innerType_, labels_=list(values_.keys()), **kwargs)
	else:
		drawSimpleDict(gui_, values_, **kwargs)
	return values_


@registerDecoratorDrawer(Title)
def drawTitle(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: Title, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	gui_.title(getValueOrValueOfProp(owner_, decorator_.title))
	return drawProperty_(value_, type_, decorator_.innerDecorator, owner_, **kwargs)


def _drawActualDescription(gui_: PythonGUI, kwargs: dict[str, Any], decorator_, owner_) -> None:
	isSingleColumnLayout = isinstance(gui_.currentLayout, SingleColumnLayout)
	descriptionKWArgs = dict(
		hasLabel=kwargs.get('hasLabel', not isSingleColumnLayout),
		enabled=kwargs.get('enabled', True),
		wordWrap=False
	)
	descriptionKWArgs.update(decorator_.kwargs)
	gui_.helpBox(getValueOrValueOfProp(owner_, decorator_.description), style='info', **descriptionKWArgs)


@registerDecoratorDrawer(Description)
def drawDescription(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: Description, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	result = drawProperty_(value_, type_, decorator_.innerDecorator, owner_, **kwargs)
	_drawActualDescription(gui_, kwargs, decorator_, owner_)
	return result


@registerDecoratorDrawer(DescriptionAbove)
def drawDescriptionAbove(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: DescriptionAbove, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	kwargs = kwargs.copy()
	label = kwargs.pop('label', None)
	if label is not None:
		gui_.prefixLabel(label, enabled=kwargs.get('enabled', True), tip=kwargs.get('tip', ''))
	_drawActualDescription(gui_, kwargs, decorator_, owner_)
	result = drawProperty_(value_, type_, decorator_.innerDecorator, owner_, **kwargs)
	return result


@registerDecoratorDrawer(Validator)
def drawValidator(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: Validator, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	value_ = drawProperty_(value_, type_, decorator_.innerDecorator, owner_, **kwargs)
	validator = getValueOrValueOfProp(owner_, decorator_.validator)
	result: Optional[ValidatorResult] = validator(value_)
	if result is not None:
		gui_.helpBox(result.message, style=result.style, hasLabel=kwargs.get('hasLabel', True), enabled=kwargs.get('enabled', True), **decorator_.kwargs)
	return value_


@registerDecoratorDrawer(Range)
def drawRange(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: Range, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	with gui_.hLayout(
		label=kwargs.get('label', None),
		fullSize=kwargs.get('fullSize', False),
		enabled=kwargs.get('enabled', True),
		tip=kwargs.get('tip', ''),
		):
		kwargs['label'] = None
		value2 = gui_.slider(value_, 
			minVal=getValueOrValueOfProp(owner_, decorator_.min),
			maxVal=getValueOrValueOfProp(owner_, decorator_.max), **kwargs)
		return gui_.valueField(value2, **kwargs)


@registerDecoratorDrawer(FolderPath)
def drawFolderPath(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: FolderPath, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	return gui_.folderPathField(value_, **kwargs)


@registerDecoratorDrawer(FilePath)
def drawFilePath(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: FilePath, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	return gui_.filePathField(value_, filters=getValueOrValueOfProp(owner_, decorator_.filters), **kwargs)


@registerDecoratorDrawer(ReadOnlyLabel)
def drawReadOnlyLabel(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: ReadOnlyLabel, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	kwargs = kwargs.copy()
	label = kwargs.pop('label', None)
	gui_.prefixLabel(label)
	gui_.label(value_, **kwargs)
	return value_


@registerDecoratorDrawer(NoUI)
def drawNoUI(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: NoUI, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	return value_


@registerDecoratorDrawer(Date)
def drawDate(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: Date, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	return gui_.dateField(value_, **kwargs)


@registerDecoratorDrawer(FontFamily)
def drawFontFamily(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: FontFamily, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	predicate = None
	if decorator_.isAnyFilterSet:
		bitmapScalable = decorator_.mustBeBitmapScalable
		scalable = decorator_.mustBeScalable
		smoothlyScalable = decorator_.mustBeSmoothlyScalable
		fixedPitch = decorator_.mustBeFixedPitch
		private = decorator_.mustBePrivateFamily

		def predicate(db: QFontDatabase, family: str) -> bool:
			if bitmapScalable is not None and db.isBitmapScalable(family) != bitmapScalable:
				return False
			if scalable is not None and db.isScalable(family) != scalable:
				return False
			if smoothlyScalable is not None and db.isSmoothlyScalable(family) != smoothlyScalable:
				return False
			if fixedPitch is not None and db.isFixedPitch(family) != fixedPitch:
				return False
			if private is not None and db.isPrivateFamily(family) != private:
				return False
			return True

	return gui_.fontFamilyComboBox(value_, writingSystem=getValueOrValueOfProp(owner_, decorator_.writingSystem), predicate=predicate, **kwargs)


@registerDecoratorDrawer(Inlined)
def drawInlined(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: Inlined, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	gui_.simpleSerializableDataclassArea(value_, **kwargs)
	return value_


@registerDecoratorDrawer(Framed)
def drawFramed(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: Framed, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	# print("__serializableContainerArea___", type(value_))
	label = kwargs.pop('label', None)
	if gui_.spoiler(label=label, **kwargs):
		with gui_.vPanel(**decorator_.kwargs, roundedCorners=CORNERS.ALL), gui_.indentation():
			return gui_.simpleSerializableDataclassArea(value_, **kwargs)
	return value_


@registerDecoratorDrawer(ToggleLeft)
def drawToggleLeft(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: ToggleLeft, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	return gui_.toggleLeft(value_, **kwargs)


@registerDecoratorDrawer(ToggleSwitch)
def drawToggleSwitch(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: ToggleSwitch, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	return gui_.toggleSwitch(value_, **kwargs)


@registerDecoratorDrawer(ComboBox)
def drawComboBox(gui_: AutoGUI, value_: _TT, type_: Optional[Type[_TT]], decorator_: ComboBox, drawProperty_: InnerDrawPropertyFunc[_TT], owner_: SerializableDataclass, **kwargs) -> _TT:
	return gui_.comboBox(
		value_,
		choices=getValueOrValueOfProp(owner_, decorator_.choices),
		editable=getValueOrValueOfProp(owner_, decorator_.editable),
		**kwargs
	)
		
		